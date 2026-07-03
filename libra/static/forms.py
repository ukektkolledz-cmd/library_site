# main/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from .models import Profile, Student

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_('Email'))
    student_id = forms.CharField(required=True, label=_('Номер студенческого билета'))

    class Meta:
        model = User
        fields = ['username', 'email', 'student_id', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_('Пользователь с таким email уже существует.'))
        return email

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if not student_id:
            raise forms.ValidationError(_('Пожалуйста, укажите номер студенческого билета.'))
        if not Student.objects.filter(student_id=student_id).exists():
            raise forms.ValidationError(_('Студенческий ID не найден в базе. Обратитесь к администрации.'))
        if Profile.objects.filter(student_id=student_id).exists():
            raise forms.ValidationError(_('Этот студенческий ID уже зарегистрирован.'))
        return student_id

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        student_id = self.cleaned_data.get('student_id')
        student = Student.objects.filter(student_id=student_id).first()
        if student:
            full_name = student.full_name.strip()
            parts = full_name.split()
            if len(parts) == 1:
                user.first_name = parts[0]
            elif len(parts) == 2:
                user.last_name, user.first_name = parts
            else:
                user.last_name = parts[0]
                user.first_name = parts[1]
        if commit:
            user.save()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.student_id = student_id
            if student:
                profile.group_name = student.group_name or profile.group_name
            profile.save()
        return user

class UserEditForm(forms.ModelForm):
    """
    Форма для редактирования данных пользователя
    """
    first_name = forms.CharField(max_length=150, required=False, label=_('Имя'))
    last_name = forms.CharField(max_length=150, required=False, label=_('Фамилия'))
    email = forms.EmailField(required=True, label=_('Email'))
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class ProfileEditForm(forms.ModelForm):
    """
    Форма для редактирования профиля пользователя
    """
    class Meta:
        model = Profile
        fields = [
            'phone', 'address', 'birth_date', 'student_id', 
            'group_name', 'bio', 'telegram', 'instagram', 'avatar'
        ]
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+7 (XXX) XXX-XX-XX'}),
            'student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '№ студенческого билета'}),
            'group_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: ИС-21'}),
            'telegram': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '@username'}),
            'instagram': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '@username'}),
        }
        labels = {
            'phone': _('Телефон'),
            'address': _('Адрес'),
            'birth_date': _('Дата рождения'),
            'student_id': _('Номер студенческого билета'),
            'group_name': _('Группа'),
            'bio': _('О себе'),
            'telegram': _('Telegram'),
            'instagram': _('Instagram'),
            'avatar': _('Фото профиля'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'avatar':
                self.fields[field].widget.attrs.update({'class': 'form-control'})