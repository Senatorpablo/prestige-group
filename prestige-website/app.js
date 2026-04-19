/**
 * ============================================================
 * Prestige Group — Main Application JavaScript
 * ============================================================
 * Vanilla JS — no frameworks, no dependencies.
 * Features:
 *   1.  Loading screen animation on page load
 *   2.  Smooth scroll navigation
 *   3.  Sticky navbar with background change on scroll
 *   4.  Mobile hamburger menu toggle
 *   5.  Scroll-triggered fade-in animations (IntersectionObserver)
 *   6.  Counter animation for stats section
 *   7.  Testimonial carousel / slider
 *   8.  Form validation for contact / demo form
 *   9.  Back-to-top button
 *  10.  Active nav link highlighting based on scroll position
 * ============================================================
 */

"use strict";

/* ----------------------------------------------------------
   0.  DOM READY HELPER
   ---------------------------------------------------------- */
function onReady(fn) {
  if (document.readyState !== "loading") fn();
  else document.addEventListener("DOMContentLoaded", fn);
}

/* ----------------------------------------------------------
   1.  LOADING SCREEN
   ---------------------------------------------------------- */
function initLoadingScreen() {
  const loader = document.getElementById("loader");
  if (!loader) return;

  // Fade-out once all critical resources are loaded
  window.addEventListener("load", function () {
    loader.classList.add("loader--hidden");
    // Remove from DOM after transition
    loader.addEventListener("transitionend", function () {
      loader.remove();
    });
  });

  // Fallback: if something stalls, force-hide after 4 s
  setTimeout(function () {
    if (loader.parentNode) {
      loader.classList.add("loader--hidden");
      setTimeout(function () { loader.remove(); }, 600);
    }
  }, 4000);
}

/* ----------------------------------------------------------
   2.  SMOOTH SCROLL NAVIGATION
   ---------------------------------------------------------- */
function initSmoothScroll() {
  document.addEventListener("click", function (e) {
    // Only handle clicks on anchor links that point to an ID on the page
    var link = e.target.closest('a[href^="#"]');
    if (!link) return;

    var targetId = link.getAttribute("href");
    if (targetId === "#" || targetId === "") return;

    var target = document.querySelector(targetId);
    if (!target) return;

    e.preventDefault();

    // Account for fixed navbar height
    var navHeight = document.querySelector(".navbar")
      ? document.querySelector(".navbar").offsetHeight
      : 0;
    var top = target.getBoundingClientRect().top + window.pageYOffset - navHeight;

    window.scrollTo({ top: top, behavior: "smooth" });

    // Close mobile menu if open
    var navMenu = document.querySelector(".nav-links");
    if (navMenu && navMenu.classList.contains("nav-links--open")) {
      navMenu.classList.remove("nav-links--open");
      var hamburger = document.querySelector(".hamburger");
      if (hamburger) hamburger.classList.remove("hamburger--active");
    }
  });
}

/* ----------------------------------------------------------
   3.  STICKY NAVBAR — background change on scroll
   ---------------------------------------------------------- */
function initStickyNavbar() {
  var navbar = document.querySelector(".navbar");
  if (!navbar) return;

  var scrollThreshold = 50; // px before we trigger style change

  function onScroll() {
    if (window.scrollY > scrollThreshold) {
      navbar.classList.add("navbar--scrolled");
    } else {
      navbar.classList.remove("navbar--scrolled");
    }
  }

  // Use passive listener for performance
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll(); // run once on init
}

/* ----------------------------------------------------------
   4.  MOBILE HAMBURGER MENU TOGGLE
   ---------------------------------------------------------- */
function initMobileMenu() {
  var hamburger = document.querySelector(".hamburger");
  var navLinks = document.querySelector(".nav-links");
  if (!hamburger || !navLinks) return;

  hamburger.addEventListener("click", function () {
    var isOpen = navLinks.classList.toggle("nav-links--open");
    hamburger.classList.toggle("hamburger--active", isOpen);
    hamburger.setAttribute("aria-expanded", isOpen);
  });

  // Close menu when clicking outside
  document.addEventListener("click", function (e) {
    if (
      navLinks.classList.contains("nav-links--open") &&
      !navLinks.contains(e.target) &&
      !hamburger.contains(e.target)
    ) {
      navLinks.classList.remove("nav-links--open");
      hamburger.classList.remove("hamburger--active");
      hamburger.setAttribute("aria-expanded", "false");
    }
  });
}

/* ----------------------------------------------------------
   5.  SCROLL-TRIGGERED FADE-IN ANIMATIONS (IntersectionObserver)
   ---------------------------------------------------------- */
function initScrollAnimations() {
  var elements = document.querySelectorAll(".fade-in, .slide-up, .slide-left, .slide-right");
  if (!elements.length) return;

  // Respect user preference for reduced motion
  var prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (prefersReducedMotion) {
    elements.forEach(function (el) {
      el.style.opacity = "1";
      el.style.transform = "none";
    });
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("animate--visible");
          observer.unobserve(entry.target); // animate once
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
  );

  elements.forEach(function (el) {
    observer.observe(el);
  });
}

