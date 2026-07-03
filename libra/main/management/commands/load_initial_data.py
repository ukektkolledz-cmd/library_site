import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save


class Command(BaseCommand):
    help = 'Load initial fixture data only if the database is empty'

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.exists():
            self.stdout.write('Database already has data — skipping loaddata.')
            return

        self.stdout.write('Database is empty — loading fixture data...')
        from django.core.management import call_command
        from main.models import create_user_profile, save_user_profile

        # Disconnect post_save signals to prevent auto-creating Profile rows
        # while loaddata is restoring Profile rows from the fixture.
        post_save.disconnect(create_user_profile, sender=User)
        post_save.disconnect(save_user_profile, sender=User)
        try:
            fixture_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'fixtures', 'data.json'
            )
            call_command('loaddata', os.path.abspath(fixture_path), verbosity=1)
        finally:
            post_save.connect(create_user_profile, sender=User)
            post_save.connect(save_user_profile, sender=User)

        self.stdout.write(self.style.SUCCESS('Fixture data loaded successfully.'))
