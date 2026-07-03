import os
import re

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from main.models import Student


def _normalize_header(header):
    return re.sub(r'[\s\-№]+', '_', str(header).strip().lower())


def _value_to_text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    return str(value).strip()


class Command(BaseCommand):
    help = 'Import a student list from an Excel file into the Student model.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            required=True,
            help='Path to the Excel file with student data.',
        )
        parser.add_argument(
            '--sheet',
            default=0,
            help='Sheet name or index in the Excel file.',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete existing Student records before import.',
        )

    def handle(self, *args, **options):
        excel_file = options['file']
        sheet_name = options['sheet']
        replace = options['replace']

        if not os.path.exists(excel_file):
            raise CommandError(f'Файл не найден: {excel_file}')

        try:
            df = pd.read_excel(excel_file, engine='openpyxl', sheet_name=sheet_name)
        except Exception as e:
            raise CommandError(f'Не удалось прочитать Excel-файл: {e}')

        if df.empty:
            self.stdout.write(self.style.WARNING('Файл пустой — нет данных для импорта.'))
            return

        normalized_columns = [_normalize_header(col) for col in df.columns]
        df.columns = normalized_columns

        def find_column(candidates):
            for candidate in candidates:
                if candidate in normalized_columns:
                    return candidate
            return None

        student_id_column = find_column([
            'id', 'student_id', 'student id', 'studentid',
            'студенческий_билет', 'студенческий_билет_номер', 'студенческий_билет_№',
        ])
        full_name_column = find_column([
            'фио', 'full_name', 'full name', 'name', 'fullname', 'фамилия_имя', 'имя'])
        group_column = find_column(['group', 'group_name', 'группа'])
        course_column = find_column(['course', 'курс'])
        homeroom_column = find_column([
            'руководитель', 'руководительница', 'классная_руководительница',
            'homeroom_teacher', 'class_teacher', 'teacher', 'teacher_name', 'классный_руководитель'
        ])

        if not student_id_column or not full_name_column:
            raise CommandError(
                'Не удалось найти обязательные столбцы. Убедитесь, что файл содержит ID и ФИО.'
            )

        if replace:
            deleted, _ = Student.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f'Удалено {deleted} существующих записей Student.'))

        imported = 0
        updated = 0
        skipped = 0

        for _, row in df.iterrows():
            raw_student_id = _value_to_text(row.get(student_id_column))
            try:
                student_id = Student.normalize_student_id(raw_student_id)
            except Exception:
                skipped += 1
                continue
            full_name = _value_to_text(row.get(full_name_column))
            group_name = _value_to_text(row.get(group_column)) if group_column else ''
            course = _value_to_text(row.get(course_column)) if course_column else ''
            homeroom_teacher = _value_to_text(row.get(homeroom_column)) if homeroom_column else ''
            parsed = Student.parse_group_info(group_name)
            if not course:
                course = parsed.get('course', '')
            year = parsed.get('year')
            specialization = parsed.get('specialization', '')
            language = parsed.get('language', '')

            if not student_id or not full_name:
                skipped += 1
                continue

            obj, created = Student.objects.update_or_create(
                student_id=student_id,
                defaults={
                    'full_name': full_name,
                    'group_name': group_name,
                    'course': course,
                    'year': year,
                    'specialization': specialization,
                    'language': language,
                    'homeroom_teacher': homeroom_teacher,
                },
            )
            if created:
                imported += 1
            else:
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f'Импорт завершён: добавлено {imported}, обновлено {updated}, пропущено {skipped}.'
        ))
