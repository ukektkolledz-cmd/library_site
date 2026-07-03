import secrets
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Category, Book_Info, BookLoan, Reservation, School_Type, Specialization, BookReservationJournal, AuthCode, Student, Teacher, Profile
from django.db import transaction
from django.db.models import Q, F, Sum
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.views import LogoutView, LoginView
from django.contrib import messages 
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.core.mail import send_mail
from django.conf import settings
from .forms import (
    UserEditForm,
    ProfileEditForm,
    UserRegisterForm,
    EmailOrUsernameAuthenticationForm,
    VerificationCodeForm,
    PasswordResetRequestForm,
    SetPasswordByCodeForm,
)
from django.core.paginator import Paginator



# Create your views here.


def _send_auth_code_email(user, auth_code):
    if auth_code.purpose == AuthCode.PURPOSE_REGISTRATION:
        subject = 'Код подтверждения регистрации'
        message = (
            f'Здравствуйте, {user.username}!\n\n'
            f'Ваш код подтверждения: {auth_code.code}\n'
            'Введите его на сайте, чтобы завершить регистрацию.\n'
            'Код действует 10 минут.'
        )
    else:
        subject = 'Код для сброса пароля'
        message = (
            f'Здравствуйте, {user.username}!\n\n'
            f'Ваш код для смены пароля: {auth_code.code}\n'
            'Введите его на сайте, чтобы задать новый пароль.\n'
            'Код действует 10 минут.'
        )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=True,
    )


def _get_active_code(user, purpose, code_value):
    auth_code = AuthCode.objects.filter(
        user=user,
        purpose=purpose,
        code=code_value,
        is_used=False,
    ).order_by('-created_at').first()

    if auth_code is None or auth_code.is_expired:
        return None
    return auth_code


def main_page(request):
    categories = Category.objects.all()[:6]
    new_books = Book_Info.objects.filter(available=True).order_by('-created')[:6]
    stats = {
        'books_count': Book_Info.objects.filter(available=True).count(),
        'pdf_count': Book_Info.objects.filter(available=True, pdf_file__isnull=False).count(),
        'authors_count': Book_Info.objects.filter(available=True).values('author').distinct().count(),
        'available_count': Book_Info.objects.filter(available=True, available_copies__gt=0).count(),
    }
    return render(request, 'main/index.html', {
        'categories': categories,
        'new_books': new_books,
        'stats': stats,
    })

@login_required(login_url='login')
def index(request, category_slug=None):
    categories = Category.objects.all()
    school_types = School_Type.objects.all()
    specializations = Specialization.objects.all()
    books = Book_Info.objects.filter(available=True)

    saved_books_ids = []
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile is not None:
            saved_books_ids = list(profile.saved_books.values_list('id', flat=True))

    category = None
    query = request.GET.get('q')
    sort_by = request.GET.get('sort', 'title')
    
    # Get filter parameters
    selected_school_types = request.GET.getlist('school_type')
    selected_specializations = request.GET.getlist('specialization')
    selected_categories = request.GET.getlist('category')
    selected_subject_areas = request.GET.getlist('subject_area')
    selected_language = request.GET.get('language', '')

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        if selected_categories:
            books = books.filter(category__id__in=selected_categories)
        else:
            books = books.filter(category=category)
    elif selected_categories:
        books = books.filter(category__id__in=selected_categories)

    if query:
        books = books.filter(
            Q(title__icontains=query) |
            Q(author__icontains=query) |
            Q(description__icontains=query) |
            Q(isbn__icontains=query)
        )
    
    # Apply filters
    if selected_school_types:
        books = books.filter(school_type__id__in=selected_school_types)
    
    if selected_specializations:
        books = books.filter(specialization__id__in=selected_specializations)

    if selected_subject_areas:
        books = books.filter(subject_area__in=selected_subject_areas)

    if selected_language:
        books = books.filter(language=selected_language)
    
    # Sorting
    if sort_by == 'author':
        books = books.order_by('author', 'title')
    elif sort_by == 'year':
        books = books.order_by('-publication_date', 'title')
    else:
        books = books.order_by('title')

    selected_category_ids = [int(x) for x in selected_categories] if selected_categories else ([category.id] if category else [])

    paginator = Paginator(books, 21)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'main/product/list.html', {
        'category': category,
        'categories': categories,
        'school_types': school_types,
        'specializations': specializations,
        'books': page_obj,
        'page_obj': page_obj,
        'query': query,
        'sort_by': sort_by,
        'selected_school_types': [int(x) for x in selected_school_types],
        'selected_specializations': [int(x) for x in selected_specializations],
        'selected_subject_areas': selected_subject_areas,
        'selected_language': selected_language,
        'selected_category_ids': selected_category_ids,
        'saved_books_ids': saved_books_ids,
    })

