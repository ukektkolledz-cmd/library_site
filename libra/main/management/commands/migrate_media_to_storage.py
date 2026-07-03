from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Upload files from MEDIA_ROOT to the configured default storage "
        "(for example, Backblaze B2 via S3)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prefix",
            default="",
            help="Optional relative subdirectory inside MEDIA_ROOT to migrate.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be uploaded without writing anything.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Upload even if file already exists in destination storage.",
        )
        parser.add_argument(
            "--delete-local",
            action="store_true",
            help="Delete local file after successful upload.",
        )

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            raise CommandError(f"MEDIA_ROOT does not exist: {media_root}")

        prefix = (options.get("prefix") or "").strip().strip("/\\")
        source_root = media_root / prefix if prefix else media_root
        if not source_root.exists():
            raise CommandError(f"Source path does not exist: {source_root}")

        dry_run = options["dry_run"]
        overwrite = options["overwrite"]
        delete_local = options["delete_local"]

        if dry_run and delete_local:
            raise CommandError("--delete-local cannot be used with --dry-run")

        backend_name = f"{default_storage.__class__.__module__}.{default_storage.__class__.__name__}"
        self.stdout.write(f"Using storage backend: {backend_name}")
        self.stdout.write(f"Source directory: {source_root}")

        scanned = 0
        uploaded = 0
        skipped_existing = 0
        failed = 0
        deleted_local = 0

        for path in source_root.rglob("*"):
            if not path.is_file():
                continue

            scanned += 1
            rel_path = path.relative_to(media_root).as_posix()

            try:
                if not overwrite and default_storage.exists(rel_path):
                    skipped_existing += 1
                    continue

                if dry_run:
                    self.stdout.write(f"[DRY RUN] upload: {rel_path}")
                    uploaded += 1
                    continue

                with path.open("rb") as local_file:
                    default_storage.save(rel_path, File(local_file))

                uploaded += 1

                if delete_local:
                    path.unlink()
                    deleted_local += 1

            except Exception as exc:  # pragma: no cover
                failed += 1
                self.stderr.write(self.style.ERROR(f"Failed: {rel_path} -> {exc}"))

        summary = (
            f"Done. scanned={scanned}, uploaded={uploaded}, "
            f"skipped_existing={skipped_existing}, failed={failed}"
        )
        if delete_local:
            summary += f", deleted_local={deleted_local}"

        if failed:
            self.stdout.write(self.style.WARNING(summary))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
