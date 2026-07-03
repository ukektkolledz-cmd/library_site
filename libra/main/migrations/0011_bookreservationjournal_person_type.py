from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0010_profile_saved_books_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bookreservationjournal',
            name='person_type',
            field=models.CharField(choices=[('student', 'Студент'), ('teacher', 'Преподаватель')], default='student', max_length=10, verbose_name='Тип клиента'),
        ),
    ]
