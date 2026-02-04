# smart_surveillance/reports/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from datetime import datetime

from accounts.decorators import viewer_required, admin_or_manager_required
from .models import IncidentReport, IncidentImage, IncidentCategory, IncidentLocation
from .forms import *

from datetime import timedelta
import requests
from django.conf import settings

from django.http import JsonResponse, HttpResponse
import csv
import json
from django.core import serializers

from django.contrib.auth import get_user_model

User = get_user_model()

# ======================
# VIEWER VIEWS
# ======================

@login_required
@viewer_required
def report_list(request):
    """List all reports (Viewer sees only their own)."""
    if request.user.can_view_all_reports():
        # Manager or Admin sees all
        reports = IncidentReport.objects.all().order_by('-created_at')
    else:
        # Viewer sees only their own
        reports = IncidentReport.objects.filter(reporter=request.user).order_by('-created_at')
    
    # Calculate counts
    total_reports = reports.count()
    pending_reports = reports.filter(status='pending').count()
    resolved_reports = reports.filter(status='resolved').count()
    processing_reports = reports.filter(status='processing').count()
    
    context = {
        'reports': reports,
        'total_reports': total_reports,
        'pending_reports': pending_reports,
        'resolved_reports': resolved_reports,
        'processing_reports': processing_reports,  # Add this
    }
    return render(request, 'reports/report_list.html', context)

@login_required
@viewer_required
def my_reports(request):
    """Viewer's personal reports dashboard."""
    reports = IncidentReport.objects.filter(reporter=request.user).order_by('-created_at')
    
    # Statistics
    stats = {
        'total': reports.count(),
        'pending': reports.filter(status='pending').count(),
        'processing': reports.filter(status='processing').count(),
        'resolved': reports.filter(status='resolved').count(),
    }
    
    context = {
        'reports': reports,
        'stats': stats,
    }
    return render(request, 'reports/my_reports.html', context)

# smart_surveillance/reports/views.py (update the create_report view)
@login_required
@viewer_required
def create_report(request):
    """Create a new incident report."""
    if request.method == 'POST':
        form = IncidentReportForm(request.POST, request.FILES)
        if form.is_valid():
            # Save report with current user as reporter
            report = form.save(commit=False)
            report.reporter = request.user
            report.save()
            
            # Handle image uploads
            images = request.FILES.getlist('images')
            for image in images:
                IncidentImage.objects.create(
                    incident=report,
                    image=image
                )
            
            messages.success(request, _('Incident report submitted successfully!'))
            return redirect('reports:my_reports')
    else:
        form = IncidentReportForm()
    
    context = {
        'form': form,
        'title': _('Report New Incident'),
    }
    return render(request, 'reports/create_report.html', context)

@login_required
def report_detail(request, report_id):
    """View details of a specific report."""
    if request.user.can_view_all_reports():
        # Manager/Admin can view any report
        report = get_object_or_404(IncidentReport, id=report_id)
    else:
        # Viewer can only view their own reports
        report = get_object_or_404(IncidentReport, id=report_id, reporter=request.user)
    
    images = report.images.all()
    updates = report.updates.all().order_by('-created_at')
    
    context = {
        'report': report,
        'images': images,
        'updates': updates,
        'can_edit': (report.reporter == request.user and report.status == 'pending'),
    }
    return render(request, 'reports/report_detail.html', context)

@login_required
def add_image(request, report_id):
    """Add additional images to an existing report."""
    if request.user.can_view_all_reports():
        report = get_object_or_404(IncidentReport, id=report_id)
    else:
        report = get_object_or_404(IncidentReport, id=report_id, reporter=request.user)
    
    if request.method == 'POST':
        form = IncidentImageForm(request.POST, request.FILES)
        if form.is_valid():
            image = form.save(commit=False)
            image.incident = report
            image.save()
            messages.success(request, _('Image added successfully!'))
            return redirect('reports:detail', report_id=report_id)
    else:
        form = IncidentImageForm()
    
    context = {
        'form': form,
        'report': report,
    }
    return render(request, 'reports/add_image.html', context)

# ======================
# API VIEWS
# ======================

@login_required
def get_locations(request):
    """Get locations for dropdown (AJAX)."""
    locations = IncidentLocation.objects.all().values('id', 'name', 'building')
    return JsonResponse(list(locations), safe=False)

@login_required
def get_categories(request):
    """Get categories for dropdown (AJAX)."""
    categories = IncidentCategory.objects.all().values('id', 'name')
    return JsonResponse(list(categories), safe=False)




