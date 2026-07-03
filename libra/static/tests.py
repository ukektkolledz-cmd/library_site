from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from main.models import BookReservationJournal, Book_Info, Category


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
