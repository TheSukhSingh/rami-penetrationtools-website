// function showPage(page) {
//   // Hide all pages
//   document
//     .querySelectorAll(".page")
//     .forEach((p) => p.classList.remove("active"));

//   // Show selected page
//   const pageElement = document.getElementById(page + "Page");
//   if (pageElement) {
//     pageElement.classList.add("active");
//     currentPage = page;
//   }

//   // Scroll to top
//   window.scrollTo(0, 0);
// }

function scrollToSection(sectionId) {
  // if (currentPage !== "home") {
  //   showPage("home");
  //   setTimeout(() => {
  //     const element = document.getElementById(sectionId);
  //     if (element) {
  //       element.scrollIntoView({ behavior: "smooth" });
  //     }
  //   }, 100);
  // } else {
  //   const element = document.getElementById(sectionId);
  //   if (element) {
  //     element.scrollIntoView({ behavior: "smooth" });
  //   }
  // }
  const el = document.getElementById(sectionId);
  if (el) el.scrollIntoView({ behavior: "smooth" });
}

// Auth functions
function showAuth(mode) {
  currentAuthMode = mode;
  updateAuthModal();
  document.getElementById("authModal").classList.add("active");
}

function closeAuth() {
  document.getElementById("authModal").classList.remove("active");
}

function toggleMobileMenu() {
  const navMenu = document.getElementById("navMenu");
  const navToggle = document.getElementById("navToggle");

  navMenu.classList.toggle("active");
  navToggle.classList.toggle("active");
}

function togglePassword(fieldId) {
  const field = document.getElementById(fieldId);
  const button = field.nextElementSibling;
  const eyeOpen = button.querySelector(".eye-open");
  const eyeClosed = button.querySelector(".eye-closed");

  if (field.type === "password") {
    field.type = "text";
    eyeOpen.style.display = "none";
    eyeClosed.style.display = "block";
  } else {
    field.type = "password";
    eyeOpen.style.display = "block";
    eyeClosed.style.display = "none";
  }
}

function getCookie(name) {
  return document.cookie
    .split("; ")
    .find((row) => row.startsWith(name + "="))
    ?.split("=")[1];
}

function showUser(user) {
  document.getElementById("loginButton").style.display = "none";
  const navMenu = document.getElementById("navMenu");
  const username = user.username;

  // const initial = user.name ? user.name.charAt(0).toUpperCase() : user.username.charAt(0).toUpperCase();
  const userElem = document.createElement("div");
  userElem.id = "userMenu";
  userElem.className = "user-menu";
  userElem.innerHTML = `
    <button id="userBtn" class="cyber-button">${username}</button>
    <div id="userDropdown" class="dropdown-content">
      <a href="#" id="logoutBtn">Logout</a>
    </div>
  `;
  navMenu.appendChild(userElem);

  document.getElementById("logoutBtn").onclick = async () => {
    await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
      headers: { "X-CSRF-TOKEN": getCookie("csrf_refresh_token") },
    });
    location.reload();
  };
}

function updateAuthModal() {
  const titles = {
    login: "Access Terminal",
    signup: "Join the Hunt",
    forgot: "Reset Access",
  };

  const subtitles = {
    login: "Enter your credentials to continue",
    signup: "Create your hunter account",
    forgot: "Recover your terminal access",
  };

  const buttonTexts = {
    login: "Access Terminal",
    signup: "Create Account",
    forgot: "Send Reset Link",
  };

  document.getElementById("authTitle").textContent = titles[currentAuthMode];
  document.getElementById("authSubtitle").textContent =
    subtitles[currentAuthMode];
  document.getElementById("authButtonText").textContent =
    buttonTexts[currentAuthMode];

  // Show/hide fields based on mode
  const nameField = document.getElementById("nameField");
  const passwordField = document.getElementById("passwordField");
  const confirmPasswordField = document.getElementById("confirmPasswordField");
  const usernameField = document.getElementById("usernameField");

  usernameField.style.display = currentAuthMode === "signup" ? "flex" : "none";
  passwordField.style.display = currentAuthMode === "forgot" ? "none" : "flex";
  nameField.style.display = currentAuthMode === "signup" ? "flex" : "none";
  confirmPasswordField.style.display =
    currentAuthMode === "signup" ? "flex" : "none";

  // Update links
  const authLinks = document.getElementById("authLinks");
  if (currentAuthMode === "login") {
    authLinks.innerHTML = `
            <div>
                <a href="#" class="auth-link" onclick="updateAuthMode('forgot')">Forgot your password?</a>
            </div>
            <div class="auth-text">
                New hunter? 
                <a href="#" class="auth-link" onclick="updateAuthMode('signup')">Join the hunt</a>
            </div>
        `;
  } else if (currentAuthMode === "signup") {
    authLinks.innerHTML = `
            <div class="auth-text">
                Already have an account? 
                <a href="#" class="auth-link" onclick="updateAuthMode('login')">Sign in</a>
            </div>
        `;
  } else if (currentAuthMode === "forgot") {
    authLinks.innerHTML = `
            <div class="auth-text">
                Remember your password? 
                <a href="#" class="auth-link" onclick="updateAuthMode('login')">Sign in</a>
            </div>
        `;
  }
}