# ======================
# MANAGER VIEWS
# ======================
@login_required
@admin_or_manager_required
def reports_queue(request):
    """Manager's queue of reports to process."""
    reports = IncidentReport.objects.filter(status='pending').order_by('-priority', '-created_at')
    
    # Filter form
    filter_form = IncidentFilterForm(request.GET or None)
    
    if filter_form.is_valid():
        status = filter_form.cleaned_data.get('status')
        category = filter_form.cleaned_data.get('category')
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')
        
        if status:
            reports = reports.filter(status=status)
        if category:
            reports = reports.filter(category=category)
        if date_from:
            reports = reports.filter(created_at__date__gte=date_from)
        if date_to:
            reports = reports.filter(created_at__date__lte=date_to)
    
    context = {
        'reports': reports,
        'filter_form': filter_form,
        'queue_count': reports.count(),
    }
    return render(request, 'reports/manager/reports_queue.html', context)

@login_required
@admin_or_manager_required
def process_report(request, report_id):
    """Process a specific report with AI tools."""
    report = get_object_or_404(IncidentReport, id=report_id)
    images = report.images.all()
    
    # Initialize forms
    status_form = IncidentUpdateForm(request.POST or None, prefix='status')
    analysis_form = ImageAnalysisForm(request.POST or None, prefix='analysis')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'analyze_images' and analysis_form.is_valid():
            # Get form data
            analyze_all = analysis_form.cleaned_data.get('analyze_all', True)
            reanalyze = analysis_form.cleaned_data.get('reanalyze', False)
            blur_faces = analysis_form.cleaned_data.get('blur_faces', True)
            
            # Determine which images to analyze
            images_to_analyze = images
            if not reanalyze:
                images_to_analyze = images.filter(ai_analysis={})  # Empty JSON field
            
            # Analyze images
            success_count = 0
            for image in images_to_analyze:
                try:
                    # Prepare data for FastAPI
                    files = {'image': image.image.file}
                    data = {
                        'blur_faces': str(blur_faces).lower(),
                        'detect_objects': str(analysis_form.cleaned_data.get('detect_objects', True)).lower(),
                        'assess_risk': str(analysis_form.cleaned_data.get('assess_risk', True)).lower(),
                        'report_id': str(report_id),
                        'image_id': str(image.id)
                    }
                    
                    # Call FastAPI endpoint
                    response = requests.post(
                        f'{settings.FASTAPI_URL}/analyze-image/',
                        files=files,
                        data=data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        image.ai_analysis = result
                        image.analyzed_at = timezone.now()
                        
                        # Update faces_blurred if faces were detected and blurred
                        if blur_faces and result.get('faces_detected', 0) > 0:
                            image.faces_blurred = True
                        
                        image.save()
                        success_count += 1
                        messages.success(request, f'AI analysis completed for image {image.id[:8]}')
                    else:
                        messages.error(request, f'Error analyzing image {image.id[:8]}: {response.text}')
                        
                except requests.exceptions.RequestException as e:
                    messages.error(request, f'Connection error for image {image.id[:8]}: {str(e)}')
                except Exception as e:
                    messages.error(request, f'Error analyzing image {image.id[:8]}: {str(e)}')
            
            if success_count > 0:
                messages.success(request, f'Successfully analyzed {success_count} image(s).')
        
        elif action == 'update_status' and status_form.is_valid():
            new_status = status_form.cleaned_data.get('status_change')
            notes = status_form.cleaned_data.get('notes', '').strip()
            
            if new_status and new_status != report.status:
                report.status = new_status
                report.save()
                
                # Create update log
                IncidentUpdate.objects.create(
                    incident=report,
                    updated_by=request.user,
                    status_change=new_status,
                    notes=notes or f'Status changed to {new_status}'
                )
                
                messages.success(request, f'Report status updated to {new_status}.')
            
            elif notes:  # Only notes update
                IncidentUpdate.objects.create(
                    incident=report,
                    updated_by=request.user,
                    notes=notes
                )
                messages.success(request, 'Note added to report.')
        
        elif action == 'assign_to_me':
            # In future, we could add assignment model
            messages.success(request, 'Report assigned to you.')
        
        return redirect('reports:process_report', report_id=report_id)
    
    context = {
        'report': report,
        'images': images,
        'status_form': status_form,
        'analysis_form': analysis_form,
        'has_unanalyzed_images': any(not img.has_analysis for img in images),
    }
    return render(request, 'reports/manager/process_report.html', context)

@login_required
@admin_or_manager_required
def case_management(request):
    """Manage cases and investigations."""
    # Get reports being processed by current manager
    processing_reports = IncidentReport.objects.filter(status='processing').order_by('-updated_at')
    resolved_reports = IncidentReport.objects.filter(status='resolved').order_by('-updated_at')[:20]
    
    context = {
        'processing_reports': processing_reports,
        'resolved_reports': resolved_reports,
    }
    return render(request, 'reports/manager/case_management.html', context)


@login_required
@admin_or_manager_required
def search_reports(request):
    """Search and filter reports with advanced options."""
    search_form = ReportSearchForm(request.GET or None)
    results = IncidentReport.objects.all()
    
    if search_form.is_valid():
        # Get search query
        query = search_form.cleaned_data.get('query', '').strip()
        if query:
            results = results.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(reporter__first_name__icontains=query) |
                Q(reporter__last_name__icontains=query) |
                Q(reporter__email__icontains=query)
            )
        
        # Apply filters
        statuses = search_form.cleaned_data.get('status')
        if statuses:
            results = results.filter(status__in=statuses)
        
        categories = search_form.cleaned_data.get('category')
        if categories:
            results = results.filter(category__in=categories)
        
        locations = search_form.cleaned_data.get('location')
        if locations:
            results = results.filter(location__in=locations)
        
        priorities = search_form.cleaned_data.get('priority')
        if priorities:
            results = results.filter(priority__in=priorities)
        
        # Date range filtering
        date_range = search_form.cleaned_data.get('date_range', 'month')
        today = timezone.now().date()
        
        if date_range == 'today':
            results = results.filter(created_at__date=today)
        elif date_range == 'week':
            week_ago = today - timedelta(days=7)
            results = results.filter(created_at__date__gte=week_ago)
        elif date_range == 'month':
            month_ago = today - timedelta(days=30)
            results = results.filter(created_at__date__gte=month_ago)
        elif date_range == 'quarter':
            quarter_ago = today - timedelta(days=90)
            results = results.filter(created_at__date__gte=quarter_ago)
        elif date_range == 'year':
            year_ago = today - timedelta(days=365)
            results = results.filter(created_at__date__gte=year_ago)
        elif date_range == 'custom':
            date_from = search_form.cleaned_data.get('custom_date_from')
            date_to = search_form.cleaned_data.get('custom_date_to')
            if date_from:
                results = results.filter(created_at__date__gte=date_from)
            if date_to:
                results = results.filter(created_at__date__lte=date_to)
        
        # Image filter
        has_images = search_form.cleaned_data.get('has_images')
        if has_images == 'yes':
            results = results.filter(images__isnull=False).distinct()
        elif has_images == 'no':
            results = results.filter(images__isnull=True)
        
        # Anonymous filter
        anonymous_only = search_form.cleaned_data.get('anonymous_only')
        if anonymous_only:
            results = results.filter(anonymous=True)
        
        # Sorting
        sort_by = search_form.cleaned_data.get('sort_by', '-created_at')
        results = results.order_by(sort_by)
    
    # Apply default ordering if no sort specified
    if not results.ordered:
        results = results.order_by('-created_at')
    
    context = {
        'results': results,
        'search_form': search_form,
        'result_count': results.count(),
    }
    return render(request, 'reports/manager/search.html', context)

