from django.contrib import admin

from import_export.admin import ImportExportModelAdmin
from .models import Student,Session,ExeatRequest,UserRole,Hod
from .admin_resources import StudentResource
# Register your models here.

from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['student_id', 'is_staff', 'is_active', 'is_superuser']
    search_fields = ['student_id']
    ordering = ['student_id']

    fieldsets = (
        (None, {'fields': ('student_id', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        # ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('student_id', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )





@admin.register(Student)
class StudentAdmin(ImportExportModelAdmin):
    resource_class = StudentResource


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    '''Admin View for Session'''

    list_display = ('session',)
    search_fields = ('session',)

@admin.register(ExeatRequest)
class ExeatRequestAdmin(admin.ModelAdmin):
    '''Admin View for ExeatRequest'''

    list_display = ('student','start_date','end_date','status','approved_by_student_affairs','approved_by_hod','approved_by_warden',)
    list_filter = ('student',)
    
    search_fields = ('student',)

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    '''Admin View for UserRole'''

    list_display = ('user','role','department',)
    list_filter = ('role','department',)
    
    search_fields = ('user',)
    
@admin.register(Hod)
class HodAdmin(admin.ModelAdmin):
    '''Admin View for Hod'''

    list_display = ('name',)
    list_filter = ('name',)
    
    