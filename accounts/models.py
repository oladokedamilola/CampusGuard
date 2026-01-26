from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

# In accounts/models.py, add this at the top
from .managers import UserManager

# In User class, add:
objects = UserManager()
    
# Also update username field to use email
USERNAME_FIELD = 'email'
REQUIRED_FIELDS = ['first_name', 'last_name']

# And remove username field (since we're using email)
# AbstractUser already has username, we need to override it
username = None
email = models.EmailField(_('email address'), unique=True)

class User(AbstractUser):
    """
    Custom User model with role-based permissions for security surveillance system.
    """
    
    class Role(models.TextChoices):
        ADMIN = 'admin', _('System Administrator')
        SECURITY_MANAGER = 'security_manager', _('Security Manager')
        SECURITY_GUARD = 'security_guard', _('Security Guard')
        ICT_STAFF = 'ict_staff', _('ICT Staff')
        INSTITUTION_ADMIN = 'institution_admin', _('Institution Administrator')
        VIEWER = 'viewer', _('Viewer (Read Only)')
    
    # Custom fields
    role = models.CharField(
        max_length=50,
        choices=Role.choices,
        default=Role.VIEWER,
        verbose_name=_('User Role')
    )
    
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_('Phone Number')
    )
    
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Department')
    )
    
    institution = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Institution')
    )
    
    email_verified = models.BooleanField(
        default=False,
        verbose_name=_('Email Verified')
    )
    
    profile_picture = models.ImageField(
        upload_to='profiles/',
        null=True,
        blank=True,
        verbose_name=_('Profile Picture')
    )
    
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Notification Preferences')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']
        permissions = [
            ("view_dashboard", "Can view surveillance dashboard"),
            ("manage_cameras", "Can add/edit/delete cameras"),
            ("acknowledge_incidents", "Can acknowledge incidents"),
            ("generate_reports", "Can generate analytics reports"),
            ("configure_alerts", "Can configure alert rules"),
            ("manage_users", "Can manage users"),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    # Role-based permission methods
    def is_security_staff(self):
        """Check if user is in security team."""
        return self.role in [self.Role.SECURITY_MANAGER, self.Role.SECURITY_GUARD]
    
    def is_administrator(self):
        """Check if user has admin privileges."""
        return self.role in [self.Role.ADMIN, self.Role.SECURITY_MANAGER, self.Role.INSTITUTION_ADMIN]
    
    def can_manage_cameras(self):
        """Check if user can manage cameras."""
        return self.role in [self.Role.ADMIN, self.Role.SECURITY_MANAGER, self.Role.ICT_STAFF]
    
    def can_acknowledge_incidents(self):
        """Check if user can acknowledge incidents."""
        return self.role in [self.Role.ADMIN, self.Role.SECURITY_MANAGER, self.Role.SECURITY_GUARD]
    
    def can_view_analytics(self):
        """Check if user can view analytics."""
        return self.role in [self.Role.ADMIN, self.Role.SECURITY_MANAGER, 
                            self.Role.INSTITUTION_ADMIN, self.Role.ICT_STAFF]
    
    def can_manage_users(self):
        """Check if user can manage other users."""
        return self.role in [self.Role.ADMIN, self.Role.INSTITUTION_ADMIN]
    
    def get_permission_codes(self):
        """Get list of permission codes for this user's role."""
        permissions = []
        
        if self.is_administrator():
            permissions.extend(['view_dashboard', 'generate_reports'])
        
        if self.can_manage_cameras():
            permissions.append('manage_cameras')
        
        if self.can_acknowledge_incidents():
            permissions.append('acknowledge_incidents')
        
        if self.can_manage_users():
            permissions.append('manage_users')
        
        return permissions