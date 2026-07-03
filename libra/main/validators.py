import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class CustomPasswordValidator:
    """Пароль: мин. 8 символов, латиница, хотя бы одна цифра и спецсимвол."""

    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(_('Пароль должен содержать не менее 8 символов.'), code='password_too_short')
        if not re.search(r'[A-Za-z]', password):
            raise ValidationError(_('Пароль должен содержать латинские буквы.'), code='password_no_latin')
        if re.search(r'[^A-Za-z0-9!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]', password):
            raise ValidationError(_('Пароль должен содержать только латинские буквы, цифры и спецсимволы.'), code='password_invalid_chars')
        if not re.search(r'\d', password):
            raise ValidationError(_('Пароль должен содержать хотя бы одну цифру.'), code='password_no_digit')
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]', password):
            raise ValidationError(_('Пароль должен содержать хотя бы один спецсимвол (!@#$%^&* и т.д.).'), code='password_no_special')

    def get_help_text(self):
        return _(
            'Пароль должен содержать минимум 8 символов, '
            'только латинские буквы, хотя бы одну цифру и один спецсимвол (!@#$%^&* и т.д.).'
        )