def book_detail(request, book_id):
    book = get_object_or_404(Book_Info, id=book_id)
    is_reserved = False
    user_loans = []
    
    if request.user.is_authenticated:
        is_reserved = Reservation.objects.filter(
            user=request.user, 
            book=book, 
            status='pending'
        ).exists()
        user_loans = BookLoan.objects.filter(user=request.user, book=book, status='active')
    
    # Похожие книги (по категории и автору)
    similar_books = Book_Info.objects.filter(
        Q(category=book.category) | Q(author=book.author)
    ).exclude(id=book.id).distinct()[:3]
    
    checked_out = 0
    try:
        checked_out = book.total_copies - book.available_copies
    except Exception:
        checked_out = 0

    is_saved = False
    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile is not None:
            is_saved = profile.saved_books.filter(id=book.id).exists()

    return render(request, 'main/book_detail.html', {
        'book': book,
        'is_reserved': is_reserved,
        'user_loans': user_loans,
        'similar_books': similar_books,
        'checked_out': checked_out,
        'is_saved': is_saved,
    })

@login_required(login_url='login')
def toggle_saved_book(request, book_id):
    book = get_object_or_404(Book_Info, id=book_id)
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        messages.error(request, _('Профиль не найден.'))
        return redirect('main:book_detail', book_id=book_id)

    if profile.saved_books.filter(id=book.id).exists():
        profile.saved_books.remove(book)
        messages.success(request, _('Книга "%(title)s" удалена из сохранённых.') % {'title': book.title})
    else:
        profile.saved_books.add(book)
        messages.success(request, _('Книга "%(title)s" сохранена.') % {'title': book.title})

    referrer = request.META.get('HTTP_REFERER')
    if referrer:
        return redirect(referrer)
    return redirect('main:book_detail', book_id=book_id)

@login_required
def profile(request):
    """Страница профиля пользователя"""
    user = request.user
    try:
        profile = user.profile
    except:
        # If profile doesn't exist, create it
        from .models import Profile
        profile = Profile.objects.create(user=user)
    
    # Получаем сохранённые книги
    saved_books_qs = profile.saved_books.all()
    saved_paginator = Paginator(saved_books_qs, 10)
    saved_page_number = request.GET.get('saved_page')
    saved_page_obj = saved_paginator.get_page(saved_page_number)
    student_record = profile.sync_with_student_data() if profile.student_id else None

    context = {
        'user': user,
        'profile': profile,
        'saved_books': saved_page_obj,
        'saved_page_obj': saved_page_obj,
        'student_record': student_record,
    }
    
    return render(request, 'main/profile.html', context)  # ← БЕЗ ПАПКИ profile


@login_required
def profile_edit(request):
    """Редактирование профиля пользователя"""
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        profile_form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile = profile_form.save()
            if profile.student_id:
                profile.sync_with_student_data()
            messages.success(request, _('Ваш профиль успешно обновлён!'))
            return redirect('main:profile')
        else:
            messages.error(request, _('Пожалуйста, исправьте ошибки в форме.'))
    else:
        user_form = UserEditForm(instance=user)
        profile_form = ProfileEditForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': user,
        'profile': profile,
    }
    
    return render(request, 'main/profile_edit.html', context)  # ← БЕЗ ПАПКИ profile


