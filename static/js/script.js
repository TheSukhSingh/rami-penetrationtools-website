// Global state
let currentPage = "home";
let currentTestimonial = 0;
let currentAuthMode = "login";
let likedPosts = new Set();

// Sample data
const testimonials = [
  {
    name: "Alex Chen",
    role: "Senior Penetration Tester • CyberSec Corp",
    content:
      "Hunter's Terminal has revolutionized our reconnaissance process. The automated chains save us hours of manual work while maintaining the precision we need.",
    avatar: "🥷",
    specialty: "Network Security",
  },
  {
    name: "Sarah Rodriguez",
    role: "Bug Hunter • Independent",
    content:
      "The solo tools are incredibly powerful. I've discovered vulnerabilities that other platforms missed. The stealth capabilities are unmatched.",
    avatar: "🕵️",
    specialty: "Web Application Security",
  },
  {
    name: "Marcus Johnson",
    role: "CISO • TechGuard Solutions",
    content:
      "Our team's productivity has increased 300% since implementing Hunter's Terminal. The reporting features are enterprise-grade.",
    avatar: "👨‍💼",
    specialty: "Enterprise Security",
  },
  {
    name: "Emma Thompson",
    role: "Red Team Lead • DefenseFirst",
    content:
      "The intelligence gathering capabilities are phenomenal. We can now correlate data from multiple sources seamlessly.",
    avatar: "🔍",
    specialty: "Threat Intelligence",
  },
];

// Initialize the application
document.addEventListener("DOMContentLoaded", function () {
  initializeApp();
});

function initializeApp() {
  setupEventListeners();
  initializeHero();
  initializeWireframeGlobe();
  initializeTestimonials();
  initializeRevealAnimation();
  initializeParticles();

  // Handle scroll events
  window.addEventListener("scroll", handleScroll);
}

function setupEventListeners() {
  // Navigation
  document
    .getElementById("prevTestimonial")
    .addEventListener("click", prevTestimonial);
  document
    .getElementById("nextTestimonial")
    .addEventListener("click", nextTestimonial);

  // Auto-advance testimonials
  setInterval(nextTestimonial, 5000);
}

function initializeHero() {
  const typedTextElement = document.getElementById("typedText");
  const fullText = "> scan-the-unseen --deep --stealth";
  let index = 0;

  function typeText() {
    if (index < fullText.length) {
      typedTextElement.textContent = fullText.slice(0, index + 1);
      index++;
      setTimeout(typeText, 100);
    } else {
      typedTextElement.classList.add("typing");
    }
  }

  typeText();
}

function initializeWireframeGlobe() {
  const canvas = document.getElementById("wireframeGlobe");
  const ctx = canvas.getContext("2d");
  let rotation = 0;

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function drawGlobe() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.min(canvas.width, canvas.height) * 0.3;

    ctx.strokeStyle = "#00FFE0";
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.6;

    // Draw longitude lines
    for (let i = 0; i < 16; i++) {
      const angle = (i * Math.PI) / 8;
      ctx.beginPath();

      for (let j = 0; j <= 100; j++) {
        const phi = (j * Math.PI) / 100;
        const x = centerX + radius * Math.sin(phi) * Math.cos(angle + rotation);
        const y = centerY + radius * Math.cos(phi);
        const z = radius * Math.sin(phi) * Math.sin(angle + rotation);

        const scale = 1 + z / (radius * 2);
        const projectedX = centerX + (x - centerX) * scale;
        const projectedY = centerY + (y - centerY) * scale;

        if (j === 0) {
          ctx.moveTo(projectedX, projectedY);
        } else {
          ctx.lineTo(projectedX, projectedY);
        }
      }
      ctx.stroke();
    }

    // Draw latitude lines
    for (let i = 1; i < 8; i++) {
      const phi = (i * Math.PI) / 8;
      const r = radius * Math.sin(phi);
      const y = centerY + radius * Math.cos(phi);

      ctx.beginPath();
      for (let j = 0; j <= 100; j++) {
        const angle = (j * Math.PI * 2) / 100;
        const x = centerX + r * Math.cos(angle + rotation);
        const z = r * Math.sin(angle + rotation);

        const scale = 1 + z / (radius * 2);
        const projectedX = centerX + (x - centerX) * scale;
        const projectedY = centerY + (y - centerY) * scale;

        if (j === 0) {
          ctx.moveTo(projectedX, projectedY);
        } else {
          ctx.lineTo(projectedX, projectedY);
        }
      }
      ctx.stroke();
    }

    rotation += 0.005;
    requestAnimationFrame(drawGlobe);
  }

  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);
  drawGlobe();
}

function initializeTestimonials() {
  updateTestimonial();
}

function updateTestimonial() {
  const testimonial = testimonials[currentTestimonial];

  document.getElementById(
    "testimonialText"
  ).textContent = `"${testimonial.content}"`;
  document.getElementById("testimonialName").textContent = testimonial.name;
  document.getElementById("testimonialRole").textContent = testimonial.role;
  document.getElementById("testimonialAvatar").textContent = testimonial.avatar;
  document.getElementById("testimonialSpecialty").innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <circle cx="12" cy="16" r="1"></circle>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
        <span>${testimonial.specialty}</span>
    `;

  // Update dots
  const dots = document.querySelectorAll(".dot");
  dots.forEach((dot, index) => {
    dot.classList.toggle("active", index === currentTestimonial);
  });
}

function nextTestimonial() {
  currentTestimonial = (currentTestimonial + 1) % testimonials.length;
  updateTestimonial();
}

function prevTestimonial() {
  currentTestimonial =
    (currentTestimonial - 1 + testimonials.length) % testimonials.length;
  updateTestimonial();
}

function setTestimonial(index) {
  currentTestimonial = index;
  updateTestimonial();
}

function initializeRevealAnimation() {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: "0px 0px -50px 0px",
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("active");
      }
    });
  }, observerOptions);

  const revealElements = document.querySelectorAll(".reveal");
  revealElements.forEach((el) => observer.observe(el));
}

function initializeParticles() {
  const particlesContainer = document.getElementById("particles");

  for (let i = 0; i < 20; i++) {
    const particle = document.createElement("div");
    particle.className = "particle";
    particle.style.left = `${Math.random() * 100}%`;
    particle.style.top = `${Math.random() * 100}%`;
    particle.style.animationDelay = `${Math.random() * 3}s`;
    particle.style.animationDuration = `${2 + Math.random() * 2}s`;
    particlesContainer.appendChild(particle);
  }
}

function handleScroll() {
  const navbar = document.getElementById("navbar");
  if (window.scrollY > 20) {
    navbar.classList.add("scrolled");
  } else {
    navbar.classList.remove("scrolled");
  }
}
