// CampusGuard AI - Main JavaScript File

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // HTMX configuration
    htmx.config.useTemplateFragments = true;
    
    // Add loading indicator for HTMX requests
    document.body.addEventListener('htmx:beforeRequest', function(evt) {
        var target = evt.target;
        if (target.hasAttribute('hx-indicator')) {
            var indicator = document.querySelector(target.getAttribute('hx-indicator'));
            if (indicator) {
                indicator.classList.add('fa-spin');
            }
        }
    });
    
    document.body.addEventListener('htmx:afterRequest', function(evt) {
        var target = evt.target;
        if (target.hasAttribute('hx-indicator')) {
            var indicator = document.querySelector(target.getAttribute('hx-indicator'));
            if (indicator) {
                indicator.classList.remove('fa-spin');
            }
        }
    });
    
    // Form validation enhancement
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            var requiredFields = form.querySelectorAll('[required]');
            var isValid = true;
            
            requiredFields.forEach(function(field) {
                if (!field.value.trim()) {
                    field.classList.add('is-invalid');
                    isValid = false;
                } else {
                    field.classList.remove('is-invalid');
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                e.stopPropagation();
                
                // Show error message
                var errorDiv = document.createElement('div');
                errorDiv.className = 'alert alert-danger mt-3';
                errorDiv.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i>Please fill in all required fields.';
                form.prepend(errorDiv);
                
                // Scroll to first error
                var firstError = form.querySelector('.is-invalid');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstError.focus();
                }
            }
        });
    });
    
    // Image preview for file inputs
    document.querySelectorAll('input[type="file"][accept^="image"]').forEach(function(input) {
        input.addEventListener('change', function(e) {
            var file = e.target.files[0];
            if (file) {
                var reader = new FileReader();
                reader.onload = function(e) {
                    // Create or update preview
                    var previewId = input.id + '-preview';
                    var preview = document.getElementById(previewId);
                    if (!preview) {
                        preview = document.createElement('div');
                        preview.id = previewId;
                        preview.className = 'image-preview mt-2';
                        input.parentNode.appendChild(preview);
                    }
                    preview.innerHTML = '<img src="' + e.target.result + '" class="img-thumbnail" style="max-height: 200px;">';
                };
                reader.readAsDataURL(file);
            }
        });
    });
    
    // Table row click handler
    document.querySelectorAll('.table tbody tr[data-href]').forEach(function(row) {
        row.addEventListener('click', function(e) {
            if (!e.target.matches('a, button, input, select, textarea')) {
                window.location = this.dataset.href;
            }
        });
        row.style.cursor = 'pointer';
    });
    
    // Mark notifications as read when dropdown opens
    var notificationDropdown = document.getElementById('notificationDropdown');
    if (notificationDropdown) {
        notificationDropdown.addEventListener('show.bs.dropdown', function() {
            // This could be enhanced to mark as read via AJAX
            console.log('Notifications dropdown opened');
        });
    }
});

// Utility functions
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-NG', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatTimeAgo(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);
    
    if (diffDay > 0) return diffDay + ' day' + (diffDay > 1 ? 's' : '') + ' ago';
    if (diffHour > 0) return diffHour + ' hour' + (diffHour > 1 ? 's' : '') + ' ago';
    if (diffMin > 0) return diffMin + ' minute' + (diffMin > 1 ? 's' : '') + ' ago';
    return 'Just now';
}

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    const toastId = 'toast-' + Date.now();
    
    const toast = document.createElement('div');
    toast.id = toastId;
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-${getIconForType(type)} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
    bsToast.show();
    
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

function getIconForType(type) {
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1060';
    document.body.appendChild(container);
    return container;
}