@login_required
def cancel_reservation(request, reservation_id):
    """Отмена бронирования книги"""
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    
    if reservation.status == 'pending':
        reservation.status = 'cancelled'
        # Вернуть копию в доступные
        if reservation.book.available_copies < reservation.book.total_copies:
            reservation.book.available_copies += 1
            reservation.book.save()
        reservation.save()
        messages.success(request, _('Бронирование книги "%(title)s" отменено.') % {'title': reservation.book.title})
    else:
        messages.error(request, _('Невозможно отменить это бронирование.'))
    
    return redirect('main:profile')


@login_required
def loan_history(request):
    """Полная история выдач пользователя"""
    loans = BookLoan.objects.filter(user=request.user).select_related('book').order_by('-loan_date')
    
    context = {
        'loans': loans,
        'total_loans': loans.count(),
    }
    
    return render(request, 'main/loan_history.html', context)  # ← БЕЗ ПАПКИ profile


@login_required
def reserve_book(request, book_id):
    """Бронирование книги"""
    book = get_object_or_404(Book_Info, id=book_id)

    if book.available_copies <= 0:
        messages.error(request, _('Книга временно недоступна'))
        return redirect('main:book_detail', book_id=book_id)

    existing_reservation = Reservation.objects.filter(user=request.user, book=book).first()
    if existing_reservation is not None:
        if existing_reservation.status in ['pending', 'ready']:
            messages.warning(request, _('Вы уже забронировали эту книгу'))
            return redirect('main:book_detail', book_id=book_id)

        # Если предыдущая бронь просрочена или отменена, обновляем её
        existing_reservation.status = 'pending'
        existing_reservation.reservation_date = timezone.now()
        existing_reservation.save()
        messages.success(request, _('Книга "%(title)s" снова забронирована!') % {'title': book.title})
        return redirect('main:book_detail', book_id=book_id)

    try:
        if book.available_copies <= 0:
            messages.error(request, _('Книга временно недоступна'))
            return redirect('main:book_detail', book_id=book_id)

        Reservation.objects.create(user=request.user, book=book)
        book.available_copies = max(book.available_copies - 1, 0)
        book.save()
        messages.success(request, _('Книга "%(title)s" забронирована!') % {'title': book.title})
    except Exception as e:
        messages.error(request, _('Не удалось создать бронь. Попробуйте позже.'))
        # Опционально: логировать e здесь

    return redirect('main:book_detail', book_id=book_id)


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    form_class = EmailOrUsernameAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        if user and user.email:
            send_mail(
                'Успешный вход в библиотеку',
                f'Здравствуйте, {user.username}!\n\nВы успешно вошли в систему College Library.\nЕсли это были не вы, пожалуйста, сбросьте пароль через страницу восстановления.',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=True,
            )
        return response


