from django.shortcuts import render, redirect,get_object_or_404
from .models import ExeatRequest,UserRole,Student,Hod
from .forms import ExeatRequestForm,EmergencyForm
from google.cloud import speech_v1p1beta1 as speech
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required 

from django.contrib.auth import authenticate, login
from .forms import MatricNumberLoginForm, UpdateProfileForm,RejectionReasonForm
from django.contrib import messages
from django.utils import timezone
from django.core.exceptions import PermissionDenied



@login_required 
def home(request): 
    user_role = None 
    if request.user.is_authenticated: 
        try: 
            user_role = UserRole.objects.get(user=request.user) 
        except UserRole.DoesNotExist: 
            user_role = None 
    
    # Get student object if exists
    student = None
    try:
        student = request.user.student
    except Student.DoesNotExist:
        pass
    
    context = {
        'user_role': user_role,
        'student': student,
        'recent_activities': ExeatRequest.objects.filter(student__user=request.user).order_by('-created_at')[:5],
    }
    
    # Add counts for all users
    if student:
        context.update({
            'total_requests': ExeatRequest.objects.filter(student=student).count(),
            'approved_requests': ExeatRequest.objects.filter(student=student, status='Approved').count(),
            'pending_requests': ExeatRequest.objects.filter(student=student, status='Pending').count(),
            'rejected_requests': ExeatRequest.objects.filter(student=student, status='Rejected').count(),
        })
    
    # Add department-specific counts for HOD
    if user_role and user_role.role == 'HeadOfDepartment':
        dept_requests = ExeatRequest.objects.filter(student__dept=user_role.department)
        context.update({
            'total_requests': dept_requests.count(),
            'approved_requests': dept_requests.filter(status='Approved').count(),
            'pending_requests': dept_requests.filter(status='Pending').count(),
            'rejected_requests': dept_requests.filter(status='Rejected').count(),
        })
    
    # Add pending approvals for staff
    if user_role and user_role.role != 'Student':
        if user_role.role == 'HeadOfDepartment':
            context['pending_approvals'] = ExeatRequest.objects.filter(
                student__dept=user_role.department, 
                approved_by_student_affairs=True,
                status='Pending'
            ).order_by('-created_at')[:5]
        elif user_role.role == 'HallWarden':
            context['pending_approvals'] = ExeatRequest.objects.filter(
                student__gender=user_role.gender,
                approved_by_hod=True,
                status='Pending'
            ).order_by('-created_at')[:5]
        elif user_role.role == 'StudentAffairs':
            context['pending_approvals'] = ExeatRequest.objects.filter(
                approved_by_student_affairs=False,
                status='Pending'
            ).order_by('-created_at')[:5]
    
    return render(request, 'home.html', context)


@login_required
def create_exeat_request(request):
    # user_role = UserRole.objects.get(user=request.user) 
    if request.method == 'POST':
        form = ExeatRequestForm(request.POST, request.FILES)
        form.instance.student = request.user.student
        if form.is_valid():
            exeat_request = form.save(commit=False)
            exeat_request.student = request.user.student
            exeat_request.approved_by_student_affairs = False
            exeat_request.approved_by_hod = False
            exeat_request.approved_by_warden = False
            
            if 'audio_file' in request.FILES:
                audio_file = request.FILES['audio_file']
                audio_file_path = os.path.join(settings.MEDIA_ROOT, audio_file.name)
                with open(audio_file_path, 'wb+') as destination:
                    for chunk in audio_file.chunks():
                        destination.write(chunk)

                # Transcribe the audio file directly
                exeat_request.reason = transcribe_audio(audio_file_path)

                # Remove the temporary file after transcription
                os.remove(audio_file_path)
            else:
                exeat_request.reason = form.cleaned_data['reason']
            
            exeat_request.save()

            # Send email notification to guardian
            send_guardian_notification(request.user.student, exeat_request)
            messages.success(request, "Your request has been submitted and will be processed by various officers")
            return redirect('home')
    else:
        form = ExeatRequestForm()
    return render(request, 'create_exeat_request.html', {'form': form})





import os
from google.cloud import speech

def transcribe_audio(audio_file_path):
    client = speech.SpeechClient()
    with open(audio_file_path, 'rb') as audio_file:
        content = audio_file.read()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.MP3,  # Change to MP3 encoding
        sample_rate_hertz=16000,
        language_code='en-US'
    )
    response = client.recognize(config=config, audio=audio)
    return response.results[0].alternatives[0].transcript if response.results else ''





