# smart_surveillance/cameras/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Camera, CameraGroup, VideoFile, MediaUpload
from core.models import Location as CoreLocation
import os

class CameraForm(forms.ModelForm):
    """Form for creating/updating cameras."""
    
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False,
        help_text=_('Camera authentication password')
    )
    
    class Meta:
        model = Camera
        fields = [
            'name', 'location', 'camera_type', 'status', 'is_active',
            'connection_protocol', 'stream_url', 'ip_address', 'port',
            'username', 'password', 'resolution', 'fps', 'has_night_vision',
            'has_audio', 'field_of_view', 'motion_detection_enabled',
            'recording_enabled', 'detection_zones', 'manufacturer', 'model',
            'serial_number', 'installation_date', 'warranty_expiry', 'notes'
        ]
        widgets = {
            'location': forms.Select(attrs={'class': 'form-select'}),
            'camera_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'connection_protocol': forms.Select(attrs={'class': 'form-select'}),
            'detection_zones': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'JSON array of coordinates: [{"x1": 0, "y1": 0, "x2": 100, "y2": 100}]'
            }),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'installation_date': forms.DateInput(attrs={'type': 'date'}),
            'warranty_expiry': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Style all fields with Bootstrap classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
        
        # Make location queryset show only locations from user's institution
        # This will be implemented later when we have user context
    
    def clean_stream_url(self):
        """Validate stream URL."""
        stream_url = self.cleaned_data.get('stream_url')
        
        if stream_url:
            # Basic validation for RTSP/HTTP URLs
            if not (stream_url.startswith('rtsp://') or 
                   stream_url.startswith('http://') or 
                   stream_url.startswith('https://')):
                raise forms.ValidationError(
                    _('Stream URL must start with rtsp://, http://, or https://')
                )
        
        return stream_url
    
    def clean_port(self):
        """Validate port number."""
        port = self.cleaned_data.get('port')
        
        if port and (port < 1 or port > 65535):
            raise forms.ValidationError(
                _('Port must be between 1 and 65535')
            )
        
        return port

class CameraGroupForm(forms.ModelForm):
    """Form for creating/updating camera groups."""
    
    class Meta:
        model = CameraGroup
        fields = ['name', 'description', 'cameras']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'cameras': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

