from django.forms import ModelForm
from .models import ExeatRequest,Student,Session

from django import forms


class ExeatRequestForm(forms.ModelForm):
    
    class Meta:
        model = ExeatRequest
        fields = ['reason', 'start_date', 'end_date','session','evidence','emergency']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    reason = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'Enter the reason for your exeat request...'}))
    audio_file = forms.FileField(required=False, help_text='Optionally, you can upload an audio file for your request.')
    def __init__(self, *args, **kwargs): 
        super(ExeatRequestForm, self).__init__(*args, **kwargs) # Get the most recent session 
        recent_session = Session.objects.order_by('-created_at').first() 
        self.fields['session'].queryset = Session.objects.filter(id=recent_session.id)

    def clean(self): 
        cleaned_data = super().clean() 
        student = self.instance.student 
        session = cleaned_data.get('session') 
        if ExeatRequest.objects.filter(student=student, session=session, status='Approved').count() >= 4: 
            raise forms.ValidationError("You cannot have more than 4 approved exeats in a session.") 
        return cleaned_data



class MatricNumberLoginForm(forms.Form):
    matric_number = forms.CharField(label='Matric Number', max_length=50)
    password = forms.CharField(widget=forms.PasswordInput)


from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

# class CustomSuperUserCreationForm(UserCreationForm):
#     student_id = forms.CharField(label='Matric Number', max_length=50)

#     class Meta:
#         model = User
#         fields = ('student_id', 'password1', 'password2')


class UpdateProfileForm(forms.ModelForm): 
    class Meta: 
        model = Student 
        fields = ['user', 'dept'] 
        
    def __init__(self, *args, **kwargs): 
        super(UpdateProfileForm, self).__init__(*args, **kwargs) 
        self.fields['user'] = forms.CharField(label='User ID')
        
        if 'instance' in kwargs: 
            print(kwargs['instance'].student_id)
            self.fields['user'].initial = kwargs['instance'].student_id
            self.fields['user'].disabled=True


class EmergencyForm(forms.ModelForm):
    student = forms.ModelChoiceField(queryset=Student.objects.all(), required=True)

    class Meta:
        model = ExeatRequest
        fields = ['student', 'reason', 'start_date', 'end_date', 'evidence', 'session', 'emergency']


class RejectionReasonForm(forms.ModelForm): 
    class Meta: 
        model = ExeatRequest 
        fields = ['rejection_reason'] 
        widgets = { 'rejection_reason': forms.Textarea(attrs={'rows': 4}), }