@login_required
def hod_dashboard(request):
    user_role = UserRole.objects.get(user=request.user)
    if user_role.role != 'HeadOfDepartment':
        return redirect('home')
    
    # Debugging: Print department info
    print(f"HOD Department: {user_role.department}")
    
    requests = ExeatRequest.objects.filter(
    student__dept=user_role.department,
    approved_by_student_affairs=True,
    approved_by_hod=False,  # Only show not-yet-approved-by-HOD
    status='Pending'  # Or whatever status you use before HOD approval
).order_by('-created_at')
    
    # Debugging: Print the query results
    print(f"Found {requests.count()} requests for HOD review")
    for req in requests:
        print(f"Request ID: {req.id}, Student: {req.student.name}, Dept: {req.student.dept}, Status: {req.status}")
    
    return render(request, 'hod_dashboard.html', {
        'requests': requests,
        'user_role': user_role
    })

@login_required
def female_hall_warden_dashboard(request):
    user = request.user
    user_role = UserRole.objects.get(user=user)
    if user_role.role == 'HallWarden' and user_role.gender == 'Female':
        requests = ExeatRequest.objects.filter(
        student__gender='Female',  # or Male
        approved_by_student_affairs=True,
        approved_by_hod=True,
        approved_by_warden=False,  # Only show not-yet-approved-by-warden
        status='Pending Warden Approval'  # The status after HOD approval
    ).order_by('-created_at')
        
        # Get counts for dashboard cards
        pending_count = requests.count()
        approved_count = ExeatRequest.objects.filter(
            student__gender='Female',
            approved_by_warden=True,
            status='Approved'
        ).count()
        rejected_count = ExeatRequest.objects.filter(
            student__gender='Female',
            status='Rejected'
        ).count()
        pending_returns_count = ExeatRequest.objects.filter(
            student__gender='Female',
            approved_by_warden=True,
            return_date__isnull=True
        ).count()
        
        context = {
            'requests': requests,
            'pending_count': pending_count,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'pending_returns_count': pending_returns_count,
            'user_role': user_role
        }
        return render(request, 'female_hall_warden_dashboard.html', context)
    else:
        messages.error(request, "You do not have permission to view this page.")
        return redirect('home')

@login_required
def male_hall_warden_dashboard(request):
    user = request.user
    user_role = UserRole.objects.get(user=user)
    if user_role.role == 'HallWarden' and user_role.gender == 'Male':
        requests = ExeatRequest.objects.filter(
            student__gender='Male',  # or Male
            approved_by_student_affairs=True,
            approved_by_hod=True,
            approved_by_warden=False,  # Only show not-yet-approved-by-warden
            status='Pending Warden Approval'  # The status after HOD approval
        ).order_by('-created_at')
        
        # Get counts for dashboard cards
        pending_count = requests.count()
        approved_count = ExeatRequest.objects.filter(
            student__gender='Male',
            approved_by_warden=True,
            status='Approved'
        ).count()
        rejected_count = ExeatRequest.objects.filter(
            student__gender='Male',
            status='Rejected'
        ).count()
        pending_returns_count = ExeatRequest.objects.filter(
            student__gender='Male',
            approved_by_warden=True,
            return_date__isnull=True
        ).count()
        
        context = {
            'requests': requests,
            'pending_count': pending_count,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'pending_returns_count': pending_returns_count,
            'user_role': user_role
        }
        return render(request, 'male_hall_warden_dashboard.html', context)
    else:
        messages.error(request, "You do not have permission to view this page.")
        return redirect('home')



def send_guardian_notification(student, exeat_request):
    subject = 'Exeat Request Notification'
    message = f'Dear Guardian,\n\nYour ward, {student.user.student_id}, has initiated an exeat request. \n\nReason: {exeat_request.reason}\nStart Date: {exeat_request.start_date}\nEnd Date: {exeat_request.end_date}\n\nPlease contact the University for further details.\n\nBest regards,\nStudent Affairs'
    recipient_list = [student.guardian_email]
    send_mail(subject, message, settings.EMAIL_HOST_USER, recipient_list)




