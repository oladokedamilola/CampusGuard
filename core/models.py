from django.db import models
from django.utils.translation import gettext_lazy as _

class Location(models.Model):
    """
    Physical location model for cameras and incidents.
    """
    class LocationType(models.TextChoices):
        CAMPUS = 'campus', _('Campus')
        BUILDING = 'building', _('Building')
        ROOM = 'room', _('Room')
        GATE = 'gate', _('Gate')
        PARKING = 'parking', _('Parking Lot')
        HOSTEL = 'hostel', _('Hostel')
        LABORATORY = 'laboratory', _('Laboratory')
        LIBRARY = 'library', _('Library')
        ADMIN = 'admin', _('Administrative')
        OTHER = 'other', _('Other')
    
    name = models.CharField(
        max_length=200,
        verbose_name=_('Location Name'),
        help_text=_('Descriptive name for the location')
    )
    
    location_type = models.CharField(
        max_length=50,
        choices=LocationType.choices,
        default=LocationType.BUILDING,
        verbose_name=_('Location Type')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description'),
        help_text=_('Detailed description of the location')
    )
    
    address = models.TextField(
        blank=True,
        verbose_name=_('Address'),
        help_text=_('Physical address')
    )
    
    floor = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Floor'),
        help_text=_('Floor number or level')
    )
    
    room_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Room Number')
    )
    
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name=_('Latitude')
    )
    
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True,
        verbose_name=_('Longitude')
    )
    
    institution = models.CharField(
        max_length=200,
        default='University of Nigeria',
        verbose_name=_('Institution'),
        help_text=_('Educational institution name')
    )
    
    is_restricted = models.BooleanField(
        default=False,
        verbose_name=_('Restricted Area'),
        help_text=_('Whether this is a restricted access area')
    )
    
    security_level = models.IntegerField(
        default=1,
        choices=[(1, 'Low'), (2, 'Medium'), (3, 'High'), (4, 'Critical')],
        verbose_name=_('Security Level')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Location')
        verbose_name_plural = _('Locations')
        ordering = ['institution', 'name']
        unique_together = ['name', 'institution']
    
    def __str__(self):
        return f"{self.name} - {self.institution}"
    
    def get_camera_count(self):
        """Get number of cameras at this location."""
        return self.cameras.count()
    
    def get_active_camera_count(self):
        """Get number of active cameras at this location."""
        return self.cameras.filter(is_active=True, status='active').count()