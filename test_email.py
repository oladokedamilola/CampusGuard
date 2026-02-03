import os
import django
from django.core.mail import send_mail

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_surveillance.settings')
django.setup()

# Test email
print("Sending test email...")
try:
    send_mail(
        subject='Test Email from CampusGuard AI',
        message='This is a test email to verify configuration.',
        from_email='CampusGuard AI <noreply@campusguard.ai>',
        recipient_list=['test@example.com'],
        fail_silently=False,
    )
    print("✅ Email sent successfully!")
    print("Check your terminal for the email output.")
except Exception as e:
    print(f"❌ Failed to send email: {e}")
    print("\nTroubleshooting steps:")
    print("1. Check your .env file exists and has correct values")
    print("2. Make sure you're loading .env in settings.py")
    print("3. Try using console backend: EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'")