def register(request):
    """Registration page with email verification code."""
    if request.user.is_authenticated:
        return redirect('main:index')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            # Build user object WITHOUT saving to DB yet
            user = form.save(commit=False)
            code = f'{secrets.randbelow(1000000):06d}'
            expires_at = (timezone.now() + timedelta(minutes=10)).isoformat()
            request.session['pending_registration'] = {
                'username': user.username,
                'email': user.email,
                'password': user.password,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'person_type': form.cleaned_data.get('person_type') or 'student',
                'external_id': form.cleaned_data['student_id'],
                'code': code,
                'expires_at': expires_at,
            }
            send_mail(
                'Код подтверждения регистрации',
                (
                    f'Здравствуйте, {user.username}!\n\n'
                    f'Ваш код подтверждения: {code}\n'
                    'Введите его на сайте, чтобы завершить регистрацию.\n'
                    'Код действует 10 минут.'
                ),
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            messages.info(request, _('Мы отправили код подтверждения на вашу почту.'))
            return redirect('main:verify_registration')
        messages.error(request, _('Пожалуйста, исправьте ошибки в форме регистрации.'))
    else:
        form = UserRegisterForm()

    return render(request, 'registration/register.html', {'form': form})


def verify_registration(request):
    pending = request.session.get('pending_registration')
    if not pending:
        messages.info(request, _('Сначала зарегистрируйтесь, чтобы подтвердить аккаунт.'))
        return redirect('main:register')

    email = pending.get('email', '')

    if request.method == 'POST':
        form = VerificationCodeForm(request.POST)
        if form.is_valid():
            entered_code = form.cleaned_data['code']
            expires_at = parse_datetime(pending['expires_at'])
            code_expired = expires_at is None or timezone.now() > expires_at

            if entered_code != pending['code'] or code_expired:
                form.add_error('code', _('Код неверный или срок его действия истёк.'))
            else:
                pending_email = (pending.get('email') or '').strip()
                if User.objects.filter(email__iexact=pending_email).exists():
                    form.add_error(None, _('Пользователь с таким email уже зарегистрирован. Войдите в аккаунт или восстановите пароль.'))
                    return render(request, 'registration/verify_registration.html', {'form': form, 'email': email})

                with transaction.atomic():
                    user = User(
                        username=pending['username'],
                        email=pending_email,
                        password=pending['password'],
                        first_name=pending.get('first_name', ''),
                        last_name=pending.get('last_name', ''),
                        is_active=True,
                    )
                    user.save()
                    profile, _created = Profile.objects.get_or_create(user=user)
                    person_type = pending.get('person_type') or 'student'
                    external_id = pending.get('external_id') or pending.get('student_id') or ''

                    profile.person_type = person_type
                    if person_type == 'teacher':
                        profile.teacher_id = external_id
                        profile.student_id = ''
                        profile.group_name = ''
                    else:
                        profile.student_id = external_id
                        profile.teacher_id = ''
                        student = Student.objects.filter(student_id=external_id).first()
                        if student:
                            profile.group_name = student.group_name or profile.group_name
                    profile.save()
                    if person_type == 'teacher':
                        profile.sync_with_teacher_data()
                    else:
                        profile.sync_with_student_data()
                request.session.pop('pending_registration', None)
                auth_login(request, user)
                messages.success(request, _('Аккаунт подтверждён. Добро пожаловать!'))
                return redirect('main:index')
    else:
        form = VerificationCodeForm()

    return render(request, 'registration/verify_registration.html', {'form': form, 'email': email})


def resend_verification_code(request):
    pending = request.session.get('pending_registration')
    if not pending:
        messages.info(request, _('Нет ожидающей регистрации для повторной отправки кода.'))
        return redirect('main:register')

    code = f'{secrets.randbelow(1000000):06d}'
    expires_at = (timezone.now() + timedelta(minutes=10)).isoformat()
    pending['code'] = code
    pending['expires_at'] = expires_at
    request.session['pending_registration'] = pending
    request.session.modified = True

    send_mail(
        'Код подтверждения регистрации',
        (
            f'Здравствуйте, {pending["username"]}!\n\n'
            f'Ваш новый код подтверждения: {code}\n'
            'Введите его на сайте, чтобы завершить регистрацию.\n'
            'Код действует 10 минут.'
        ),
        settings.DEFAULT_FROM_EMAIL,
        [pending['email']],
        fail_silently=True,
    )
    messages.info(request, _('Новый код подтверждения отправлен на вашу почту.'))
    return redirect('main:verify_registration')


def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            users = User.objects.filter(email__iexact=email).order_by('id')
            users_count = users.count()

            if users_count == 0:
                form.add_error('email', _('Пользователь с таким email не найден.'))
            elif users_count > 1:
                form.add_error('email', _('С этим email найдено несколько аккаунтов. Обратитесь к администратору или используйте имя пользователя.'))
            else:
                user = users.first()
                auth_code = AuthCode.issue_code(user, AuthCode.PURPOSE_PASSWORD_RESET)
                _send_auth_code_email(user, auth_code)
                request.session['password_reset_user_id'] = user.id
                messages.info(request, _('Код для смены пароля отправлен на вашу почту.'))
                return redirect('password_reset_verify_code')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'registration/password_reset_form.html', {'form': form})


