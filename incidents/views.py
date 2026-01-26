from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, F
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
import json

from .models import Incident, IncidentComment, IncidentActionLog, Evidence, IncidentStatistic
from .forms import (IncidentForm, IncidentFilterForm, IncidentCommentForm, 
                   EvidenceUploadForm, IncidentBulkActionForm)
from accounts.models import User

class IncidentListView(LoginRequiredMixin, ListView):
    """List all incidents with filtering."""
    model = Incident
    template_name = 'incidents/incident_list.html'
    context_object_name = 'incidents'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Incident.objects.select_related(
            'camera', 'camera__location', 'assigned_to'
        ).order_by('-detected_at')
        
        # Apply filters from form
        form = IncidentFilterForm(self.request.GET, user=self.request.user)
        if form.is_valid():
            status = form.cleaned_data.get('status')
            severity = form.cleaned_data.get('severity')
            incident_type = form.cleaned_data.get('incident_type')
            camera = form.cleaned_data.get('camera')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            assigned_to = form.cleaned_data.get('assigned_to')
            search = form.cleaned_data.get('search')
            
            if status:
                queryset = queryset.filter(status=status)
            
            if severity:
                queryset = queryset.filter(severity=severity)
            
            if incident_type:
                queryset = queryset.filter(incident_type=incident_type)
            
            if camera:
                queryset = queryset.filter(camera=camera)
            
            if date_from:
                queryset = queryset.filter(detected_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(detected_at__date__lte=date_to)
            
            if assigned_to:
                queryset = queryset.filter(assigned_to=assigned_to)
            
            if search:
                queryset = queryset.filter(
                    Q(incident_id__icontains=search) |
                    Q(title__icontains=search) |
                    Q(description__icontains=search) |
                    Q(camera__name__icontains=search) |
                    Q(location_description__icontains=search)
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = IncidentFilterForm(self.request.GET, user=self.request.user)
        
        # Stats for dashboard
        context['total_incidents'] = Incident.objects.count()
        context['open_incidents'] = Incident.objects.exclude(
            status__in=['resolved', 'false_alarm']
        ).count()
        context['today_incidents'] = Incident.objects.filter(
            detected_at__date=timezone.now().date()
        ).count()
        context['unacknowledged_incidents'] = Incident.objects.filter(
            status='detected'
        ).count()
        
        # Bulk action form
        context['bulk_action_form'] = IncidentBulkActionForm(user=self.request.user)
        
        return context

class IncidentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """View incident details."""
    model = Incident
    template_name = 'incidents/incident_detail.html'
    context_object_name = 'incident'
    
    def test_func(self):
        """Check if user can view incidents."""
        return self.request.user.can_acknowledge_incidents()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get related data
        context['comments'] = self.object.comments.all().order_by('created_at')
        context['action_logs'] = self.object.action_logs.all().order_by('-created_at')[:10]
        context['additional_evidence'] = self.object.additional_evidence.all().order_by('-uploaded_at')
        
        # Forms
        context['comment_form'] = IncidentCommentForm()
        context['evidence_form'] = EvidenceUploadForm()
        
        # Check permissions for actions
        context['can_acknowledge'] = (
            self.object.can_be_acknowledged() and 
            self.request.user.can_acknowledge_incidents()
        )
        context['can_resolve'] = (
            self.object.can_be_resolved() and 
            self.request.user.can_acknowledge_incidents()
        )
        
        return context

class IncidentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new incident (manual entry)."""
    model = Incident
    form_class = IncidentForm
    template_name = 'incidents/incident_form.html'
    success_url = reverse_lazy('incidents:list')
    
    def test_func(self):
        """Check if user can manage incidents."""
        return self.request.user.can_acknowledge_incidents()
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Handle successful form submission."""
        incident = form.save(commit=False)
        
        # Set detected time if not set
        if not incident.detected_at:
            incident.detected_at = timezone.now()
        
        # Save the incident
        incident.save()
        
        # Log the action
        IncidentActionLog.objects.create(
            incident=incident,
            user=self.request.user,
            action='created',
            details={'method': 'manual', 'form_data': form.cleaned_data},
            ip_address=self.request.META.get('REMOTE_ADDR'),
            user_agent=self.request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(
            self.request,
            _(f'Incident "{incident.incident_id}" created successfully!')
        )
        return redirect('incidents:detail', pk=incident.pk)

class IncidentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update an existing incident."""
    model = Incident
    form_class = IncidentForm
    template_name = 'incidents/incident_form.html'
    
    def test_func(self):
        """Check if user can manage incidents."""
        return self.request.user.can_acknowledge_incidents()
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        return reverse_lazy('incidents:detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        """Handle successful form update."""
        old_status = self.object.status
        old_assigned = self.object.assigned_to
        
        response = super().form_valid(form)
        
        # Log changes
        changes = {}
        if old_status != self.object.status:
            changes['status'] = {'from': old_status, 'to': self.object.status}
        
        if old_assigned != self.object.assigned_to:
            changes['assigned_to'] = {
                'from': str(old_assigned) if old_assigned else None,
                'to': str(self.object.assigned_to) if self.object.assigned_to else None
            }
        
        if changes:
            IncidentActionLog.objects.create(
                incident=self.object,
                user=self.request.user,
                action='updated',
                details={'changes': changes, 'form_data': form.cleaned_data},
                ip_address=self.request.META.get('REMOTE_ADDR'),
                user_agent=self.request.META.get('HTTP_USER_AGENT', '')
            )
        
        messages.success(
            self.request,
            _(f'Incident "{self.object.incident_id}" updated successfully!')
        )
        return response

@login_required
def acknowledge_incident(request, pk):
    """Acknowledge an incident."""
    if not request.user.can_acknowledge_incidents():
        messages.error(request, _('You do not have permission to acknowledge incidents.'))
        return redirect('incidents:list')
    
    incident = get_object_or_404(Incident, pk=pk)
    
    if incident.acknowledge(request.user):
        # Log the action
        IncidentActionLog.objects.create(
            incident=incident,
            user=request.user,
            action='acknowledged',
            details={'method': 'manual'},
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(request, _(f'Incident "{incident.incident_id}" acknowledged.'))
    else:
        messages.warning(request, _('Cannot acknowledge this incident.'))
    
    return redirect('incidents:detail', pk=incident.pk)

@login_required
def resolve_incident(request, pk):
    """Resolve an incident."""
    if not request.user.can_acknowledge_incidents():
        messages.error(request, _('You do not have permission to resolve incidents.'))
        return redirect('incidents:list')
    
    incident = get_object_or_404(Incident, pk=pk)
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        is_false_positive = request.POST.get('is_false_positive') == 'on'
        
        if incident.resolve(request.user, notes, is_false_positive):
            # Log the action
            action = 'false_alarm' if is_false_positive else 'resolved'
            IncidentActionLog.objects.create(
                incident=incident,
                user=request.user,
                action=action,
                details={'notes': notes, 'is_false_positive': is_false_positive},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, _(f'Incident "{incident.incident_id}" resolved.'))
        else:
            messages.warning(request, _('Cannot resolve this incident.'))
    
    return redirect('incidents:detail', pk=incident.pk)

@login_required
def add_comment(request, pk):
    """Add a comment to an incident."""
    if not request.user.can_acknowledge_incidents():
        messages.error(request, _('You do not have permission to comment on incidents.'))
        return redirect('incidents:list')
    
    incident = get_object_or_404(Incident, pk=pk)
    
    if request.method == 'POST':
        form = IncidentCommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.incident = incident
            comment.user = request.user
            comment.save()
            
            # Log the action
            IncidentActionLog.objects.create(
                incident=incident,
                user=request.user,
                action='comment_added',
                details={'comment_id': comment.pk, 'is_internal': comment.is_internal},
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, _('Comment added successfully.'))
    
    return redirect('incidents:detail', pk=incident.pk)

@login_required
def upload_evidence(request, pk):
    """Upload additional evidence for an incident."""
    if not request.user.can_acknowledge_incidents():
        messages.error(request, _('You do not have permission to upload evidence.'))
        return redirect('incidents:list')
    
    incident = get_object_or_404(Incident, pk=pk)
    
    if request.method == 'POST':
        form = EvidenceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.incident = incident
            evidence.uploaded_by = request.user
            evidence.save()
            
            # Log the action
            IncidentActionLog.objects.create(
                incident=incident,
                user=request.user,
                action='evidence_added',
                details={
                    'evidence_id': evidence.pk,
                    'evidence_type': evidence.evidence_type,
                    'filename': evidence.file.name
                },
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            messages.success(request, _('Evidence uploaded successfully.'))
    
    return redirect('incidents:detail', pk=incident.pk)

@login_required
def incident_dashboard(request):
    """Incident dashboard with statistics."""
    if not request.user.can_acknowledge_incidents():
        messages.error(request, _('You do not have permission to view the dashboard.'))
        return redirect('dashboard:index')
    
    # Date range for statistics
    today = timezone.now().date()
    week_ago = today - timezone.timedelta(days=7)
    month_ago = today - timezone.timedelta(days=30)
    
    # Basic counts
    total_incidents = Incident.objects.count()
    open_incidents = Incident.objects.exclude(
        status__in=['resolved', 'false_alarm']
    ).count()
    
    # Today's incidents
    today_incidents = Incident.objects.filter(
        detected_at__date=today
    )
    
    # Recent incidents (last 24 hours)
    recent_incidents = Incident.objects.filter(
        detected_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).order_by('-detected_at')[:10]
    
    # Incidents by type (last 30 days)
    incidents_by_type = Incident.objects.filter(
        detected_at__gte=month_ago
    ).values('incident_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Incidents by severity (last 30 days)
    incidents_by_severity = Incident.objects.filter(
        detected_at__gte=month_ago
    ).values('severity').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Most active cameras (last 30 days)
    active_cameras = Incident.objects.filter(
        detected_at__gte=month_ago
    ).values('camera__name', 'camera__location__name').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Response time statistics (last 30 days)
    acknowledged_incidents = Incident.objects.filter(
        acknowledged_at__isnull=False,
        detected_at__gte=month_ago
    )
    
    avg_response_time = 0
    if acknowledged_incidents.exists():
        total_seconds = sum(
            (inc.acknowledged_at - inc.detected_at).total_seconds()
            for inc in acknowledged_incidents
        )
        avg_response_time = total_seconds / acknowledged_incidents.count() / 60  # in minutes
    
    context = {
        'total_incidents': total_incidents,
        'open_incidents': open_incidents,
        'today_incidents': today_incidents.count(),
        'recent_incidents': recent_incidents,
        'incidents_by_type': incidents_by_type,
        'incidents_by_severity': incidents_by_severity,
        'active_cameras': active_cameras,
        'avg_response_time': round(avg_response_time, 1),
        'today': today,
        'week_ago': week_ago,
        'month_ago': month_ago,
    }
    
    return render(request, 'incidents/dashboard.html', context)

@login_required
def bulk_action(request):
    """Perform bulk actions on incidents."""
    if not request.user.can_acknowledge_incidents():
        messages.error(request, _('You do not have permission to perform bulk actions.'))
        return redirect('incidents:list')
    
    if request.method == 'POST':
        incident_ids = request.POST.getlist('incident_ids')
        action = request.POST.get('action')
        
        if not incident_ids:
            messages.warning(request, _('No incidents selected.'))
            return redirect('incidents:list')
        
        incidents = Incident.objects.filter(pk__in=incident_ids)
        
        if action == 'acknowledge':
            count = 0
            for incident in incidents.filter(status='detected'):
                if incident.acknowledge(request.user):
                    count += 1
            messages.success(request, _(f'{count} incidents acknowledged.'))
        
        elif action == 'assign':
            user_id = request.POST.get('assigned_user')
            if user_id:
                user = get_object_or_404(User, pk=user_id)
                incidents.update(assigned_to=user)
                messages.success(request, _(f'{incidents.count()} incidents assigned to {user}.'))
        
        elif action == 'resolve':
            notes = request.POST.get('resolution_notes', '')
            count = 0
            for incident in incidents:
                if incident.resolve(request.user, notes):
                    count += 1
            messages.success(request, _(f'{count} incidents resolved.'))
        
        elif action == 'false_alarm':
            count = 0
            for incident in incidents:
                if incident.mark_as_false_alarm(request.user):
                    count += 1
            messages.success(request, _(f'{count} incidents marked as false alarms.'))
        
        elif action == 'delete':
            if request.user.is_superuser:
                count = incidents.count()
                incidents.delete()
                messages.success(request, _(f'{count} incidents deleted.'))
            else:
                messages.error(request, _('Only administrators can delete incidents.'))
    
    return redirect('incidents:list')

@login_required
def incident_export(request):
    """Export incidents as CSV or JSON."""
    if not request.user.can_acknowledge_incidents():
        return HttpResponseForbidden()
    
    format = request.GET.get('format', 'csv')
    incidents = Incident.objects.all().order_by('-detected_at')
    
    if format == 'json':
        import json
        from django.http import JsonResponse
        
        data = []
        for incident in incidents:
            data.append({
                'id': incident.incident_id,
                'title': incident.title,
                'type': incident.get_incident_type_display(),
                'severity': incident.get_severity_display(),
                'status': incident.get_status_display(),
                'camera': incident.camera.name if incident.camera else None,
                'detected_at': incident.detected_at.isoformat(),
                'location': incident.location_description,
            })
        
        return JsonResponse(data, safe=False, json_dumps_params={'indent': 2})
    
    else:  # CSV
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="incidents.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Incident ID', 'Title', 'Type', 'Severity', 'Status',
            'Camera', 'Location', 'Detected At', 'Acknowledged At',
            'Resolved At', 'Assigned To', 'Confidence Score'
        ])
        
        for incident in incidents:
            writer.writerow([
                incident.incident_id,
                incident.title,
                incident.get_incident_type_display(),
                incident.get_severity_display(),
                incident.get_status_display(),
                incident.camera.name if incident.camera else '',
                incident.location_description,
                incident.detected_at.strftime('%Y-%m-%d %H:%M:%S'),
                incident.acknowledged_at.strftime('%Y-%m-%d %H:%M:%S') if incident.acknowledged_at else '',
                incident.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if incident.resolved_at else '',
                str(incident.assigned_to) if incident.assigned_to else '',
                incident.confidence_score
            ])
        
        return response