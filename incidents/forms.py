from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Incident, IncidentComment, Evidence
from cameras.models import Camera, VideoFile

class IncidentForm(forms.ModelForm):
    """Form for creating/editing incidents."""
    
    class Meta:
        model = Incident
        fields = [
            'title', 'description', 'incident_type', 'severity',
            'camera', 'video_file', 'location_description',
            'gps_coordinates', 'confidence_score', 'assigned_to',
            'tags', 'requires_police_report', 'police_report_number',
            'notes'
        ]
        widgets = {
            'incident_type': forms.Select(attrs={'class': 'form-select'}),
            'severity': forms.Select(attrs={'class': 'form-select'}),
            'camera': forms.Select(attrs={'class': 'form-select'}),
            'video_file': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'location_description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'confidence_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '1',
                'step': '0.01'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'comma,separated,tags'
            }),
            'gps_coordinates': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'latitude,longitude'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Style all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
        
        # Filter cameras based on user's institution
        if user and not user.is_superuser:
            self.fields['camera'].queryset = Camera.objects.filter(
                location__institution=user.institution
            )
            self.fields['assigned_to'].queryset = user.__class__.objects.filter(
                institution=user.institution,
                role__in=['security_manager', 'security_guard']
            )
    
    def clean_gps_coordinates(self):
        """Validate GPS coordinates."""
        coords = self.cleaned_data.get('gps_coordinates')
        
        if coords:
            try:
                lat_str, lon_str = coords.split(',')
                lat = float(lat_str.strip())
                lon = float(lon_str.strip())
                
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    raise forms.ValidationError(
                        _('Invalid coordinates. Latitude must be between -90 and 90, '
                          'Longitude between -180 and 180.')
                    )
                
                return f"{lat},{lon}"
            
            except (ValueError, AttributeError):
                raise forms.ValidationError(
                    _('Enter coordinates as "latitude,longitude" (e.g., "6.5244,3.3792")')
                )
        
        return coords
    
    def clean_confidence_score(self):
        """Validate confidence score."""
        score = self.cleaned_data.get('confidence_score')
        
        if score is not None:
            if score < 0 or score > 1:
                raise forms.ValidationError(
                    _('Confidence score must be between 0.0 and 1.0')
                )
        
        return score

class IncidentFilterForm(forms.Form):
    """Form for filtering incidents."""
    
    STATUS_CHOICES = [('', 'All Status')] + list(Incident.Status.choices)
    SEVERITY_CHOICES = [('', 'All Severity')] + list(Incident.SeverityLevel.choices)
    TYPE_CHOICES = [('', 'All Types')] + list(Incident.IncidentType.choices)
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    severity = forms.ChoiceField(
        choices=SEVERITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    incident_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    camera = forms.ModelChoiceField(
        queryset=Camera.objects.all(),
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
    
    assigned_to = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by ID, title, description...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Only show users from same institution
            from accounts.models import User
            self.fields['assigned_to'].queryset = User.objects.filter(
                institution=user.institution,
                role__in=['security_manager', 'security_guard']
            )

class IncidentCommentForm(forms.ModelForm):
    """Form for adding comments to incidents."""
    
    class Meta:
        model = IncidentComment
        fields = ['comment', 'attachment', 'is_internal']
        widgets = {
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add your comment here...'
            }),
            'attachment': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
            'is_internal': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['attachment'].required = False
        self.fields['is_internal'].required = False

class EvidenceUploadForm(forms.ModelForm):
    """Form for uploading additional evidence."""
    
    class Meta:
        model = Evidence
        fields = ['evidence_type', 'file', 'description']
        widgets = {
            'evidence_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Describe this evidence...'
            }),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class IncidentBulkActionForm(forms.Form):
    """Form for bulk actions on incidents."""
    
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('acknowledge', 'Acknowledge Selected'),
        ('assign', 'Assign to User'),
        ('resolve', 'Mark as Resolved'),
        ('false_alarm', 'Mark as False Alarm'),
        ('delete', 'Delete Selected'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    assigned_user = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    resolution_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Resolution notes (optional)'
        })
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            from accounts.models import User
            self.fields['assigned_user'].queryset = User.objects.filter(
                institution=user.institution,
                role__in=['security_manager', 'security_guard']
            )