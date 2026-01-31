from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class SurveillanceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'surveillance'
    verbose_name = 'Video Surveillance'
    
    def ready(self):
        """Initialize surveillance app."""
        # Import and start job monitor when Django starts
        try:
            from .services.job_monitor import start_job_monitor
            
            # Only start in production or when explicitly enabled
            import os
            if os.environ.get('START_JOB_MONITOR', 'false').lower() == 'true':
                start_job_monitor()
                logger.info("Job monitor started by app config")
            else:
                logger.info("Job monitor not started (disabled by environment)")
                
        except ImportError as e:
            logger.warning(f"Could not import job monitor: {str(e)}")
        except Exception as e:
            logger.error(f"Error starting job monitor: {str(e)}")