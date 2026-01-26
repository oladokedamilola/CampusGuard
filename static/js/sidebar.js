// Sidebar functionality
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mainContent = document.querySelector('.main-content');
    const sidebarOverlay = document.querySelector('.sidebar-overlay');
    
    // Check for saved preference
    const isSidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    
    // Initialize sidebar state
    if (isSidebarCollapsed) {
        collapseSidebar();
    }
    
    // Toggle sidebar
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            if (sidebar.classList.contains('collapsed')) {
                expandSidebar();
            } else {
                collapseSidebar();
            }
        });
    }
    
    // Mobile sidebar toggle
    const mobileSidebarToggle = document.getElementById('mobileSidebarToggle');
    if (mobileSidebarToggle) {
        mobileSidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('mobile-open');
            if (sidebarOverlay) {
                sidebarOverlay.classList.toggle('show');
            }
        });
    }
    
    // Close sidebar on overlay click (mobile)
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            sidebar.classList.remove('mobile-open');
            sidebarOverlay.classList.remove('show');
        });
    }
    
    // Auto-collapse sidebar on mobile
    function handleResize() {
        if (window.innerWidth <= 992) {
            sidebar.classList.remove('collapsed');
            mainContent.classList.remove('expanded');
        }
    }
    
    window.addEventListener('resize', handleResize);
    handleResize(); // Initial check
    
    // Functions
    function collapseSidebar() {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('expanded');
        localStorage.setItem('sidebarCollapsed', 'true');
        
        // Update tooltips for collapsed icons
        updateSidebarTooltips();
    }
    
    function expandSidebar() {
        sidebar.classList.remove('collapsed');
        mainContent.classList.remove('expanded');
        localStorage.setItem('sidebarCollapsed', 'false');
        
        // Remove tooltips when expanded
        removeSidebarTooltips();
    }
    
    function updateSidebarTooltips() {
        // Add tooltips to sidebar items when collapsed
        const navLinks = sidebar.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            const text = link.querySelector('.nav-link-text')?.textContent || '';
            if (text && !link.hasAttribute('data-bs-original-title')) {
                link.setAttribute('data-bs-toggle', 'tooltip');
                link.setAttribute('data-bs-placement', 'right');
                link.setAttribute('data-bs-title', text);
                
                // Initialize tooltip
                new bootstrap.Tooltip(link, {
                    trigger: 'hover'
                });
            }
        });
    }
    
    function removeSidebarTooltips() {
        // Remove tooltips from sidebar items
        const navLinks = sidebar.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            if (link.hasAttribute('data-bs-original-title')) {
                const tooltip = bootstrap.Tooltip.getInstance(link);
                if (tooltip) {
                    tooltip.dispose();
                }
                link.removeAttribute('data-bs-toggle');
                link.removeAttribute('data-bs-placement');
                link.removeAttribute('data-bs-title');
                link.removeAttribute('data-bs-original-title');
            }
        });
    }
    
    // Set active sidebar item based on current page
    function setActiveSidebarItem() {
        const currentPath = window.location.pathname;
        const navLinks = sidebar.querySelectorAll('.nav-link');
        
        navLinks.forEach(link => {
            link.classList.remove('active');
            const href = link.getAttribute('href');
            
            if (href && currentPath.startsWith(href)) {
                link.classList.add('active');
                
                // Also activate parent dropdown if exists
                const parentDropdown = link.closest('.dropdown');
                if (parentDropdown) {
                    const dropdownToggle = parentDropdown.querySelector('.dropdown-toggle');
                    if (dropdownToggle) {
                        dropdownToggle.classList.add('active');
                    }
                }
            }
        });
    }
    
    setActiveSidebarItem();
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl + B to toggle sidebar
        if (e.ctrlKey && e.key === 'b') {
            e.preventDefault();
            if (sidebarToggle) {
                sidebarToggle.click();
            }
        }
        
        // Escape to close mobile sidebar
        if (e.key === 'Escape' && window.innerWidth <= 992) {
            if (sidebar.classList.contains('mobile-open')) {
                sidebar.classList.remove('mobile-open');
                if (sidebarOverlay) {
                    sidebarOverlay.classList.remove('show');
                }
            }
        }
    });
    
    // Initialize tooltips for collapsed sidebar
    if (sidebar.classList.contains('collapsed')) {
        updateSidebarTooltips();
    }
});