def custom_login_view(request):
    if request.method == 'POST':
        form = MatricNumberLoginForm(request.POST)
        if form.is_valid():
            matric_number = form.cleaned_data['matric_number']
            password = form.cleaned_data['password']
            user = authenticate(request, username=matric_number, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')
            else:
                form.add_error(None, 'Invalid matric number or password.')
    else:
        form = MatricNumberLoginForm()
    
    # Pass the form with any submitted data back to the template
    return render(request, 'login.html', {'form': form})



@login_required
def student_dashboard(request):
    try: 
        student = request.user.student
    except Student.DoesNotExist:
        return render(request, 'error.html', {'message': 'Student profile not found.'})
    
    # Only show requests approved by all three authorities
    fully_approved = ExeatRequest.objects.filter(
        student=student,
        status='Approved',
        approved_by_student_affairs=True,
        approved_by_hod=True,
        approved_by_warden=True
    ).order_by('-created_at')
    
    recent_activities = ExeatRequest.objects.filter(student=student).order_by('-created_at')[:5]
    pending_requests = ExeatRequest.objects.filter(student=student, status='Pending').order_by('-created_at')[:5]
    rejected_requests = ExeatRequest.objects.filter(student=student, status='Rejected').order_by('-created_at')[:5]

    context = {
        'recent_activities': recent_activities,
        'pending_requests': pending_requests,
        'approved_requests': fully_approved[:5],  # Only show fully approved requests
        'rejected_requests': rejected_requests
    }
    return render(request, 'studentDash.html', context)



@login_required 
def update_profile(request): 
    student = request.user 
    if request.method == 'POST': 
        form = UpdateProfileForm(request.POST, instance=student) 
        if form.is_valid(): 
            form.save() 
            return redirect('student_dashboard') 
    else: 
        form = UpdateProfileForm(instance=student) 
    return render(request, 'update_profile.html', {'form':form})




@login_required
def approve_exeat_request(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)
    
    # Check if user is HOD of the student's department
    if user_role.role == 'HeadOfDepartment' and exeat_request.student.dept == user_role.department:
        # Check if Student Affairs has already approved
        if not exeat_request.approved_by_student_affairs:
            messages.error(request, "This request hasn't been approved by Student Affairs yet")
            return redirect('hod_dashboard')
            
        # Approve the request
        exeat_request.approved_by_hod = True
        exeat_request.status = 'Pending'  # Keep as Pending for warden review
        exeat_request.save()
        
        
        
        messages.success(request, f"Exeat request for {exeat_request.student.name} has been approved and forwarded to {exeat_request.student.gender} Hall Warden")
    else:
        messages.error(request, "You don't have permission to approve this request")
    
    return redirect('hod_dashboard')



@login_required
def reject_exeat_request(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)

    # Initialize the appropriate redirect URL based on user role and gender
    redirect_url = 'home'
    if user_role.role == 'StudentAffairs':
        redirect_url = 'student_affairs_dashboard'
    elif user_role.role == 'HeadOfDepartment':
        if exeat_request.student.dept == user_role.department:
            redirect_url = 'hod_dashboard'
        else:
            messages.error(request, "You do not have permission to reject this request.")
            return redirect(redirect_url)
    elif user_role.role == 'HallWarden' and user_role.gender == 'Female':
        redirect_url = 'female_hall_warden_dashboard'
    elif user_role.role == 'HallWarden' and user_role.gender == 'Male':
        redirect_url = 'male_hall_warden_dashboard'
    else:
        messages.error(request, "You do not have permission to reject this request.")
        return redirect(redirect_url)
    
    # Handle form submission for rejection reason
    if request.method == 'POST':
        form = RejectionReasonForm(request.POST, instance=exeat_request)
        if form.is_valid():
            exeat_request = form.save(commit=False)
            exeat_request.status = 'Rejected'
            exeat_request.save()
            messages.success(request, f"Exeat request for {exeat_request.student.user.student_id} has been rejected.")
            return redirect(redirect_url)
    else:
        form = RejectionReasonForm(instance=exeat_request)

    return render(request, 'reject_exeat_request.html', {'form': form, 'exeat_request': exeat_request})




@login_required
def student_affairs_dashboard(request):
    user = request.user
    user_role = UserRole.objects.get(user=user)
    
    if user_role.role == 'StudentAffairs':
        # Retrieve all exeat requests that need to be processed by Student Affairs
        pending_exeat_requests = ExeatRequest.objects.filter(
            approved_by_student_affairs=False, 
            status='Pending'
        ).order_by('-created_at') 
        
        rejected_requests = ExeatRequest.objects.filter(
            approved_by_student_affairs=False, 
            status='Rejected'
        ).order_by('-created_at')
        
        context = {
            'pending_exeat_requests': pending_exeat_requests,
            'rejected_requests': rejected_requests,
            'user_role': user_role,
        }
        return render(request, 'student_affairs_dashboard.html', context)
    else:
        messages.error(request, "You do not have permission to view this page.")
        return render(request, 'access_denied.html')


@login_required
def approve_student_affairs_exeat_request(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)
    
    if user_role.role == 'StudentAffairs':
        exeat_request.approved_by_student_affairs = True
        exeat_request.status = 'Pending'  # Ensure status is Pending for HOD review
        exeat_request.save()
        messages.success(request, f"Exeat request for {exeat_request.student.user.student_id} has been approved by Student Affairs.")
    else:
        messages.error(request, "You do not have permission to approve this request.")
    
    return redirect('student_affairs_dashboard')

@login_required
def reject_student_affairs_exeat_request(request, request_id):
    # This view is no longer needed as we'll use the generic reject_exeat_request view
    return redirect('reject_exeat_request', request_id=request_id)


@login_required
def approve_exeat_request_female_warden(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)

    user_role = UserRole.objects.get(user=request.user)
    if user_role.role == 'HallWarden' and user_role.gender == 'Female':
        exeat_request.approved_by_warden = True
        exeat_request.save()
        messages.success(request, f"Exeat request for {exeat_request.student.user.student_id} has been approved by the Female Hall Warden.")
    else:
        messages.error(request, "You do not have permission to approve this request.")

    return redirect('female_hall_warden_dashboard')

@login_required
def reject_exeat_request_female_warden(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)

    user_role = UserRole.objects.get(user=request.user)
    if user_role.role == 'HallWarden' and user_role.gender == 'Female':
        exeat_request.status = 'Rejected'
        exeat_request.save()
        messages.success(request, f"Exeat request for {exeat_request.student.user.student_id} has been rejected by the Female Hall Warden.")
    else:
        messages.error(request, "You do not have permission to reject this request.")

    return redirect('female_hall_warden_dashboard')

@login_required
def approve_exeat_request_male_warden(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)

    user_role = UserRole.objects.get(user=request.user)
    if user_role.role == 'HallWarden' and user_role.gender == 'Male':
        exeat_request.approved_by_warden = True
        exeat_request.save()
        messages.success(request, f"Exeat request for {exeat_request.student.user.student_id} has been approved by the Male Hall Warden.")
    else:
        messages.error(request, "You do not have permission to approve this request.")

    return redirect('male_hall_warden_dashboard')

@login_required
def reject_exeat_request_male_warden(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)

    user_role = UserRole.objects.get(user=request.user)
    if user_role.role == 'HallWarden' and user_role.gender == 'Male':
        exeat_request.status = 'Rejected'
        exeat_request.save()
        messages.success(request, f"Exeat request for {exeat_request.student.user.student_id} has been rejected by the Female Hall Warden.")
    else:
        messages.error(request, "You do not have permission to reject this request.")

    return redirect('male_hall_warden_dashboard')



@login_required
def create_emergency_exeat_by_officer(request):
    user_role = UserRole.objects.get(user=request.user)
    if user_role.role != 'StudentAffairs':
        messages.error(request, "You do not have permission to create emergency exeat requests.")
        return redirect('home')

    if request.method == 'POST':
        form = EmergencyForm(request.POST, request.FILES)
        if form.is_valid():
            exeat_request = form.save(commit=False)
            exeat_request.emergency = True  # Mark as emergency
            exeat_request.approved_by_student_affairs = True  # Automatically approve
            exeat_request.status = 'Approved'  # Set status to approved
            exeat_request.save()
            messages.success(request, "Emergency exeat request has been created and approved.")
            return redirect('student_affairs_dashboard')
    else:
        form = EmergencyForm()
    return render(request, 'create_emergency_exeat_by_officer.html', {'form': form,'user_role':user_role})



@login_required
def pending_returns_female_warden(request):
    user_role = UserRole.objects.get(user=request.user)
    
    if user_role.role == 'HallWarden' and user_role.gender == 'Female':
        pending_returns = ExeatRequest.objects.filter(
            student__gender='Female', 
            approved_by_student_affairs=True, 
            approved_by_hod=True, 
            approved_by_warden=True, 
            return_date__isnull=True
        ).order_by('-start_date')
        
        context = {
            'pending_returns': pending_returns,
        }
        return render(request, 'pending_returns_female_warden.html', context)
    else:
        messages.error(request, "You do not have permission to view this page.")
        return redirect('home')

@login_required
def pending_returns_male_warden(request):
    user_role = UserRole.objects.get(user=request.user)
    
    if user_role.role == 'HallWarden' and user_role.gender == 'Male':
        pending_returns = ExeatRequest.objects.filter(
            student__gender='Male', 
            approved_by_student_affairs=True, 
            approved_by_hod=True, 
            approved_by_warden=True, 
            return_date__isnull=True
        ).order_by('-start_date')
        
        context = {
            'pending_returns': pending_returns,
        }
        return render(request, 'pending_returns_male_warden.html', context)
    else:
        messages.error(request, "You do not have permission to view this page.")
        return redirect('home')


@login_required
def mark_return_female_warden(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)
    
    if user_role.role == 'HallWarden' and user_role.gender == 'Female':
        exeat_request.return_date = timezone.now()
        exeat_request.save()
        messages.success(request, f"Return date for {exeat_request.student.user.student_id} has been updated.")
        return redirect('pending_returns_female_warden')
    else:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('home')

@login_required
def mark_return_male_warden(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)
    
    if user_role.role == 'HallWarden' and user_role.gender == 'Male':
        exeat_request.return_date = timezone.now()
        exeat_request.save()
        messages.success(request, f"Return date for {exeat_request.student.user.student_id} has been updated.")
        return redirect('pending_returns_male_warden')
    else:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('home')


from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse

@login_required
def exeat_slip(request, request_id):
    exeat_request = get_object_or_404(
        ExeatRequest, 
        id=request_id, 
        student__user=request.user,
        status='Approved',
        approved_by_student_affairs=True,
        approved_by_hod=True,
        approved_by_warden=True
    )
    
    return render(request, 'exeat_slip.html', {'exeat': exeat_request})

@login_required
def verify_exeat(request, request_id=None):
    if request_id:
        exeat_request = get_object_or_404(ExeatRequest, id=request_id)
        return render(request, 'verify_exeat.html', {'exeat': exeat_request})
    
    # For manual entry form
    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        if request_id:
            return redirect('verify_exeat', request_id=request_id)
    
    return render(request, 'verify_exeat_form.html')


@login_required
def request_detail(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)
    
    # Permission checks
    if user_role.role == 'Student':
        if exeat_request.student.user != request.user:
            raise PermissionDenied("You don't have permission to view this request")
    elif user_role.role == 'HeadOfDepartment':
        if exeat_request.student.dept != user_role.department:
            raise PermissionDenied("This request is not from your department")
    # Student Affairs and Wardens can view all requests
    
    return render(request, 'request_detail.html', {'request': exeat_request,'user_role': user_role})

@login_required
def approve_hod_exeat_request(request, request_id):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)
    
    if user_role.role == 'HeadOfDepartment' and exeat_request.student.dept == user_role.department:
        if not exeat_request.approved_by_student_affairs:
            messages.error(request, "Student Affairs hasn't approved this request yet")
            return redirect('hod_dashboard')
            
        exeat_request.approved_by_hod = True
        # exeat_request.hod_approval_date = timezone.now()  # Add this field to your model
        exeat_request.status = 'Pending Warden Approval'  # New status
        exeat_request.save()
        
        messages.success(request, f"Request approved and forwarded to {exeat_request.student.gender} Hall Warden")
    else:
        messages.error(request, "Permission denied")
    
    return redirect('hod_dashboard')

