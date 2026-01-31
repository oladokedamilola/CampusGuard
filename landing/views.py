from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.core.mail import send_mail
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.conf import settings

class HomeView(TemplateView):
    """Home page view for the landing page."""
    template_name = 'landing/home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('CampusGuard AI - Smart Campus Security')
        context['meta_description'] = _(
            'Intelligent surveillance and crime detection system for Nigerian educational institutions. '
            'AI-powered security, real-time alerts, and comprehensive campus protection.'
        )
        return context


class PricingView(TemplateView):
    """Pricing page view."""
    template_name = 'landing/pricing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Pricing - CampusGuard AI')
        context['meta_description'] = _(
            'Affordable pricing plans for schools and universities. '
            'Choose the right plan for your institution\'s security needs.'
        )
        
        # Pricing plans data
        context['plans'] = [
            {
                'name': _('Basic'),
                'description': _('For small schools & hostels'),
                'price': '₦50,000',
                'period': _('/month'),
                'features': [
                    _('Up to 10 cameras'),
                    _('Basic motion detection'),
                    _('Email alerts'),
                    _('7-day video retention'),
                    _('Basic analytics dashboard'),
                    _('Email support'),
                ],
                'not_included': [
                    _('AI facial recognition'),
                    _('Advanced analytics'),
                    _('Phone support'),
                    _('Custom integrations'),
                ],
                'cta_text': _('Get Started'),
                'cta_class': 'btn-outline-primary',
                'popular': False,
            },
            {
                'name': _('Professional'),
                'description': _('For medium universities & colleges'),
                'price': '₦150,000',
                'period': _('/month'),
                'features': [
                    _('Up to 50 cameras'),
                    _('AI motion & object detection'),
                    _('Email & SMS alerts'),
                    _('30-day video retention'),
                    _('Advanced analytics'),
                    _('Priority support'),
                    _('Mobile app access'),
                    _('Incident reporting'),
                ],
                'not_included': [
                    _('Custom AI models'),
                    _('On-site training'),
                    _('24/7 phone support'),
                ],
                'cta_text': _('Most Popular'),
                'cta_class': 'btn-primary',
                'popular': True,
            },
            {
                'name': _('Enterprise'),
                'description': _('For large institutions & campuses'),
                'price': _('Custom'),
                'period': '',
                'features': [
                    _('Unlimited cameras'),
                    _('Full AI suite (face, object, behavior)'),
                    _('Multi-channel alerts'),
                    _('90+ day video retention'),
                    _('Custom analytics & reports'),
                    _('24/7 dedicated support'),
                    _('On-site training'),
                    _('Custom integrations'),
                    _('SLA guarantee'),
                    _('Security audit'),
                ],
                'not_included': [],
                'cta_text': _('Contact Sales'),
                'cta_class': 'btn-outline-primary',
                'popular': False,
            },
        ]
        
        # FAQ data
        context['faqs'] = [
            {
                'question': _('Do I need special cameras?'),
                'answer': _('No, CampusGuard AI works with most existing CCTV and IP cameras. '
                          'We support RTSP, ONVIF, and other standard protocols.'),
            },
            {
                'question': _('Can I try before I buy?'),
                'answer': _('Yes! We offer a 14-day free trial for all plans. No credit card required. '
                          'You can test all features with up to 5 cameras during the trial period.'),
            },
            {
                'question': _('What about internet connectivity?'),
                'answer': _('CampusGuard AI can work with intermittent internet. '
                          'The system buffers locally and syncs when connectivity is available. '
                          'We also offer hybrid solutions for areas with poor internet.'),
            },
            {
                'question': _('Is training provided?'),
                'answer': _('Yes! We provide comprehensive training for your security staff '
                          'and administrators. Professional plan includes online training, '
                          'Enterprise includes on-site training.'),
            },
            {
                'question': _('How is data privacy handled?'),
                'answer': _('We comply with Nigeria Data Protection Act (NDPA) 2023. '
                          'All data is encrypted, access is logged, and we never share '
                          'your data with third parties. You own all your data.'),
            },
            {
                'question': _('What support do you offer?'),
                'answer': _('Basic plan includes email support. Professional includes '
                          'priority email and chat support. Enterprise includes 24/7 '
                          'phone and dedicated account manager.'),
            },
        ]
        
        return context


