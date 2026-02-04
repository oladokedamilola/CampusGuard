# smart_surveillance/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import uuid

from .models import User, Invitation
from .email_utils import send_invitation_email, send_welcome_email


class CustomUserAdmin(UserAdmin):
    """Custom admin interface for User model."""
    
    # Fields to display in list view
    list_display = ('email', 'first_name', 'last_name', 'role_badge', 'institution', 
                   'department', 'is_active', 'email_verified_badge', 'date_joined', 'invite_action')
    
    # Filter options
    list_filter = ('role', 'institution', 'department', 'is_active', 'email_verified', 'date_joined')
    
    # Search fields
    search_fields = ('email', 'first_name', 'last_name', 'institution', 'department', 'phone_number')
    
    # Ordering
    ordering = ('-date_joined',)
    
    # Fieldsets for edit view
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name', 'phone_number', 
                                        'profile_picture')}),
        (_('Professional Info'), {'fields': ('role', 'department', 'institution')}),
        (_('Verification'), {'fields': ('email_verified',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                      'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'created_at')}),
        (_('Preferences'), {'fields': ('notification_preferences',)}),
    )
    
    # Fieldsets for add view
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 'department', 'institution',
                      'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )
    
    # Readonly fields
    readonly_fields = ('date_joined', 'last_login', 'created_at')
    
    # Admin actions - must be a list of strings (method names)
    actions = ['make_active', 'make_inactive', 'send_welcome_email', 'change_role_to_viewer',
              'mark_email_verified', 'mark_email_unverified']
    
    def role_badge(self, obj):
        """Display role as colored badge."""
        colors = {
            User.Role.ADMIN: '#dc3545',  # Red
            User.Role.MANAGER: '#0d6efd',  # Blue
            User.Role.VIEWER: '#198754',  # Green
        }
        color = colors.get(obj.role, '#6c757d')  # Gray default
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: 500;">{}</span>',
            color, obj.get_role_display()
        )
    role_badge.short_description = _('Role')
    role_badge.admin_order_field = 'role'
    
    def email_verified_badge(self, obj):
        """Display email verification status."""
        if obj.email_verified:
            return format_html(
                '<span style="color: #198754; font-weight: bold;">✓ {}</span>',
                _('Verified')
            )
        else:
            return format_html(
                '<span style="color: #dc3545; font-weight: bold;">✗ {}</span>',
                _('Not Verified')
            )
    email_verified_badge.short_description = _('Email Verified')
    
    def invite_action(self, obj):
        """Add invite button for users who haven't verified email."""
        if not obj.email_verified:
            return format_html(
                '<a class="button" href="{}" style="background-color: #0d6efd; color: white; '
                'padding: 4px 12px; text-decoration: none; border-radius: 4px; font-size: 12px;">'
                '📧 Send Invite</a>',
                reverse('admin:resend_invitation', args=[obj.id])
            )
        return format_html('<span style="color: #198754;">✓</span>')
    invite_action.short_description = _('Actions')
    
    # Admin action methods
    def make_active(self, request, queryset):
        """Mark selected users as active."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) marked as active.', messages.SUCCESS)
    make_active.short_description = _("✅ Activate selected users")
    
    def make_inactive(self, request, queryset):
        """Mark selected users as inactive."""
        # Don't deactivate yourself
        if request.user in queryset:
            self.message_user(request, 'You cannot deactivate yourself!', messages.ERROR)
            queryset = queryset.exclude(id=request.user.id)
        
        updated = queryset.update(is_active=False)
        if updated:
            self.message_user(request, f'{updated} user(s) marked as inactive.', messages.SUCCESS)
    make_inactive.short_description = _("⛔ Deactivate selected users")
    
    def send_welcome_email(self, request, queryset):
        """Send welcome email to selected users."""
        for user in queryset:
            send_welcome_email(user, request)
        
        self.message_user(request, 
                         f'Welcome emails sent to {queryset.count()} user(s).', 
                         messages.SUCCESS)
    send_welcome_email.short_description = _("📧 Send welcome email")
    
    def change_role_to_viewer(self, request, queryset):
        """Change selected users' role to Viewer."""
        # Don't allow changing own role to viewer
        if request.user in queryset:
            self.message_user(request, 'You cannot change your own role!', messages.WARNING)
            queryset = queryset.exclude(id=request.user.id)
        
        updated = queryset.update(role=User.Role.VIEWER)
        if updated:
            self.message_user(request, 
                             f'{updated} user(s) changed to Viewer role.', 
                             messages.SUCCESS)
    change_role_to_viewer.short_description = _("👁️ Change role to Viewer")
    
    def mark_email_verified(self, request, queryset):
        """Mark selected users' email as verified."""
        updated = queryset.update(email_verified=True)
        self.message_user(request, 
                         f'{updated} user(s) marked as email verified.', 
                         messages.SUCCESS)
    mark_email_verified.short_description = _("✓ Mark email as verified")
    
    def mark_email_unverified(self, request, queryset):
        """Mark selected users' email as unverified."""
        updated = queryset.update(email_verified=False)
        self.message_user(request, 
                         f'{updated} user(s) marked as email unverified.', 
                         messages.SUCCESS)
    mark_email_unverified.short_description = _("✗ Mark email as unverified")
    
    # Custom admin views
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:user_id>/resend-invitation/', 
                 self.admin_site.admin_view(self.resend_invitation_view),
                 name='resend_invitation'),
        ]
        return custom_urls + urls
    
    def resend_invitation_view(self, request, user_id):
        """Resend invitation email to a specific user."""
        try:
            user = User.objects.get(id=user_id)
            
            # Check if invitation already exists
            invitation = Invitation.objects.filter(email=user.email, is_accepted=False).first()
            
            if not invitation or invitation.is_expired():
                # Create new invitation
                invitation = Invitation.objects.create(
                    email=user.email,
                    role=user.role,
                    invited_by=request.user,
                    institution=user.institution or '',
                    department=user.department or '',
                    token=str(uuid.uuid4()),
                    expires_at=timezone.now() + timedelta(days=2)
                )
            else:
                # Update existing invitation
                invitation.token = str(uuid.uuid4())
                invitation.expires_at = timezone.now() + timedelta(days=2)
                invitation.sent_at = None  # Reset sent_at so we know it was resent
                invitation.save()
            
            # Send email
            if send_invitation_email(invitation, request):
                user.email_verified = False
                user.save()
                messages.success(request, 
                               f'Invitation email sent to {user.email}')
            else:
                messages.error(request, 
                             f'Failed to send invitation email to {user.email}')
                
        except User.DoesNotExist:
            messages.error(request, 'User not found')
        
        return redirect('admin:accounts_user_changelist')


