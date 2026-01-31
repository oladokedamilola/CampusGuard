# smart_surveillance/accounts/management/commands/createuser.py
from django.core.management.base import BaseCommand
import getpass
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from accounts.models import User

class Command(BaseCommand):
    help = 'Create a new user with specific role (interactive)'
    
    def handle(self, *args, **options):
        """Handle the command."""
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("CampusGuard AI - User Creation"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        # Get user details
        email = self.get_email()
        first_name = input("First name: ").strip()
        last_name = input("Last name: ").strip()
        password = self.get_password()
        role = self.get_role()
        
        # Optional fields
        phone_number = input("Phone number (optional): ").strip()
        department = input("Department (optional): ").strip()
        institution = input("Institution (optional): ").strip()
        
        # Confirm
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Review user details:")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Email:       {email}")
        self.stdout.write(f"Name:        {first_name} {last_name}")
        self.stdout.write(f"Role:        {role[1]}")
        if phone_number:
            self.stdout.write(f"Phone:       {phone_number}")
        if department:
            self.stdout.write(f"Department:  {department}")
        if institution:
            self.stdout.write(f"Institution: {institution}")
        self.stdout.write("=" * 60)
        
        confirm = input("\nCreate this user? (y/n): ").lower()
        
        if confirm == 'y':
            try:
                # Create user
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=role[0],
                    phone_number=phone_number,
                    department=department,
                    institution=institution,
                    is_active=True
                )
                
                # Set staff/superuser based on role
                if role[0] in ['admin', 'security_manager', 'institution_admin']:
                    user.is_staff = True
                    if role[0] == 'admin':
                        user.is_superuser = True
                        make_superuser = input("\nMake this user a superuser? (y/n): ").lower()
                        if make_superuser == 'y':
                            user.is_superuser = True
                    user.save()
                
                self.stdout.write(self.style.SUCCESS(f"\n✅ User created successfully!"))
                self.stdout.write(self.style.SUCCESS(f"   Email: {user.email}"))
                self.stdout.write(self.style.SUCCESS(f"   Name:  {user.get_full_name()}"))
                self.stdout.write(self.style.SUCCESS(f"   Role:  {user.get_role_display()}"))
                self.stdout.write(self.style.SUCCESS(f"   Staff: {'Yes' if user.is_staff else 'No'}"))
                self.stdout.write(self.style.SUCCESS(f"   Superuser: {'Yes' if user.is_superuser else 'No'}"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"\n❌ Error creating user: {e}"))
        else:
            self.stdout.write(self.style.WARNING("User creation cancelled."))
    
    def get_email(self):
        """Get and validate email."""
        while True:
            email = input("\nEmail address: ").strip()
            if not email:
                self.stdout.write(self.style.ERROR("❌ Email is required!"))
                continue
            
            if User.objects.filter(email=email).exists():
                self.stdout.write(self.style.ERROR("❌ A user with this email already exists!"))
                retry = input("Try a different email? (y/n): ").lower()
                if retry != 'y':
                    raise SystemExit("User creation cancelled.")
                continue
            
            return email
    
    def get_password(self):
        """Get and validate password."""
        while True:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm password: ")
            
            if password != confirm:
                self.stdout.write(self.style.ERROR("❌ Passwords do not match!"))
            elif len(password) < 8:
                self.stdout.write(self.style.ERROR("❌ Password must be at least 8 characters!"))
            else:
                # Try to validate password
                try:
                    validate_password(password)
                    return password
                except ValidationError as errors:
                    self.stdout.write(self.style.ERROR("❌ Password validation failed:"))
                    for error in errors:
                        self.stdout.write(self.style.ERROR(f"   - {error}"))
    
    def get_role(self):
        """Get role selection."""
        self.stdout.write("\nAvailable roles:")
        self.stdout.write("-" * 40)
        for idx, role in enumerate(User.Role.choices, 1):
            self.stdout.write(f"{idx}. {role[1]} ({role[0]})")
        self.stdout.write("-" * 40)
        
        while True:
            choice = input(f"\nSelect role (1-{len(User.Role.choices)}): ").strip()
            if not choice.isdigit():
                self.stdout.write(self.style.ERROR("❌ Please enter a number!"))
                continue
            
            idx = int(choice) - 1
            if 0 <= idx < len(User.Role.choices):
                return User.Role.choices[idx]
            else:
                self.stdout.write(self.style.ERROR(
                    f"❌ Please enter a number between 1 and {len(User.Role.choices)}!"
                ))