class ContactView(TemplateView):
    """Contact page view with form handling."""
    template_name = 'landing/contact.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = _('Contact Us - CampusGuard AI')
        context['meta_description'] = _(
            'Get in touch with our team. We\'re here to help you secure your campus '
            'with intelligent surveillance technology.'
        )
        
        # Contact information
        context['contact_info'] = {
            'email': 'contact@campusguard-ai.com',
            'phone': '+234 812 345 6789',
            'address': _('Lagos Office: 123 Security Avenue, Victoria Island, Lagos'),
            'hours': _('Monday - Friday: 8:00 AM - 6:00 PM WAT'),
        }
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle contact form submission."""
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        institution = request.POST.get('institution', '').strip()
        message = request.POST.get('message', '').strip()
        contact_method = request.POST.get('contact_method', 'email')
        
        # Basic validation
        if not all([name, email, message]):
            messages.error(request, _('Please fill in all required fields.'))
            return self.get(request, *args, **kwargs)
        
        # Create email message
        subject = f'CampusGuard AI Contact Form: {name} from {institution or "Unknown Institution"}'
        
        email_body = f"""
        New Contact Form Submission
        ----------------------------
        Name: {name}
        Email: {email}
        Phone: {phone}
        Institution: {institution or 'Not provided'}
        Preferred Contact Method: {contact_method}
        
        Message:
        {message}
        
        ----------------------------
        Sent from CampusGuard AI Contact Form
        """
        
        html_body = f"""
        <h2>New Contact Form Submission</h2>
        <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Name:</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{name}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Email:</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{email}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Phone:</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{phone or 'Not provided'}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Institution:</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{institution or 'Not provided'}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; background-color: #f9f9f9;"><strong>Contact Method:</strong></td>
                <td style="padding: 10px; border: 1px solid #ddd;">{contact_method}</td>
            </tr>
        </table>
        
        <h3 style="margin-top: 20px;">Message:</h3>
        <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; border-left: 4px solid #0066CC;">
            {message.replace(chr(10), '<br>')}
        </div>
        
        <p style="margin-top: 20px; color: #666; font-size: 12px;">
            Sent from CampusGuard AI Contact Form
        </p>
        """
        
        try:
            # Send email to admin
            send_mail(
                subject=subject,
                message=email_body,
                html_message=html_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_EMAIL] if hasattr(settings, 'CONTACT_EMAIL') else ['contact@campusguard-ai.com'],
                fail_silently=False,
            )
            
            # Send confirmation email to user
            confirmation_subject = _('Thank you for contacting CampusGuard AI')
            confirmation_body = f"""
            Dear {name},
            
            Thank you for reaching out to CampusGuard AI. We have received your message and 
            one of our security specialists will contact you within 24 hours.
            
            Here's a copy of your message:
            {message}
            
            If you have any urgent security concerns, please call our emergency line: +234 812 345 6789
            
            Best regards,
            CampusGuard AI Team
            """
            
            send_mail(
                subject=confirmation_subject,
                message=confirmation_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,  # Don't fail if user email fails
            )
            
            messages.success(request, _(
                'Thank you for your message! We have received it and will contact you '
                'within 24 hours. A confirmation has been sent to your email.'
            ))
            
        except Exception as e:
            # Log the error but don't show technical details to user
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send contact form email: {str(e)}")
            
            messages.error(request, _(
                'Sorry, there was an error sending your message. '
                'Please try again or contact us directly at contact@campusguard-ai.com'
            ))
        
        return redirect('landing:contact')
    
    
from django.http import HttpResponse

def test_view(request):
    return HttpResponse("Landing app is working!")