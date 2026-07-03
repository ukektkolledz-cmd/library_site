from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Жанр')
        verbose_name_plural = _('Жанры')


    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse("main:book_list_by_category", args=[self.slug])


class School_Type(models.Model):
    """Тип школы/уровень образования"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    
    class Meta:
        verbose_name = _('Тип школы')
        verbose_name_plural = _('Типы школ')
    
    def __str__(self):
        return self.name


class Specialization(models.Model):
    """Специализация книги"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    
    class Meta:
        verbose_name = _('Специализация')
        verbose_name_plural = _('Специализации')
    
    def __str__(self):
        return self.name
    

class Book_Info(models.Model):
    category = models.ForeignKey(Category, related_name='books',
                                on_delete=models.CASCADE)
    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=200, unique=True)
    author = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    isbn = models.CharField(max_length=13, unique=True)
    publication_date = models.DateField()
    available = models.BooleanField(default=True)
    total_copies = models.PositiveIntegerField(default=1, verbose_name=_('Всего экземпляров'))
    available_copies = models.PositiveIntegerField(default=1, verbose_name=_('Доступно экземпляров'))
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='books/%Y/%m/%d', blank=True)
    pdf_file = models.FileField(upload_to='books/pdf/%Y/%m/%d', blank=True, null=True, verbose_name=_('PDF файл'))
    school_type = models.ForeignKey(School_Type, on_delete=models.SET_NULL, null=True, blank=True, related_name='books', verbose_name=_('Тип школы'))
    specialization = models.ForeignKey(Specialization, on_delete=models.SET_NULL, null=True, blank=True, related_name='books', verbose_name=_('Специализация'))

    LANGUAGE_CHOICES = [
        ('ru', _('Русский')),
        ('kk', _('Қазақша')),
        ('en', _('English')),
    ]
    language = models.CharField(
        max_length=2,
        choices=LANGUAGE_CHOICES,
        default='ru',
        verbose_name=_('Язык'),
    )

    SUBJECT_AREA_CHOICES = [
        ('humanitarian', _('Гуманитарное')),
        ('technical', _('Техническое')),
    ]
    subject_area = models.CharField(
        max_length=20,
        choices=SUBJECT_AREA_CHOICES,
        blank=True,
        verbose_name=_('Направление'),
    )

    class Meta:
        ordering = ['title']
        indexes = [models.Index(fields=['id', 'slug'])]
        verbose_name = _('Книга')
        verbose_name_plural = _('Книги')
    

    def __str__(self):
        return f"{self.title} - {self.author}"
    
    @property
    def year(self):
        return self.publication_date.year if self.publication_date else None

    @property
    def date_added(self):
        return self.created
    
    @property
    def is_available(self):
        return getattr(self, 'available_copies', 0) > 0

class BookLoan(models.Model):
    STATUS_CHOICES = [
        ('active', _('Активна')),
        ('returned', _('Возвращена')),
        ('overdue', _('Просрочена')),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name=_('Пользователь'))
    book = models.ForeignKey(Book_Info, on_delete=models.CASCADE, verbose_name=_('Книга'))
    loan_date = models.DateField(default=timezone.now, verbose_name=_('Дата выдачи'))
    due_date = models.DateField(verbose_name=_('Срок возврата'))
    return_date = models.DateField(null=True, blank=True, verbose_name=_('Дата возврата'))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    
    class Meta:
        verbose_name = _('Выдача книги')
        verbose_name_plural = _('Выдачи книг')
    
    def __str__(self):
        return f"{self.user.username} - {self.book.title}"
    
    @property
    def is_overdue(self):
        return self.due_date < timezone.now().date() and self.status == 'active'

class Reservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book_Info, on_delete=models.CASCADE)
    reservation_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', _('В ожидании')),
        ('ready', _('Готов к выдаче')),
        ('cancelled', _('Отменена')),
    ], default='pending')
    
    class Meta:
        unique_together = ['user', 'book']

