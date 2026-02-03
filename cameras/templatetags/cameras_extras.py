from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter
def get_status_badge_class(status):
    """Get Bootstrap badge class for processing status."""
    if status == 'completed':
        return 'success'
    elif status == 'failed':
        return 'danger'
    elif status in ['processing', 'pending']:
        return 'warning'
    else:
        return 'secondary'

@register.filter
def get_media_type_badge_class(is_image):
    """Get Bootstrap badge class for media type."""
    return 'primary' if is_image else 'warning'

@register.filter
def get_detection_label(detection):
    """Extract label from detection dict."""
    if isinstance(detection, dict):
        # Try different possible keys
        if 'label' in detection:
            return detection['label']
        elif 'type' in detection:
            return detection['type']
        elif 'class' in detection:
            return detection['class']
        elif 'attributes' in detection and 'class_id' in detection['attributes']:
            # Map COCO class IDs to labels
            class_map = {
                0: 'person',
                1: 'bicycle',
                2: 'car',
                3: 'motorcycle',
                5: 'bus',
                7: 'truck',
                15: 'cat',
                16: 'dog',
                # Add more as needed
            }
            class_id = detection['attributes']['class_id']
            return class_map.get(class_id, f'class_{class_id}')
    return 'unknown'

@register.filter
def get_detection_badge_class(label):
    """Get Bootstrap badge class for detection type."""
    if label == 'person':
        return 'primary'
    elif label in ['car', 'truck', 'bus', 'motorcycle', 'vehicle']:
        return 'warning'
    else:
        return 'secondary'

@register.filter
def get_detection_icon(label):
    """Get FontAwesome icon for detection type."""
    icon_map = {
        'person': 'user',
        'car': 'car',
        'truck': 'truck',
        'bus': 'bus',
        'motorcycle': 'motorcycle',
        'bicycle': 'bicycle',
        'cat': 'cat',
        'dog': 'dog',
    }
    return icon_map.get(label, 'cube')

@register.filter
def to_json(value):
    """Convert value to JSON string."""
    return mark_safe(json.dumps(value))


@register.filter
def get_detection_icon(label):
    """Safely get icon for detection type."""
    if not label:
        return 'cube'
    
    icons = {
        'person': 'user',
        'car': 'car',
        'truck': 'truck',
        'bus': 'bus',
        'motorcycle': 'motorcycle',
        'bicycle': 'bicycle',
        'vehicle': 'car',
    }
    return icons.get(str(label).lower(), 'cube')

@register.filter
def get_detection_color(label):
    """Safely get color for detection type."""
    if not label:
        return 'secondary'
    
    colors = {
        'person': 'primary',
        'car': 'warning',
        'truck': 'warning',
        'bus': 'warning',
        'motorcycle': 'warning',
        'bicycle': 'info',
        'vehicle': 'warning',
    }
    return colors.get(str(label).lower(), 'secondary')

@register.filter
def get_risk_level(confidence):
    """Get risk level based on confidence."""
    try:
        conf = float(confidence)
    except (ValueError, TypeError):
        conf = 0
    
    if conf > 0.8:
        return {'label': 'Low Risk', 'color': 'success', 'icon': 'shield-alt'}
    elif conf > 0.6:
        return {'label': 'Medium Risk', 'color': 'warning', 'icon': 'exclamation-circle'}
    else:
        return {'label': 'Review Needed', 'color': 'danger', 'icon': 'exclamation-triangle'}

@register.filter
def get_detection_label(detection):
    """Safely get label from detection object."""
    if isinstance(detection, dict):
        return detection.get('label') or detection.get('type') or detection.get('class') or 'unknown'
    return 'unknown'