/* ----------------------------------------------------------
   6.  COUNTER ANIMATION FOR STATS SECTION
   ---------------------------------------------------------- */
function initCounterAnimation() {
  var counters = document.querySelectorAll("[data-count]");
  if (!counters.length) return;

  var duration = 2000; // ms for count-up
  var frameRate = 30; // frames per second
  var totalFrames = Math.round(duration / (1000 / frameRate));

  /**
   * Animate a single counter element from 0 to its target value.
   * @param {HTMLElement} el — element with data-count attribute
   */
  function animateCounter(el) {
    var target = parseInt(el.getAttribute("data-count"), 10);
    if (isNaN(target)) return;

    // Support optional suffix (e.g., "+", "%") via data-suffix
    var suffix = el.getAttribute("data-suffix") || "";
    var prefix = el.getAttribute("data-prefix") || "";

    var frame = 0;
    var step = target / totalFrames;

    function update() {
      frame++;
      var current = Math.min(Math.round(step * frame), target);
      el.textContent = prefix + current.toLocaleString() + suffix;

      if (frame < totalFrames) {
        requestAnimationFrame(update);
      } else {
        el.textContent = prefix + target.toLocaleString() + suffix;
      }
    }

    requestAnimationFrame(update);
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          observer.unobserve(entry.target); // count once
        }
      });
    },
    { threshold: 0.5 }
  );

  counters.forEach(function (el) { observer.observe(el); });
}

/* ----------------------------------------------------------
   7.  TESTIMONIAL CAROUSEL / SLIDER
   ---------------------------------------------------------- */
function initTestimonialCarousel() {
  var track = document.querySelector(".testimonial-track");
  var cards = document.querySelectorAll(".testimonial-card");
  var prevBtn = document.querySelector(".testimonial-btn--prev");
  var nextBtn = document.querySelector(".testimonial-btn--next");
  var dotsContainer = document.querySelector(".testimonial-dots");

  if (!track || !cards.length) return;

  var currentIndex = 0;
  var totalSlides = cards.length;
  var autoplayInterval = null;
  var autoplayDelay = 5000;

  // Build dots if container exists
  var dots = [];
  if (dotsContainer) {
    for (var i = 0; i < totalSlides; i++) {
      (function (idx) {
        var dot = document.createElement("button");
        dot.setAttribute("aria-label", "Go to testimonial " + (idx + 1));
        dot.classList.add("testimonial-dot");
        if (idx === 0) dot.classList.add("testimonial-dot--active");
        dot.addEventListener("click", function () { goTo(idx); });
        dotsContainer.appendChild(dot);
        dots.push(dot);
      })(i);
    }
  }

  function goTo(index) {
    currentIndex = ((index % totalSlides) + totalSlides) % totalSlides;
    track.style.transform = "translateX(-" + (currentIndex * 100) + "%)";

    // Update dots
    dots.forEach(function (d, i) {
      d.classList.toggle("testimonial-dot--active", i === currentIndex);
    });

    // Update card aria visibility
    cards.forEach(function (card, i) {
      card.setAttribute("aria-hidden", i !== currentIndex);
    });
  }

  function next() { goTo(currentIndex + 1); }
  function prev() { goTo(currentIndex - 1); }

  if (nextBtn) nextBtn.addEventListener("click", function () { next(); resetAutoplay(); });
  if (prevBtn) prevBtn.addEventListener("click", function () { prev(); resetAutoplay(); });

  // Autoplay
  function startAutoplay() {
    stopAutoplay();
    autoplayInterval = setInterval(next, autoplayDelay);
  }
  function stopAutoplay() {
    if (autoplayInterval) { clearInterval(autoplayInterval); autoplayInterval = null; }
  }
  function resetAutoplay() { stopAutoplay(); startAutoplay(); }

  // Pause on hover
  track.addEventListener("mouseenter", stopAutoplay);
  track.addEventListener("mouseleave", startAutoplay);

  // Touch / swipe support
  var touchStartX = 0;
  var touchEndX = 0;

  track.addEventListener("touchstart", function (e) {
    touchStartX = e.changedTouches[0].clientX;
    stopAutoplay();
  }, { passive: true });

  track.addEventListener("touchend", function (e) {
    touchEndX = e.changedTouches[0].clientX;
    var diff = touchStartX - touchEndX;
    if (Math.abs(diff) > 50) {
      diff > 0 ? next() : prev();
    }
    startAutoplay();
  }, { passive: true });

  // Keyboard support
  track.setAttribute("tabindex", "0");
  track.addEventListener("keydown", function (e) {
    if (e.key === "ArrowRight") { next(); resetAutoplay(); }
    if (e.key === "ArrowLeft")  { prev(); resetAutoplay(); }
  });

  startAutoplay();
  goTo(0); // initialise
}

