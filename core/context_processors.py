from django.urls import reverse
from .models import DashboardStats

def menu_context(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'role'):
        return {}

    user_role = request.user.role.role_name.lower()
    
    from django.urls import reverse
    
    # Define menu structure
    menu_structure = {
        'teacher': [
            {
                'title': 'Dashboard',
                'url': '/dashboard',
                'icon': 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
            },
            {
                'title': 'Upload Files',
                'url': reverse('teacher:upload'),
                'icon': 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12',
            }
        ],
        'student': [
            {
                'title': 'Dashboard',
                'url': '/dashboard',
                'icon': 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
            },
            {
                'title': 'View Files',
                'url': '/student/received/',
                'icon': 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
            }
        ],
        'admin': [
            {
                'title': 'Dashboard',
                'url': '/dashboard',
                'icon': 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
            },
            {
                'title': 'Manage Batch Codes',
                'url': reverse('core:manage_batchcodes'),
                'icon': 'M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z',
            },
            {
                'title': 'Upload Files',
                'url': '/teacher/upload/',
                'icon': 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12',
            },
            {
                'title': 'View Files',
                'url': '/student/received/',
                'icon': 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
            },
            
        ]
    }
    
    # Get the user's menu items (only their own role)
    user_menu = menu_structure.get(user_role, [])

    # Get stats for the context
    stats = DashboardStats.objects.first() or DashboardStats.objects.create()

    # Get notifications for authenticated users
    from .models import Notification
    notifications = []
    unread_count = 0
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    # Prepare the context
    context = {
        'menu_items': user_menu,
        'show_teacher_menu': user_role == 'teacher',
        'show_student_menu': user_role == 'student',
        'show_admin_menu': user_role == 'admin',
        'current_url': request.path,
        'user_role': user_role,
        'stats': stats,
        'notifications': notifications,
        'unread_notification_count': unread_count,
    }

    return context