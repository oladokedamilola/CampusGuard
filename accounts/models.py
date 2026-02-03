# smart_surveillance/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from .managers import UserManager

import uuid
from django.utils import timezone
from django.conf import settings

class User(AbstractUser):
    """
    Custom User model with role-based permissions for security surveillance system.
    """
    
    # IMPORTANT: Remove username field and make email the username field
    username = None  # Remove username field
    email = models.EmailField(_('email address'), unique=True)
    
    # Override the USERNAME_FIELD to use email
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    # Use custom manager
    objects = UserManager()
    
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
    


class Invitation(models.Model):
    """Model for tracking user invitations."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(
        max_length=50,
        choices=User.Role.choices,
        verbose_name=_('Role')
    )
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='invitations_sent',
        verbose_name=_('Invited by')
    )
    institution = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_('Institution')
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('Department')
    )
    
    # Status fields
    token = models.CharField(max_length=100, unique=True, db_index=True)
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invitations_accepted',
        verbose_name=_('Accepted by')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = _('Invitation')
        verbose_name_plural = _('Invitations')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['email']),
            models.Index(fields=['is_accepted']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Invitation for {self.email} ({self.get_role_display()})"
    
    def is_expired(self):
        """Check if the invitation has expired."""
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if invitation is still valid (not accepted and not expired)."""
        return not self.is_accepted and not self.is_expired()
    
    def get_role_display(self):
        """Get the display name for the role."""
        return dict(User.Role.choices)[self.role]
    
    def accept(self, user):
        """Mark invitation as accepted."""
        self.is_accepted = True
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save()