class CameraFilterForm(forms.Form):
    """Form for filtering cameras."""
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + list(Camera.Status.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    camera_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(Camera.CameraType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    location = forms.ModelChoiceField(
        queryset=CoreLocation.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    is_active = forms.ChoiceField(
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, IP, or serial...'
        })
    )
    
    
class VideoUploadForm(forms.ModelForm):
    """Form for uploading video files for processing."""
    
    class Meta:
        model = VideoFile
        fields = ['title', 'description', 'video_file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter video title (e.g., "Parking Lot - Friday Night")'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe what to analyze in this video...'
            }),
            'video_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'video/*,.mp4,.avi,.mov,.mkv,.flv'
            }),
        }
    
    def clean_video_file(self):
        """Validate video file upload."""
        video_file = self.cleaned_data.get('video_file')
        
        if video_file:
            # Check file size (max 500MB)
            max_size = 500 * 1024 * 1024  # 500MB
            if video_file.size > max_size:
                raise forms.ValidationError(
                    _('File size must be less than 500MB.')
                )
            
            # Check file extension
            valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
            ext = os.path.splitext(video_file.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError(
                    _('Unsupported file format. Supported formats: MP4, AVI, MOV, MKV, FLV, WEBM')
                )
        
        return video_file

class VideoProcessingForm(forms.Form):
    """Form for configuring video processing parameters."""
    
    DETECTION_TYPES = [
        ('motion', 'Motion Detection'),
        ('person', 'Person Detection'),
        ('vehicle', 'Vehicle Detection'),
        ('all', 'All Detections'),
    ]
    
    detection_type = forms.ChoiceField(
        choices=DETECTION_TYPES,
        initial='motion',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    sensitivity = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'type': 'range',
            'min': '1',
            'max': '10'
        })
    )
    
    draw_boxes = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    save_output = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    email_notification = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class MediaUploadForm(forms.ModelForm):
    """
    Form for uploading media (images/videos) for FastAPI processing.
    """
    
    # Detection type choices for FastAPI
    DETECTION_CHOICES = [
        ('person', 'Person Detection'),
        ('vehicle', 'Vehicle Detection'),
        ('face', 'Face Recognition'),
        ('weapon', 'Weapon Detection'),
        ('all', 'All Detections'),
    ]
    
    detection_types = forms.MultipleChoiceField(
        choices=DETECTION_CHOICES,
        initial=['person', 'vehicle'],
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'data-placeholder': 'Select detection types...'
        }),
        help_text=_('Select what types of objects to detect (Ctrl+Click for multiple)')
    )
    
    class Meta:
        model = MediaUpload
        fields = ['title', 'description', 'original_file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter media title (e.g., "Entrance Camera - Monday Morning")'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe what to analyze in this media...'
            }),
            'original_file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*,video/*,.jpg,.jpeg,.png,.bmp,.gif,.mp4,.avi,.mov,.mkv'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Style all fields with Bootstrap classes
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.update({'class': 'form-select'})
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({'class': 'form-control'})
            elif isinstance(field.widget, forms.ClearableFileInput):
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
    
    def clean_original_file(self):
        """Validate media file upload."""
        original_file = self.cleaned_data.get('original_file')
        
        if not original_file:
            raise forms.ValidationError(_('Please select a file to upload.'))
        
        # Check file size (max 500MB)
        max_size = 500 * 1024 * 1024  # 500MB
        if original_file.size > max_size:
            raise forms.ValidationError(
                _('File size must be less than 500MB.')
            )
        
        # Check file extension
        filename = original_file.name.lower()
        
        # Allowed image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']
        # Allowed video extensions
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
        
        allowed_extensions = image_extensions + video_extensions
        
        # Get file extension
        ext = os.path.splitext(filename)[1].lower()
        
        if ext not in allowed_extensions:
            raise forms.ValidationError(
                _('Unsupported file format. Supported formats: JPG, PNG, BMP, GIF, WebP, MP4, AVI, MOV, MKV, FLV, WebM')
            )
        
        # Check MIME type
        content_type = original_file.content_type
        
        allowed_mime_types = [
            'image/jpeg', 'image/png', 'image/bmp', 'image/gif', 'image/webp',
            'video/mp4', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska',
            'video/x-flv', 'video/webm'
        ]
        
        if content_type and content_type not in allowed_mime_types:
            # If content type detection fails, rely on extension
            if not any(filename.endswith(ext) for ext in allowed_extensions):
                raise forms.ValidationError(
                    _('Invalid file type. Please upload an image or video file.')
                )
        
        return original_file
    
    def save(self, commit=True):
        """
        Save the media upload instance and set media type based on file.
        """
        instance = super().save(commit=False)
        
        # Set media type based on file extension
        filename = self.cleaned_data['original_file'].name.lower()
        
        # Image extensions
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp']
        # Video extensions
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.webm']
        
        if any(filename.endswith(ext) for ext in image_extensions):
            instance.media_type = MediaUpload.MediaType.IMAGE
        elif any(filename.endswith(ext) for ext in video_extensions):
            instance.media_type = MediaUpload.MediaType.VIDEO
        
        if commit:
            instance.save()
        
        return instance


class MediaUploadFilterForm(forms.Form):
    """
    Form for filtering media uploads.
    """
    media_type = forms.ChoiceField(
        choices=[('', 'All Types')] + list(MediaUpload.MediaType.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    processing_status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + list(MediaUpload.ProcessingStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': 'From date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'placeholder': 'To date'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by title or description...'
        })
    )