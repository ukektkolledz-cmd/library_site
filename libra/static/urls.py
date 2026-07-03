from django.urls import path
from . import views

app_name = 'main'

urlpatterns = [
    path('', views.main_page, name='main_page'),
    path('index/', views.index, name='index'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/history/', views.loan_history, name='loan_history'),
    path('book/<int:book_id>/', views.book_detail, name='book_detail'),
    path('book/<int:book_id>/reserve/', views.reserve_book, name='reserve_book'),
    path('book/<int:book_id>/save/', views.toggle_saved_book, name='toggle_saved_book'),
    path('category/<slug:category_slug>/', views.index, name='book_list_by_category'),
    path('reservation/<int:reservation_id>/cancel/', views.cancel_reservation, name='cancel_reservation'),
    path('admin-journal/', views.reservation_journal, name='reservation_journal'),
    path('admin-journal/create/', views.create_reservation, name='create_reservation'),
    path('return-book/<int:reservation_id>/', views.return_book, name='return_book'),
    path('accounts/register/', views.register, name='register'),
]
