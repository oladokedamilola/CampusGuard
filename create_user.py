# smart_surveillance/create_user.py
#!/usr/bin/env python
"""
Interactive script to create users with specific roles.
Run with: python create_user.py
"""
import os
import sys
import getpass

# Setup Django environment FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smart_surveillance.settings')

# Add the current directory to Python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

try:
    import django
    django.setup()
    
    # NOW import Django models
    from accounts.models import User
except Exception as e:
    print(f"❌ Failed to setup Django: {e}")
    print("Make sure you're in the project directory and Django is installed.")
    sys.exit(1)

def create_user_interactive():
    """Interactive user creation script."""
    print("=" * 60)
    print("CampusGuard AI - User Creation Tool")
    print("=" * 60)
    
    # Get user details
    print("\nEnter user details:")
    
    while True:
        email = input("Email address: ").strip()
        if email:
            # Check if email already exists
            if User.objects.filter(email=email).exists():
                print("❌ A user with this email already exists!")
                retry = input("Try a different email? (y/n): ").lower()
                if retry != 'y':
                    return
            else:
                break
        else:
            print("❌ Email is required!")
    
    # Get first and last name
    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()
    
    # Password input with confirmation
    while True:
        password = getpass.getpass("Password: ")
        confirm_password = getpass.getpass("Confirm password: ")
        
        if password != confirm_password:
            print("❌ Passwords do not match! Please try again.")
        elif len(password) < 8:
            print("❌ Password must be at least 8 characters long!")
        else:
            break
    
    # Role selection
    print("\nAvailable roles:")
    print("-" * 40)
    for idx, role in enumerate(User.Role.choices, 1):
        print(f"{idx}. {role[1]} ({role[0]})")
    print("-" * 40)
    
    while True:
        try:
            role_choice = input(f"\nSelect role (1-{len(User.Role.choices)}): ").strip()
            if not role_choice.isdigit():
                print("❌ Please enter a number!")
                continue
                
            role_idx = int(role_choice) - 1
            if 0 <= role_idx < len(User.Role.choices):
                role_code = User.Role.choices[role_idx][0]
                role_name = User.Role.choices[role_idx][1]
                break
            else:
                print(f"❌ Please enter a number between 1 and {len(User.Role.choices)}!")
        except ValueError:
            print("❌ Invalid input!")
    
    # Additional fields
    phone_number = input("Phone number (optional): ").strip()
    department = input("Department (optional): ").strip()
    institution = input("Institution (optional): ").strip()
    
    # Confirm creation
    print("\n" + "=" * 60)
    print("Review user details:")
    print("=" * 60)
    print(f"Email:         {email}")
    print(f"Name:          {first_name} {last_name}")
    print(f"Role:          {role_name}")
    print(f"Phone:         {phone_number or 'Not provided'}")
    print(f"Department:    {department or 'Not provided'}")
    print(f"Institution:   {institution or 'Not provided'}")
    print("=" * 60)
    
    confirm = input("\nCreate this user? (y/n): ").lower()
    
    if confirm == 'y':
        try:
            # Create the user
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role_code,
                phone_number=phone_number,
                department=department,
                institution=institution,
                is_active=True
            )
            
            print(f"\n✅ User created successfully!")
            print(f"   User ID: {user.id}")
            print(f"   Email: {user.email}")
            print(f"   Role: {user.get_role_display()}")
            
            # Ask if user should be staff/superuser
            if role_code in ['admin', 'security_manager', 'institution_admin']:
                make_staff = input("\nMake this user a staff member? (y/n): ").lower()
                if make_staff == 'y':
                    user.is_staff = True
                    
                    if role_code == 'admin':
                        make_superuser = input("Make this user a superuser? (y/n): ").lower()
                        if make_superuser == 'y':
                            user.is_superuser = True
                    
                    user.save()
                    print("✅ User permissions updated!")
            
        except Exception as e:
            print(f"\n❌ Error creating user: {e}")
    else:
        print("\n❌ User creation cancelled.")

if __name__ == '__main__':
    create_user_interactive()