from datetime import date

import re

import json
from unittest.mock import patch

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core import mail
from django.http import HttpResponse
from django.test import Client, TestCase, override_settings, RequestFactory
from django.urls import reverse

from .forms import UserRegisterForm
from .forms import EmailOrUsernameAuthenticationForm
from .models import BookReservationJournal, Book_Info, Category, Profile, Student, Teacher, ReservedStudent, AuthCode
from .views import password_reset_request


@override_settings(ALLOWED_HOSTS=['testserver', '127.0.0.1', 'localhost'])
class ReservationJournalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='staffuser',
            password='strong-pass-123',
            is_staff=True,
            is_superuser=True,
        )
        self.client.login(username='staffuser', password='strong-pass-123')

        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.book = Book_Info.objects.create(
            category=self.category,
            title='Test Book',
            slug='test-book',
            author='Author',
            description='Desc',
            isbn='9999999999999',
            publication_date=date(2024, 1, 1),
            available=True,
            total_copies=5,
            available_copies=5,
        )

    def test_reservation_journal_contains_booking_modal(self):
        response = self.client.get(reverse('main:reservation_journal'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'createBookingModal')

    def test_student_autocomplete_returns_matches(self):
        Student.objects.create(student_id='0999', full_name='Байжан Нурлан', group_name='TP-41')

        response = self.client.get(reverse('main:student_autocomplete'), {'q': 'Ба'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any('Байжан Нурлан' in item['label'] for item in payload['results']))

    def test_teacher_autocomplete_returns_matches(self):
        Student.objects.create(
            student_id='1000',
            full_name='Тестовый Студент',
            group_name='TP-41',
            homeroom_teacher='Сейтов Ержан',
        )
        BookReservationJournal.objects.create(
            book=self.book,
            student_name='Student One',
            group_name='TP-41',
            teacher_name='Сейтинова Айгерим',
            quantity=1,
            expiration_date='2026-01-01T00:00:00Z',
            status='reserved',
            created_by=self.user,
        )

        response = self.client.get(reverse('main:teacher_autocomplete'), {'q': 'Сейт'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(item['value'] == 'Сейтов Ержан' for item in payload['results']))
        self.assertTrue(any(item['value'] == 'Сейтинова Айгерим' for item in payload['results']))

    def test_book_autocomplete_returns_matches(self):
        response = self.client.get(reverse('main:book_autocomplete'), {'q': 'Test'})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any('Test Book' in item['label'] for item in payload['results']))

    def test_return_overdue_book_marks_late_and_restores_copies(self):
        reservation = BookReservationJournal.objects.create(
            book=self.book,
            student_name='Student Late',
            group_name='TP-50',
            quantity=2,
            expiration_date='2024-01-01T00:00:00Z',
            status='reserved',
            created_by=self.user,
        )
        self.book.available_copies = 3
        self.book.save(update_fields=['available_copies'])

        response = self.client.post(
            reverse('main:return_book', args=[reservation.id]),
            data=json.dumps({'returned': True, 'mark_overdue': True}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(reservation.status, 'returned_late')
        self.assertEqual(self.book.available_copies, 5)

    def test_create_reservation_uses_defaults_when_dates_missing(self):
        response = self.client.post(
            reverse('main:create_reservation'),
            {
                'student_name': 'Student One',
                'group_name': 'TP-41',
                'teacher_name': '',
                'quantity': '1',
                'book': str(self.book.id),
                'reservation_datetime': '',
                'expiration_date': '',
                'notes': 'Created without manual dates',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(BookReservationJournal.objects.count(), 1)

        reservation = BookReservationJournal.objects.get()
        self.assertIsNotNone(reservation.reservation_datetime)
        self.assertIsNotNone(reservation.expiration_date)

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 4)

    def test_invalid_dates_do_not_reduce_available_copies(self):
        response = self.client.post(
            reverse('main:create_reservation'),
            {
                'student_name': 'Student Two',
                'group_name': 'TP-42',
                'teacher_name': '',
                'quantity': '1',
                'book': str(self.book.id),
                'reservation_datetime': 'bad-date',
                'expiration_date': 'still-bad',
                'notes': 'Invalid dates',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(BookReservationJournal.objects.count(), 0)

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 5)


@override_settings(
    ALLOWED_HOSTS=['testserver', '127.0.0.1', 'localhost'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class AuthFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.student = Student.objects.create(
            student_id='ST-1001',
            full_name='Иванов Иван Иванович',
            group_name='22ТП-41Р',
            course='4',
            year=2022,
            specialization='Разработчик программного обеспечения',
            language='ru',
            homeroom_teacher='Петров П.П.',
        )

    def _extract_code(self, message):
        match = re.search(r'(\d{6})', message)
        self.assertIsNotNone(match, 'Verification code not found in email message')
        return match.group(1)

    def test_student_id_is_normalized_to_four_digits(self):
        self.assertEqual(Student.normalize_student_id('7'), '0007')
        self.assertEqual(Student.normalize_student_id('0932'), '0932')

    def test_register_sends_code_and_activates_only_after_verification(self):
        response = self.client.post(
            reverse('main:register'),
            {
                'username': 'studentuser',
                'email': 'student@example.com',
                'student_id': self.student.student_id,
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        self.assertRedirects(response, reverse('main:verify_registration'))

        user = User.objects.get(username='studentuser')
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)

        code = self._extract_code(mail.outbox[0].body)
        verify_response = self.client.post(
            reverse('main:verify_registration'),
            {'code': code},
        )

        self.assertRedirects(verify_response, reverse('main:index'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.student_id, self.student.student_id)
        self.assertEqual(profile.group_name, self.student.group_name)
        self.assertEqual(user.last_name, 'Иванов')
        self.assertEqual(user.first_name, 'Иван')

    def test_password_reset_by_code_updates_password(self):
        user = User.objects.create_user(
            username='resetuser',
            email='reset@example.com',
            password='OldPass123!',
            is_active=True,
        )
        Profile.objects.update_or_create(user=user, defaults={'student_id': self.student.student_id})

        response = self.client.post(reverse('password_reset'), {'email': user.email})
        self.assertRedirects(response, reverse('password_reset_verify_code'))
        self.assertEqual(len(mail.outbox), 1)

        code = self._extract_code(mail.outbox[0].body)
        confirm_response = self.client.post(
            reverse('password_reset_verify_code'),
            {
                'code': code,
                'new_password1': 'NewStrongPass123!',
                'new_password2': 'NewStrongPass123!',
            },
        )

        self.assertRedirects(confirm_response, reverse('login'))
        user.refresh_from_db()
        self.assertTrue(user.check_password('NewStrongPass123!'))

    def test_teacher_can_register_and_verify_by_teacher_id(self):
        teacher = Teacher.objects.create(
            teacher_id='42',
            full_name='Серикова Алина Нурлановна',
            department='Информатика',
            position='Преподаватель',
        )

        response = self.client.post(
            reverse('main:register'),
            {
                'username': 'teacheruser',
                'email': 'teacher@example.com',
                'person_type': 'teacher',
                'student_id': teacher.teacher_id,
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('main:verify_registration'))
        self.assertEqual(len(mail.outbox), 1)

        code = self._extract_code(mail.outbox[0].body)
        verify_response = self.client.post(reverse('main:verify_registration'), {'code': code})

        self.assertEqual(verify_response.status_code, 302)
        self.assertEqual(verify_response.url, reverse('main:index'))

        user = User.objects.get(username='teacheruser')
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.person_type, 'teacher')
        self.assertEqual(profile.teacher_id, '0042')
        self.assertEqual(profile.student_id, '')
        self.assertEqual(user.last_name, 'Серикова')
        self.assertEqual(user.first_name, 'Алина')

    def test_login_allows_username_or_email(self):
        user = User.objects.create_user(
            username='email_login_user',
            email='mail.login@example.com',
            password='StrongPass123!',
            is_active=True,
        )

        response = self.client.post(
            reverse('login'),
            {
                'username': 'MAIL.LOGIN@example.com',
                'password': 'StrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session.get('_auth_user_id')), user.id)

    def test_admin_authenticate_by_username_and_email(self):
        admin_user = User.objects.create_superuser(
            username='adminmain',
            email='adminmain@example.com',
            password='StrongPass123!',
        )

        by_username = authenticate(username='adminmain', password='StrongPass123!')
        by_email = authenticate(username='ADMINMAIN@EXAMPLE.COM', password='StrongPass123!')

        self.assertIsNotNone(by_username)
        self.assertIsNotNone(by_email)
        self.assertEqual(by_username.id, admin_user.id)
        self.assertEqual(by_email.id, admin_user.id)

    def test_login_email_like_username_still_works(self):
        admin_user = User.objects.create_user(
            username='admin@example.com',
            email='shared@example.com',
            password='StrongPass123!',
            is_active=True,
        )
        User.objects.create_user(
            username='another_user',
            email='shared@example.com',
            password='StrongPass123!',
            is_active=True,
        )

        response = self.client.post(
            reverse('login'),
            {
                'username': 'admin@example.com',
                'password': 'StrongPass123!',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session.get('_auth_user_id')), admin_user.id)

    def test_auth_form_allows_case_insensitive_username(self):
        user = User.objects.create_user(
            username='MixedCaseUser',
            email='mixedcase@example.com',
            password='StrongPass123!',
            is_active=True,
        )

        form = EmailOrUsernameAuthenticationForm(
            request=None,
            data={'username': 'mixedcaseuser', 'password': 'StrongPass123!'},
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.get_user().id, user.id)

    def test_auth_form_shows_user_not_found_message(self):
        form = EmailOrUsernameAuthenticationForm(
            request=None,
            data={'username': 'unknown_user_123', 'password': 'StrongPass123!'},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Пользователь не найден', str(form.non_field_errors()))

    def test_registration_blocks_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            username='existing_user',
            email='duplicate@example.com',
            password='StrongPass123!',
            is_active=True,
        )

        form = UserRegisterForm(
            data={
                'username': 'new_user',
                'email': 'DUPLICATE@EXAMPLE.COM',
                'person_type': 'student',
                'student_id': self.student.student_id,
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertFalse(User.objects.filter(username='new_user').exists())

    def test_password_reset_rejects_ambiguous_duplicate_email(self):
        user_one = User.objects.create_user(
            username='dup_email_1',
            email='same@example.com',
            password='OldPass123!',
            is_active=True,
        )
        user_two = User.objects.create_user(
            username='dup_email_2',
            email='same@example.com',
            password='OldPass123!',
            is_active=True,
        )
        Profile.objects.get_or_create(user=user_one)
        Profile.objects.get_or_create(user=user_two)

        request = self.factory.post(reverse('password_reset'), {'email': 'same@example.com'})
        with patch('main.views.render', return_value=HttpResponse('rendered', status=200)) as render_mock:
            response = password_reset_request(request)

        self.assertEqual(response.status_code, 200)
        passed_form = render_mock.call_args.args[2]['form']
        self.assertIn('email', passed_form.errors)
        self.assertIn('С этим email найдено несколько аккаунтов', str(passed_form.errors['email']))
        self.assertEqual(AuthCode.objects.count(), 0)


class StudentReserveArchiveTests(TestCase):
    def test_deleted_student_is_kept_in_reserved_students(self):
        student = Student.objects.create(
            student_id='1234',
            full_name='Резервный Студент',
            group_name='TP-99',
            course='2',
            year=2025,
            specialization='Тестовая специальность',
            language='ru',
            homeroom_teacher='Тестовый Куратор',
        )

        student.delete()

        self.assertFalse(Student.objects.filter(student_id='1234').exists())
        archive = ReservedStudent.objects.filter(student_id='1234').first()
        self.assertIsNotNone(archive)
        self.assertEqual(archive.full_name, 'Резервный Студент')
        self.assertEqual(archive.group_name, 'TP-99')