class BookReservationJournal(models.Model):
    """
    Журнал бронирования книг для администраторов
    """
    PERSON_TYPE_CHOICES = [
        ('student', _('Студент')),
        ('teacher', _('Преподаватель')),
    ]

    STATUS_CHOICES = [
        ('reserved', _('Зарезервирована')),
        ('returned', _('Возвращена')),
        ('expired', _('Просрочена')),
    ]
    
    book = models.ForeignKey(Book_Info, on_delete=models.CASCADE, verbose_name=_('Книга'))
    person_type = models.CharField(max_length=10, choices=PERSON_TYPE_CHOICES, default='student', verbose_name=_('Тип клиента'))
    student_name = models.CharField(max_length=150, verbose_name=_('Имя студента'))
    group_name = models.CharField(max_length=100, verbose_name=_('Группа'))
    teacher_name = models.CharField(max_length=150, blank=True, verbose_name=_('Имя преподавателя'))
    quantity = models.PositiveIntegerField(default=1, verbose_name=_('Количество'))
    reservation_datetime = models.DateTimeField(default=timezone.now, verbose_name=_('Дата и время бронирования'))
    expiration_date = models.DateTimeField(verbose_name=_('Дата и время окончания'))
    returned_date = models.DateTimeField(null=True, blank=True, verbose_name=_('Дата возврата'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='reserved', verbose_name=_('Статус'))
    notes = models.TextField(blank=True, verbose_name=_('Примечания'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_reservations', verbose_name=_('Создано'))
    
    class Meta:
        verbose_name = _('Бронь в журнале')
        verbose_name_plural = _('Брони в журнале')
        ordering = ['-reservation_datetime']
    
    def __str__(self):
        if self.person_type == 'teacher':
            return f"{self.teacher_name} - {self.book.title} ({self.quantity} шт.)"
        return f"{self.student_name} - {self.book.title} ({self.quantity} шт.)"
    
    def clean(self):
        super().clean()
        if self.person_type == 'teacher':
            self.student_name = ''
            self.group_name = ''
        else:
            self.teacher_name = ''

    @property
    def is_expired(self):
        return self.expiration_date < timezone.now() and self.status == 'reserved'

class Student(models.Model):
    """Школьный студент, доступный для регистрации по ID."""
    STUDY_PROGRAM_MAP = {
        'ТП': _('Разработчик программного обеспечения'),
        'РП': _('Разработчик программного обеспечения'),
        # Добавьте сюда остальные коды и названия программ
    }

    LANGUAGE_CHOICES = [
        ('ru', _('Русский')),
        ('kk', _('Қазақша')),
    ]

    student_id = models.CharField(max_length=50, unique=True, verbose_name=_('Номер студенческого билета'))
    full_name = models.CharField(max_length=200, verbose_name=_('ФИО'))
    group_name = models.CharField(max_length=100, blank=True, verbose_name=_('Группа'))
    course = models.CharField(max_length=100, blank=True, verbose_name=_('Курс'))
    year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Год'))
    specialization = models.CharField(max_length=200, blank=True, verbose_name=_('Специальность'))
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, blank=True, verbose_name=_('Язык'))
    homeroom_teacher = models.CharField(max_length=200, blank=True, verbose_name=_('Руководитель'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Дата добавления'))

    class Meta:
        verbose_name = _('Студент')
        verbose_name_plural = _('Студенты')
        ordering = ['student_id']

    def __str__(self):
        return f"{self.student_id} — {self.full_name}"

    @staticmethod
    def parse_group_info(group_name):
        if not group_name:
            return {}

        group = str(group_name).strip().upper().replace(' ', '')
        result = {
            'year': None,
            'course': '',
            'specialization': '',
            'language': '',
        }

        # Пример: 22ТП-41р
        import re
        pattern = re.compile(r'^(?P<year>\d{2})(?P<program>[А-ЯA-Z]{1,4})[-–]?(?P<course>\d)(?P<group>\d)?(?P<lang>[РRKК])?$', re.IGNORECASE)
        match = pattern.match(group)
        if match:
            year = match.group('year')
            result['year'] = 2000 + int(year)
            program_code = match.group('program').upper()
            result['specialization'] = Student.STUDY_PROGRAM_MAP.get(program_code, program_code)
            result['course'] = match.group('course')
            lang = match.group('lang')
            if lang:
                if lang.upper() in ('Р', 'P'):
                    result['language'] = 'ru'
                elif lang.upper() in ('К', 'K'):
                    result['language'] = 'kk'
        else:
            # Попытка выделить номер курса по разделителю
            import re as _re
            year_match = _re.match(r'^(\d{2})', group)
            if year_match:
                result['year'] = 2000 + int(year_match.group(1))
            lang_match = _re.search(r'([РRKК])$', group)
            if lang_match:
                lang = lang_match.group(1).upper()
                result['language'] = 'ru' if lang in ('Р', 'P') else 'kk'
            course_match = _re.search(r'-(\d)', group)
            if course_match:
                result['course'] = course_match.group(1)
            # Специализация как код из середины
            program_match = _re.match(r'^\d{2}([А-ЯA-Z]{1,4})', group)
            if program_match:
                result['specialization'] = Student.STUDY_PROGRAM_MAP.get(program_match.group(1).upper(), program_match.group(1).upper())

        return result

class Profile(models.Model):
    """
    Модель профиля пользователя, расширяющая стандартную модель User
    """
    # Связь с пользователем (один к одному)
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name=_('Пользователь'))
    
    # Дополнительные поля для профиля
    phone = models.CharField(max_length=20, blank=True, verbose_name=_('Телефон'))
    address = models.TextField(blank=True, verbose_name=_('Адрес'))
    birth_date = models.DateField(null=True, blank=True, verbose_name=_('Дата рождения'))
    student_id = models.CharField(max_length=50, blank=True, verbose_name=_('Студенческий билет №'))
    group_name = models.CharField(max_length=50, blank=True, verbose_name=_('Группа'))
    avatar = models.ImageField(upload_to='avatars/%Y/%m/%d', blank=True, null=True, verbose_name=_('Аватар'))
    saved_books = models.ManyToManyField('Book_Info', blank=True, related_name='saved_by', verbose_name=_('Сохранённые книги'))
    
    # Дополнительная информация
    bio = models.TextField(blank=True, verbose_name=_('О себе'))
    telegram = models.CharField(max_length=100, blank=True, verbose_name=_('Telegram'))
    instagram = models.CharField(max_length=100, blank=True, verbose_name=_('Instagram'))
    
    # Системные поля
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Дата регистрации'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Дата обновления'))
    
    class Meta:
        verbose_name = _('Профиль пользователя')
        verbose_name_plural = _('Профили пользователей')
    
    def __str__(self):
        return f"Профиль пользователя {self.user.username}"
    
    def get_absolute_url(self):
        return reverse('main:profile')
    
    @property
    def full_name(self):
        """Возвращает полное имя пользователя"""
        if self.user.first_name and self.user.last_name:
            return f"{self.user.last_name} {self.user.first_name}"
        return self.user.username

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Сигнал: автоматически создаёт профиль при создании пользователя"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Сигнал: автоматически сохраняет профиль при сохранении пользователя"""
    # Some legacy users may not have a related profile row.
    profile, _ = Profile.objects.get_or_create(user=instance)
    profile.save()