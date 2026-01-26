from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

class CustomUserAdmin(UserAdmin):
    """Custom admin interface for User model."""
    
    # Fields to display in list view
    list_display = ('email', 'first_name', 'last_name', 'role', 'institution', 
                   'is_staff', 'is_active', 'date_joined')
    
    # Filter options
    list_filter = ('role', 'institution', 'is_staff', 'is_active', 'date_joined')
    
    # Search fields
    search_fields = ('email', 'first_name', 'last_name', 'institution', 'phone_number')
    
    # Ordering
    ordering = ('-date_joined',)
    
    # Fieldsets for edit view
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal Info'), {'fields': ('first_name', 'last_name', 'phone_number', 
                                        'profile_picture')}),
        (_('Professional Info'), {'fields': ('role', 'department', 'institution')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                      'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Preferences'), {'fields': ('notification_preferences',)}),
    )
    
    # Fieldsets for add view
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'role', 
                      'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )
    
    # Readonly fields
    readonly_fields = ('date_joined', 'last_login')
    
    # Action to make users active
    actions = ['make_active', 'make_inactive']
    
    def make_active(self, request, queryset):
        """Mark selected users as active."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users marked as active.')
    
    def make_inactive(self, request, queryset):
        """Mark selected users as inactive."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users marked as inactive.')
    
    make_active.short_description = _("Activate selected users")
    make_inactive.short_description = _("Deactivate selected users")

# Register the model
admin.site.register(User, CustomUserAdmin)
