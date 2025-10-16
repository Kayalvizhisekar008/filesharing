import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, OperationalError
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from datetime import datetime
from student.models import Student
from .models import Notification, DashboardStats, User, Role, BatchCode
from teacher.models import Batch
import pandas as pd
import io
import openpyxl
from functools import wraps
import time
from django.contrib.sessions.models import Session

# Decorator for handling database lock issues
def retry_on_db_lock(func):
    """Retry function execution on database locks"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_attempts = 3
        attempt = 1
        last_error = None
        
        while attempt <= max_attempts:
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                last_error = e
                if "database is locked" not in str(e):
                    raise
                if attempt == max_attempts:
                    break
                time.sleep(0.2 * attempt)
                attempt += 1
            except Exception as e:
                raise
        
        # If we got here, we failed all attempts
        if last_error:
            print(f"Failed after {max_attempts} attempts: {str(last_error)}")
        raise last_error
    
    return wrapper

@login_required
def manage_batchcodes(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        messages.error(request, "You don't have permission to access this page.")
        return redirect('core:dashboard')
    
    # Get all existing BatchCode objects
    existing_batches = BatchCode.objects.all().order_by('-created_at')
    
    # Get unique batch codes from User model that don't exist in BatchCode
    user_batchcodes = User.objects.exclude(batchcode='').values_list('batchcode', flat=True).distinct()
    
    # Create missing batch codes from User model
    for code in user_batchcodes:
        if not BatchCode.objects.filter(batch_code=code).exists():
            BatchCode.objects.create(
                batch_code=code,
                class_name=f"Class for {code}",
                academic_year="2025-2026",
                branch="Nehru nagar"
            )
    
    # Get all batch codes after creating missing ones
    batches = BatchCode.objects.all().order_by('-created_at')
    print(f"Found {len(batches)} batch codes")
    
    # Prepare batch data with students
    batch_data = []
    for batch_code in batches:
        try:
            teacher_batch, _ = Batch.objects.get_or_create(batch_code=batch_code.batch_code)
            students = Student.objects.filter(batch=teacher_batch)
            batch_code.students = students
        except Exception as e:
            print(f"Error getting students for batch {batch_code.batch_code}: {str(e)}")
            batch_code.students = []
        batch_data.append(batch_code)
    
    context = {
        'batches': batch_data
    }
    return render(request, 'batchcode.html', context)

@login_required
def add_batchcode(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return HttpResponseForbidden("You don't have permission to perform this action.")
        
    if request.method == "POST":
        batch_code = request.POST.get('batch_code')
        class_name = request.POST.get('class_name')
        academic_year = request.POST.get('academic_year')
        branch = request.POST.get('branch')
        
        if not all([batch_code, class_name, academic_year, branch]):
            messages.error(request, "All fields are required.")
            return redirect('core:manage_batchcodes')
            
        if BatchCode.objects.filter(batch_code=batch_code).exists():
            messages.error(request, f"Batch code '{batch_code}' already exists.")
            return redirect('core:manage_batchcodes')
            
        BatchCode.objects.create(
            batch_code=batch_code,
            class_name=class_name,
            academic_year=academic_year,
            branch=branch
        )
        Batch.objects.get_or_create(batch_code=batch_code)
        messages.success(request, f"Batch code '{batch_code}' created successfully.")
        
    return redirect('core:manage_batchcodes')

@login_required
def delete_batchcode(request, batch_id):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return JsonResponse({
            "status": "error",
            "message": "You don't have permission to perform this action."
        }, status=403)
        
    if request.method == "POST":
        try:
            import json
            data = json.loads(request.body)
            reason = data.get('reason', 'No reason provided')
            
            batch = BatchCode.objects.get(id=batch_id)
            batch_code = batch.batch_code
            
            # Create delete notification for admin users
            admin_role = Role.objects.get(role_name='Admin')
            admin_users = User.objects.filter(role=admin_role)
            for admin in admin_users:
                Notification.objects.create(
                    user=admin,
                    title="Batch Deletion Record",
                    message=f"Batch '{batch_code}' was deleted.\nReason: {reason}"
                )
            
            # Delete associated students first
            try:
                teacher_batch = Batch.objects.get(batch_code=batch_code)
                students = Student.objects.filter(batch=teacher_batch)
                # Delete student users
                for student in students:
                    if student.user:
                        student.user.delete()
                students.delete()
                teacher_batch.delete()
            except Batch.DoesNotExist:
                pass
            
            # Finally delete the batch code
            batch.delete()
            
            return JsonResponse({
                "status": "success",
                "message": f"Batch code '{batch_code}' and associated students deleted successfully."
            })
            
        except BatchCode.DoesNotExist:
            return JsonResponse({
                "status": "error",
                "message": "Batch code not found."
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                "status": "error",
                "message": "Invalid JSON data in request."
            }, status=400)
        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": f"An error occurred: {str(e)}"
            }, status=500)
            
    return JsonResponse({
        "status": "error",
        "message": "Invalid request method."
    }, status=405)

@login_required
def get_batch_summary(request):
    """Get summary of all batches including student counts and class details"""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    
    try:
        batch_summary = []
        batches = BatchCode.objects.all().order_by('batch_code')
        
        for batch in batches:
            teacher_batch = Batch.objects.filter(batch_code=batch.batch_code).first()
            student_count = Student.objects.filter(batch=teacher_batch).count() if teacher_batch else 0
            
            batch_summary.append({
                'id': str(batch.id),  # Convert ID to string
                'batch_code': batch.batch_code or '',
                'class_name': batch.class_name or '',
                'academic_year': batch.academic_year or '',
                'branch': batch.branch or '',
                'student_count': student_count
            })
        
        return JsonResponse({
            'status': 'success',
            'data': batch_summary
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def get_students_by_batch(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return JsonResponse({"error": "Permission denied"}, status=403)
    
    batch_code = request.GET.get('batch_code')
    batch_id = request.GET.get('batch_id')
    
    if not batch_code and not batch_id:
        return JsonResponse({"error": "Either batch code or batch ID is required"}, status=400)
    
    try:
        if batch_id:
            batch_code_obj = BatchCode.objects.get(id=batch_id)
            batch_code = batch_code_obj.batch_code
        else:
            batch_code_obj = BatchCode.objects.get(batch_code=batch_code)
        
        batch = Batch.objects.get(batch_code=batch_code)
        students = Student.objects.filter(batch=batch)
        
        students_data = [{
            "id": student.id,
            "name": student.name,
            "student_code": student.student_code,
            "batch": batch.batch_code,
            "class_name": batch_code_obj.class_name,
            "username": student.user.username if student.user else student.student_code,
            "password": student.student_code  # Using student_code as initial password
        } for student in students]
        
        print(f"Found {len(students_data)} students for batch {batch_code}")
        return JsonResponse({"students": students_data})
        
    except BatchCode.DoesNotExist:
        return JsonResponse({"error": f"Batch code {batch_code} not found"}, status=404)
    except Batch.DoesNotExist:
        return JsonResponse({"error": f"Teacher batch {batch_code} not found"}, status=404)
    except Exception as e:
        print(f"Error getting students: {str(e)}")
        return JsonResponse({"error": "An error occurred while fetching students"}, status=500)

@login_required
def delete_student(request, student_id):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return HttpResponseForbidden("You don't have permission to perform this action.")
    
    if request.method == "POST":
        try:
            with transaction.atomic():
                student = Student.objects.get(id=student_id)
                student_name = student.name
                batch_code = student.batch.batch_code if student.batch else "No Batch"
                delete_reason = request.POST.get('delete_reason', 'No reason provided')
                
                admin_role = Role.objects.get(role_name='Admin')
                admin_users = User.objects.filter(role=admin_role)
                
                for admin in admin_users:
                    Notification.objects.create(
                        user=admin,
                        title=f"Student Deletion Record",
                        message=f"Student '{student_name}' from batch '{batch_code}' was deleted.\nReason: {delete_reason}"
                    )
                
                if student.user:
                    student.user.delete()
                else:
                    student.delete()
                
                success_message = f"Student '{student_name}' from batch '{batch_code}' has been deleted successfully."
                if delete_reason:
                    success_message += f"\nReason: {delete_reason}"
                
                return JsonResponse({
                    'status': 'success',
                    'message': success_message
                })
                
        except Student.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': "Student not found."
                }, status=404)
            else:
                messages.error(request, "Student not found.")
                return redirect('core:manage_batchcodes')
                
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'message': f"Error deleting student: {str(e)}"
                }, status=500)
            else:
                messages.error(request, f"Error deleting student: {str(e)}")
                return redirect('core:manage_batchcodes')
    
    return redirect('core:manage_batchcodes')

def transfer_student(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return HttpResponseForbidden("You don't have permission to perform this action.")
    
    if request.method != "POST":
        return redirect('core:manage_batchcodes')
    
    from_batch = request.POST.get('from_batch')
    to_batch = request.POST.get('to_batch')
    student_id = request.POST.get('student_id')
    transfer_date = request.POST.get('transfer_date')
    remarks = request.POST.get('remarks')
    
    if not all([from_batch, to_batch, student_id, transfer_date]):
        messages.error(request, "All fields are required.")
        return redirect('core:manage_batchcodes')
    
    try:
        transfer_date = datetime.strptime(transfer_date, '%Y-%m-%d').date()
        student = Student.objects.get(id=student_id)
        from_batch_inner = Batch.objects.get(batch_code=from_batch)
        to_batch_inner = Batch.objects.get_or_create(batch_code=to_batch)[0]
        
        if student.batch != from_batch_inner:
            messages.error(request, "Student is not in the specified batch.")
            return redirect('core:manage_batchcodes')
        
        student.batch = to_batch_inner
        student.save()
        
        Notification.objects.create(
            user=student.user,
            title=f"Batch Transfer Notification",
            message=f"You have been transferred from {from_batch} to {to_batch}.\nRemarks: {remarks if remarks else 'No remarks provided'}"
        )
        
        messages.success(request, f"Student {student.name} successfully transferred from {from_batch} to {to_batch}.")
        
    except (Student.DoesNotExist, Batch.DoesNotExist) as e:
        messages.error(request, "Invalid student or batch code.")
    except ValueError as e:
        messages.error(request, "Invalid date format.")
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
    
    return redirect('core:manage_batchcodes')

@retry_on_db_lock
def download_bulk_files(request):
    """Download all uploaded files in bulk"""
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return HttpResponseForbidden("You don't have permission to perform this action.")
    
    try:
        # Import required modules
        import zipfile
        import os
        from teacher.models import Upload
        from django.conf import settings
        
        # Create a zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Get all uploads
            uploads = Upload.objects.all().order_by('-upload_date')
            
            # Add each file to the zip
            for upload in uploads:
                if upload.file and os.path.exists(upload.file.path):
                    # Get the original filename
                    filename = os.path.basename(upload.file.name)
                    # Add file to zip with a path structure: teacher_name/batch/filename
                    zip_path = f"{upload.teacher.user.get_full_name()}/{upload.batch.batch_code}/{filename}"
                    zip_file.write(upload.file.path, zip_path)
        
        # Prepare response with zip file
        zip_buffer.seek(0)
        response = HttpResponse(
            zip_buffer.getvalue(),
            content_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename=bulk_downloads_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
                'Cache-Control': 'no-cache, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
        
        return response
        
    except Exception as e:
        print(f"Error generating bulk download: {str(e)}")
        messages.error(request, "Error generating bulk download. Please try again.")
        return redirect('core:dashboard')

@retry_on_db_lock
def download_format(request, format_type):
    """Download Excel format for student upload"""
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return HttpResponseForbidden("You don't have permission to perform this action.")
    
    try:
        # Create workbook in memory
        wb = openpyxl.Workbook()
        ws = wb.active
        
        if format_type == 'individual':
            ws.append(['Enrollment Number', 'Batch Code', 'Student Name', 'Class', 'Academic Year', 'Branch'])
            ws.append(['2025001', 'CS2025A', 'John Doe', 'Class 10', '2025-2026', 'Nehru nagar'])
        elif format_type == 'bulk':
            ws.append(['Enrollment Number', 'Batch Code', 'Student Name', 'Class', 'Academic Year', 'Branch'])
            ws.append(['2025001', 'CS2025A', 'John Doe', 'Computer Science', '2025-2026', 'Nehru nagar'])
            ws.append(['2025002', 'CS2025A', 'Jane Smith', 'Computer Science', '2025-2026', 'Gandhipuram'])
        
        # Use a StreamingHttpResponse to prevent session file handling issues
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename=student_{format_type}_format.xlsx',
                'Cache-Control': 'no-cache, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        )
        
        # Save to response buffer
        wb.save(response)
        
        # Mark the session as modified to False to prevent unnecessary saves
        request.session.modified = False
        
        return response
        
    except Exception as e:
        print(f"Error generating Excel format: {str(e)}")
        messages.error(request, "Error generating Excel format. Please try again.")
        return redirect('core:manage_batchcodes')

@retry_on_db_lock
def bulk_upload_students(request):
    """Handle bulk upload of students via Excel file"""
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return JsonResponse({
            'status': 'error',
            'message': 'You do not have permission to perform this action.'
        }, status=403)
        
    if request.method != 'POST':
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request method.'
        }, status=405)

    # Mark session as unmodified to prevent session save attempts
    request.session.modified = False
    if 'excel_file' not in request.FILES:
        return JsonResponse({'status': 'error', 'message': 'No file uploaded'}, status=400)

    excel_file = request.FILES['excel_file']
    
    try:
        # Print file details for debugging
        print(f"File name: {excel_file.name}")
        print(f"File size: {excel_file.size} bytes")
        print(f"Content type: {excel_file.content_type}")

        # Check if file is empty
        if excel_file.size == 0:
            return JsonResponse({
                'status': 'error',
                'message': 'The uploaded file is empty'
            }, status=400)

        # Check file type
        if not excel_file.name.lower().endswith(('.xlsx', '.xls')):
            return JsonResponse({
                'status': 'error',
                'message': 'Please upload a valid Excel file (.xlsx or .xls)'
            }, status=400)

        # Read Excel file with explicit engine specification
        try:
            df = pd.read_excel(excel_file, engine='openpyxl')
        except Exception as e:
            print(f"Error reading Excel file with openpyxl: {str(e)}")
            try:
                # Try with xlrd as fallback for older .xls files
                df = pd.read_excel(excel_file, engine='xlrd')
            except Exception as e2:
                print(f"Error reading Excel file with xlrd: {str(e2)}")
                error_msg = 'Unable to read Excel file. Please ensure it is not corrupted and try again.'
                if "No sheet found" in str(e) or "No sheet found" in str(e2):
                    error_msg = 'The Excel file appears to be empty or contains no valid sheets.'
                elif "Unsupported format" in str(e) or "Unsupported format" in str(e2):
                    error_msg = 'Unsupported Excel format. Please save the file as .xlsx or .xls and try again.'
                return JsonResponse({
                    'status': 'error',
                    'message': error_msg
                }, status=400)

        # Check if DataFrame is empty
        if df.empty:
            return JsonResponse({
                'status': 'error',
                'message': 'The Excel file contains no data'
            }, status=400)

        # Clean up column names (remove extra spaces, make case-insensitive)
        df.columns = [str(col).strip() if pd.notna(col) else '' for col in df.columns]
        
        # Print columns for debugging
        print(f"Found columns: {list(df.columns)}")
        
        # Create a mapping of possible variations to standard column names
        column_variations = {
            'Enrollment Number': ['enrollment number', 'enrollment', 'enrollment no', 'enrollment no.', 'enrollmentnumber', 'enroll', 'enrol', 'enrollment_number', 'enrollment_no', 'ENROLLMENT NUMBER', 'ENROLLMENT'],
            'Batch Code': ['batch code', 'batchcode', 'batch', 'batch no', 'batch no.', 'batchno', 'batch_code', 'batch_no', 'BATCH CODE', 'BATCH'],
            'Student Name': ['student name', 'studentname', 'name', 'full name', 'fullname', 'student_name', 'full_name', 'STUDENT NAME'],
            'Class': ['class', 'class name', 'classname', 'std', 'standard', 'class_name', 'CLASS'],
            'Academic Year': ['academic year', 'academicyear', 'year', 'academic', 'academic_year', 'academic session', 'academic_session', 'session year', 'session_year'],
            'Branch': ['branch', 'branch name', 'branchname', 'campus', 'branch_name', 'location', 'center']
        }
        
        # Default values for Academic Year and Branch
        default_academic_year = "2025-2026"  # Current academic year
        default_branch = "Nehru nagar"  # Default branch
        
        # Map actual column names to standard names with improved flexibility
        column_mapping = {}
        for std_col, variations in column_variations.items():
            for col in df.columns:
                # Normalize both the column name and variations for comparison
                normalized_col = col.lower().replace(' ', '').replace('_', '').replace('-', '')
                normalized_variations = [v.lower().replace(' ', '').replace('_', '').replace('-', '') for v in variations + [std_col]]
                if normalized_col in normalized_variations:
                    column_mapping[std_col] = col
                    break
        
        # Check for essential columns (Enrollment, Student Name, Batch Code, Class)
        essential_columns = ['Enrollment Number', 'Batch Code', 'Student Name', 'Class']
        missing_essential = [col for col in essential_columns if col not in column_mapping]
        
        if missing_essential:
            error_msg = f"Missing essential columns in Excel file: {', '.join(missing_essential)}.\nFound columns: {', '.join(df.columns)}"
            return JsonResponse({'status': 'error', 'message': error_msg}, status=400)
            
        # Use default values for Academic Year and Branch if not provided
        if 'Academic Year' not in column_mapping:
            df['Academic Year'] = default_academic_year
            column_mapping['Academic Year'] = 'Academic Year'
            
        if 'Branch' not in column_mapping:
            df['Branch'] = default_branch
            column_mapping['Branch'] = 'Branch'
        
        successful = 0
        failed = 0
        errors = []
        
        with transaction.atomic():
            # Process each row in the Excel file
            df = df.replace({pd.NA: None, pd.NaT: None})  # Handle NaN values
            for index, row in df.iterrows():
                try:
                    # Extract data from row using the mapped column names
                    if pd.isna(row[column_mapping['Enrollment Number']]) or \
                       pd.isna(row[column_mapping['Batch Code']]) or \
                       pd.isna(row[column_mapping['Student Name']]) or \
                       pd.isna(row[column_mapping['Class']]) or \
                       pd.isna(row[column_mapping['Academic Year']]) or \
                       pd.isna(row[column_mapping['Branch']]):
                        raise ValueError("Row contains empty values")
                    enrollment = str(row[column_mapping['Enrollment Number']]).strip()
                    batch_code = str(row[column_mapping['Batch Code']]).strip()
                    student_name = str(row[column_mapping['Student Name']]).strip()
                    class_name = str(row[column_mapping['Class']]).strip()
                    academic_year = str(row[column_mapping['Academic Year']]).strip()
                    branch = str(row[column_mapping['Branch']]).strip()
                    
                    if not all([enrollment, batch_code, student_name, class_name, academic_year, branch]):
                        raise ValueError("All fields are required")
                    
                    # Validate academic year format (optional)
                    if not academic_year.replace('-', '').isdigit():
                        raise ValueError(f"Invalid academic year format: {academic_year}. Expected format: YYYY-YYYY")
                    
                    # Get or create BatchCode and Batch
                    batch_code_obj, _ = BatchCode.objects.get_or_create(
                        batch_code=batch_code,
                        defaults={
                            'class_name': class_name,
                            'academic_year': academic_year,
                            'branch': branch
                        }
                    )
                    
                    # Update existing batch code with new values if needed
                    if batch_code_obj.academic_year != academic_year or \
                       batch_code_obj.branch != branch or \
                       batch_code_obj.class_name != class_name:
                        batch_code_obj.academic_year = academic_year
                        batch_code_obj.branch = branch
                        batch_code_obj.class_name = class_name
                        batch_code_obj.save()
                    
                    batch, _ = Batch.objects.get_or_create(batch_code=batch_code)
                    
                    # Process student name
                    name_parts = student_name.split(maxsplit=1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else ""
                    
                    # Generate username
                    base_username = (first_name + last_name).lower()
                    base_username = ''.join(c for c in base_username if c.isalnum())
                    username = base_username
                    counter = 1
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    # Create user
                    student_role = Role.objects.get(role_name='Student')
                    user = User.objects.create(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        role=student_role,
                        batchcode=batch_code
                    )
                    user.set_password(enrollment)
                    user.save()
                    
                    # Create student
                    Student.objects.create(
                        user=user,
                        student_code=enrollment,
                        name=student_name,
                        batch=batch
                    )
                    successful += 1
                except Exception as e:
                    failed += 1
                    error_msg = f"Row {index + 2}: {student_name if 'student_name' in locals() else 'Unknown'} - {str(e)}"
                    errors.append(error_msg)
                    continue
        
        # Prepare response
        response_data = {
            'status': 'success' if not errors else 'partial_success',
            'message': f"Processed {successful + failed} students. {successful} successful, {failed} failed.",
            'successful': successful,
            'failed': failed,
            'errors': errors
        }
        
        return JsonResponse(response_data)
        
    except pd.errors.EmptyDataError:
        return JsonResponse({'status': 'error', 'message': "The Excel file is empty"}, status=400)
        
    except Exception as e:
        error_msg = f"Error processing Excel file: {str(e)}"
        return JsonResponse({'status': 'error', 'message': error_msg}, status=500)

@login_required
def add_individual_student(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return HttpResponseForbidden("You don't have permission to perform this action.")
    
    if request.method == 'POST':
        enrollment = request.POST.get('enrollment')
        batch_code_str = request.POST.get('batch_code')
        student_name = request.POST.get('student_name')
        class_name = request.POST.get('class_name')
        
        if not all([enrollment, batch_code_str, student_name]):
            error_msg = "All fields are required for individual student."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=400)
            messages.error(request, error_msg)
            return redirect('core:manage_batchcodes')
        
        try:
            with transaction.atomic():
                try:
                    batch_code = BatchCode.objects.get(batch_code=batch_code_str)
                except BatchCode.DoesNotExist:
                    batch_code = BatchCode.objects.create(
                        batch_code=batch_code_str,
                        class_name=class_name or f"Class for {batch_code_str}",
                        academic_year="2025-2026",
                        branch="Nehru nagar"
                    )
                
                batch, _ = Batch.objects.get_or_create(batch_code=batch_code_str)
                
                name_parts = student_name.split(maxsplit=1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""
                
                base_username = (first_name + last_name).lower()
                base_username = ''.join(c for c in base_username if c.isalnum())
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                student_role = Role.objects.get(role_name='Student')
                user = User.objects.create(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    role=student_role,
                    batchcode=batch_code_str
                )
                user.set_password(enrollment)
                user.save()
                
                student = Student.objects.create(
                    user=user,
                    student_code=enrollment,
                    name=student_name,
                    batch=batch
                )
                
                success_msg = f"Student '{student_name}' added successfully. Username: {username}, Initial password: {enrollment}"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'message': success_msg})
                messages.success(request, success_msg)
            
        except BatchCode.DoesNotExist:
            error_msg = f"Batch code '{batch_code_str}' does not exist."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=404)
            messages.error(request, error_msg)
        except Role.DoesNotExist:
            error_msg = "Student role not found. Please contact the administrator."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=500)
            messages.error(request, error_msg)
        except Exception as e:
            error_msg = f"Error adding student: {str(e)}"
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=500)
            messages.error(request, error_msg)
    
    return redirect('core:manage_batchcodes')

def dashboard_stats(request):
    try:
        from teacher.models import Batch, Upload
        from django.utils import timezone
        from django.db.models import Q
        
        user_role = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None
        
        total_teachers = User.objects.filter(role__role_name='Teacher').count()
        total_students = User.objects.filter(role__role_name='Student').count()
        total_batches = Batch.objects.count()
        total_sent_files = Upload.objects.count()
        student_stats = {}
        
        # Calculate student-specific stats if user is a student
        if user_role == "Student":
            from student.models import Student
            try:
                student = Student.objects.get(user=request.user)
                current_date = timezone.now().date()
                
                # Get active files for this student
                active_files = Upload.objects.filter(
                    Q(batch=student.batch) | Q(shared_with=student),
                    is_active=True,
                    to_date__gte=current_date
                ).distinct()
                
                # Calculate total received files
                total_received_files = active_files.count()
                
                # Calculate total teachers who shared files
                sharing_teachers = active_files.values('teacher').distinct().count()
                
                # Calculate total subjects
                total_subjects = active_files.values('subject').distinct().count()
                
                student_stats = {
                    'total_received_files': total_received_files,
                    'total_sharing_teachers': sharing_teachers,
                    'total_subjects': total_subjects
                }
            except Student.DoesNotExist:
                student_stats = {
                    'total_received_files': 0,
                    'total_sharing_teachers': 0,
                    'total_subjects': 0
                }
        
        stats, _ = DashboardStats.objects.get_or_create(pk=1)
        stats.total_teachers = total_teachers
        stats.total_students = total_students
        stats.total_batches = total_batches
        stats.total_sent_files = total_sent_files
        stats.save()
        
        data = {
            'success': True,
            'total_teachers': total_teachers,
            'total_students': total_students,
            'total_batches': total_batches,
            'total_sent_files': total_sent_files,
            **student_stats
        }
    except Exception as e:
        data = {
            'success': False,
            'error': str(e)
        }
    return JsonResponse(data)

@retry_on_db_lock
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return render(request, "login.html")
        
        try:
            # First validate user credentials without database writes
            user = authenticate(request, username=username, password=password)
            if user is None:
                messages.error(request, "Invalid username or password.")
                return render(request, "login.html")
            
            if not hasattr(user, 'role') or user.role is None:
                messages.error(request, "No role assigned to this user. Please contact administrator.")
                return render(request, "login.html")
            
            if not user.is_active:
                messages.error(request, "Your account has been deactivated. Please contact administrator.")
                return render(request, "login.html")
            
            # Use atomic transaction for all database writes
            with transaction.atomic():
                # Check if student needs profile creation
                if hasattr(user, 'role') and user.role and user.role.role_name == "Student":
                    try:
                        student = Student.objects.select_for_update().get(user=user)
                    except Student.DoesNotExist:
                        batch = None
                        if hasattr(user, 'batchcode') and user.batchcode:
                            batch, _ = Batch.objects.select_for_update().get_or_create(batch_code=user.batchcode)
                        
                        if batch:
                            student_count = Student.objects.filter(batch=batch).count()
                            unique_student_code = f"{user.batchcode}-{student_count+1:03d}"
                        else:
                            unique_student_code = f"STU{user.id:04d}"
                        
                        student = Student.objects.create(
                            user=user,
                            student_code=unique_student_code,
                            name=user.get_full_name() or user.username,
                            batch=batch
                        )
                        print(f'Created student profile for {user.username}')
                
                # Attempt login after profile creation
                try:
                    # Delete any existing session for this user to prevent conflicts
                    Session.objects.filter(
                        session_data__contains=str(user.id)
                    ).delete()
                    
                    login(request, user)
                    request.session.save()  # Explicitly save the session
                    
                    messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                    return redirect("core:dashboard")
                except Exception as e:
                    print(f"Session error during login: {str(e)}")
                    # If session creation fails, log out the user and show error
                    logout(request)
                    messages.error(request, "Error creating session. Please try again.")
                    return render(request, "login.html")
        
        except Exception as e:
            print(f"Login error: {str(e)}")
            messages.error(request, "An error occurred during login. Please try again.")
            return render(request, "login.html")
    
    return render(request, "login.html")

def signup_view(request):
    is_student_login = request.session.get('student_login', False)
    stored_username = request.session.get('student_username', '')
    
    roles = Role.objects.all()
    if not roles.exists():
        messages.error(request, "No roles available. Please contact the administrator.")
        return render(request, "signup.html", {"roles": roles})
    
    student_role = None
    if is_student_login:
        try:
            student_role = Role.objects.get(role_name__iexact='student')
        except Role.DoesNotExist:
            pass
    
    if request.method == "POST":
        first_name = request.POST.get("firstName")
        last_name = request.POST.get("lastName")
        username = request.POST.get("username", stored_username)
        batch_code = request.POST.get("batchCode")
        role_id = request.POST.get("role", student_role.id if student_role else None)
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirmPassword")
        
        try:
            selected_role = Role.objects.get(id=role_id)
            is_admin = selected_role.role_name.lower() == 'admin'
        except Role.DoesNotExist:
            messages.error(request, "Invalid role selected.")
            return render(request, "signup.html", {"roles": roles})
        
        if is_admin:
            required_fields = [first_name, last_name, username, role_id, password, confirm_password]
        else:
            required_fields = [first_name, last_name, username, batch_code, role_id, password, confirm_password]
            
        if not all(required_fields):
            messages.error(request, "All fields are required.")
            return render(request, "signup.html", {"roles": roles})
        
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "signup.html", {"roles": roles})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, "signup.html", {"roles": roles})
        
        try:
            with transaction.atomic():
                role = Role.objects.get(id=role_id)
                user_data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'username': username,
                    'role': role
                }
                
                if role.role_name.lower() != 'admin':
                    user_data['batchcode'] = batch_code
                    
                user = User(**user_data)
                user.set_password(password)
                user.save()
                
                if role.role_name.lower() == 'student':
                    batch = None
                    if batch_code:
                        batch, _ = Batch.objects.get_or_create(batch_code=batch_code)
                    
                    student_count = Student.objects.filter(batch=batch).count() if batch else 0
                    unique_student_code = f"{batch_code}-{student_count+1:03d}" if batch else f"STU{user.id:04d}"
                    
                    student = Student.objects.create(
                        user=user,
                        student_code=unique_student_code,
                        name=f"{first_name} {last_name}",
                        batch=batch
                    )
                    print(f"Created student profile: {student.name} ({student.student_code})")
            
            messages.success(request, "Sign up successful! Please log in.")
            return redirect("core:login")
        except Role.DoesNotExist:
            messages.error(request, "Invalid role selected.")
            return render(request, "signup.html", {"roles": roles})
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            context = {
                "roles": roles,
                "is_student_login": is_student_login,
                "stored_username": stored_username,
                "student_role": student_role
            }
            return render(request, "signup.html", context)
    
    if 'student_login' in request.session:
        del request.session['student_login']
    if 'student_username' in request.session:
        del request.session['student_username']
    if 'temp_username' in request.session:
        del request.session['temp_username']
    if 'temp_password' in request.session:
        del request.session['temp_password']
    
    context = {
        "roles": roles,
        "is_student_login": is_student_login,
        "stored_username": stored_username,
        "student_role": student_role
    }
    return render(request, "signup.html", context)

def forgot_password(request):
    if request.method == "POST":
        username = request.POST.get("username")
        if not username:
            messages.error(request, "Username is required.")
            return render(request, "forgot_password.html")
        
        try:
            user = User.objects.get(username=username)
            request.session["reset_username"] = username
            return redirect("core:reset_password")
        except User.DoesNotExist:
            messages.error(request, "No account found with that username.")
    
    return render(request, "forgot_password.html")

def reset_password(request):
    username = request.session.get("reset_username")
    if not username:
        messages.error(request, "Session expired. Please start the password reset process again.")
        return redirect("core:forgot_password")
    
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        
        if not new_password or not confirm_password:
            messages.error(request, "Both password fields are required.")
            return render(request, "reset_password.html")
        
        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "reset_password.html")
        
        try:
            user = User.objects.get(username=username)
            user.set_password(new_password)
            user.save()
            messages.success(request, "Password updated successfully! Please log in.")
            if "reset_username" in request.session:
                del request.session["reset_username"]
            return redirect("core:login")
        except User.DoesNotExist:
            messages.error(request, "User not found.")
            return redirect("core:forgot_password")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, "reset_password.html")
    
    return render(request, "reset_password.html")

@login_required
@login_required
def update_batch_credentials(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return JsonResponse({
            'status': 'error',
            'message': 'You do not have permission to perform this action.'
        }, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            batch_id = data.get('batch_id')
            username = data.get('username')
            password = data.get('password')
            
            batch = BatchCode.objects.get(id=batch_id)
            batch.username = username
            if password:  # Only update password if provided
                batch.password = password
            batch.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Credentials updated successfully'
            })
            
        except BatchCode.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Batch not found'
            }, status=404)
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

def home(request):
    try:
        if not hasattr(request.user, 'role') or request.user.role is None:
            messages.error(request, "No role assigned. Please contact the administrator.")
            return redirect("core:login")
        
        user_role = request.user.role.role_name
        valid_roles = ["Teacher", "Student", "Admin"]
        
        if user_role not in valid_roles:
            messages.error(request, "Invalid role assigned. Please contact the administrator.")
            return redirect("core:login")
        
        stats = DashboardStats.objects.first()
        if stats is None:
            stats = DashboardStats.objects.create()
        
        show_menus = {
            'show_teacher_menu': False,
            'show_student_menu': False,
            'show_admin_menu': False
        }
        
        if user_role == "Teacher":
            show_menus['show_teacher_menu'] = True
        elif user_role == "Student":
            show_menus['show_student_menu'] = True
        elif user_role == "Admin":
            show_menus['show_teacher_menu'] = True
            show_menus['show_student_menu'] = True
            show_menus['show_admin_menu'] = True
        
        context = {
            'user_role': user_role,
            'total_teachers': stats.total_teachers,
            'total_students': stats.total_students,
            'total_batches': stats.total_batches,
            'total_sent_files': stats.total_sent_files,
            **show_menus
        }
        
        if user_role == "Teacher":
            context['allowed_pages'] = ["dashboard", "upload_file"]
        elif user_role == "Student":
            context['allowed_pages'] = ["dashboard", "study_books"]
        elif user_role == "Admin":
            context['allowed_pages'] = ["dashboard", "upload_file", "study_books"]
        
        return render(request, "dashboard.html", context)
    
    except AttributeError:
        messages.error(request, "Role configuration error. Please contact the administrator.")
        return redirect("core:login")

@login_required
def update_student_credentials(request, student_id):
    if not request.user.is_authenticated or not hasattr(request.user, 'role') or request.user.role.role_name != "Admin":
        return JsonResponse({
            'status': 'error',
            'message': 'You do not have permission to perform this action.'
        }, status=403)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            
            if not username:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Username is required'
                }, status=400)

            student = Student.objects.get(id=student_id)
            if not student.user:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Student has no associated user account'
                }, status=404)

            # Update username if different and not already taken
            if username != student.user.username:
                if User.objects.filter(username=username).exclude(id=student.user.id).exists():
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Username already taken'
                    }, status=400)
                student.user.username = username

            # Update password if provided
            if password:
                student.user.set_password(password)

            student.user.save()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Student credentials updated successfully',
                'username': username
            })
            
        except Student.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Student not found'
            }, status=404)
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

@retry_on_db_lock
def logout_view(request):
    try:
        request.session.flush()
        with transaction.atomic():
            session_key = request.session.session_key
            logout(request)
            if session_key:
                Session.objects.filter(session_key=session_key).delete()
        messages.info(request, "You have been logged out successfully.")
    except Exception as e:
        try:
            logout(request)
        except:
            pass
        messages.warning(request, "Logged out with some errors. Please refresh the page.")
    
    response = redirect("core:login")
    response.delete_cookie('sessionid')
    return response

@login_required
def mark_notifications_read(request):
    """Mark notifications as read when user opens notification dropdown"""
    if request.method == 'POST':
        try:
            # Mark all unread notifications for this user as read
            with transaction.atomic():
                Notification.objects.filter(
                    user=request.user,
                    is_read=False
                ).update(is_read=True)
                
            return JsonResponse({
                'status': 'success',
                'message': 'Notifications marked as read'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)

@login_required
def delete_notification(request, notification_id):
    """Delete a specific notification"""
    if request.method == 'DELETE':
        try:
            with transaction.atomic():
                notification = Notification.objects.get(
                    id=notification_id,
                    user=request.user  # Ensure user owns this notification
                )
                notification.delete()
                
                # Get updated unread count
                unread_count = Notification.objects.filter(
                    user=request.user,
                    is_read=False
                ).count()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Notification deleted successfully',
                    'unread_count': unread_count
                })
        except Notification.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Notification not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=405)