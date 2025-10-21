# teacher/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.utils import timezone
from student.models import Student
from .models import Batch, Upload
from core.models import Role
import os
import logging
import uuid
from datetime import datetime

# Get the custom user model
User = get_user_model()

# Set up logging
logger = logging.getLogger(__name__)

@login_required
def share_file(request):
    if not request.user.is_authenticated:
        messages.error(request, "Please log in to share files.")
        return redirect('core:login')
    
    if not hasattr(request.user, 'role') or not request.user.role:
        messages.error(request, "Your account is not properly configured. Please contact administrator.")
        return redirect('dashboard')
    
    user_role = request.user.role.role_name
    if user_role not in ["Teacher", "Admin"]:
        messages.error(request, "You do not have permission to share files.")
        return redirect('core:dashboard')
        
    logger.info(f"User {request.user.username} (role: {user_role}) accessing share_file view")

    if request.method == 'POST':
        teacher_name = request.POST.get('teacherName', '').strip()
        teacher_code = request.POST.get('teacherCode', '').strip()
        subject = request.POST.get('subject', '').strip()
        topic = request.POST.get('topic', '').strip()
        sub_topic = request.POST.get('subTopic', '').strip()
        batch_code = request.POST.get('batchCode', '').strip()
        from_date = request.POST.get('fromDate', '').strip()
        to_date = request.POST.get('toDate', '').strip()
        student_ids = request.POST.getlist('batchStudents')
        student_ids = ['all' if x == '0' else x for x in student_ids]
        uploaded_file = request.FILES.get('file')

        logger.debug(
            f"Received POST data: teacher_name={teacher_name}, teacher_code={teacher_code}, "
            f"subject={subject}, topic={topic}, batch_code={batch_code}, student_ids={student_ids}, "
            f"from_date={from_date}, to_date={to_date}"
        )

        # Server-side validation
        required_fields = {
            'Teacher Name': teacher_name,
            'Teacher Code': teacher_code,
            'Subject': subject,
            'Topic': topic,
            'Batch Code': batch_code,
            'File': uploaded_file
        }
        missing_fields = [field for field, value in required_fields.items() if not value]
        if missing_fields:
            messages.error(request, f'Please fill in all required fields: {", ".join(missing_fields)}.')
            return redirect('teacher:upload')

        # Validate file extension and size
        allowed_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg']
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        max_size = 1024 * 1024 * 1024  # 1GB in bytes

        logger.debug(f"Validating file: {uploaded_file.name} (size: {uploaded_file.size}, extension: {file_extension})")

        if file_extension.lower() not in [ext.lower() for ext in allowed_extensions]:
            logger.warning(f"Invalid file extension: {file_extension}")
            messages.error(request, 'Invalid file format. Allowed formats: PDF, DOC, DOCX, JPG, JPEG.')
            return redirect('teacher:upload')

        if uploaded_file.size > max_size:
            messages.error(request, 'File size exceeds 1GB limit.')
            return redirect('teacher:upload')

        # Validate dates
        try:
            from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date() if from_date else None
            to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date() if to_date else None
            if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
                messages.error(request, 'From date cannot be later than To date.')
                return redirect('teacher:upload')
        except ValueError:
            messages.error(request, 'Invalid date format. Use YYYY-MM-DD.')
            return redirect('teacher:upload')

        try:
            # Get or create the default Student role
            student_role, _ = Role.objects.get_or_create(role_name='Student')

            # Get or create batch
            try:
                batch = Batch.objects.get(batch_code=batch_code)
                logger.info(f"Found existing batch: {batch_code}")
            except Batch.DoesNotExist:
                batch = Batch.objects.create(batch_code=batch_code)
                logger.info(f"Created new batch: {batch_code}")
            
            # Check if batch has students
            student_count = Student.objects.filter(batch=batch).count()
            logger.info(f"Batch {batch_code} has {student_count} students")
            
            if student_count == 0:
                messages.warning(request, f"Batch {batch_code} has no students. Please add students to this batch first.")
                return redirect('teacher:upload')

            # Create Upload instance
            logger.info(f"Attempting to create Upload instance with:\n" +
                      f"Teacher: {request.user.get_full_name()} (ID: {request.user.id})\n" +
                      f"Batch: {batch_code}\n" +
                      f"Topic: {topic}")

            upload = Upload(
                teacher=request.user,
                teacher_code=teacher_code,
                subject=subject,
                topic=topic,
                sub_topic=sub_topic,
                batch=batch,
                file=uploaded_file,
                from_date=from_date_obj,
                to_date=to_date_obj,
                is_active=True
            )

            try:
                upload.save()
                logger.info(f"Successfully saved upload with ID: {upload.id}")
                
                # Verify file was saved
                if upload.file:
                    logger.info(f"File saved at: {upload.file.path}")
                else:
                    raise Exception("File was not saved correctly")
                    
            except Exception as e:
                logger.error(f"Error creating upload: {str(e)}", exc_info=True)
                messages.error(request, f"Error uploading file: {str(e)}")
                return redirect('teacher:upload')
            
            # Handle student selection
            if not student_ids:
                messages.error(request, 'No students selected.')
                if upload.id:
                    upload.delete()
                return redirect('teacher:upload')

            try:
                logger.info(f"Processing student selection. Student IDs: {student_ids}")
                
                if student_count == 0:
                    logger.warning(f"Batch {batch_code} has no students!")
                    messages.warning(request, f"Warning: Batch {batch_code} currently has no students.")
                    if upload.id:
                        upload.delete()
                    return redirect('teacher:upload')
                
                if 'all' in student_ids:
                    # For "all students" option, don't add any specific students to shared_with
                    upload.shared_with.clear()
                    logger.info(f"Sharing file with ALL students in batch {batch_code}")
                    success_message = f'File shared successfully to all {student_count} students in batch {batch_code}.'
                    logger.info(f"Batch {batch_code} has {student_count} students")
                else:
                    # Get the selected students
                    students_to_add = Student.objects.filter(student_code__in=student_ids, batch=batch)
                    if not students_to_add.exists():
                        messages.error(request, 'No valid students selected.')
                        upload.delete()
                        return redirect('teacher:upload')
                    
                    # Set specific students
                    upload.shared_with.set(students_to_add)
                    student_names = ", ".join([student.name for student in students_to_add])
                    success_message = f'File shared successfully to {students_to_add.count()} selected students in batch {batch_code}.'
                    logger.info(f"Sharing file with {students_to_add.count()} students: {[s.student_code for s in students_to_add]}")

            except Exception as e:
                logger.error(f"Error sharing file: {str(e)}", exc_info=True)
                if upload.id:
                    upload.delete()
                messages.error(request, 'Error sharing file. Please try again.')
                return redirect('teacher:upload')

            logger.info(f"Successfully shared file:\n" +
                      f"File: {uploaded_file.name}\n" +
                      f"Subject: {subject}\n" +
                      f"Topic: {topic}\n" +
                      f"Batch: {batch_code}\n" +
                      f"Teacher: {teacher_name} ({teacher_code})")
                      
            messages.success(request, success_message)
            return redirect('teacher:upload')

        except Exception as e:
            logger.error(f"Unexpected error in share_file: {str(e)}", exc_info=True)
            messages.error(request, 'An unexpected error occurred. Please try again.')
            return redirect('teacher:upload')

    # GET request: Render the form
    batches = Batch.objects.all()

    if not batches:
        messages.info(request, 'No batches available. Please create a batch first.')

    context = {
        'batches': batches
    }
    return render(request, 'teacher/upload.html', context)

