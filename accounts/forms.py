from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from .models import User

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

class UserProfileForm(forms.ModelForm):
    """Form for users to edit their own profile."""
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone_number', 
                 'department', 'profile_picture')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all fields not required
        for field in self.fields.values():
            field.required = False

class LoginForm(forms.Form):
    """Login form using email instead of username."""
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )