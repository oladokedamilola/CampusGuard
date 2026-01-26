from django import forms
from django.utils.translation import gettext_lazy as _
from .models import AlertRule, NotificationPreference, Alert
from incidents.models import Incident
from cameras.models import Camera

class AlertRuleForm(forms.ModelForm):
    """Form for creating/editing alert rules."""
    
    class Meta:
        model = AlertRule
        fields = [
            'name', 'description', 'is_active', 'trigger_type',
            'condition_operator', 'condition_value',
            'incident_types', 'severity_levels', 'camera_ids',
            'location_ids', 'start_time', 'end_time', 'days_of_week',
            'channels', 'message_template', 'email_template',
            'recipient_roles', 'specific_recipients',
            'cooldown_minutes', 'max_alerts_per_day', 'priority'
        ]
        widgets = {
            'trigger_type': forms.Select(attrs={'class': 'form-select'}),
            'condition_operator': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'channels': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'recipient_roles': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'specific_recipients': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'days_of_week': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'incident_types': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'severity_levels': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'message_template': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'email_template': forms.Textarea(attrs={'rows': 6, 'class': 'form-control'}),
            'cooldown_minutes': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_alerts_per_day': forms.NumberInput(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'camera_ids': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'location_ids': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set choices for multi-select fields
        from incidents.models import Incident
        from accounts.models import User
        
        self.fields['incident_types'].choices = Incident.IncidentType.choices
        self.fields['severity_levels'].choices = Incident.SeverityLevel.choices
        self.fields['recipient_roles'].choices = User.Role.choices
        
        # Camera and location choices
        self.fields['camera_ids'].queryset = Camera.objects.all()
        from core.models import Location
        self.fields['location_ids'].queryset = Location.objects.all()
        
        # Days of week choices
        self.fields['days_of_week'].choices = [
            (0, 'Sunday'), (1, 'Monday'), (2, 'Tuesday'),
            (3, 'Wednesday'), (4, 'Thursday'), (5, 'Friday'),
            (6, 'Saturday')
        ]
        
        # Channel choices
        self.fields['channels'].choices = [
            ('email', 'Email'),
            ('in_app', 'In-App Notification'),
        ]

class NotificationPreferenceForm(forms.ModelForm):
    """Form for user notification preferences."""
    
    class Meta:
        model = NotificationPreference
        fields = [
            'email_enabled', 'in_app_enabled',
            'severity_preferences', 'quiet_hours_start',
            'quiet_hours_end', 'receive_digest', 'digest_time'
        ]
        widgets = {
            'email_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'in_app_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'receive_digest': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quiet_hours_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'quiet_hours_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'digest_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'severity_preferences': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        from incidents.models import Incident
        self.fields['severity_preferences'].choices = Incident.SeverityLevel.choices

class AlertFilterForm(forms.Form):
    """Form for filtering alerts."""
    
    STATUS_CHOICES = [('', 'All Status')] + list(Alert.AlertStatus.choices)
    TYPE_CHOICES = [('', 'All Types')] + list(Alert.AlertType.choices)
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    alert_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    read_status = forms.ChoiceField(
        choices=[('', 'All'), ('read', 'Read'), ('unread', 'Unread')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search alerts...'
        })
    )