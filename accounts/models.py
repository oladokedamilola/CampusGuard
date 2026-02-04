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
    Custom User model for CampusGuard AI - Evidence Intelligence Platform.
    """
    
    # IMPORTANT: Remove username field and make email the username field
    username = None  # Remove username field
    email = models.EmailField(_('email address'), unique=True)
    
    # Override the USERNAME_FIELD to use email
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    # Use custom manager
    objects = UserManager()
    
    # Simplified roles for our new plan
    class Role(models.TextChoices):
        ADMIN = 'admin', _('System Administrator')
        MANAGER = 'manager', _('Security Manager')
        VIEWER = 'viewer', _('Viewer/Reporter')
    
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
    
    # Notification preferences for incident alerts
    notification_preferences = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_('Notification Preferences'),
        help_text=_('User preferences for notifications (email, SMS, etc.)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']
        permissions = [
            ("invite_users", "Can invite new users to the system"),
            ("view_reports", "Can view incident reports"),
            ("create_reports", "Can create incident reports"),
            ("process_reports", "Can process and analyze incident reports"),
            ("manage_cases", "Can manage investigation cases"),
            ("view_analytics", "Can view analytics dashboard"),
            ("export_data", "Can export incident data"),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"
    
    # ===========================================
    # Role-based permission methods (Simplified)
    # ===========================================
    
    def is_admin(self):
        """Check if user is admin."""
        return self.role == self.Role.ADMIN
    
    def is_manager(self):
        """Check if user is manager (security personnel)."""
        return self.role == self.Role.MANAGER
    
    def is_viewer(self):
        """Check if user is viewer/reporter."""
        return self.role == self.Role.VIEWER
    
    def can_invite_users(self):
        """Check if user can invite new users."""
        return self.is_admin()
    
    def can_create_reports(self):
        """Check if user can create incident reports."""
        return True  # All authenticated users can report incidents
    
    def can_view_all_reports(self):
        """Check if user can view all incident reports (not just their own)."""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER]
    
    def can_process_reports(self):
        """Check if user can process and analyze incident reports."""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER]
    
    def can_manage_cases(self):
        """Check if user can manage investigation cases."""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER]
    
    def can_view_analytics(self):
        """Check if user can view analytics dashboard."""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER]
    
    def can_export_data(self):
        """Check if user can export incident data."""
        return self.role in [self.Role.ADMIN, self.Role.MANAGER]
    
    def get_permission_codes(self):
        """Get list of permission codes for this user's role."""
        permissions = []
        
        # Base permissions for all users
        permissions.append('create_reports')
        
        # Admin permissions
        if self.is_admin():
            permissions.extend([
                'invite_users', 
                'view_reports',
                'process_reports',
                'manage_cases',
                'view_analytics',
                'export_data'
            ])
        
        # Manager permissions
        elif self.is_manager():
            permissions.extend([
                'view_reports',
                'process_reports',
                'manage_cases',
                'view_analytics',
                'export_data'
            ])
        
        # Viewer permissions (only create and view own reports)
        elif self.is_viewer():
            permissions.append('view_reports')  # Only their own
        
        return permissions
    
    def get_assigned_department_reports(self):
        """For managers: Get reports from their department."""
        if self.is_manager() and self.department:
            # This would filter reports by department
            # Assuming Incident model has a 'department' field
            return None  # Placeholder - actual implementation depends on Incident model
        return None


class Invitation(models.Model):
    """Model for tracking user invitations (invite-only system)."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(
        max_length=50,
        choices=User.Role.choices,
        default=User.Role.VIEWER,
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
    
    # Token for secure invitation link
    token = models.CharField(max_length=100, unique=True, db_index=True)
    
    # Status fields
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
    expires_at = models.DateTimeField()  # 48 hours from creation
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
        """Mark invitation as accepted and link to user."""
        if not self.is_valid():
            raise ValueError("Invitation is no longer valid")
        
        self.is_accepted = True
        self.accepted_at = timezone.now()
        self.accepted_by = user
        self.save()
        
        # Update user's institution/department if provided in invitation
        if self.institution and not user.institution:
            user.institution = self.institution
        
        if self.department and not user.department:
            user.department = self.department
        
        user.save()