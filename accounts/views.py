# smart_surveillance/accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from django.utils import timezone
from .models import Invitation
from .forms import InvitationForm, RegistrationForm
from .email_utils import send_invitation_email, send_welcome_email

from django.utils import timezone

from .forms import LoginForm, UserProfileForm, CustomUserCreationForm
from .models import User, Invitation

def login_view(request):
    """Custom login view using email."""
    if request.user.is_authenticated:
        return redirect('dashboard:index') 
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data['remember_me']
            
            # Use the custom authentication backend
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                login(request, user)
                
                # Set session expiration
                if not remember_me:
                    request.session.set_expiry(0)  # Browser close
                
                messages.success(request, _('Login successful!'))
                
                # Redirect based on user role
                if user.role == User.Role.VIEWER:
                    return redirect('dashboard:viewer_dashboard')
                else:
                    return redirect('dashboard:index')
            else:
                messages.error(request, _('Invalid email or password.'))
        else:
            messages.error(request, _('Please correct the errors below.'))
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    """Logout view."""
    logout(request)
    messages.success(request, _('You have been logged out.'))
    return redirect('accounts:login')

@login_required
def profile_view(request):
    """View and edit user profile."""
    user = request.user
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, _('Profile updated successfully!'))
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=user)
    
    context = {
        'form': form,
        'user': user,
    }
    return render(request, 'accounts/profile.html', context)

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Class-based view for profile update."""
    model = User
    form_class = UserProfileForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, _('Profile updated successfully!'))
        return super().form_valid(form)

@login_required
def user_list_view(request):
    """List all users (admin only)."""
    if not request.user.can_manage_users():
        messages.error(request, _('You do not have permission to view this page.'))
        return redirect('dashboard:index')
    
    users = User.objects.all().order_by('-date_joined')
    
    # Filter by role if provided
    role_filter = request.GET.get('role')
    if role_filter:
        users = users.filter(role=role_filter)
    
    # Filter by institution if provided
    institution_filter = request.GET.get('institution')
    if institution_filter:
        users = users.filter(institution__icontains=institution_filter)
    
    # Get pending invitations (only show those created by the current user)
    pending_invitations = Invitation.objects.filter(
        invited_by=request.user,
        is_accepted=False,
        expires_at__gt=timezone.now()
    ).order_by('-created_at')
    
    # Get today's date at midnight
    today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Statistics
    stats = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'pending_invitations': pending_invitations.count(),
        'today_logins': User.objects.filter(last_login__gte=today).count(),
    }
    
    context = {
        'users': users,
        'invitations': pending_invitations,
        'roles': User.Role.choices,
        'total_users': stats['total_users'],
        'active_users': stats['active_users'],
        'pending_invitations': stats['pending_invitations'],
        'today_logins': stats['today_logins'],
    }
    return render(request, 'accounts/user_list.html', context)

@login_required
def user_detail_view(request, pk):
    """View user details."""
    user = get_object_or_404(User, pk=pk)
    
    # Check permission: admins can view anyone, others can only view themselves
    if not (request.user.can_manage_users() or request.user.pk == user.pk):
        messages.error(request, _('You do not have permission to view this user.'))
        return redirect('dashboard:index')
    
    context = {
        'viewed_user': user,
    }
    return render(request, 'accounts/user_detail.html', context)

def register_view(request):
    """User registration view (for institution admins to add users)."""
    if not request.user.can_manage_users():
        messages.error(request, _('You do not have permission to register users.'))
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password1'])
            
            # Set institution from admin's institution if not provided
            if not user.institution and request.user.institution:
                user.institution = request.user.institution
            
            user.save()
            
            # Send welcome email (to be implemented)
            messages.success(request, _('User registered successfully!'))
            return redirect('accounts:user_list')
    else:
        form = CustomUserCreationForm()
    
    context = {
        'form': form,
        'title': _('Register New User'),
    }
    return render(request, 'accounts/register.html', context)



@login_required
def invite_user_view(request):
    """Invite a new user."""
    if not request.user.can_manage_users():
        messages.error(request, _('You do not have permission to invite users.'))
        return redirect('dashboard:index')
    
    if request.method == 'POST':
        form = InvitationForm(request.POST, inviter=request.user)
        if form.is_valid():
            try:
                invitation = form.save()
                
                # Send invitation email
                if send_invitation_email(invitation, request):
                    messages.success(request, _('Invitation sent successfully!'))
                    return redirect('accounts:user_list')
                else:
                    messages.error(request, _('Failed to send invitation email. Please try again.'))
                    # Delete the invitation if email failed
                    invitation.delete()
                    
            except Exception as e:
                messages.error(request, _('An error occurred while sending the invitation.'))
    else:
        form = InvitationForm(inviter=request.user)
    
    context = {
        'form': form,
        'title': _('Invite User'),
    }
    return render(request, 'accounts/invite_user.html', context)

def register_invited_user_view(request, token):
    """Register a user who was invited."""
    # Get invitation
    invitation = get_object_or_404(
        Invitation.objects.select_related('invited_by'),
        token=token
    )
    
    # Check if invitation is valid
    if invitation.is_accepted:
        messages.error(request, _('This invitation has already been accepted.'))
        return redirect('accounts:login')
    
    if invitation.is_expired():
        messages.error(request, _('This invitation has expired.'))
        return redirect('accounts:login')
    
    # Check if user already exists (shouldn't happen with our validation)
    if User.objects.filter(email=invitation.email).exists():
        messages.error(request, _('A user with this email already exists.'))
        return redirect('accounts:login')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST, invitation=invitation)
        if form.is_valid():
            try:
                user = form.save()
                
                # Send welcome email
                send_welcome_email(user, request)
                
                # Auto-login the user
                from django.contrib.auth import login
                login(request, user)
                
                messages.success(request, _('Account created successfully! Welcome to CampusGuard AI.'))
                
                # Redirect based on user role
                if user.role == User.Role.VIEWER:
                    return redirect('dashboard:viewer_dashboard')
                else:
                    return redirect('dashboard:index')
                    
            except Exception as e:
                messages.error(request, _('An error occurred while creating your account.'))
    else:
        form = RegistrationForm(invitation=invitation)
    
    context = {
        'form': form,
        'invitation': invitation,
        'title': _('Complete Registration'),
    }
    return render(request, 'accounts/register_invited.html', context)

@login_required
def resend_invitation_view(request, pk):
    """Resend invitation to user."""
    if not request.user.can_manage_users():
        messages.error(request, _('You do not have permission to resend invitations.'))
        return redirect('dashboard:index')
    
    invitation = get_object_or_404(Invitation, pk=pk, invited_by=request.user)
    
    if invitation.is_accepted:
        messages.error(request, _('This invitation has already been accepted.'))
    elif invitation.is_expired():
        messages.error(request, _('This invitation has expired.'))
    else:
        if send_invitation_email(invitation, request):
            messages.success(request, _('Invitation resent successfully!'))
        else:
            messages.error(request, _('Failed to resend invitation.'))
    
    return redirect('accounts:user_list')

@login_required
def cancel_invitation_view(request, pk):
    """Cancel a pending invitation."""
    if not request.user.can_manage_users():
        messages.error(request, _('You do not have permission to cancel invitations.'))
        return redirect('dashboard:index')
    
    invitation = get_object_or_404(Invitation, pk=pk, invited_by=request.user)
    
    if not invitation.is_accepted:
        invitation.delete()
        messages.success(request, _('Invitation cancelled successfully.'))
    else:
        messages.error(request, _('Cannot cancel an accepted invitation.'))
    
    return redirect('accounts:user_list')