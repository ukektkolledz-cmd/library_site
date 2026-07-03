from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate by username or email for all auth entry points, including /admin/."""

    def _resolve_user(self, identifier):
        # 1) Exact username has top priority.
        user = User.objects.filter(username=identifier).first()
        if user is not None:
            return user

        # 2) Case-insensitive username fallback if unique.
        username_matches = User.objects.filter(username__iexact=identifier).order_by('id')
        if username_matches.count() == 1:
            return username_matches.first()

        # 3) Email fallback if unique.
        if '@' in identifier:
            email_matches = User.objects.filter(email__iexact=identifier).order_by('id')
            if email_matches.count() == 1:
                return email_matches.first()

        return None

    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = (username or kwargs.get(User.USERNAME_FIELD) or '').strip()
        if not identifier or password is None:
            return None

        user = self._resolve_user(identifier)

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None