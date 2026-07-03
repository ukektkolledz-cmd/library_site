from django.core.validators import RegexValidator
from django.db import migrations, models


def normalize_student_ids(apps, schema_editor):
    Student = apps.get_model('main', 'Student')
    Profile = apps.get_model('main', 'Profile')

    students = list(Student.objects.order_by('pk'))
    if len(students) > 9999:
        raise RuntimeError('Количество студентов превышает лимит 4-значных ID.')

    mapping = {}

    for index, student in enumerate(students, start=1):
        original = '' if student.student_id is None else str(student.student_id).strip()
        digits = ''.join(ch for ch in original if ch.isdigit())
        final_id = f'{index:04d}'

        mapping[original] = final_id
        if digits:
            mapping[digits] = final_id
            if len(digits) <= 4:
                mapping[digits.zfill(4)] = final_id

        Student.objects.filter(pk=student.pk).update(student_id=f'T{index:04d}')

    for index, student in enumerate(students, start=1):
        Student.objects.filter(pk=student.pk).update(student_id=f'{index:04d}')

    for profile in Profile.objects.exclude(student_id=''):
        current = '' if profile.student_id is None else str(profile.student_id).strip()
        digits = ''.join(ch for ch in current if ch.isdigit())

        new_id = mapping.get(current)
        if new_id is None and digits:
            new_id = mapping.get(digits) or mapping.get(digits.zfill(4))

        if new_id is None:
            new_id = digits.zfill(4) if digits and len(digits) <= 4 else ''

        Profile.objects.filter(pk=profile.pk).update(student_id=new_id)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0017_authcode'),
    ]

    operations = [
        migrations.RunPython(normalize_student_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='student',
            name='student_id',
            field=models.CharField(
                max_length=4,
                unique=True,
                validators=[RegexValidator(r'^\d{4}$', 'ID должен состоять из 4 цифр.')],
                verbose_name='ID',
            ),
        ),
        migrations.AlterField(
            model_name='profile',
            name='student_id',
            field=models.CharField(
                blank=True,
                max_length=4,
                validators=[RegexValidator(r'^\d{4}$', 'ID должен состоять из 4 цифр.')],
                verbose_name='ID',
            ),
        ),
    ]
