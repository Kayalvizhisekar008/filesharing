from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count
import logging

class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    student_code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    batch = models.ForeignKey('teacher.Batch', on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.student_code})"

    def get_active_files(self):
        """
        Returns QuerySet of Upload objects accessible to this student.
        """
        from teacher.models import Upload
        from django.utils import timezone

        today = timezone.now().date()
        logger = logging.getLogger(__name__)
        logger.info(f"Getting active files for student {self.student_code} on {today}")

        try:
            qs = Upload.objects.filter(
                is_active=True,
                to_date__gte=today  # Only check if file hasn't expired
            )

            qs_annotated = qs.annotate(num_shared=Count('shared_with'))

            direct_shares = qs_annotated.filter(shared_with=self)
            batch_shares = qs_annotated.filter(
                batch=self.batch,
                num_shared=0
            ) if self.batch else Upload.objects.none()
            general_shares = qs_annotated.filter(
                batch__isnull=True,
                num_shared=0
            )

            accessible_files = direct_shares.union(
                batch_shares,
                general_shares
            ).select_related('teacher', 'batch').order_by('-uploaded_at')

            logger.info(f"Found {accessible_files.count()} accessible files for student {self.student_code}")
            return accessible_files
        except Exception as e:
            logger.exception(f"Error fetching files for student {self.student_code}: {str(e)}")
            return Upload.objects.none()

    class Meta:
        ordering = ['-created_at']