@login_required
@admin_or_manager_required
def analytics_dashboard(request):
    """Advanced analytics and pattern recognition with filtering."""
    filter_form = AnalyticsFilterForm(request.GET or None)
    
    # Default values
    today = timezone.now().date()
    start_date = today - timedelta(days=30)
    end_date = today
    group_by = 'day'
    
    if filter_form.is_valid():
        period = filter_form.cleaned_data.get('period', 'month')
        group_by = filter_form.cleaned_data.get('group_by', 'day')
        
        # Set date range based on period
        if period == 'today':
            start_date = today
            end_date = today
        elif period == 'week':
            start_date = today - timedelta(days=7)
        elif period == 'month':
            start_date = today - timedelta(days=30)
        elif period == 'quarter':
            start_date = today - timedelta(days=90)
        elif period == 'year':
            start_date = today - timedelta(days=365)
        elif period == 'custom':
            start_date = filter_form.cleaned_data.get('custom_start') or start_date
            end_date = filter_form.cleaned_data.get('custom_end') or end_date
    
    # Get base queryset
    reports = IncidentReport.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    
    # Apply additional filters
    if filter_form.is_valid():
        categories = filter_form.cleaned_data.get('category')
        locations = filter_form.cleaned_data.get('location')
        
        if categories:
            reports = reports.filter(category__in=categories)
        if locations:
            reports = reports.filter(location__in=locations)
    
    # Generate data based on grouping
    if group_by == 'day':
        # Daily counts
        date_dict = {}
        current_date = start_date
        while current_date <= end_date:
            date_dict[current_date] = 0
            current_date += timedelta(days=1)
        
        daily_counts = reports.values('created_at__date').annotate(
            count=Count('id')
        ).order_by('created_at__date')
        
        for item in daily_counts:
            date_dict[item['created_at__date']] = item['count']
        
        chart_data = [{'date': date.strftime('%b %d'), 'count': count} 
                     for date, count in sorted(date_dict.items())]
        
    elif group_by == 'category':
        # By category
        chart_data = reports.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')
        
    elif group_by == 'location':
        # By location
        chart_data = reports.values('location__name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
    elif group_by == 'status':
        # By status
        chart_data = reports.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
    elif group_by == 'priority':
        # By priority
        chart_data = reports.values('priority').annotate(
            count=Count('id')
        ).order_by('priority')
    
    # Get category distribution
    category_data = reports.values('category__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Get location hotspots
    location_data = reports.values('location__name', 'location__building').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Get resolution time stats
    resolved_reports = reports.filter(status='resolved')
    if resolved_reports.exists():
        avg_resolution_time = resolved_reports.aggregate(
            avg_time=Avg(F('updated_at') - F('created_at'))
        )['avg_time']
    else:
        avg_resolution_time = None
    
    context = {
        'filter_form': filter_form,
        'chart_data': chart_data,
        'category_data': category_data,
        'location_data': location_data,
        'group_by': group_by,
        'total_reports': reports.count(),
        'avg_resolution_time': avg_resolution_time,
        'today_count': IncidentReport.objects.filter(created_at__date=today).count(),
        'week_count': IncidentReport.objects.filter(
            created_at__date__gte=today - timedelta(days=7)
        ).count(),
        'month_count': IncidentReport.objects.filter(
            created_at__date__gte=today - timedelta(days=30)
        ).count(),
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'reports/manager/analytics.html', context)

@login_required
@admin_or_manager_required
def bulk_actions(request):
    """Handle bulk actions on reports."""
    if request.method == 'POST':
        form = BulkActionForm(request.POST)
        selected_reports = request.POST.getlist('selected_reports')
        
        if form.is_valid() and selected_reports:
            action = form.cleaned_data['action']
            
            if action == 'change_status':
                new_status = form.cleaned_data['target_status']
                count = IncidentReport.objects.filter(
                    id__in=selected_reports
                ).update(status=new_status)
                
                # Create update logs
                for report_id in selected_reports:
                    IncidentUpdate.objects.create(
                        incident_id=report_id,
                        updated_by=request.user,
                        status_change=new_status,
                        notes=f'Bulk status update to {new_status}'
                    )
                
                messages.success(request, f'Updated status for {count} report(s).')
            
            elif action == 'assign_to_me':
                # Future implementation
                messages.success(request, f'Assigned {len(selected_reports)} report(s) to you.')
            
            elif action == 'add_note':
                note = form.cleaned_data['bulk_note']
                count = 0
                for report_id in selected_reports:
                    IncidentUpdate.objects.create(
                        incident_id=report_id,
                        updated_by=request.user,
                        notes=note
                    )
                    count += 1
                messages.success(request, f'Added note to {count} report(s).')
        
        else:
            messages.error(request, 'Please select reports and an action.')
    
    return redirect(request.META.get('HTTP_REFERER', 'reports:reports_queue'))


@login_required
@admin_or_manager_required
def export_reports(request):
    """Export reports in various formats."""
    format = request.GET.get('format', 'csv')
    report_ids = request.GET.getlist('report_ids')
    
    if report_ids:
        reports = IncidentReport.objects.filter(id__in=report_ids)
    else:
        # Get all reports if none specified
        reports = IncidentReport.objects.all()
    
    if format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="incident_reports.csv"'
        
        writer = csv.writer(response)
        # Write header
        writer.writerow([
            'ID', 'Title', 'Description', 'Category', 'Location',
            'Status', 'Priority', 'Reporter', 'Anonymous', 
            'Incident Date', 'Created At', 'Updated At'
        ])
        
        # Write data
        for report in reports:
            writer.writerow([
                report.id,
                report.title,
                report.description[:500],  # Limit description length
                report.category.name if report.category else '',
                report.location.name if report.location else '',
                report.get_status_display(),
                report.get_priority_display(),
                report.display_reporter,
                'Yes' if report.anonymous else 'No',
                report.incident_date,
                report.created_at,
                report.updated_at
            ])
        
        return response
    
    elif format == 'json':
        data = serializers.serialize('json', reports)
        return HttpResponse(data, content_type='application/json')
    
    elif format == 'excel':
        messages.warning(request, 'Excel export requires additional dependencies.')
        return redirect('reports:search')
    
    else:
        messages.error(request, 'Invalid export format.')
        return redirect('reports:search')

@login_required
@admin_or_manager_required
def system_statistics(request):
    """System-wide statistics for admins."""
    from django.db.models import Count, Avg, F
    from django.db.models.functions import ExtractHour
    from django.contrib.auth import get_user_model
    
    User = get_user_model()  # Get the actual User model
    
    # User statistics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    users_by_role = User.objects.values('role').annotate(count=Count('id'))
    
    # Report statistics
    total_reports = IncidentReport.objects.count()
    reports_last_30_days = IncidentReport.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Category statistics
    top_categories = IncidentReport.objects.values(
        'category__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Resolution time statistics
    resolved_reports = IncidentReport.objects.filter(status='resolved')
    if resolved_reports.exists():
        # Calculate average resolution time in hours
        time_diffs = []
        for report in resolved_reports:
            if report.updated_at and report.created_at:
                diff = report.updated_at - report.created_at
                time_diffs.append(diff.total_seconds() / 3600)  # Convert to hours
        
        if time_diffs:
            avg_resolution_hours = sum(time_diffs) / len(time_diffs)
        else:
            avg_resolution_hours = None
    else:
        avg_resolution_hours = None
    
    # Hourly distribution
    hourly_distribution = IncidentReport.objects.annotate(
        hour=ExtractHour('created_at')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Find max count for percentage calculations
    max_hourly_count = max([item['count'] for item in hourly_distribution], default=1)
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'users_by_role': users_by_role,
        'total_reports': total_reports,
        'reports_last_30_days': reports_last_30_days,
        'top_categories': top_categories,
        'avg_resolution_hours': avg_resolution_hours,
        'hourly_distribution': hourly_distribution,
        'max_hourly_count': max_hourly_count,
    }
    return render(request, 'reports/admin/system_stats.html', context)


@login_required
def report_statistics_api(request):
    """API endpoint for report statistics."""
    days = int(request.GET.get('days', 7))
    start_date = timezone.now() - timedelta(days=days)
    
    # Get daily counts
    daily_counts = IncidentReport.objects.filter(
        created_at__gte=start_date
    ).extra({
        'date': "DATE(created_at)"
    }).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Get status distribution
    status_distribution = IncidentReport.objects.values(
        'status'
    ).annotate(
        count=Count('id')
    )
    
    # Get priority distribution
    priority_distribution = IncidentReport.objects.values(
        'priority'
    ).annotate(
        count=Count('id')
    )
    
    data = {
        'daily_counts': list(daily_counts),
        'status_distribution': list(status_distribution),
        'priority_distribution': list(priority_distribution),
        'total_reports': IncidentReport.objects.count(),
        'pending_reports': IncidentReport.objects.filter(status='pending').count(),
    }
    
    return JsonResponse(data)

@login_required
def analytics_data_api(request):
    """API endpoint for analytics data."""
    group_by = request.GET.get('group_by', 'day')
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    reports = IncidentReport.objects.filter(created_at__gte=start_date)
    
    if group_by == 'day':
        data = reports.extra({
            'date': "DATE(created_at)"
        }).values('date').annotate(
            count=Count('id')
        ).order_by('date')
    
    elif group_by == 'category':
        data = reports.values('category__name').annotate(
            count=Count('id')
        ).order_by('-count')
    
    elif group_by == 'location':
        data = reports.values('location__name').annotate(
            count=Count('id')
        ).order_by('-count')
    
    elif group_by == 'hour':
        from django.db.models.functions import ExtractHour
        data = reports.annotate(
            hour=ExtractHour('created_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
    
    else:
        data = []
    
    return JsonResponse({'data': list(data)})

# Add the missing AJAX views
@login_required
@admin_or_manager_required
def ajax_update_status(request, report_id):
    """AJAX endpoint for updating report status."""
    if request.method == 'POST':
        try:
            report = IncidentReport.objects.get(id=report_id)
            new_status = request.POST.get('status')
            notes = request.POST.get('notes', '').strip()
            
            if new_status and new_status in dict(IncidentReport.Status.choices):
                old_status = report.status
                report.status = new_status
                report.save()
                
                # Create update log
                IncidentUpdate.objects.create(
                    incident=report,
                    updated_by=request.user,
                    status_change=new_status,
                    notes=notes or f'Status changed from {old_status} to {new_status}'
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Status updated to {new_status}',
                    'new_status': new_status,
                    'status_display': report.get_status_display()
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid status'
                }, status=400)
                
        except IncidentReport.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Report not found'
            }, status=404)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
@admin_or_manager_required
def ajax_add_note(request, report_id):
    """AJAX endpoint for adding notes to reports."""
    if request.method == 'POST':
        try:
            report = IncidentReport.objects.get(id=report_id)
            notes = request.POST.get('notes', '').strip()
            
            if notes:
                update = IncidentUpdate.objects.create(
                    incident=report,
                    updated_by=request.user,
                    notes=notes
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Note added successfully',
                    'note_id': str(update.id),
                    'created_at': update.created_at.isoformat(),
                    'updated_by': request.user.get_full_name() or request.user.email
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Note cannot be empty'
                }, status=400)
                
        except IncidentReport.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Report not found'
            }, status=404)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