/* ----------------------------------------------------------
   8.  FORM VALIDATION (Contact / Demo form)
   ---------------------------------------------------------- */
function initFormValidation() {
  var form = document.getElementById("contact-form") || document.getElementById("demo-form");
  if (!form) return;

  var validators = {
    // Returns error string or empty string if valid
    name: function (v) {
      return v.trim().length < 2 ? "Please enter your full name." : "";
    },
    email: function (v) {
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? "" : "Please enter a valid email address.";
    },
    phone: function (v) {
      if (!v.trim()) return ""; // optional
      return /^[+\d\s().-]{7,20}$/.test(v) ? "" : "Please enter a valid phone number.";
    },
    company: function (v) {
      return v.trim().length < 2 ? "Please enter your company name." : "";
    },
    message: function (v) {
      return v.trim().length < 10 ? "Message must be at least 10 characters." : "";
    },
    service: function (v) {
      return v ? "" : "Please select a service.";
    }
  };

  /**
   * Validate a single field, show / clear error message.
   * @returns {boolean} true if field is valid
   */
  function validateField(input) {
    var name = input.getAttribute("name");
    var validator = validators[name];
    if (!validator) return true;

    var error = validator(input.value);
    var errorEl = input.parentElement.querySelector(".form-error");

    if (error) {
      input.classList.add("form-field--error");
      input.classList.remove("form-field--valid");
      if (errorEl) errorEl.textContent = error;
      return false;
    } else {
      input.classList.remove("form-field--error");
      input.classList.add("form-field--valid");
      if (errorEl) errorEl.textContent = "";
      return true;
    }
  }

  // Live validation on blur
  form.addEventListener("focusout", function (e) {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") {
      validateField(e.target);
    }
  });

  // Submit handler
  form.addEventListener("submit", function (e) {
    e.preventDefault();

    var inputs = form.querySelectorAll("input, textarea, select");
    var isValid = true;

    inputs.forEach(function (input) {
      if (!validateField(input)) isValid = false;
    });

    if (!isValid) {
      // Focus first invalid field
      var firstError = form.querySelector(".form-field--error");
      if (firstError) firstError.focus();
      return;
    }

    // Simulate submission (replace with real endpoint)
    var submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Sending…";
    }

    // ---- Replace this block with actual fetch() to your API ----
    setTimeout(function () {
      form.classList.add("form--success");
      var successMsg = form.querySelector(".form-success-msg");
      if (successMsg) successMsg.style.display = "block";
      form.reset();

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = "Send Message";
      }
    }, 1500);
    // -------------------------------------------------------------
  });
}

/* ----------------------------------------------------------
   9.  BACK-TO-TOP BUTTON
   ---------------------------------------------------------- */
function initBackToTop() {
  var btn = document.getElementById("back-to-top");
  if (!btn) return;

  var showThreshold = 400;

  function toggleVisibility() {
    if (window.scrollY > showThreshold) {
      btn.classList.add("back-to-top--visible");
    } else {
      btn.classList.remove("back-to-top--visible");
    }
  }

  window.addEventListener("scroll", toggleVisibility, { passive: true });

  btn.addEventListener("click", function () {
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
}

/* ----------------------------------------------------------
   10.  ACTIVE NAV LINK HIGHLIGHTING BASED ON SCROLL POSITION
   ---------------------------------------------------------- */
function initActiveNavHighlight() {
  var sections = document.querySelectorAll("section[id]");
  var navLinks = document.querySelectorAll(".nav-link");
  if (!sections.length || !navLinks.length) return;

  var navbarHeight = document.querySelector(".navbar")
    ? document.querySelector(".navbar").offsetHeight
    : 0;

  function onScroll() {
    var scrollPos = window.scrollY + navbarHeight + 80; // 80 px buffer

    sections.forEach(function (section) {
      var top = section.offsetTop;
      var height = section.offsetHeight;
      var id = section.getAttribute("id");

      if (scrollPos >= top && scrollPos < top + height) {
        navLinks.forEach(function (link) {
          link.classList.remove("nav-link--active");
          if (link.getAttribute("href") === "#" + id) {
            link.classList.add("nav-link--active");
          }
        });
      }
    });
  }

  // Throttle scroll events to ~60 fps
  var ticking = false;
  window.addEventListener("scroll", function () {
    if (!ticking) {
      requestAnimationFrame(function () {
        onScroll();
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });

  onScroll(); // run once on init
}

/* ----------------------------------------------------------
   BOOT — Initialise everything when DOM is ready
   ---------------------------------------------------------- */
onReady(function () {
  initLoadingScreen();
  initSmoothScroll();
  initStickyNavbar();
  initMobileMenu();
  initScrollAnimations();
  initCounterAnimation();
  initTestimonialCarousel();
  initFormValidation();
  initBackToTop();
  initActiveNavHighlight();
});