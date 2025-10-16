# core/urls.py (updated full code)

from django.urls import path
from core.views import (
    update_batch_credentials, update_student_credentials,
    login_view, signup_view, forgot_password, reset_password, home, 
    logout_view, dashboard_stats, manage_batchcodes, add_batchcode, 
    delete_batchcode, download_format, bulk_upload_students,
    add_individual_student, transfer_student, get_students_by_batch,
    delete_student, download_bulk_files, get_batch_summary,
    mark_notifications_read, delete_notification
)

app_name = 'core'  # Add namespace

urlpatterns = [
    path('download-bulk-files/', download_bulk_files, name='download_bulk_files'),
    path('', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('reset-password/', reset_password, name='reset_password'),
    path('dashboard/', home, name='dashboard'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/stats/', dashboard_stats, name='dashboard_stats'),
    path('batchcodes/', manage_batchcodes, name='manage_batchcodes'),
    path('batchcodes/add/', add_batchcode, name='add_batchcode'),
    path('batchcodes/delete/<int:batch_id>/', delete_batchcode, name='delete_batchcode'),
    path('download_format/<str:format_type>/', download_format, name='download_format'),
    path('bulk_upload_students/', bulk_upload_students, name='bulk_upload_students'),
    path('add_individual_student/', add_individual_student, name='add_individual_student'),
    path('transfer_student/', transfer_student, name='transfer_student'),
    path('get_students_by_batch/', get_students_by_batch, name='get_students_by_batch'),
    path('delete_student/<int:student_id>/', delete_student, name='delete_student'),
    path('batch-summary/', get_batch_summary, name='batch_summary'),
    path('update-batch-credentials/', update_batch_credentials, name='update_batch_credentials'),
    path('update-student-credentials/<int:student_id>/', update_student_credentials, name='update_student_credentials'),
    path('mark-notifications-read/', mark_notifications_read, name='mark_notifications_read'),
    path('delete-notification/<int:notification_id>/', delete_notification, name='delete_notification'),
]