@admin_or_manager_required
def ajax_analyze_image(request, image_id):
    """AJAX endpoint for analyzing a single image."""
    if request.method == 'POST':
        try:
            image = IncidentImage.objects.get(id=image_id)
            
            # Check if image needs analysis
            if image.has_analysis and not request.POST.get('reanalyze'):
                return JsonResponse({
                    'success': False,
                    'message': 'Image already analyzed. Use reanalyze option.'
                })
            
            # Call FastAPI
            files = {'image': image.image.file}
            data = {
                'blur_faces': request.POST.get('blur_faces', 'true'),
                'detect_objects': request.POST.get('detect_objects', 'true'),
                'assess_risk': request.POST.get('assess_risk', 'true'),
                'report_id': str(image.incident.id),
                'image_id': str(image.id)
            }
            
            response = requests.post(
                f'{settings.FASTAPI_URL}/analyze-image/',
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                image.ai_analysis = result
                image.analyzed_at = timezone.now()
                
                if data['blur_faces'] == 'true' and result.get('faces_detected', 0) > 0:
                    image.faces_blurred = True
                
                image.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Image analysis completed',
                    'analysis': result,
                    'analyzed_at': image.analyzed_at.isoformat()
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'Analysis failed: {response.text}'
                }, status=response.status_code)
                
        except IncidentImage.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Image not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    }, status=405)

