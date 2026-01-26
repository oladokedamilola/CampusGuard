from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.generic import ListView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy

from .models import Alert, AlertRule, NotificationPreference
from .forms import AlertRuleForm, NotificationPreferenceForm, AlertFilterForm
from .services import UserNotificationService

class AlertListView(LoginRequiredMixin, ListView):
    """List alerts for the current user."""
    model = Alert
    template_name = 'alerts/alert_list.html'
    context_object_name = 'alerts'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Alert.objects.filter(recipient=self.request.user).order_by('-created_at')
        
        # Apply filters from form
        form = AlertFilterForm(self.request.GET)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            alert_type = form.cleaned_data.get('alert_type')
            read_status = form.cleaned_data.get('read_status')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            search = form.cleaned_data.get('search')
            
            if status:
                queryset = queryset.filter(status=status)
            
            if alert_type:
                queryset = queryset.filter(alert_type=alert_type)
            
            if read_status == 'read':
                queryset = queryset.filter(is_read=True)
            elif read_status == 'unread':
                queryset = queryset.filter(is_read=False)
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
            
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(message__icontains=search) |
                    Q(alert_id__icontains=search)
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = AlertFilterForm(self.request.GET)
        context['unread_count'] = UserNotificationService.get_unread_alerts(self.request.user).count()
        return context

@login_required
def mark_alert_as_read(request, pk):
    """Mark an alert as read."""
    alert = get_object_or_404(Alert, pk=pk, recipient=request.user)
    
    alert.mark_as_read()
    messages.success(request, _('Alert marked as read.'))
    
    # Return to previous page or alert list
    return_url = request.META.get('HTTP_REFERER', reverse_lazy('alerts:list'))
    return redirect(return_url)

@login_required
def mark_all_alerts_as_read(request):
    """Mark all user's alerts as read."""
    count = UserNotificationService.mark_all_as_read(request.user)
    messages.success(request, _(f'Marked {count} alerts as read.'))
    
    return_url = request.META.get('HTTP_REFERER', reverse_lazy('alerts:list'))
    return redirect(return_url)

@login_required
def alert_detail(request, pk):
    """View alert details."""
    alert = get_object_or_404(Alert, pk=pk, recipient=request.user)
    
    # Mark as read when viewing
    if not alert.is_read and 'in_app' in alert.channels:
        alert.mark_as_read()
    
    context = {
        'alert': alert,
    }
    return render(request, 'alerts/alert_detail.html', context)

@login_required
def notification_preferences(request):
    """Manage notification preferences."""
    try:
        preferences = NotificationPreference.objects.get(user=request.user)
    except NotificationPreference.DoesNotExist:
        preferences = NotificationPreference.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=preferences)
        if form.is_valid():
            form.save()
            messages.success(request, _('Notification preferences updated.'))
            return redirect('alerts:preferences')
    else:
        form = NotificationPreferenceForm(instance=preferences)
    
    context = {
        'form': form,
        'preferences': preferences,
    }
    return render(request, 'alerts/preferences.html', context)

# Admin views for alert rules (only for admins/managers)
class AlertRuleListView(LoginRequiredMixin, ListView):
    """List alert rules (admin only)."""
    model = AlertRule
    template_name = 'alerts/rule_list.html'
    context_object_name = 'rules'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser and request.user.role not in ['admin', 'security_manager']:
            messages.error(request, _('You do not have permission to view alert rules.'))
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

class AlertRuleCreateView(LoginRequiredMixin, UpdateView):
    """Create alert rule (admin only)."""
    model = AlertRule
    form_class = AlertRuleForm
    template_name = 'alerts/rule_form.html'
    success_url = reverse_lazy('alerts:rule_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser and request.user.role not in ['admin', 'security_manager']:
            messages.error(request, _('You do not have permission to manage alert rules.'))
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Alert rule created successfully.'))
        return response

class AlertRuleUpdateView(LoginRequiredMixin, UpdateView):
    """Update alert rule (admin only)."""
    model = AlertRule
    form_class = AlertRuleForm
    template_name = 'alerts/rule_form.html'
    success_url = reverse_lazy('alerts:rule_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser and request.user.role not in ['admin', 'security_manager']:
            messages.error(request, _('You do not have permission to manage alert rules.'))
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, _('Alert rule updated successfully.'))
        return response

class AlertRuleDeleteView(LoginRequiredMixin, DeleteView):
    """Delete alert rule (admin only)."""
    model = AlertRule
    template_name = 'alerts/rule_confirm_delete.html'
    success_url = reverse_lazy('alerts:rule_list')
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser and request.user.role not in ['admin', 'security_manager']:
            messages.error(request, _('You do not have permission to manage alert rules.'))
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        rule_name = self.object.name
        response = super().form_valid(form)
        messages.success(self.request, _(f'Alert rule "{rule_name}" deleted.'))
        return response

@login_required
def toggle_alert_rule(request, pk):
    """Toggle alert rule active status (admin only)."""
    if not request.user.is_superuser and request.user.role not in ['admin', 'security_manager']:
        messages.error(request, _('You do not have permission to manage alert rules.'))
        return redirect('dashboard:index')
    
    rule = get_object_or_404(AlertRule, pk=pk)
    rule.is_active = not rule.is_active
    rule.save()
    
    status = "activated" if rule.is_active else "deactivated"
    messages.success(request, _(f'Alert rule "{rule.name}" {status}.'))
    
    return redirect('alerts:rule_list')

# API endpoints for AJAX
@login_required
def get_unread_alerts_count(request):
    """Get count of unread alerts (AJAX endpoint)."""
    count = UserNotificationService.get_unread_alerts(request.user).count()
    return JsonResponse({'count': count})

@login_required
def get_recent_alerts(request):
    """Get recent alerts for notification dropdown (AJAX endpoint)."""
    alerts = UserNotificationService.get_recent_alerts(request.user, limit=5)
    
    alerts_data = []
    for alert in alerts:
        alerts_data.append({
            'id': alert.pk,
            'title': alert.title,
            'message': alert.message[:100] + '...' if len(alert.message) > 100 else alert.message,
            'created_at': alert.created_at.strftime('%H:%M'),
            'is_read': alert.is_read,
            'severity_color': alert.get_severity_color(),
            'url': reverse_lazy('alerts:detail', kwargs={'pk': alert.pk}),
        })
    
    return JsonResponse({'alerts': alerts_data})