def password_reset_verify_code(request):
    user_id = request.session.get('password_reset_user_id')
    if not user_id:
        messages.info(request, _('Сначала запросите код для сброса пароля.'))
        return redirect('password_reset')

    from django.contrib.auth.models import User
    user = User.objects.filter(id=user_id).first()
    if user is None:
        request.session.pop('password_reset_user_id', None)
        return redirect('password_reset')

    if request.method == 'POST':
        form = SetPasswordByCodeForm(request.POST, user=user)
        if form.is_valid():
            auth_code = _get_active_code(user, AuthCode.PURPOSE_PASSWORD_RESET, form.cleaned_data['code'])
            if auth_code is None:
                form.add_error('code', _('Код неверный или срок его действия истёк.'))
            else:
                auth_code.is_used = True
                auth_code.save(update_fields=['is_used'])
                user.set_password(form.cleaned_data['new_password1'])
                user.save(update_fields=['password'])
                request.session.pop('password_reset_user_id', None)
                messages.success(request, _('Пароль успешно изменён. Теперь вы можете войти.'))
                return redirect('login')
    else:
        form = SetPasswordByCodeForm(user=user)

    return render(request, 'registration/password_reset_verify_code.html', {'form': form, 'email': user.email})


def logout_and_register(request):
    """Log out then redirect to registration to avoid 405 and show register page."""
    auth_logout(request)
    messages.info(request, _('Вы вышли из системы. Пожалуйста, зарегистрируйтесь или войдите снова.'))
    return redirect('main:register')


def create_reservation(request):
    """Admin-only view to create new book reservations."""
    if not request.user.is_staff:
        messages.error(request, _('У вас нет доступа к этой функции.'))
        return redirect('main:index')

    if request.method == 'POST':
        student_name = (request.POST.get('student_name') or '').strip()
        group_name = (request.POST.get('group_name') or '').strip()
        teacher_name = (request.POST.get('teacher_name') or '').strip()
        quantity = request.POST.get('quantity')
        book_id = request.POST.get('book')
        reservation_datetime_str = (request.POST.get('reservation_datetime') or '').strip()
        expiration_date_str = (request.POST.get('expiration_date') or '').strip()
        notes = (request.POST.get('notes') or '').strip()

        try:
            quantity = int(quantity)
            if quantity <= 0:
                messages.error(request, _('Количество должно быть больше 0.'))
                return redirect('main:reservation_journal')

            if not student_name:
                messages.error(request, _('Укажите имя студента.'))
                return redirect('main:reservation_journal')

            if not group_name:
                messages.error(request, _('Укажите группу.'))
                return redirect('main:reservation_journal')

            default_reservation_datetime = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
            default_expiration_datetime = default_reservation_datetime + timedelta(days=7)

            reservation_datetime = parse_datetime(reservation_datetime_str) if reservation_datetime_str else default_reservation_datetime
            expiration_date = parse_datetime(expiration_date_str) if expiration_date_str else default_expiration_datetime

            if reservation_datetime is None or expiration_date is None:
                raise ValueError(_('Некорректный формат даты и времени.'))

            if timezone.is_naive(reservation_datetime):
                reservation_datetime = timezone.make_aware(reservation_datetime, timezone.get_current_timezone())
            if timezone.is_naive(expiration_date):
                expiration_date = timezone.make_aware(expiration_date, timezone.get_current_timezone())

            if expiration_date <= reservation_datetime:
                messages.error(request, _('Дата окончания должна быть позже даты бронирования.'))
                return redirect('main:reservation_journal')

            with transaction.atomic():
                book = Book_Info.objects.select_for_update().get(id=book_id)

                if quantity > book.available_copies:
                    messages.error(request, _('Недостаточно доступных копий. Доступно: %(available)s, запрошено: %(requested)s.') % {'available': book.available_copies, 'requested': quantity})
                    return redirect('main:reservation_journal')

                BookReservationJournal.objects.create(
                    book=book,
                    student_name=student_name,
                    group_name=group_name,
                    teacher_name=teacher_name,
                    quantity=quantity,
                    reservation_datetime=reservation_datetime,
                    expiration_date=expiration_date,
                    notes=notes,
                    created_by=request.user
                )

                book.available_copies = max(book.available_copies - quantity, 0)
                book.save(update_fields=['available_copies'])

            messages.success(request, _('Бронь для "%(student)s" на книгу "%(title)s" (%(quantity)s шт.) создана успешно!') % {'student': student_name, 'title': book.title, 'quantity': quantity})
            return redirect('main:reservation_journal')

        except Book_Info.DoesNotExist:
            messages.error(request, _('Выбранная книга не найдена.'))
        except ValueError as e:
            messages.error(request, _('Ошибка в формате данных: %(error)s') % {'error': e})
        except Exception as e:
            messages.error(request, _('Ошибка при создании брони: %(error)s') % {'error': e})

    return redirect('main:reservation_journal')


