from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('teacher', '0005_alter_upload_to_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='upload',
            name='subject',
            field=models.CharField(max_length=50, choices=[
                ('PHYSICS', 'Physics'),
                ('CHEMISTRY', 'Chemistry'),
                ('BIOLOGY', 'Biology'),
                ('ZOOLOGY', 'Zoology'),
                ('BOTANY', 'Botany'),
                ('COMPUTER_SCIENCE', 'Computer Science'),
                ('MATHEMATICS', 'Mathematics'),
                ('LANGUAGE', 'Language'),
                ('SOCIAL_SCIENCE', 'Social Science'),
                ('ENGLISH', 'English'),
                ('OTHER', 'Other')
            ]),
        ),
        migrations.AddField(
            model_name='upload',
            name='other_subject',
            field=models.CharField(max_length=50, blank=True, null=True, help_text='Specify subject if Other is selected'),
        ),
    ]