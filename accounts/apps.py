from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = _('User Accounts')
    
    def ready(self):
        """Import signals when app is ready."""
        try:
            import accounts.signals
        except ImportError:
            pass