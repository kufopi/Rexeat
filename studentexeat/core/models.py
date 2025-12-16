from django.db import models
from django.contrib.auth.models import User
from PIL import Image
from io import BytesIO
from django.conf import settings
from django.core.files.base import ContentFile
# Create your models here.

GENDER = (
    ('Female','Female'),
    ("Male","Male")
)

DEPARTMENT = (
    ('Accounting','Accounting'),
    ('Biochemistry','Biochemistry'),
    ('Biotechnology','Biotechnology'),
    ('Business Administration','Business Administration'),
    ('Computer Science','Computer Science'),
    ('Economics','Economics'),
    ('International Relations','International Relations'),
    ('Law','Law'),
    ('Mass Communication','Mass Communication'),
    ('Mathematics','Mathematics'),
    ('Medical Lab Science','Medical Lab Science'),
    ('Microbiology','Microbiology'),
    ('Nursing','Nursing'),
    ('Physiotherapy','Physiotherapy'),
    ('Political Science','Political Science'),
    ('Public Health','Public Health'),
)

SESS = [tuple([str(x)+'/'+str(x+1),str(x)+'/'+str(x+1)]) for x in range(2024,2070,1)]

def resize_image(image,max_size_kb=150):
    img = Image.open(image)
    img_format = img.format
    quality = 85
    width,height = img.size
    img_io = BytesIO()
    img.save(img_io,format=img_format,quality=quality)
    while img_io.tell() > max_size_kb*1024 and quality >10:
        quality -=5
        width=int(width*0.9)
        height=int(height*0.9)
        img = img.resize((width,height),Image.Resampling.LANCZOS)
        img_io=BytesIO()
        img.save(img_io,format=img_format,quality=quality)
    return  ContentFile(img_io.getvalue(), name=image.name)


class Session(models.Model):
    session  = models.CharField(choices=SESS, max_length=50)
    created_at = models.DateField( auto_now=False, auto_now_add=True)

    class Meta:
        verbose_name = ("session")
        verbose_name_plural = ("sessions")
        ordering = ['-created_at',]

    def __str__(self):
        return self.session

    

class Student(models.Model):
    """Model definition for Student."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # matric = models.CharField(max_length=50)
    name  = models.CharField(max_length=50)
    gender = models.CharField(choices=GENDER,max_length=10)
    guardian_email = models.EmailField(max_length=254)
    guardian_phone = models.CharField( max_length=50)
    dept  = models.CharField(choices=DEPARTMENT, max_length=50)


    # TODO: Define fields here

    class Meta:
        """Meta definition for Student."""

        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        """Unicode representation of Student."""
        return self.name

class Department(models.Model):
    """Model definition for Department."""
    dept = models.CharField(choices=DEPARTMENT,max_length=50)

    # TODO: Define fields here

    class Meta:
        """Meta definition for Department."""

        verbose_name = 'Department'
        verbose_name_plural = 'Departments'

    def __str__(self):
        """Unicode representation of Department."""
        return self.dept


class ExeatRequest(models.Model):
    student=models.ForeignKey(Student,  on_delete=models.CASCADE)
    reason  = models.TextField()
    start_date  = models.DateField(auto_now=False, auto_now_add=False)
    end_date  = models.DateField( auto_now=False, auto_now_add=False)
    evidence = models.ImageField( upload_to='evidence/', help_text='Supporting proof')
    status = models.CharField(max_length=20, choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending') 
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    approved_by_student_affairs = models.BooleanField(default=False) 
    approved_by_hod = models.BooleanField(default=False) 
    approved_by_warden = models.BooleanField(default=False)
    emergency = models.BooleanField(default=False)
    rejection_reason = models.TextField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField( auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.evidence:
            self.evidence = resize_image(self.evidence)
        return super().save(*args, **kwargs)

    

    class Meta:
        verbose_name = ("ExeatRequest")
        verbose_name_plural = ("ExeatRequests")
        ordering = ['-created_at',]

    def __str__(self):
        return self.student.user.student_id

    # def get_absolute_url(self):
    #     return reverse("ExeatRequest_detail", kwargs={"pk": self.pk})

class UserRole(models.Model):
    """Model definition for UserRole."""

    # TODO: Define fields here
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[('StudentAffairs', 'Student Affairs'), ('HeadOfDepartment', 'Head of Department'), ('HallWarden', 'Hall Warden')])
    department = models.CharField(choices=DEPARTMENT, null=True, blank=True,max_length=50)
    gender = models.CharField(choices=GENDER,max_length=10,default='Male')

    class Meta:
        """Meta definition for UserRole."""

        verbose_name = 'UserRole'
        verbose_name_plural = 'UserRoles'

    def __str__(self):
        """Unicode representation of UserRole."""
        return self.user.student_id


from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class CustomUserManager(BaseUserManager):
    def create_user(self, student_id, password=None, **extra_fields):
        if not student_id:
            raise ValueError('The Student ID field must be set')
        user = self.model(student_id=student_id, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, student_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(student_id, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    student_id = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    objects = CustomUserManager()

    USERNAME_FIELD = 'student_id'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.student_id


class Hod(models.Model):
    hod = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField( max_length=50)
    
    """Model definition for Hod."""

    # TODO: Define fields here

    class Meta:
        """Meta definition for Hod."""

        verbose_name = 'Hod'
        verbose_name_plural = 'Hods'

    def __str__(self):
        """Unicode representation of Hod."""
        return self.name