@login_required
def approve_female_warden_exeat_request(request, request_id):
    return _approve_warden_request(request, request_id, 'Female')

@login_required
def approve_male_warden_exeat_request(request, request_id):
    return _approve_warden_request(request, request_id, 'Male')

def _approve_warden_request(request, request_id, expected_gender):
    exeat_request = get_object_or_404(ExeatRequest, id=request_id)
    user_role = UserRole.objects.get(user=request.user)
    
    if (user_role.role == 'HallWarden' and 
        user_role.gender == expected_gender and
        exeat_request.student.gender == expected_gender):
        
        if not (exeat_request.approved_by_student_affairs and exeat_request.approved_by_hod):
            messages.error(request, "Request hasn't completed previous approvals")
            return redirect('female_hall_warden_dashboard' if expected_gender == 'Female' else 'male_hall_warden_dashboard')
            
        exeat_request.approved_by_warden = True
        # exeat_request.warden_approval_date = timezone.now()  # Add this field
        exeat_request.status = 'Approved'  # Final approval
        exeat_request.save()
        
        messages.success(request, "Exeat request fully approved")
    else:
        messages.error(request, "Permission denied")
    
    return redirect('female_hall_warden_dashboard' if expected_gender == 'Female' else 'male_hall_warden_dashboard')