function updateAuthMode(mode) {
  currentAuthMode = mode;
  updateAuthModal();
}

async function handleAuthSubmit(event) {
  event.preventDefault();

  const submitButton = document.getElementById("authSubmit");
  const buttonText = document.getElementById("authButtonText");
  const buttonIcon = document.getElementById("authButtonIcon");
  const spinner = document.getElementById("authSpinner");

  buttonText.style.display = "none";
  buttonIcon.style.display = "none";
  spinner.style.display = "block";
  submitButton.disabled = true;

  const urlMap = {
    login: "/auth/signin",
    signup: "/auth/signup",
    forgot: "/auth/forgot-password",
  };
  const url = urlMap[currentAuthMode];
  const form = document.getElementById("authForm");
  const formData = new FormData(form);
  const payload = {};
  formData.forEach((v, k) => {
    payload[k] = v;
  });

  try {
    const res = await fetch(url, {
      method: currentAuthMode === "login" ? "POST" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      // body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.msg || data.message);

    if (currentAuthMode === "login") {
      // localStorage.setItem('access_token', data.access_token);
      // localStorage.setItem('refresh_token', data.refresh_token);
      // // fetch user profile
      // const meRes = await fetch('/auth/me', {
      //   headers: { 'Authorization': `Bearer ${data.access_token}` }
      // });
      // const me = await meRes.json();
      // localStorage.setItem('user', JSON.stringify(me));
      // showUser(me);

      // the cookies are now set by the server,
      // so just hit /auth/me with credentials to get the user profile:
      const meRes = await fetch("/auth/me", {
        method: "GET",
        credentials: "include",
        headers: { "X-CSRF-TOKEN": getCookie("csrf_access_token") },
      });
      if (!meRes.ok) throw new Error("Failed to load user");
      const me = await meRes.json();
      showUser(me);
    }

    closeAuth();
    // alert(currentAuthMode === 'signup'
    //   ? 'Account created! Check your email to confirm.'
    //   : 'Success!'
    // );
  } catch (err) {
    alert(err.message);
  }

  // Simulate API call
  setTimeout(() => {
    // Reset button state
    buttonText.style.display = "inline";
    buttonIcon.style.display = "inline";
    spinner.style.display = "none";
    submitButton.disabled = false;

    // Close modal
    closeAuth();
  }, 2000);
}
// auth
// function initAuth() {
//   const token = localStorage.getItem("access_token");
//   const user = localStorage.getItem("user");
//   if (token && user) {
//     showUser(JSON.parse(user));
//   }
// }

async function initAuth() {
  try {
    const res = await fetch('/auth/me', {
      method: 'GET',
      credentials: 'include',                          // send HTTP-only cookies
      headers: { 'X-CSRF-TOKEN': getCookie('csrf_access_token') }
    });
    if (!res.ok) return;                              // not logged in → bail
    const user = await res.json();
    showUser(user);
  } catch (err) {
    console.error('Auth check failed', err);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initAuth();
  document
    .getElementById("authForm")
    .addEventListener("submit", handleAuthSubmit);
});