def is_admin(user):
    """Check if user is staff/admin"""
    return user.is_staff


@user_passes_test(is_admin)
def reservation_journal(request):
    """Admin-only page for reservation journal with book availability"""
    # Get all reservations
    reservations = BookReservationJournal.objects.all().select_related('book', 'created_by').order_by('-reservation_datetime')

    # Auto-update late reserved records to expired
    now = timezone.now()
    for reservation in reservations.filter(status='reserved', expiration_date__lt=now):
        reservation.status = 'expired'
        reservation.save()

    # Refresh queryset after status updates
    reservations = BookReservationJournal.objects.all().select_related('book', 'created_by').order_by('-reservation_datetime')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    group_filter = request.GET.get('group', '')
    book_filter = request.GET.get('book', '')
    
    # Apply filters
    if status_filter:
        reservations = reservations.filter(status=status_filter)
    if group_filter:
        reservations = reservations.filter(group_name__icontains=group_filter)
    if book_filter:
        reservations = reservations.filter(book__title__icontains=book_filter)
    
    # Pagination
    paginator = Paginator(reservations, 10)  # Show 10 reservations per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all books with availability info
    books_with_availability = Book_Info.objects.all().values(
        'id', 'title', 'author', 'isbn', 'total_copies', 'available_copies'
    ).order_by('title')
    
    # Get unique groups
    groups = BookReservationJournal.objects.values_list('group_name', flat=True).distinct().order_by('group_name')
    
    # Statistics
    total_reservations = BookReservationJournal.objects.count()
    active_reservations = BookReservationJournal.objects.filter(status='reserved').count()
    returned_reservations = BookReservationJournal.objects.filter(status__in=['returned', 'returned_late']).count()
    total_books = Book_Info.objects.count()
    total_available_copies = Book_Info.objects.aggregate(Sum('available_copies'))['available_copies__sum'] or 0
    
    default_reservation_datetime = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
    default_expiration_datetime = default_reservation_datetime + timedelta(days=7)

    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'reservations': page_obj,  # Keep for backward compatibility
        'books_with_availability': books_with_availability,
        'groups': groups,
        'status_filter': status_filter,
        'group_filter': group_filter,
        'book_filter': book_filter,
        'total_reservations': total_reservations,
        'active_reservations': active_reservations,
        'returned_reservations': returned_reservations,
        'total_books': total_books,
        'total_available_copies': total_available_copies,
        'reservation_default_value': default_reservation_datetime.strftime('%Y-%m-%dT%H:%M'),
        'expiration_default_value': default_expiration_datetime.strftime('%Y-%m-%dT%H:%M'),
    }
    
    return render(request, 'main/admin_reservation_journal.html', context)


