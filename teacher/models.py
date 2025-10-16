# teacher/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class Batch(models.Model):
    batch_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.batch_code

    @property
    def student_count(self):
        from student.models import Student
        return Student.objects.filter(batch=self).count()

class Upload(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='uploads')
    teacher_code = models.CharField(max_length=50, blank=True, null=True)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploads')
    description = models.TextField(blank=True, null=True)
    topic = models.CharField(max_length=255)
    sub_topic = models.CharField(max_length=255, blank=True, null=True)
    subject = models.CharField(max_length=50)
    file = models.FileField(upload_to='uploads/')
    def get_default_to_date():
        return timezone.now() + timezone.timedelta(days=30)

    is_active = models.BooleanField(default=True)
    from_date = models.DateField(default=timezone.now)
    to_date = models.DateField(default=get_default_to_date)  # Default 30 days access
    uploaded_at = models.DateTimeField(auto_now_add=True)
    shared_with = models.ManyToManyField('student.Student', blank=True, related_name='shared_uploads')

    def __str__(self):
        return f"{self.topic} ({self.subject})"

    def is_shared_with_all(self):
        return self.shared_with.count() == 0
        
    def save(self, *args, **kwargs):
        from core.models import Notification
        from student.models import Student
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Check if this is a new upload
        is_new = not self.pk
        
        # Save the upload first
        super().save(*args, **kwargs)
        
        # Only create notifications for new uploads
        if is_new and self.is_active:
            teacher_name = self.teacher.get_full_name() if self.teacher else "A teacher"
            
            # If a batch is selected, only notify students in that batch
            if self.batch:
                logger.info(f"Sending notifications to students in batch {self.batch.batch_code}")
                batch_students = Student.objects.filter(batch=self.batch)
                for student in batch_students:
                    logger.info(f"Creating notification for batch student {student.student_code}")
                    Notification.create_file_notification(
                        user=student.user,
                        subject=self.subject,
                        topic=self.topic,
                        teacher_name=teacher_name,
                        batch_code=self.batch.batch_code,
                        is_batch_upload=True
                    )
            # If no batch is selected but specific students are shared with
            elif self.shared_with.exists():
                for student in self.shared_with.all():
                    logger.info(f"Creating notification for specifically shared student {student.student_code}")
                    Notification.create_file_notification(
                        user=student.user,
                        subject=self.subject,
                        topic=self.topic,
                        teacher_name=teacher_name,
                        batch_code=student.batch.batch_code if student.batch else None,
                        is_batch_upload=False
                    )

    def is_accessible_by_student(self, student):
        import logging
        logger = logging.getLogger(__name__)
        from django.utils import timezone

        logger.info(f"Checking accessibility for file {self.id} for student {student.student_code}")

        try:
            if not self.is_active:
                logger.info(f"File {self.id} is not active")
                return False

            today = timezone.now().date()
            # Only check if file has expired, allowing early access
            if today > self.to_date:
                logger.info(f"File {self.id} has expired. Current: {today}, Expired on: {self.to_date}")
                return False

            if self.shared_with.filter(id=student.id).exists():
                logger.info(f"Student {student.student_code} has direct access to file {self.id}")
                return True

            if self.shared_with.exists():
                logger.info(f"File {self.id} has specific students but {student.student_code} is not one of them")
                return False

            if self.batch:
                if not student.batch:
                    logger.info(f"Student {student.student_code} has no batch assigned")
                    return False

                if self.batch.id == student.batch.id:
                    logger.info(f"File {self.id} is accessible to student {student.student_code} through batch {self.batch.batch_code}")
                    return True
                else:
                    logger.info(f"Student batch ({student.batch.batch_code}) doesn't match file batch ({self.batch.batch_code})")
                    return False

            if not self.batch:
                logger.info(f"File {self.id} is shared with all students (no batch restriction)")
                return True

            logger.info(f"File {self.id} is not accessible to student {student.student_code}")
            return False

        except Exception as e:
            logger.exception(f"Error checking file accessibility: {str(e)}")
            return False