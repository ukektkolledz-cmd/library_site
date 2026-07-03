from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import Category, Book_Info, School_Type, Specialization, BookReservationJournal, Reservation, Student

# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(School_Type)
class SchoolTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Book_Info)
class BookInfoAdmin(admin.ModelAdmin):
    list_filter = ['available', 'created', 'updated', 'category', 'school_type', 'specialization', 'language', 'subject_area']
    list_editable = ['available']
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ['title', 'author', 'isbn']
    list_display = ['title', 'author', 'available', 'language', 'school_type', 'specialization', 'subject_area', 'pdf_file']
    fields = ['title', 'slug', 'author', 'description', 'isbn', 'publication_date', 'available', 'total_copies', 'available_copies', 'category', 'school_type', 'specialization', 'language', 'subject_area', 'image', 'pdf_file']


class BookReservationJournalForm(forms.ModelForm):
    person_type = forms.ChoiceField(
        choices=BookReservationJournal.PERSON_TYPE_CHOICES,
        widget=forms.RadioSelect,
        label=_('Тип клиента'),
        initial='student'
    )

    class Meta:
        model = BookReservationJournal
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Requiredness depends on person_type; enforce in clean().
        self.fields['student_name'].required = False
        self.fields['group_name'].required = False
        self.fields['teacher_name'].required = False

    def clean(self):
        cleaned_data = super().clean()
        person_type = cleaned_data.get('person_type')

        if person_type == 'teacher':
            cleaned_data['student_name'] = ''
            cleaned_data['group_name'] = ''
            if not cleaned_data.get('teacher_name'):
                self.add_error('teacher_name', _('Введите имя преподавателя'))
        else:
            cleaned_data['teacher_name'] = ''
            if not cleaned_data.get('student_name'):
                self.add_error('student_name', _('Введите имя студента'))
            if not cleaned_data.get('group_name'):
                self.add_error('group_name', _('Введите группу'))

        return cleaned_data


@admin.register(BookReservationJournal)
class BookReservationJournalAdmin(admin.ModelAdmin):
    form = BookReservationJournalForm
    """
    Admin interface for book reservation journal
    Only admins can access and modify this
    """
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete
        return request.user.is_superuser
    
    def has_add_permission(self, request):
        # Only admins can add
        return request.user.is_staff
    
    def has_change_permission(self, request, obj=None):
        # Only admins can change
        return request.user.is_staff
    
    # Mark book as returned action
    def mark_as_returned(self, request, queryset):
        updated = queryset.filter(status='reserved').update(
            status='returned',
            returned_date=timezone.now()
        )
        self.message_user(request, _('%(count)d книг(и) отмечены как возвращённые') % {'count': updated})
    mark_as_returned.short_description = _('Отметить как возвращённую')
    
    actions = [mark_as_returned]
    
    # Display status with color coding
    def status_display(self, obj):
        if obj.status == 'reserved':
            color = 'orange'
            label = _('Зарезервирована')
        else:
            color = 'green'
            label = _('Возвращена')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            label,
        )
    status_display.short_description = _('Статус')
    
    # Display expiration status
    def expiration_status(self, obj):
        if obj.status == 'returned':
            return format_html('<span style="color: green;">✓ {}</span>', _('Возвращена'))
        if obj.is_expired:
            return format_html('<span style="color: red; font-weight: bold;">⚠ {}</span>', _('Просрочена'))
        return format_html('<span style="color: blue;">{}</span>', _('Активна'))
    expiration_status.short_description = _('Статус срока')
    
    list_display = [
        'id',
        'student_name',
        'group_name',
        'book',
        'reservation_datetime',
        'expiration_date',
        'status_display',
        'expiration_status',
    ]
    
    list_filter = [
        'status',
        'reservation_datetime',
        'group_name',
        'book__category',
    ]
    
    search_fields = [
        'student_name',
        'group_name',
        'book__title',
        'notes',
    ]
    
    readonly_fields = [
        'created_by',
        'reservation_datetime',
        'returned_date',
        'is_expired',
        'status_display',
    ]
    
    fieldsets = (
        (_('Тип клиента'), {
            'fields': ('person_type',)
        }),
        (_('Информация о студенте'), {
            'fields': ('student_name', 'group_name')
        }),
        (_('Информация о преподавателе'), {
            'fields': ('teacher_name',)
        }),
        (_('Информация о бронировании'), {
            'fields': (
                'book',
                'reservation_datetime',
                'expiration_date',
                'returned_date',
            )
        }),
        (_('Статус'), {
            'fields': ('status', 'status_display', 'is_expired')
        }),
        (_('Дополнительное'), {
            'fields': ('notes', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    class Media:
        js = ('js/bookreservationjournal_admin.js',)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Non-superusers only see their own entries, superusers see all
        if not request.user.is_superuser:
            queryset = queryset.filter(created_by=request.user)
        return queryset
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by on new entries
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'full_name', 'group_name', 'course', 'year', 'specialization', 'language', 'homeroom_teacher']
    search_fields = ['student_id', 'full_name', 'group_name', 'course', 'year', 'specialization', 'language', 'homeroom_teacher']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'book', 'reservation_date', 'status']
    list_filter = ['status', 'reservation_date']
    search_fields = ['user__username', 'book__title']
    readonly_fields = ['reservation_date', 'user']