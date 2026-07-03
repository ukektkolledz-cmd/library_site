from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0011_bookreservationjournal_person_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='book_info',
            name='subject_area',
            field=models.CharField(
                blank=True,
                choices=[
                    ('humanitarian', 'Гуманитарное'),
                    ('technical', 'Техническое'),
                ],
                default='',
                max_length=20,
                verbose_name='Направление',
            ),
            preserve_default=False,
        ),
    ]
