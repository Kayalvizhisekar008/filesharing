from django.urls import path
from . import views

app_name = 'student'

urlpatterns = [
    path('received/', views.received_files, name='received_files'),
    path('view/<int:file_id>/', views.view_file, name='view_file'),
]