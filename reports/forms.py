# smart_surveillance/reports/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta

from .models import IncidentReport, IncidentImage, IncidentCategory, IncidentLocation, IncidentUpdate

class MultipleFileInput(forms.ClearableFileInput):
    """Custom widget for multiple file uploads."""
    def __init__(self, attrs=None):
        super().__init__(attrs)
        if attrs is None:
            attrs = {}
        attrs['multiple'] = True
        self.attrs.update(attrs)
    
    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return files.get(name)

class IncidentReportForm(forms.ModelForm):
    """Form for creating/editing incident reports."""
    
    images = forms.FileField(
        label=_('Upload Images'),
        widget=MultipleFileInput(),
        required=False,
        help_text=_('Upload multiple images of the incident (max 10)')
    )
    
    incident_date = forms.DateTimeField(
        label=_('Date/Time of Incident'),
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text=_('When did the incident occur?')
    )
    
    class Meta:
        model = IncidentReport
        fields = [
            'title', 'description', 'category', 'location', 
            'incident_date', 'priority', 'anonymous'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'title': forms.TextInput(attrs={'placeholder': _('Brief title of the incident')}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current datetime as default for incident_date
        if not self.instance.pk:
            self.fields['incident_date'].initial = forms.utils.from_current_timezone(
                forms.utils.get_current_timezone()
            )
        
        # Limit image uploads
        self.fields['images'].widget.attrs.update({
            'accept': 'image/*',
            'max': '10'
        })

class IncidentImageForm(forms.ModelForm):
    """Form for uploading additional images."""
    
    class Meta:
        model = IncidentImage
        fields = ['image', 'caption']
        widgets = {
            'caption': forms.TextInput(attrs={
                'placeholder': _('Optional caption for this image')
            }),
        }

class IncidentFilterForm(forms.Form):
    """Form for filtering reports."""
    status = forms.ChoiceField(
        choices=[('', _('All Statuses'))] + list(IncidentReport.Status.choices),
        required=False,
        label=_('Status'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ModelChoiceField(
        queryset=IncidentCategory.objects.all(),
        required=False,
        label=_('Category'),
        empty_label=_('All Categories'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    location = forms.ModelChoiceField(
        queryset=IncidentLocation.objects.all(),
        required=False,
        label=_('Location'),
        empty_label=_('All Locations'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    priority = forms.ChoiceField(
        choices=[('', _('All Priorities'))] + list(IncidentReport.Priority.choices),
        required=False,
        label=_('Priority'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        label=_('From Date'),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_to = forms.DateField(
        required=False,
        label=_('To Date'),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to last 30 days
        if not self.is_bound:
            self.fields['date_from'].initial = (timezone.now() - timedelta(days=30)).date()
            self.fields['date_to'].initial = timezone.now().date()

class IncidentUpdateForm(forms.ModelForm):
    """Form for updating incident status and notes."""
    
    class Meta:
        model = IncidentUpdate
        fields = ['status_change', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': _('Add update notes here...')
            }),
            'status_change': forms.Select(attrs={'class': 'form-select'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show statuses that make sense for updates
        self.fields['status_change'].choices = [
            ('', _('No status change')),
            ('processing', _('Processing')),
            ('resolved', _('Resolved')),
            ('closed', _('Closed'))
        ]

class ReportSearchForm(forms.Form):
    """Form for searching reports with advanced filters."""
    
    query = forms.CharField(
        required=False,
        label=_('Search'),
        widget=forms.TextInput(attrs={
            'placeholder': _('Search by title, description, reporter...'),
            'class': 'form-control'
        })
    )
    
    status = forms.MultipleChoiceField(
        choices=IncidentReport.Status.choices,
        required=False,
        label=_('Status'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    category = forms.ModelMultipleChoiceField(
        queryset=IncidentCategory.objects.all(),
        required=False,
        label=_('Category'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    location = forms.ModelMultipleChoiceField(
        queryset=IncidentLocation.objects.all(),
        required=False,
        label=_('Location'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    priority = forms.MultipleChoiceField(
        choices=IncidentReport.Priority.choices,
        required=False,
        label=_('Priority'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    date_range = forms.ChoiceField(
        choices=[
            ('today', _('Today')),
            ('week', _('Last 7 days')),
            ('month', _('Last 30 days')),
            ('quarter', _('Last 90 days')),
            ('year', _('Last year')),
            ('all', _('All time')),
            ('custom', _('Custom range')),
        ],
        required=False,
        initial='month',
        label=_('Date Range'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    custom_date_from = forms.DateField(
        required=False,
        label=_('From Date'),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    custom_date_to = forms.DateField(
        required=False,
        label=_('To Date'),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    sort_by = forms.ChoiceField(
        choices=[
            ('-created_at', _('Newest First')),
            ('created_at', _('Oldest First')),
            ('-priority', _('Highest Priority First')),
            ('priority', _('Lowest Priority First')),
            ('-updated_at', _('Recently Updated')),
        ],
        required=False,
        initial='-created_at',
        label=_('Sort By'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    has_images = forms.ChoiceField(
        choices=[
            ('', _('Any')),
            ('yes', _('Has Images')),
            ('no', _('No Images')),
        ],
        required=False,
        label=_('Images'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    anonymous_only = forms.BooleanField(
        required=False,
        label=_('Anonymous Reports Only'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        custom_date_from = cleaned_data.get('custom_date_from')
        custom_date_to = cleaned_data.get('custom_date_to')
        
        # Validate custom date range
        if date_range == 'custom':
            if not custom_date_from:
                self.add_error('custom_date_from', _('Please select a start date.'))
            if not custom_date_to:
                self.add_error('custom_date_to', _('Please select an end date.'))
            if custom_date_from and custom_date_to and custom_date_from > custom_date_to:
                self.add_error('custom_date_to', _('End date must be after start date.'))
        
        return cleaned_data

class ImageAnalysisForm(forms.Form):
    """Form for triggering AI image analysis."""
    
    analyze_all = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Analyze all unanalyzed images'),
        help_text=_('Process all images that haven\'t been analyzed yet'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    reanalyze = forms.BooleanField(
        required=False,
        label=_('Re-analyze existing images'),
        help_text=_('Process images even if they already have analysis results'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    blur_faces = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Blur detected faces'),
        help_text=_('Automatically blur faces in images for privacy'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    detect_objects = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Detect objects'),
        help_text=_('Identify objects in images (weapons, vehicles, etc.)'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    assess_risk = forms.BooleanField(
        required=False,
        initial=True,
        label=_('Assess risk level'),
        help_text=_('Calculate risk score based on image content'),
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

class BulkActionForm(forms.Form):
    """Form for bulk actions on reports."""
    
    ACTION_CHOICES = [
        ('', _('Select action...')),
        ('change_status', _('Change Status')),
        ('assign_to_me', _('Assign to Me')),
        ('export', _('Export Selected')),
        ('add_note', _('Add Note to All')),
    ]
    
    STATUS_CHOICES = [
        ('', _('Select status...')),
        ('processing', _('Processing')),
        ('resolved', _('Resolved')),
        ('closed', _('Closed')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        label=_('Bulk Action'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'bulkActionSelect'})
    )
    
    target_status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label=_('New Status'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'targetStatusSelect'})
    )
    
    bulk_note = forms.CharField(
        required=False,
        label=_('Note for all selected reports'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': _('Enter note to add to all selected reports...'),
            'class': 'form-control',
            'id': 'bulkNoteText'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        target_status = cleaned_data.get('target_status')
        bulk_note = cleaned_data.get('bulk_note')
        
        if action == 'change_status' and not target_status:
            self.add_error('target_status', _('Please select a new status.'))
        
        if action == 'add_note' and not bulk_note.strip():
            self.add_error('bulk_note', _('Please enter a note.'))
        
        return cleaned_data

class AnalyticsFilterForm(forms.Form):
    """Form for filtering analytics data."""
    
    PERIOD_CHOICES = [
        ('today', _('Today')),
        ('week', _('Last 7 days')),
        ('month', _('Last 30 days')),
        ('quarter', _('Last 90 days')),
        ('year', _('Last year')),
        ('all', _('All time')),
        ('custom', _('Custom range')),
    ]
    
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        required=False,
        initial='month',
        label=_('Time Period'),
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'analyticsPeriod'})
    )
    
    custom_start = forms.DateField(
        required=False,
        label=_('Start Date'),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    custom_end = forms.DateField(
        required=False,
        label=_('End Date'),
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    category = forms.ModelMultipleChoiceField(
        queryset=IncidentCategory.objects.all(),
        required=False,
        label=_('Filter by Category'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    location = forms.ModelMultipleChoiceField(
        queryset=IncidentLocation.objects.all(),
        required=False,
        label=_('Filter by Location'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )
    
    group_by = forms.ChoiceField(
        choices=[
            ('day', _('Daily')),
            ('week', _('Weekly')),
            ('month', _('Monthly')),
            ('category', _('By Category')),
            ('location', _('By Location')),
            ('status', _('By Status')),
            ('priority', _('By Priority')),
        ],
        required=False,
        initial='day',
        label=_('Group Results By'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default dates
        if not self.is_bound:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
            self.fields['custom_start'].initial = start_date
            self.fields['custom_end'].initial = end_date
    
    def clean(self):
        cleaned_data = super().clean()
        period = cleaned_data.get('period')
        custom_start = cleaned_data.get('custom_start')
        custom_end = cleaned_data.get('custom_end')
        
        if period == 'custom':
            if not custom_start:
                self.add_error('custom_start', _('Please select a start date.'))
            if not custom_end:
                self.add_error('custom_end', _('Please select an end date.'))
            if custom_start and custom_end and custom_start > custom_end:
                self.add_error('custom_end', _('End date must be after start date.'))
        
        return cleaned_data

# Create formset for bulk updates
BulkUpdateFormSet = forms.formset_factory(
    IncidentUpdateForm,
    extra=0,
    can_delete=False
)