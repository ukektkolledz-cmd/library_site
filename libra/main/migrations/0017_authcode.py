from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0016_student_language_student_specialization_student_year'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('purpose', models.CharField(choices=[('registration', 'Подтверждение регистрации'), ('password_reset', 'Сброс пароля')], max_length=30, verbose_name='Назначение')),
                ('code', models.CharField(max_length=6, verbose_name='Код')),
                ('expires_at', models.DateTimeField(verbose_name='Действителен до')),
                ('is_used', models.BooleanField(default=False, verbose_name='Использован')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auth_codes', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Код подтверждения',
                'verbose_name_plural': 'Коды подтверждения',
                'ordering': ['-created_at'],
            },
        ),
    ]
