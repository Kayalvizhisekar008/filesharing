import os
import json
import time
import logging
from datetime import date
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.http import FileResponse, HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.static import serve
from django.conf import settings
from teacher.models import Upload, Batch
from .models import Student
from .decorators import prevent_pdf_download

# Configure logging
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('student.views')

if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    file_handler = logging.FileHandler('debug.log')
    file_handler.setFormatter(log_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.setLevel(logging.DEBUG)

@login_required
def view_file(request, file_id):
    """View file in browser without download option"""
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = HttpResponse()
        response['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With, Range'
        response['Access-Control-Max-Age'] = '86400'  # 24 hours
        return response
        
    logger.info(f"Attempting to serve file ID: {file_id} for user: {request.user.username}")

    user_role = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None
    
    if user_role not in ["Student", "Admin"]:
        logger.warning(f"Access denied: User {request.user.username} has role {user_role}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'permission_denied',
                'message': 'You do not have permission to access files.'
            }, status=403)
        messages.error(request, "You do not have permission to access this file.")
        return redirect('dashboard')
        
    try:
        file = Upload.objects.get(id=file_id, is_active=True)
        current_date = timezone.now().date()
        
        logger.info(f"""
        File Access Check:
        File: {file.topic} (ID: {file.id})
        Active: {file.is_active}
        Date Range: {file.from_date} to {file.to_date}
        Current Date: {current_date}
        """)
        
        # Check only to_date, allowing early access before from_date
        if current_date > file.to_date:
            logger.warning(f"File {file.id} has expired: {current_date} is after {file.to_date}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'date_range',
                    'message': f'This file is no longer available (expired on {file.to_date}).'
                }, status=403)
            messages.error(request, f"This file is no longer available (expired on {file.to_date}).")
            return redirect('student:received_files')

        # Check if the file exists on the server
        if not os.path.exists(file.file.path):
            logger.error(f"File not found on server: {file.file.path}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'file_not_found',
                    'message': 'The requested PDF file was not found on the server.'
                }, status=404)
            messages.error(request, "The requested PDF file was not found.")
            return redirect('student:received_files')

        # Check if student has access to this file
        if user_role == "Student":
            try:
                student = Student.objects.get(user=request.user)
                logger.info(f"Student: {student.name}, Batch: {student.batch}")
                
                # Check if file is accessible by student
                if not file.is_accessible_by_student(student):
                    logger.warning(f"Access denied for student {student.student_code} to file {file.id}")
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'error': 'access_denied',
                            'message': 'You do not have permission to access this file.'
                        }, status=403)
                    messages.error(request, "You do not have permission to access this file.")
                    return redirect('student:received_files')
                    
            except Student.DoesNotExist:
                logger.error(f"Student profile not found for user: {request.user.username}")
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': 'student_not_found',
                        'message': 'Student profile not found.'
                    }, status=403)
                messages.error(request, "Your account is not properly configured. Please contact administrator.")
                return redirect('student:received_files')
                
        # Create a secure file response with strict no-download headers
        response = FileResponse(open(file.file.path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = 'inline; filename="view.pdf"'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        response['Content-Security-Policy'] = "frame-ancestors 'self'"
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        response['Cross-Origin-Opener-Policy'] = 'same-origin'
        response['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
        response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, X-Requested-With, Range'
        
        logger.info(f"Successfully serving file ID: {file_id} to user: {request.user.username}")
        return response
        
    except Upload.DoesNotExist:
        logger.error(f"File ID {file_id} does not exist or is not active")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'file_not_found',
                'message': 'The requested file does not exist or is not active.'
            }, status=404)
        messages.error(request, "File not found or access denied.")
        return redirect('student:received_files')
    except Exception as e:
        logger.error(f"Error serving file ID {file_id}: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'server_error',
                'message': f"An error occurred while accessing the file: {str(e)}"
            }, status=500)
        messages.error(request, "An error occurred while accessing the file.")
        return redirect('student:received_files')

