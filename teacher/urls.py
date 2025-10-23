from django.urls import path
from . import views

app_name = 'teacher'  # Matches the /teacher/ prefix in the project URLs

urlpatterns = [
    path('upload/', views.share_file, name='upload'),
    path('get-students-by-batch/', views.get_students_by_batch, name='get_students_by_batch'),
    path('get_batch_students/<int:batch_id>/', views.get_batch_students, name='get_batch_students'),
    # path('manage-students/', views.manage_students, name='manage_students'),
    # path('remove-student/', views.remove_student, name='remove_student'),
]
