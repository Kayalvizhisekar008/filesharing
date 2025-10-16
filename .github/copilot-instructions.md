# Django File Sharing Platform - Copilot Instructions

This document provides guidance for AI agents to effectively contribute to this Django-based file sharing application.

## Project Overview & Architecture

This is a monolithic Django application designed for file sharing between teachers and students, with an admin role for oversight.

-   **`fileshare`**: The main Django project directory containing `settings.py` and root `urls.py`.
-   **`core`**: A shared app that defines the custom `User` model (`core.User`) and `Role` model. This is the foundation of the application's role-based access control (RBAC). All user management and authentication logic must reference `core.User`.
-   **`teacher`**: This app contains the logic for users with the "Teacher" role. Key functionality includes uploading files, creating student batches, and sharing files with specific students or entire batches (`teacher.views.share_file`).
-   **`student`**: This app provides the student-facing functionality, primarily viewing and downloading files that have been shared with them (`student.views.received_files`).
-   **`media/`**: This directory stores all user-uploaded files, as configured in `settings.py`.

The core data flow is as follows:
1.  A `Teacher` user logs in and accesses the `/teacher/upload/` page.
2.  They upload a file, which creates an `Upload` record (see `teacher/models.py`). This record links the file to the teacher, a batch, and optionally specific students.
3.  A `Student` user logs in. The `student.views.received_files` view queries for `Upload` objects associated with that student, either directly or through their batch membership, and respecting the `from_date` and `to_date` availability window.

## Developer Workflow

### Backend

1.  **Activate the virtual environment**:
    ```powershell
    .\env\Scripts\Activate.ps1
    ```
2.  **Run the development server**:
    ```bash
    python manage.py runserver
    ```
3.  **Apply database migrations**:
    ```bash
    python manage.py makemigrations
    python manage.py migrate
    ```
4.  **Create an admin user**:
    ```bash
    python manage.py createsuperuser
    ```
    You can then access the Django admin panel at `/admin/`.

### Frontend

The project uses Tailwind CSS.

1.  **Install dependencies**:
    ```bash
    npm install
    ```
2.  **Run the Tailwind CSS compiler in watch mode**:
    ```bash
    npm run tailwind:watch
    ```
    This will watch for changes in template files and rebuild the CSS automatically.

## Project-Specific Conventions

-   **Custom User Model**: Always use `get_user_model()` or import `from core.models import User`. Standard `django.contrib.auth.models.User` is **not** used. The `User` model is linked to a `Role` via a foreign key.

-   **Role-Based Access Control (RBAC)**: Views typically check the user's role at the beginning of the function:
    ```python
    # From student/views.py
    user_role = request.user.role.role_name if hasattr(request.user, 'role') and request.user.role else None
    if user_role not in ["Student", "Admin"]:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("home")
    ```
    When implementing new features, ensure similar role checks are in place.

-   **Dummy Data Generation**: The `teacher` app contains logic to create dummy `Student` and `Batch` objects if they don't exist (e.g., in `teacher.views.get_students_by_batch`). This is intended for development and testing purposes to ensure the UI is functional even with an empty database.

-   **File Sharing Logic**: The `Upload` model in `teacher/models.py` is central to file sharing. It controls file visibility through `from_date`, `to_date`, and relationships to `Batch` and `Student` models.

-   **Logging**: The application uses Python's `logging` module. Use `logger.debug()`, `logger.info()`, etc., to log important events, especially in complex views like `student.views.received_files`.