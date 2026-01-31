// static/js/sidebar.js

// Sidebar functionality
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle'); // From top navbar
    const mobileSidebarClose = document.getElementById('mobileSidebarClose');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    const mainContent = document.querySelector('.main-content');
    
    // Check if we're on mobile
    function isMobile() {
        return window.innerWidth < 992;
    }
    
    // Toggle sidebar on mobile only
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (isMobile()) {
                openMobileSidebar();
            }
        });
    }
    
    // Close sidebar on mobile
    if (mobileSidebarClose) {
        mobileSidebarClose.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            closeMobileSidebar();
        });
    }
    
    // Close sidebar on overlay click
    if (sidebarOverlay) {
        sidebarOverlay.addEventListener('click', function() {
            closeMobileSidebar();
        });
    }
    
    // Close sidebar when clicking a link (mobile only)
    document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
        link.addEventListener('click', function() {
            if (isMobile()) {
                closeMobileSidebar();
            }
        });
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        // If resizing to desktop, ensure sidebar is visible
        if (!isMobile()) {
            closeMobileSidebar();
        }
    });
    
    // Keyboard support
    document.addEventListener('keydown', function(e) {
        // Escape to close mobile sidebar
        if (e.key === 'Escape' && isMobile()) {
            closeMobileSidebar();
        }
    });
    
    // Functions
    function openMobileSidebar() {
        sidebar.classList.add('mobile-open');
        sidebarOverlay.classList.add('show');
        mainContent.classList.add('blurred');
        document.body.style.overflow = 'hidden'; // Prevent scrolling
    }
    
    function closeMobileSidebar() {
        sidebar.classList.remove('mobile-open');
        sidebarOverlay.classList.remove('show');
        mainContent.classList.remove('blurred');
        document.body.style.overflow = ''; // Restore scrolling
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
            }
        });
    }
    
    setActiveSidebarItem();
});