@login_required
def ajax_get_report_data(request, report_id):
    """AJAX endpoint for getting report data."""
    try:
        if request.user.can_view_all_reports():
            report = IncidentReport.objects.get(id=report_id)
        else:
            report = IncidentReport.objects.get(id=report_id, reporter=request.user)
        
        data = {
            'id': str(report.id),
            'title': report.title,
            'description': report.description,
            'status': report.status,
            'status_display': report.get_status_display(),
            'priority': report.priority,
            'priority_display': report.get_priority_display(),
            'category': report.category.name if report.category else None,
            'location': report.location.name if report.location else None,
            'anonymous': report.anonymous,
            'display_reporter': report.display_reporter,
            'incident_date': report.incident_date.isoformat(),
            'created_at': report.created_at.isoformat(),
            'updated_at': report.updated_at.isoformat(),
            'image_count': report.images.count(),
            'updates': [
                {
                    'notes': update.notes,
                    'status_change': update.status_change,
                    'status_change_display': update.get_status_change_display() if update.status_change else None,
                    'created_at': update.created_at.isoformat(),
                    'updated_by': update.updated_by.get_full_name() if update.updated_by else None
                }
                for update in report.updates.all().order_by('-created_at')[:10]
            ]
        }
        
        return JsonResponse({
            'success': True,
            'report': data
        })
        
    except IncidentReport.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Report not found'
        }, status=404)