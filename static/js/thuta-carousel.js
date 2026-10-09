/**
 * THUTA E-Learning — Accessible Horizontal Carousel Controller
 * Supports keyboard accessibility, smooth scrolling, reduced motion preference,
 * desktop prev/next controls, and touch swipe.
 */
(function() {
    function initCarousels() {
        const prevButtons = document.querySelectorAll('[data-carousel-prev]');
        
        prevButtons.forEach(function(prevBtn) {
            const sectionId = prevBtn.getAttribute('data-carousel-prev');
            const track = document.getElementById('carousel-track-' + sectionId);
            const nextBtn = document.querySelector('[data-carousel-next="' + sectionId + '"]');
            
            if (!track) return;

            // Respect prefers-reduced-motion
            const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            const behavior = prefersReducedMotion ? 'auto' : 'smooth';

            function updateButtons() {
                const maxScrollLeft = track.scrollWidth - track.clientWidth;
                if (maxScrollLeft <= 0) {
                    prevBtn.disabled = true;
                    if (nextBtn) nextBtn.disabled = true;
                    return;
                }
                prevBtn.disabled = track.scrollLeft <= 5;
                if (nextBtn) nextBtn.disabled = track.scrollLeft >= maxScrollLeft - 5;
            }

            prevBtn.addEventListener('click', function() {
                const item = track.querySelector('.thuta-carousel-item');
                const scrollAmount = item ? (item.offsetWidth + 20) * 2 : track.clientWidth * 0.8;
                track.scrollBy({ left: -scrollAmount, behavior: behavior });
            });

            if (nextBtn) {
                nextBtn.addEventListener('click', function() {
                    const item = track.querySelector('.thuta-carousel-item');
                    const scrollAmount = item ? (item.offsetWidth + 20) * 2 : track.clientWidth * 0.8;
                    track.scrollBy({ left: scrollAmount, behavior: behavior });
                });
            }

            // Keyboard navigation when track is focused
            track.addEventListener('keydown', function(e) {
                if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    prevBtn.click();
                } else if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    if (nextBtn) nextBtn.click();
                }
            });

            track.addEventListener('scroll', updateButtons, { passive: true });
            window.addEventListener('resize', updateButtons);
            // Initial check
            updateButtons();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCarousels);
    } else {
        initCarousels();
    }
})();

