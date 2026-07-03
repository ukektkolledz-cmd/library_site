from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

try:
    import polib
except ImportError as exc:  # pragma: no cover
    polib = None
    POLIB_IMPORT_ERROR = exc
else:
    POLIB_IMPORT_ERROR = None


class Command(BaseCommand):
    help = "Compile locale .po files into .mo files without GNU gettext."

    def handle(self, *args, **options):
        if polib is None:
            raise CommandError(
                "The 'polib' package is required. Install it in the active environment first."
            ) from POLIB_IMPORT_ERROR

        locale_dir = Path(settings.BASE_DIR) / "locale"
        if not locale_dir.exists():
            raise CommandError(f"Locale directory not found: {locale_dir}")

        po_files = sorted(locale_dir.glob("*/LC_MESSAGES/*.po"))
        if not po_files:
            raise CommandError("No .po files were found in the locale directory.")

        compiled_count = 0
        for po_file in po_files:
            po = polib.pofile(str(po_file))
            mo_file = po_file.with_suffix(".mo")
            po.save_as_mofile(str(mo_file))

            translated = sum(1 for entry in po if entry.msgstr.strip())
            total = sum(1 for entry in po if not entry.obsolete)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Compiled {po_file.name} -> {mo_file.name} ({translated}/{total} translated)"
                )
            )
            compiled_count += 1

        self.stdout.write(self.style.SUCCESS(f"Done. Compiled {compiled_count} locale files."))
