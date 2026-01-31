# smart_surveillance/accounts/backends.py
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailBackend(BaseBackend):
    """
    Custom authentication backend for email-based authentication.
    """
    
    def authenticate(self, request, email=None, password=None, **kwargs):
        """
        Authenticate using email instead of username.
        """
        try:
            # Try to find a user with the given email
            user = User.objects.get(email=email)
            
            # Check the password
            if user.check_password(password):
                return user
                
        except User.DoesNotExist:
            # No user found with this email
            return None
        
        except Exception:
            return None
    
    def get_user(self, user_id):
        """
        Get user by ID.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None