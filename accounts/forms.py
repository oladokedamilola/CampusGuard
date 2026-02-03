# smart_surveillance/accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User

from django.utils import timezone
from django.utils.crypto import get_random_string
from .models import Invitation
import uuid

class LoginForm(forms.Form):
    """Custom login form using email."""
    email = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email',
            'autofocus': True,
        })
    )
    
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        label=_('Remember me'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        """Custom validation for login."""
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if email and password:
            # Check if user exists
            try:
                user = User.objects.get(email=email)
                if not user.is_active:
                    raise forms.ValidationError(
                        _('This account is inactive. Please contact an administrator.')
                    )
            except User.DoesNotExist:
                # Don't reveal that user doesn't exist for security
                pass
        
        return cleaned_data

class CustomUserCreationForm(UserCreationForm):
    """Form for creating new users."""
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'institution')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email required
        self.fields['email'].required = True
        # Style all fields with Bootstrap classes
        for field_name, field in self.fields.items():
            if field_name != 'role':
                field.widget.attrs.update({'class': 'form-control'})


class CustomUserChangeForm(UserChangeForm):
    """Form for updating existing users."""
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'phone_number',
                 'department', 'institution', 'profile_picture', 
                 'notification_preferences', 'is_active')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'notification_preferences': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style all fields with Bootstrap classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

# smart_surveillance/accounts/forms.py (updated UserProfileForm)
class UserProfileForm(forms.ModelForm):
    """Form for users to edit their own profile."""
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone_number', 
                 'department', 'institution', 'profile_picture')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+255 XXX XXX XXX'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your department'
            }),
            'institution': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your institution'
            }),
            'profile_picture': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields not required except names
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True
        for field_name, field in self.fields.items():
            if field_name not in ['first_name', 'last_name']:
                field.required = False
                
                


class InvitationForm(forms.ModelForm):
    """Form for inviting new users."""
    
    class Meta:
        model = Invitation
        fields = ('email', 'role', 'institution', 'department')
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter email address'
            }),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'institution': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter institution name'
            }),
            'department': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter department name'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.inviter = kwargs.pop('inviter', None)
        super().__init__(*args, **kwargs)
        
        # Style all fields
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                if 'class' not in field.widget.attrs:
                    if isinstance(field.widget, forms.Select):
                        field.widget.attrs['class'] = 'form-select'
                    else:
                        field.widget.attrs['class'] = 'form-control'
    
    def clean_email(self):
        """Check if email is already registered or invited."""
        email = self.cleaned_data['email']
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(_('A user with this email already exists.'))
        
        # Check if there's a pending invitation
        if Invitation.objects.filter(
            email=email, 
            is_accepted=False,
            expires_at__gt=timezone.now()
        ).exists():
            raise forms.ValidationError(_('This email has already been invited.'))
        
        return email
    
    def save(self, commit=True):
        """Save invitation with generated token and expiry."""
        invitation = super().save(commit=False)
        invitation.invited_by = self.inviter
        
        # Generate unique token
        invitation.token = str(uuid.uuid4())
        
        # Set expiry (7 days from now)
        invitation.expires_at = timezone.now() + timezone.timedelta(days=7)
        
        if commit:
            invitation.save()
        
        return invitation

class RegistrationForm(forms.ModelForm):
    """Form for invited users to complete registration."""
    
    password1 = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password'
        })
    )
    
    password2 = forms.CharField(
        label=_('Confirm Password'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone_number')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your last name'
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+255 XXX XXX XXX'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.invitation = kwargs.pop('invitation', None)
        super().__init__(*args, **kwargs)
        
        if self.invitation:
            # Pre-fill some fields from invitation
            self.fields['first_name'].required = True
            self.fields['last_name'].required = True
    
    def clean_password2(self):
        """Check that passwords match."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_('Passwords do not match.'))
        
        return password2
    
    def save(self, commit=True):
        """Create user from invitation."""
        user = super().save(commit=False)
        user.email = self.invitation.email
        user.role = self.invitation.role
        user.institution = self.invitation.institution
        user.department = self.invitation.department
        user.set_password(self.cleaned_data['password1'])
        user.email_verified = True
        
        if commit:
            user.save()
            # Mark invitation as accepted
            self.invitation.accept(user)
        
        return user