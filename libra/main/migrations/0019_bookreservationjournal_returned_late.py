from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0018_normalize_student_ids_to_four_digits'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bookreservationjournal',
            name='status',
            field=models.CharField(
                choices=[
                    ('reserved', 'Зарезервирована'),
                    ('returned', 'Возвращена'),
                    ('returned_late', 'Возвращена с просрочкой'),
                    ('expired', 'Просрочена'),
                ],
                default='reserved',
                max_length=20,
                verbose_name='Статус',
            ),
        ),
    ]