@user_passes_test(is_admin)
def student_autocomplete(request):
    query = (request.GET.get('q') or '').strip()
    results = []

    if query:
        students = Student.objects.filter(full_name__icontains=query).order_by('full_name')[:10]
        results = [
            {
                'value': student.full_name,
                'label': f'{student.full_name} — {student.group_name or "Без группы"} (ID {student.student_id})',
                'group_name': student.group_name or '',
                'student_id': student.student_id,
            }
            for student in students
        ]

    return JsonResponse({'results': results})


@user_passes_test(is_admin)
def teacher_autocomplete(request):
    query = (request.GET.get('q') or '').strip()
    results = []

    if query:
        teacher_records = Teacher.objects.filter(
            full_name__icontains=query
        ).order_by('full_name').values_list('full_name', flat=True)

        student_teachers = Student.objects.filter(
            homeroom_teacher__icontains=query
        ).exclude(
            homeroom_teacher=''
        ).order_by('homeroom_teacher').values_list('homeroom_teacher', flat=True)

        journal_teachers = BookReservationJournal.objects.filter(
            teacher_name__icontains=query
        ).exclude(
            teacher_name=''
        ).order_by('teacher_name').values_list('teacher_name', flat=True)

        seen = set()
        for name in list(teacher_records[:20]) + list(student_teachers[:20]) + list(journal_teachers[:20]):
            normalized = (name or '').strip()
            if not normalized:
                continue

            dedupe_key = normalized.lower()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            results.append({'value': normalized, 'label': normalized})

            if len(results) >= 10:
                break

    return JsonResponse({'results': results})


@user_passes_test(is_admin)
def book_autocomplete(request):
    query = (request.GET.get('q') or '').strip()
    results = []

    if query:
        books = Book_Info.objects.filter(
            Q(title__icontains=query) | Q(author__icontains=query)
        ).order_by('title')[:10]
        results = [
            {
                'id': book.id,
                'value': book.title,
                'label': f'{book.title} — {book.author} (доступно: {book.available_copies})',
                'author': book.author,
                'available_copies': book.available_copies,
            }
            for book in books
        ]

    return JsonResponse({'results': results})


@user_passes_test(is_admin)
def return_book(request, reservation_id):
    """AJAX view to mark a book reservation as returned."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не разрешен.'})

    try:
        reservation = BookReservationJournal.objects.get(id=reservation_id)

        if reservation.status in ['returned', 'returned_late']:
            return JsonResponse({'success': False, 'error': 'Книга уже отмечена как возвращенная.'})

        payload = {}
        try:
            import json
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

        is_late_return = bool(payload.get('mark_overdue')) or reservation.status == 'expired' or reservation.is_expired

        reservation.status = 'returned_late' if is_late_return else 'returned'
        reservation.returned_date = timezone.now()
        reservation.save(update_fields=['status', 'returned_date'])

        reservation.book.available_copies = min(
            reservation.book.available_copies + reservation.quantity,
            reservation.book.total_copies,
        )
        reservation.book.save(update_fields=['available_copies'])

        returned_date = reservation.returned_date.strftime('%d.%m.%Y %H:%M')

        return JsonResponse({
            'success': True,
            'message': 'Книга отмечена как возвращенная.',
            'returned_date': returned_date,
            'status': reservation.status,
            'status_label': 'Возвращена, но просрочена' if reservation.status == 'returned_late' else 'Возвращена',
        })
        
    except BookReservationJournal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Бронирование не найдено.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Ошибка: {str(e)}'})