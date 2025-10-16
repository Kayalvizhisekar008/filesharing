from django.db import models
from django.contrib.auth.models import AbstractUser

class Role(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("teacher", "Teacher"),
        ("student", "Student"),
    )
    role_name = models.CharField(max_length=50, unique=True, choices=ROLE_CHOICES)

    def __str__(self):
        return self.role_name

class BatchCode(models.Model):
    BRANCH_CHOICES = (
        ("Nehru nagar", "Nehru nagar"),
        ("Gandhipuram", "Gandhipuram"),
    )
    
    batch_code = models.CharField(max_length=20, unique=True)
    class_name = models.CharField(max_length=50)
    academic_year = models.CharField(max_length=20)
    branch = models.CharField(max_length=50, choices=BRANCH_CHOICES)
    username = models.CharField(max_length=100, null=True, blank=True)
    password = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.batch_code} - {self.class_name} ({self.branch})"

class User(AbstractUser):
    first_name = models.CharField(max_length=50)  # Changed to first_name for AbstractUser compatibility
    last_name = models.CharField(max_length=50)   # Changed to last_name
    username = models.CharField(max_length=50, unique=True)
    # email = models.EmailField(unique=True)
    # phone_number = models.CharField(max_length=15, unique=True)
    batchcode = models.CharField(max_length=10)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username

class DashboardStats(models.Model):
    total_teachers = models.IntegerField(default=50)
    total_students = models.IntegerField(default=1200)
    total_batches = models.IntegerField(default=30)
    total_sent_files = models.IntegerField(default=450)

    def __str__(self):
        return "Dashboard Statistics"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"

    @classmethod
    def create_file_notification(cls, user, subject, topic, teacher_name, batch_code=None, is_batch_upload=False):
        """Create a notification for a new file upload
        
        Args:
            user: The user to notify
            subject: The subject of the file
            topic: The topic/name of the file
            teacher_name: Name of the teacher who shared the file
            batch_code: Optional batch code if the file is shared with a batch
            is_batch_upload: True if file is uploaded to a batch, False if shared individually
        """
        title = f"New {subject} File Available"
        
        # For batch uploads, show batch-specific message
        if is_batch_upload and batch_code:
            message = f"A new file '{topic}' has been shared by {teacher_name} for your batch ({batch_code})"
        # For individual shares, show personal message
        else:
            message = f"A new file '{topic}' has been shared with you by {teacher_name}"
            if batch_code:
                message += f" (Batch: {batch_code})"
                
        return cls.objects.create(user=user, title=title, message=message)