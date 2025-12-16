from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Student, CustomUser

class StudentResource(resources.ModelResource):
    user = fields.Field(
        column_name='student_id',
        attribute='user',
        widget=ForeignKeyWidget(CustomUser, 'student_id'))

    class Meta:
        model = Student
        fields = ('user', 'name', 'gender', 'guardian_email', 'guardian_phone', 'dept')
        import_id_fields = ('user',)

    def before_import_row(self, row, **kwargs):
        student_id = row['student_id']
        password = 'generic_password'  # Set your generic password here

        if not CustomUser.objects.filter(student_id=student_id).exists():
            user = CustomUser(student_id=student_id)
            user.set_password(password)
            user.save()
        row['user'] = CustomUser.objects.get(student_id=student_id).id
