// Shared navbar behavior (theme toggle, mobile menu) -- used by both the
// landing page and the app pages via templates/partials/navbar.html. See
// docs/06-ui-review.md for why this was extracted (used to be copy-pasted
// per page and drifted).
//
// Note: the *initial* theme (before this script even runs) is set by an
// inline script in <head> to avoid a flash of the wrong theme on load --
// initTheme() here just syncs the icon state to whatever that already set.

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const sunIcons = document.querySelectorAll('.sun-icon');
    const moonIcons = document.querySelectorAll('.moon-icon');

    if (theme === 'light') {
        sunIcons.forEach(icon => icon.style.display = 'none');
        moonIcons.forEach(icon => icon.style.display = 'block');
    } else {
        sunIcons.forEach(icon => icon.style.display = 'block');
        moonIcons.forEach(icon => icon.style.display = 'none');
    }
}

function initTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    updateThemeIcon(currentTheme);
}

document.addEventListener('DOMContentLoaded', initTheme);

function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const isOpen = menu.classList.toggle('active');
    // aria-expanded (docs/16, 16-17): the button never reflected open/
    // closed state to assistive tech -- it was hardcoded false in the
    // markup and never updated.
    const btn = document.querySelector('.mobile-menu-btn');
    if (btn) btn.setAttribute('aria-expanded', String(isOpen));
}

// Close mobile menu when clicking outside it (or its toggle button).
document.addEventListener('click', (e) => {
    const mobileMenu = document.getElementById('mobileMenu');
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    if (!mobileMenu || !mobileMenuBtn) return;

    if (mobileMenu.classList.contains('active') &&
        !mobileMenu.contains(e.target) &&
        !mobileMenuBtn.contains(e.target)) {
        mobileMenu.classList.remove('active');
        mobileMenuBtn.setAttribute('aria-expanded', 'false');
    }
});
