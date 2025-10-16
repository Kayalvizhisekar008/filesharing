document.addEventListener('DOMContentLoaded', function() {
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const menuButton = document.getElementById('menu-button');
    const dropdownMenu = document.getElementById('dropdown-menu');

    // Initialize sidebar from localStorage
    const sidebarState = localStorage.getItem('sidebarState');
    if (sidebarState === 'closed') {
        sidebar.classList.add('sidebar-hidden');
        sidebar.classList.remove('sidebar-open');
    } else {
        if (window.innerWidth >= 640) {  // On desktop, default to open
            sidebar.classList.remove('sidebar-hidden');
            sidebar.classList.add('sidebar-open');
        } else {  // On mobile, default to closed
            sidebar.classList.add('sidebar-hidden');
            sidebar.classList.remove('sidebar-open');
        }
    }

    // Sidebar toggle
    sidebarToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        sidebar.classList.toggle('sidebar-hidden');
        sidebar.classList.toggle('sidebar-open');
        localStorage.setItem('sidebarState', 
            sidebar.classList.contains('sidebar-hidden') ? 'closed' : 'open'
        );
    });

    // Profile menu toggle with animation
    menuButton.addEventListener('click', (e) => {
        e.stopPropagation();
        const isVisible = !dropdownMenu.classList.contains('hidden');
        
        // First hide any visible dropdowns
        document.querySelectorAll('.dropdown-menu').forEach(menu => {
            if (menu !== dropdownMenu && !menu.classList.contains('hidden')) {
                menu.classList.add('hidden');
            }
        });
        
        // Toggle the clicked dropdown with animation
        if (isVisible) {
            dropdownMenu.classList.add('hidden');
        } else {
            dropdownMenu.classList.remove('hidden');
            // Add animation
            dropdownMenu.style.opacity = '0';
            dropdownMenu.style.transform = 'translateY(-10px)';
            setTimeout(() => {
                dropdownMenu.style.opacity = '1';
                dropdownMenu.style.transform = 'translateY(0)';
            }, 50);
        }
    });

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!menuButton.contains(e.target) && !dropdownMenu.contains(e.target)) {
            dropdownMenu.classList.add('hidden');
        }

        // Close sidebar on mobile
        if (window.innerWidth < 640 && 
            !sidebar.contains(e.target) && 
            !sidebarToggle.contains(e.target)) {
            sidebar.classList.add('sidebar-hidden');
            sidebar.classList.remove('sidebar-open');
        }
    });

    // Handle window resize
    window.addEventListener('resize', () => {
        if (window.innerWidth >= 640 && !sidebar.classList.contains('sidebar-open')) {
            sidebar.classList.remove('sidebar-hidden');
            sidebar.classList.add('sidebar-open');
        } else if (window.innerWidth < 640 && sidebar.classList.contains('sidebar-open')) {
            sidebar.classList.add('sidebar-hidden');
            sidebar.classList.remove('sidebar-open');
        }
        // Hide dropdown on resize
        dropdownMenu.classList.add('hidden');
    });
});