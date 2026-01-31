"""
Service for monitoring video processing jobs with FastAPI server.
"""
import threading
import time
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction

from core.utils.fastapi_client import fastapi_client
from surveillance.models import VideoProcessingJob

logger = logging.getLogger(__name__)

class JobMonitor:
    """
    Monitors and updates status of video processing jobs.
    """
    
    def __init__(self, check_interval=30):
        """
        Initialize job monitor.
        
        Args:
            check_interval: Seconds between checks for each job
        """
        self.check_interval = check_interval
        self.monitoring = False
        self.monitor_thread = None
        self.active_jobs = set()
    
    def start_monitoring(self):
        """Start the job monitoring thread."""
        if self.monitoring:
            logger.warning("Job monitor is already running")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="JobMonitor"
        )
        self.monitor_thread.start()
        logger.info("Job monitor started")
    
    def stop_monitoring(self):
        """Stop the job monitoring thread."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Job monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.monitoring:
            try:
                self._check_active_jobs()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitor loop: {str(e)}")
                time.sleep(self.check_interval * 2)  # Longer sleep on error
    
    def _check_active_jobs(self):
        """Check status of all active jobs."""
        try:
            # Get active jobs from database
            active_jobs = VideoProcessingJob.objects.filter(
                status__in=['submitted', 'pending', 'processing']
            ).exclude(
                submitted_at__lt=timezone.now() - timedelta(hours=24)  # Don't check old jobs
            )
            
            logger.debug(f"Checking {active_jobs.count()} active jobs")
            
            for job in active_jobs:
                try:
                    self._update_job_status(job)
                except Exception as e:
                    logger.error(f"Error updating job {job.job_id}: {str(e)}")
                    # Mark job as failed if we can't check it
                    job.status = 'failed'
                    job.error = f"Monitoring error: {str(e)}"
                    job.save()
        
        except Exception as e:
            logger.error(f"Error checking active jobs: {str(e)}")
    
    def _update_job_status(self, job: VideoProcessingJob):
        """
        Update status of a single job.
        
        Args:
            job: VideoProcessingJob instance
        """
        # Check if job is too old to monitor
        if job.submitted_at < timezone.now() - timedelta(hours=6):
            job.status = 'failed'
            job.error = 'Job timed out (older than 6 hours)'
            job.save()
            return
        
        # Get status from FastAPI server
        status_data = fastapi_client.get_job_status(job.job_id)
        
        if status_data.get('status') == 'error':
            # Job not found on server or server error
            job.status = 'failed'
            job.error = status_data.get('message', 'Job not found on processing server')
            job.save()
            return
        
        # Update job from status data
        with transaction.atomic():
            job.refresh_from_db()  # Get fresh copy
            if job.status not in ['completed', 'failed', 'cancelled']:
                job.update_from_fastapi_status(status_data)
                logger.debug(f"Updated job {job.job_id}: {job.status} - {job.progress}%")
    
    def add_job_to_monitor(self, job_id: str):
        """
        Add a job to the monitoring set.
        
        Args:
            job_id: Job ID to monitor
        """
        self.active_jobs.add(job_id)
    
    def remove_job_from_monitor(self, job_id: str):
        """
        Remove a job from the monitoring set.
        
        Args:
            job_id: Job ID to stop monitoring
        """
        self.active_jobs.discard(job_id)
    
    def check_single_job(self, job_id: str) -> bool:
        """
        Check and update a single job immediately.
        
        Args:
            job_id: Job ID to check
        
        Returns:
            True if job status was updated
        """
        try:
            job = VideoProcessingJob.objects.get(job_id=job_id)
            self._update_job_status(job)
            return True
        except VideoProcessingJob.DoesNotExist:
            logger.error(f"Job {job_id} not found in database")
            return False
        except Exception as e:
            logger.error(f"Error checking job {job_id}: {str(e)}")
            return False

# Global instance
job_monitor = JobMonitor(check_interval=30)  # Check every 30 seconds

def start_job_monitor():
    """Start the global job monitor."""
    job_monitor.start_monitoring()

def stop_job_monitor():
    """Stop the global job monitor."""
    job_monitor.stop_monitoring()

def check_job_status(job_id: str):
    """
    Check status of a specific job.
    
    Args:
        job_id: Job ID to check
    
    Returns:
        Job status dictionary
    """
    try:
        job = VideoProcessingJob.objects.get(job_id=job_id)
        return {
            'job_id': job.job_id,
            'status': job.status,
            'progress': job.progress,
            'message': job.message,
            'submitted_at': job.submitted_at.isoformat() if job.submitted_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'error': job.error,
        }
    except VideoProcessingJob.DoesNotExist:
        return {
            'error': f'Job {job_id} not found in database'
        }