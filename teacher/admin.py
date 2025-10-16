from django.contrib import admin
from .models import Batch, Upload

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_code', 'name', 'get_student_count')
    search_fields = ('batch_code', 'name')
    
    def get_student_count(self, obj):
        return obj.students.count()
    get_student_count.short_description = 'Number of Students'

@admin.register(Upload)
class UploadAdmin(admin.ModelAdmin):
    list_display = ('topic', 'subject', 'teacher', 'batch', 'is_active', 'from_date', 'to_date')
    list_filter = ('is_active', 'subject', 'batch', 'uploaded_at')
    search_fields = ('topic', 'subject', 'teacher__username', 'batch__batch_code')
    date_hierarchy = 'uploaded_at'
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'batch' in form.base_fields:
            form.base_fields['batch'].widget.attrs['onchange'] = 'updateStudentList(this.value)'
        return form
    
    def render_change_form(self, request, context, *args, **kwargs):
        context['media'] = context.get('media', '') + '''
        <script type="text/javascript">
            django.jQuery(document).ready(function() {
                django.jQuery('#id_batch').change(function() {
                    var batchId = django.jQuery(this).val();
                    if(batchId) {
                        django.jQuery.ajax({
                            url: '/get_batch_students/' + batchId + '/',
                            type: 'GET',
                            success: function(data) {
                                var studentField = django.jQuery('#id_shared_with');
                                studentField.empty();
                                data.students.forEach(function(student) {
                                    studentField.append(new Option(student.name + ' (' + student.student_code + ')', student.id));
                                });
                            }
                        });
                    } else {
                        django.jQuery('#id_shared_with').empty();
                    }
                });
            });
        </script>
        '''
        return super().render_change_form(request, context, *args, **kwargs)