@login_required
def get_students_by_batch(request):
    batch_code = request.GET.get('batchCode', '').strip()
    if not batch_code:
        return JsonResponse({'error': 'Batch code is required'}, status=400)

    logger.info(f"Fetching students for batch_code: {batch_code}")

    try:
        # Get batch
        try:
            batch = Batch.objects.get(batch_code=batch_code)
            logger.info(f"Found batch: {batch_code}")
        except Batch.DoesNotExist:
            logger.warning(f"Batch not found: {batch_code}")
            return JsonResponse({
                'students': [],
                'message': f'Batch "{batch_code}" does not exist. Please create it first.'
            })

        # Get students in this batch
        students = Student.objects.filter(batch=batch).select_related('user').order_by('name')
        
        student_data = []
        student_count = students.count()
        logger.info(f"Found {student_count} students in batch {batch_code}")
        
        if not students.exists():
            logger.info(f"No students found in batch {batch_code}")
            return JsonResponse({
                'students': [],
                'message': f'No students found in batch "{batch_code}". Use the Manage Students page to add students to this batch.'
            })
        
        # Collect student data
        for student in students:
            try:
                student_info = {
                    'id': student.id,
                    'name': student.name,
                    'student_code': student.student_code,
                    'email': student.user.email if student.user else '',
                    'phone': getattr(student.user, 'phone_number', '') if student.user else '',
                    'batch_code': batch_code,
                }
                student_data.append(student_info)
                logger.debug(f"Added student: {student.name} ({student.student_code})")
            except Exception as e:
                logger.error(f"Error getting data for student {student.student_code}: {str(e)}")
        
        return JsonResponse({
            'students': student_data,
            'total_students': len(student_data),
            'batch_code': batch_code,
            'message': f"Successfully retrieved {len(student_data)} students from batch {batch_code}"
        })

    except Exception as e:
        logger.error(f"Unexpected error in get_students_by_batch: {str(e)}", exc_info=True)
        return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)

