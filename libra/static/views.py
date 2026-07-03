from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Category, Book_Info, BookLoan, Reservation, School_Type, Specialization, BookReservationJournal
from django.db import transaction
from django.db.models import Q, F, Sum
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.views import LogoutView, LoginView
from django.contrib import messages 
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.core.mail import send_mail
from django.conf import settings
from .forms import UserEditForm, ProfileEditForm, UserRegisterForm
from django.core.paginator import Paginator
from .forms import UserEditForm, ProfileEditForm



# Create your views here.

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
    
    return render(request, 'main/product/list.html', {
        'category': category,
        'categories': categories,
        'school_types': school_types,
        'specializations': specializations,
        'books': books,
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
    saved_books = profile.saved_books.all()
    
    context = {
        'user': user,
        'profile': profile,
        'saved_books': saved_books,
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
            profile_form.save()
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
    """Registration page."""
    if request.user.is_authenticated:
        return redirect('main:index')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            if user.email:
                send_mail(
                    'Добро пожаловать в библиотеку',
                    f'Здравствуйте, {user.username}!\n\nСпасибо за регистрацию в College Library. Ваш логин: {user.username}.\n\nЕсли вы забудете пароль, вы можете восстановить его через эту почту.',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            auth_login(request, user)
            messages.success(request, _('Регистрация прошла успешно. Вы вошли в систему.'))
            return redirect('main:index')
        else:
            messages.error(request, _('Пожалуйста, исправьте ошибки в форме регистрации.'))
    else:
        form = UserRegisterForm()

    return render(request, 'registration/register.html', {'form': form})


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
    returned_reservations = BookReservationJournal.objects.filter(status='returned').count()
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
def return_book(request, reservation_id):
    """AJAX view to mark a book reservation as returned."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Метод не разрешен.'})
    
    try:
        reservation = BookReservationJournal.objects.get(id=reservation_id)
        
        if reservation.status == 'returned':
            return JsonResponse({'success': False, 'error': 'Книга уже отмечена как возвращенная.'})
        
        # Mark as returned
        reservation.status = 'returned'
        reservation.returned_date = timezone.now()
        reservation.save()

        # Return reserved copies back to general availability
        if reservation.book.available_copies + reservation.quantity <= reservation.book.total_copies:
            reservation.book.available_copies += reservation.quantity
            reservation.book.save()
        
        # Format returned date for display
        returned_date = reservation.returned_date.strftime('%d.%m.%Y %H:%M')
        
        return JsonResponse({
            'success': True,
            'message': 'Книга отмечена как возвращенная.',
            'returned_date': returned_date
        })
        
    except BookReservationJournal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Бронирование не найдено.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Ошибка: {str(e)}'})