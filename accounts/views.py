# smart_surveillance/accounts/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.generic import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from .forms import LoginForm, UserProfileForm, CustomUserCreationForm
from .models import User

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
    
    context = {
        'users': users,
        'roles': User.Role.choices,
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