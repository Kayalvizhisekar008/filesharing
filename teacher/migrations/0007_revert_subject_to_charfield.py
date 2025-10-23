from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('teacher', '0006_update_upload_subject_choices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='upload',
            name='subject',
            field=models.CharField(max_length=50),
        ),
        migrations.RemoveField(
            model_name='upload',
            name='other_subject',
        ),
    ]