@login_required
def received_files(request):
    logger.info("\n=== Starting received_files view ===")
    
    # Check if user is authenticated
    if not request.user.is_authenticated:
        logger.error("User is not authenticated")
        messages.error(request, "Please log in to access this page.")
        return redirect('core:login')
    
    # Debug user information
    logger.info(f"""
    User Information:
    Username: {request.user.username}
    Is authenticated: {request.user.is_authenticated}
    Has role: {hasattr(request.user, 'role')}
    Role: {request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else 'No role'}
    """)
    
    # Check if user has a role
    if not hasattr(request.user, 'role') or not request.user.role:
        logger.error(f"User {request.user.username} has no role assigned")
        messages.error(request, "Your account is not properly configured. Please contact administrator.")
        return redirect('dashboard')
    
    user_role = request.user.role.role_name
    logger.info(f"User {request.user.username} has role: {user_role}")
    
    # Validate student role
    if user_role not in ["Student", "Admin"]:
        logger.warning(f"Invalid role access attempt: {user_role} by user {request.user.username}")
        messages.error(request, "You must be a student or admin to access this page.")
        return redirect('dashboard')
        
    current_date = timezone.now().date()
    logger.info(f"Current date: {current_date}")
    
    files = []
    student = None
    try:
        if user_role == "Student":
            # Get or create student profile with transaction
            with transaction.atomic():
                student, created = Student.objects.get_or_create(
                    user=request.user,
                    defaults={
                        'student_code': getattr(request.user, 'batchcode', None) or f'STU{request.user.id}',
                        'name': request.user.get_full_name() or request.user.username
                    }
                )
                if created:
                    logger.info(f"Created new student profile for {request.user.username}")
            logger.info(f"Using student profile: {student.name} ({student.student_code})")

            # Verify student's batch assignment
            logger.info(f"""
            Student Batch Information:
            Student: {student.name} ({student.student_code})
            Has batch: {student.batch is not None}
            Batch details: {student.batch.batch_code if student.batch else 'No batch'}
            """)
            
            if not student.batch:
                logger.error(f"Student {student.student_code} has no batch assigned")
                messages.warning(request, "You are not assigned to any batch. Please contact your teacher.")
                return render(request, "student/received.html", {
                    'files_by_subject': {},
                    'files_data_json': '{}',
                    'user_role': user_role,
                    'error_message': 'No batch assigned'
                })
            
            logger.info(f"Checking files for student {student.student_code} in batch {student.batch.batch_code}")
            
            # Get files accessible to this student with current date check
            files = Upload.objects.select_related('teacher', 'batch').filter(
                Q(batch=student.batch) | Q(shared_with=student),
                is_active=True,
                to_date__gte=current_date  # Only check if the file hasn't expired yet
            ).distinct().order_by('-uploaded_at')
            
            logger.info(f"Files query: {files.query}")
            logger.info(f"Total files retrieved: {files.count()}")
            
            for file in files:
                logger.info(f"""
                Retrieved file:
                ID: {file.id}
                Topic: {file.topic}
                Subject: {file.subject}
                Batch: {file.batch.batch_code if file.batch else 'No batch'}
                Teacher: {file.teacher}
                Active: {file.is_active}
                From date: {file.from_date}
                To date: {file.to_date}
                File exists: {os.path.exists(file.file.path) if file.file else 'No file'}
                """)
        else:  # Admin
            logger.info("Admin user - fetching all files")
            files = Upload.objects.filter(is_active=True).select_related('teacher', 'batch')

        # Prepare context for no files case
        if user_role == "Admin":
            no_files_context = {
                'files_by_subject': {},
                'files_data_json': '{}',
                'user_role': user_role,
                'no_files_message': "No active files found in the system.",
                'no_files_reasons': [
                    "No files have been uploaded yet",
                    "Files are not active or have been archived"
                ]
            }
        else:
            no_files_context = {
                'files_by_subject': {},
                'files_data_json': '{}',
                'user_role': user_role,
                'no_files_message': "No files are currently shared with you. This could be because:",
                'no_files_reasons': [
                    "No files have been shared with your batch yet",
                    "Shared files are not within their valid date range",
                    "Files are not active or have been archived"
                ]
            }

        if not files:
            if user_role == "Student":
                batch_info = f" in batch {student.batch.batch_code}" if student and student.batch else ""
                logger.warning(f"No accessible files found for student {student.student_code}{batch_info}")
            else:
                logger.warning("No active files found for admin")
            return render(request, "student/received.html", no_files_context)

        # Get unique subjects from existing files, filtering out None
        subjects = {file.subject for file in files if file.subject is not None}
        unique_subjects = sorted(list(subjects))
        files_by_subject = {subject: [] for subject in unique_subjects}
        
        # Process each file
        for file in files:
            try:
                # Check file availability and existence
                file_exists = os.path.exists(file.file.path) if file.file else False
                is_available = current_date <= file.to_date  # File is available until it expires
                
                # Prepare file data
                file_data = {
                    'id': file.id,
                    'pdf_url': f"/student/view/{file.id}/" if file.file and file_exists else None,
                    'title': f"{file.topic} - {file.sub_topic}" if file.sub_topic else file.topic,
                    'teacher': (file.teacher.get_full_name() or file.teacher.username) if file.teacher else 'Unknown Teacher',
                    'topic': file.topic,
                    'subtopic': file.sub_topic,
                    'batch': file.batch.batch_code if file.batch else 'General',
                    'available': {
                        'is_available': is_available,
                        'status': 'Available' if is_available else 'Not Available',
                        'from': file.from_date.strftime("%Y-%m-%d"),
                        'to': file.to_date.strftime("%Y-%m-%d")
                    },
                    'file_exists': file_exists
                }
                
                # Add file to appropriate subject list, skip if subject is None
                if file.subject:
                    files_by_subject[file.subject].append(file_data)
                    logger.info(f"Added file {file.id} to subject {file.subject} - Available: {is_available}, Exists: {file_exists}")
                
            except Exception as e:
                logger.error(f"Error processing file {file.id}: {str(e)}")
                continue

        # Remove subjects with no files
        files_by_subject = {k: v for k, v in files_by_subject.items() if v}
        
        if not files_by_subject:
            logger.warning("No files could be processed successfully")
            return render(request, "student/received.html", no_files_context)

        # Convert to JSON for template
        files_data_json = json.dumps(files_by_subject)
        files_data_hash = str(hash(files_data_json))

        logger.info(f"Rendering template with {len(files)} files across {len(files_by_subject)} subjects")

        # Prepare final response with cache control headers
        response = render(request, "student/received.html", {
            'files_by_subject': files_by_subject,
            'files_data_json': files_data_json,
            'user_role': user_role,
            'timestamp': timezone.now().timestamp(),
            'files_data_hash': files_data_hash,
        })
        
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response
        
    except Exception as e:
        logger.error(f"Error in received_files view: {str(e)}", exc_info=True)
        messages.error(request, f"Error loading files: {str(e)}")
        return render(request, "student/received.html", {
            'files_by_subject': {},
            'files_data_json': '{}',
            'user_role': user_role,
        })