# smart_surveillance/accounts/decorators.py
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import User
from django.shortcuts import redirect

def role_required(allowed_roles=None, redirect_url='dashboard:index'):
    """
    Decorator for views that checks if the user has a specific role.
    
    Usage:
    @role_required(allowed_roles=['admin', 'security_manager'])
    def my_view(request):
        ...
    """
    if allowed_roles is None:
        allowed_roles = []
    
    def check_role(user):
        if not user.is_authenticated:
            return False
        
        # Superuser can access everything
        if user.is_superuser:
            return True
        
        # Check if user's role is in allowed roles
        if user.role in allowed_roles:
            return True
        
        return False
    
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if check_role(request.user):
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, _('You do not have permission to access this page.'))
                return redirect(redirect_url)
        return wrapped_view
    
    return decorator

def role_redirect(view_func):
    """
    Decorator that redirects users based on their role.
    Used on the main dashboard index view.
    """
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.shortcuts import redirect
            return redirect('accounts:login')
        
        # Get the appropriate dashboard view based on role
        role = request.user.role
        
        # Map roles to their specific dashboard views
        role_dashboards = {
            User.Role.ADMIN: 'dashboard:admin_dashboard',
            User.Role.SECURITY_MANAGER: 'dashboard:security_manager_dashboard',
            User.Role.SECURITY_GUARD: 'dashboard:security_guard_dashboard',
            User.Role.ICT_STAFF: 'dashboard:ict_dashboard',
            User.Role.INSTITUTION_ADMIN: 'dashboard:institution_admin_dashboard',
            User.Role.VIEWER: 'dashboard:viewer_dashboard',
        }
        
        # If superuser but not specifically set as admin role
        if request.user.is_superuser and role not in role_dashboards:
            return redirect('dashboard:admin_dashboard')
        
        # Redirect to role-specific dashboard
        from django.shortcuts import redirect
        return redirect(role_dashboards.get(role, 'dashboard:viewer_dashboard'))
    
    return wrapped_view