class InvitationAdmin(admin.ModelAdmin):
    """Admin interface for Invitation model."""
    
    # RENAME: Changed from 'actions' to 'quick_actions' to avoid conflict
    list_display = ('email', 'role_badge', 'invited_by', 'status_badge', 
                   'created_at', 'expires_in', 'quick_actions')
    
    list_filter = ('role', 'is_accepted', 'created_at', 'invited_by')
    
    search_fields = ('email', 'invited_by__email', 'invited_by__first_name', 
                    'invited_by__last_name', 'institution', 'department')
    
    readonly_fields = ('token', 'created_at', 'expires_at', 'sent_at', 
                      'accepted_at', 'accepted_by', 'invited_by', 'status_display')
    
    fieldsets = (
        (_('Invitation Details'), {
            'fields': ('email', 'role', 'institution', 'department')
        }),
        (_('Inviter'), {
            'fields': ('invited_by',)
        }),
        (_('Status'), {
            'fields': ('status_display', 'is_accepted', 'accepted_at', 'accepted_by')
        }),
        (_('Technical Details'), {
            'fields': ('token', 'created_at', 'expires_at', 'sent_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Admin actions - must be a list of strings (method names)
    actions = ['resend_invitations', 'delete_expired', 'mark_as_accepted']
    
    def role_badge(self, obj):
        """Display role as colored badge."""
        colors = {
            User.Role.ADMIN: '#dc3545',  # Red
            User.Role.MANAGER: '#0d6efd',  # Blue
            User.Role.VIEWER: '#198754',  # Green
        }
        color = colors.get(obj.role, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 10px; font-size: 11px;">{}</span>',
            color, obj.get_role_display()
        )
    role_badge.short_description = _('Role')
    role_badge.admin_order_field = 'role'
    
    def status_badge(self, obj):
        """Display invitation status as badge."""
        if obj.is_accepted:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px; font-weight: 500;">✓ Accepted</span>'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="background-color: #6c757d; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px;">⌛ Expired</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #0d6efd; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px;">📧 Active</span>'
            )
    status_badge.short_description = _('Status')
    
    def expires_in(self, obj):
        """Show how long until expiration."""
        if obj.is_accepted:
            return format_html('<span style="color: #198754;">✓ Accepted</span>')
        
        now = timezone.now()
        if obj.expires_at > now:
            delta = obj.expires_at - now
            if delta.days > 0:
                return format_html('<span style="color: #0d6efd;">{} days</span>', delta.days)
            else:
                hours = delta.seconds // 3600
                return format_html('<span style="color: #ffc107;">{} hours</span>', hours)
        else:
            return format_html('<span style="color: #dc3545;">Expired</span>')
    expires_in.short_description = _('Expires In')
    
    # RENAMED: Changed from 'actions' to 'quick_actions'
    def quick_actions(self, obj):
        """Action buttons for each invitation."""
        if not obj.is_accepted and not obj.is_expired():
            return format_html(
                '<a href="{}" style="background-color: #0d6efd; color: white; '
                'padding: 4px 8px; text-decoration: none; border-radius: 4px; '
                'font-size: 12px; margin-right: 5px;">Resend</a>',
                reverse('admin:accounts_invitation_resend', args=[obj.id])
            )
        return '-'
    quick_actions.short_description = _('Actions')
    
    def status_display(self, obj):
        """Detailed status display for edit view."""
        if obj.is_accepted:
            return format_html(
                '<div style="padding: 10px; background-color: #d4edda; border-radius: 5px;">'
                '<strong>Accepted</strong><br>'
                'Accepted by: {}<br>'
                'Accepted at: {}'
                '</div>',
                obj.accepted_by.get_full_name() if obj.accepted_by else 'Unknown',
                obj.accepted_at.strftime('%Y-%m-%d %H:%M:%S') if obj.accepted_at else 'N/A'
            )
        elif obj.is_expired():
            return format_html(
                '<div style="padding: 10px; background-color: #f8d7da; border-radius: 5px;">'
                '<strong>Expired</strong><br>'
                'Expired at: {}'
                '</div>',
                obj.expires_at.strftime('%Y-%m-%d %H:%M:%S')
            )
        else:
            return format_html(
                '<div style="padding: 10px; background-color: #d1ecf1; border-radius: 5px;">'
                '<strong>Active</strong><br>'
                'Expires at: {}<br>'
                'Sent at: {}'
                '</div>',
                obj.expires_at.strftime('%Y-%m-%d %H:%M:%S'),
                obj.sent_at.strftime('%Y-%m-%d %H:%M:%S') if obj.sent_at else 'Not sent yet'
            )
    status_display.short_description = _('Status Details')
    
    # Admin action methods
    def resend_invitations(self, request, queryset):
        """Resend invitation emails for selected invitations."""
        count = 0
        for invitation in queryset:
            if not invitation.is_accepted:
                # Update token and expiration
                invitation.token = str(uuid.uuid4())
                invitation.expires_at = timezone.now() + timedelta(days=2)
                invitation.save()
                
                # Send email
                if send_invitation_email(invitation, request):
                    count += 1
        
        if count > 0:
            self.message_user(request, 
                             f'{count} invitation(s) resent successfully.', 
                             messages.SUCCESS)
        else:
            self.message_user(request, 
                             'No invitations were resent (all were already accepted or failed).', 
                             messages.WARNING)
    resend_invitations.short_description = _("📧 Resend selected invitations")
    
    def delete_expired(self, request, queryset):
        """Delete expired invitations."""
        expired = queryset.filter(is_accepted=False, expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        self.message_user(request, 
                         f'{count} expired invitation(s) deleted.', 
                         messages.SUCCESS)
    delete_expired.short_description = _("🗑️ Delete expired invitations")
    
    def mark_as_accepted(self, request, queryset):
        """Manually mark invitations as accepted (for testing/cleanup)."""
        for invitation in queryset:
            if not invitation.is_accepted:
                invitation.is_accepted = True
                invitation.accepted_at = timezone.now()
                invitation.save()
        
        self.message_user(request, 
                         f'{queryset.count()} invitation(s) marked as accepted.', 
                         messages.SUCCESS)
    mark_as_accepted.short_description = _("✓ Mark as accepted")
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('invited_by', 'accepted_by')
    
    # Custom URL for resend action
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<uuid:invitation_id>/resend/', 
                 self.admin_site.admin_view(self.resend_single_invitation),
                 name='accounts_invitation_resend'),
        ]
        return custom_urls + urls
    
    def resend_single_invitation(self, request, invitation_id):
        """Resend a single invitation."""
        try:
            invitation = Invitation.objects.get(id=invitation_id)
            if not invitation.is_accepted:
                # Update token
                invitation.token = str(uuid.uuid4())
                invitation.expires_at = timezone.now() + timedelta(days=2)
                invitation.save()
                
                if send_invitation_email(invitation, request):
                    messages.success(request, f'Invitation resent to {invitation.email}')
                else:
                    messages.error(request, f'Failed to resend invitation to {invitation.email}')
            else:
                messages.warning(request, 'Invitation has already been accepted')
                
        except Invitation.DoesNotExist:
            messages.error(request, 'Invitation not found')
        
        return redirect('admin:accounts_invitation_changelist')


# Register the models
admin.site.register(User, CustomUserAdmin)
admin.site.register(Invitation, InvitationAdmin)