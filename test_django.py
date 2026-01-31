# test_django.py
import os
import sys
import django

# Setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_surveillance.settings')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

try:
    django.setup()
    print("✅ Django setup successful!")
    
    from accounts.models import User
    print("✅ User model imported successfully!")
    
    # Count users
    count = User.objects.count()
    print(f"✅ Database connection successful! Total users: {count}")
    
except Exception as e:
    print(f"❌ Error: {e}")