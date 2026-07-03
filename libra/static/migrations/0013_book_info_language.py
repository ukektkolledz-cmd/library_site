from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0012_book_info_subject_area'),
    ]

    operations = [
        migrations.AddField(
            model_name='book_info',
            name='language',
            field=models.CharField(
                choices=[
                    ('ru', 'Русский'),
                    ('kk', 'Қазақша'),
                    ('en', 'English'),
                ],
                default='ru',
                max_length=2,
                verbose_name='Язык',
            ),
            preserve_default=False,
        ),
    ]