@login_required
def manage_students(request):
    user_role = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None
    if user_role not in ["Teacher", "Admin"]:
        messages.error(request, "You do not have permission to manage students.")
        return redirect('core:dashboard')

    if request.method == 'POST':
        batch_code = request.POST.get('batchCode')
        student_names = request.POST.getlist('student_names[]')
        student_emails = request.POST.getlist('student_emails[]')
        student_phones = request.POST.getlist('student_phones[]')

        if not batch_code:
            messages.error(request, "Batch code is required.")
            return redirect('teacher:manage_students')

        try:
            # Get or create the Student role
            student_role, _ = Role.objects.get_or_create(role_name='Student')
            
            # Get or create the batch
            batch, created = Batch.objects.get_or_create(batch_code=batch_code)
            if created:
                logger.info(f"Created new batch: {batch_code}")
            else:
                logger.info(f"Using existing batch: {batch_code}")
            
            added_count = 0
            # Process each student
            for name, email, phone in zip(student_names, student_emails, student_phones):
                if not all([name.strip(), email.strip(), phone.strip()]):
                    continue

                student_code = f"{batch_code}_{uuid.uuid4().hex[:6]}"
                logger.info(f"Creating/updating student {name} with code {student_code}")
                
                # Create user account
                user_data = {
                    'first_name': name.split()[0] if ' ' in name else name,
                    'last_name': name.split()[-1] if len(name.split()) > 1 else '',
                    'email': email,
                    'phone_number': phone,
                    'role': student_role,
                    'is_active': True
                }
                
                # Try to create new user, if email exists, update the user
                try:
                    user = User.objects.get(email=email)
                    for key, value in user_data.items():
                        setattr(user, key, value)
                    user.save()
                    logger.info(f"Updated existing user: {user.email}")
                except User.DoesNotExist:
                    user = User.objects.create_user(
                        username=student_code,
                        password='student123',  # Default password
                        **user_data
                    )
                    logger.info(f"Created new user: {user.email}")
                
                # Create or update student profile with batch
                student, created = Student.objects.get_or_create(
                    user=user,
                    defaults={
                        'student_code': student_code,
                        'name': name,
                        'batch': batch  # Set the batch here
                    }
                )
                
                if not created:
                    student.name = name
                    student.batch = batch  # Update batch if student exists
                    student.save()
                    logger.info(f"Updated existing student: {student.name}")
                else:
                    logger.info(f"Created new student: {student.name}")
                    added_count += 1

            messages.success(request, f"Successfully added {added_count} students to batch {batch_code}!")
            return redirect('teacher:manage_students')

        except Exception as e:
            logger.error(f"Error adding students: {str(e)}", exc_info=True)
            messages.error(request, f"Error adding students: {str(e)}")
            return redirect('teacher:manage_students')

    # GET request
    batches = Batch.objects.all()
    return render(request, 'teacher/manage_students.html', {'batches': batches})

@login_required
def get_batch_students(request, batch_id):
    try:
        batch = Batch.objects.get(id=batch_id)
        students = Student.objects.filter(batch=batch)
        student_list = [{'id': s.id, 'name': s.name, 'student_code': s.student_code} for s in students]
        return JsonResponse({'students': student_list})
    except Batch.DoesNotExist:
        return JsonResponse({'error': 'Batch not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)