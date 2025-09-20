let currentAuthMode = "login";

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
let turnstileWidgetId = null;

function getTurnstileSiteKey() {
  const meta = document.querySelector('meta[name="turnstile-site-key"]');
  return meta ? meta.content : "";
}

function ensureCaptchaRendered() {
  const container = document.getElementById("captchaContainer");
  if (!container) return;
  container.innerHTML = ""; // re-render cleanly when mode changes

  // Only show for signup/forgot
  if (currentAuthMode === "signup" || currentAuthMode === "forgot") {
    const sitekey = getTurnstileSiteKey();
    if (!sitekey || !window.turnstile) return;
    turnstileWidgetId = turnstile.render("#captchaContainer", {
      sitekey,
      theme: "auto", // or "light"/"dark"
      action: currentAuthMode, // useful for server analytics
      appearance: "always",
    });
  } else {
    turnstileWidgetId = null;
  }
}

// Auth functions
function showAuth(mode) {
  currentAuthMode = mode;
  updateAuthModal();
  const modal = document.getElementById("authModal");
  modal.classList.add("active");

  // bind submit every time modal opens (avoid duplicate listeners)
  const form = document.getElementById("authForm");
  form.removeEventListener("submit", handleAuthSubmit);
  form.addEventListener("submit", handleAuthSubmit);

  initOAuth();
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

function showUser(user) {
  // hide "Sign In"
  const loginBtn = document.getElementById("loginButton");
  if (loginBtn) loginBtn.style.display = "none";

  const navMenu = document.getElementById("navMenu");
  const name  = (user?.name || user?.username || "User").trim();
  const email = (user?.email || "").trim();
  const initial = (name || email || "?").charAt(0).toUpperCase();

  const wrap = document.createElement("div");
  wrap.id = "userMenu";
  wrap.className = "user-menu";
  wrap.innerHTML = `
    <button id="userBtn" class="cyber-button">${initial}</button>

    <div id="userDropdown" class="dropdown-content">
      <div class="menu-hd">
        <div class="name">${name}</div>
        ${email ? `<div class="muted">${email}</div>` : ""}
      </div>

      <a href="/" id="user-dashboard-btn">User Dashboard</a>
      <a href="/account/" id="account-settings-btn">Account Settings</a>
      <a href="/" id="billing-plan-btn">Billing &amp; Plan</a>
      <a href="/" id="help-btn">Help</a>

      <div class="sep"></div>
      <a href="#" id="logoutBtn" style="color:#ff6e6e">Logout</a>
    </div>
  `;
  navMenu.appendChild(wrap);

  // --- actions ---
  document.getElementById("user-dashboard-btn").onclick = (e) => { /* placeholder */ };
  document.getElementById("account-settings-btn").onclick = (e) => { /* placeholder */ };
  document.getElementById("billing-plan-btn").onclick  = (e) => { /* placeholder */ };
  document.getElementById("help-btn").onclick          = (e) => { /* placeholder */ };

  // Real logout; then force logged-out UI + redirect home
  document.getElementById("logoutBtn").onclick = async (e) => {
    e.preventDefault();
    try {
      const { ok, status } = await postJSON(
        "/auth/logout",
        {},
        { csrf: "refresh", refresh: false, credentials: "include" }
      );
      if (!(ok || [401, 422].includes(status))) {
        console.warn("Logout response:", status);
      }
    } catch (_) {
      /* ignore */
    } finally {
      showLoggedOut();
      window.location.href = "/";
    }
  };
}

function showLoggedOut() {
  document.getElementById("userMenu")?.remove();
  const btn = document.getElementById("loginButton");
  if (btn) btn.style.display = "inline-flex";
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
                <a href="#" class="auth-link" data-mode="forgot"">Forgot your password?</a>
            </div>
            <div class="auth-text">
                New hunter? 
                <a href="#" class="auth-link" data-mode="signup">Join the hunt</a>
            </div>
        `;
  } else if (currentAuthMode === "signup") {
    authLinks.innerHTML = `
            <div class="auth-text">
                Already have an account? 
                <a href="#" class="auth-link" data-mode="login">Sign in</a>
            </div>
        `;
  } else if (currentAuthMode === "forgot") {
    authLinks.innerHTML = `
            <div class="auth-text">
                Remember your password? 
                <a href="#" class="auth-link" data-mode="login">Sign in</a>
            </div>
        `;
  }
  ensureCaptchaRendered();
}

function updateAuthMode(mode) {
  currentAuthMode = mode;
  updateAuthModal();
}

function setFieldError(inputId, message) {
  const input = document.getElementById(inputId);
  if (!input) return;
  let err = input.closest(".form-group").querySelector(".field-error");
  if (!err) {
    err = document.createElement("div");
    err.className = "field-error";
    err.style.color = "#ff6b6b";
    err.style.fontSize = "12px";
    err.style.marginTop = "6px";
    input.closest(".form-group").appendChild(err);
  }
  err.textContent = message || "";
}

function getMetaCSRF() {
  return document
    .querySelector('meta[name="csrf-token"]')
    ?.getAttribute("content");
}

function clearFieldError(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const err = input.closest(".form-group").querySelector(".field-error");
  if (err) err.textContent = "";
}

function isEmail(str) {
  // light but solid email check
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(str || "");
}

const RESERVED_USERNAMES = new Set([
  "admin",
  "administrator",
  "root",
  "system",
  "support",
  "null",
  "none",
  "user",
  "username",
  "test",
  "info",
  "sys",
]);

function validateUsername(u) {
  const v = (u || "").trim();
  if (v.length < 4 || v.length > 15) return "Username must be 4–15 characters.";
  if (!/^[A-Za-z0-9_]+$/.test(v))
    return "Only letters, digits, and underscore.";
  if (RESERVED_USERNAMES.has(v.toLowerCase()))
    return "This username is reserved.";
  return null;
}

function validatePassword(pw, { name, username, email }) {
  const p = pw || "";
  if (p.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Z]/.test(p)) return "Include at least one uppercase letter.";
  if (!/\d/.test(p)) return "Include at least one digit.";
  if (!/[^A-Za-z0-9]/.test(p)) return "Include at least one special character.";
  if (/(.)\1\1/.test(p)) return "No character may repeat three times in a row.";

  const lower = p.toLowerCase();
  const checks = [
    (name || "").toLowerCase(),
    (username || "").toLowerCase(),
    ((email || "").split("@")[0] || "").toLowerCase(),
  ].filter((s) => s && s.length >= 3);
  if (checks.some((s) => lower.includes(s))) {
    return "Password must not contain your name/username/email.";
  }

  // tiny client-side blacklist (server still enforces the full COMMON_PASSWORDS)
  const weak = [
    "password",
    "qwerty",
    "letmein",
    "welcome",
    "12345678",
    "hunter2",
  ];
  if (weak.includes(lower)) return "Choose a stronger password.";

  return null;
}

function validateAuthForm(mode) {
  let ok = true;

  // clear previous
  ["email", "username", "password", "confirmPassword", "name"].forEach(
    clearFieldError
  );

  const email = (document.getElementById("email")?.value || "").trim();
  const password = document.getElementById("password")?.value || "";
  const confirmPassword =
    document.getElementById("confirmPassword")?.value || "";
  const username = (document.getElementById("username")?.value || "").trim();
  const name = (document.getElementById("name")?.value || "").trim();

  if (mode === "login") {
    if (!isEmail(email)) {
      setFieldError("email", "Enter a valid email.");
      ok = false;
    }
    if (!password) {
      setFieldError("password", "Password is required.");
      ok = false;
    }
  }

  if (mode === "forgot") {
    if (!isEmail(email)) {
      setFieldError("email", "Enter a valid email.");
      ok = false;
    }
  }

  if (mode === "signup") {
    if (!isEmail(email)) {
      setFieldError("email", "Enter a valid email.");
      ok = false;
    }
    const uErr = validateUsername(username);
    if (uErr) {
      setFieldError("username", uErr);
      ok = false;
    }

    const pErr = validatePassword(password, { name, username, email });
    if (pErr) {
      setFieldError("password", pErr);
      ok = false;
    }

    if (!confirmPassword) {
      setFieldError("confirmPassword", "Confirm your password.");
      ok = false;
    } else if (password !== confirmPassword) {
      setFieldError("confirmPassword", "Passwords do not match.");
      ok = false;
    }
  }

  return { ok };
}

async function handleAuthSubmit(event) {
  event.preventDefault();
  const submitButton = document.getElementById("authSubmit");
  const buttonText = document.getElementById("authButtonText");
  const buttonIcon = document.getElementById("authButtonIcon");
  const spinner = document.getElementById("authSpinner");

  const { ok } = validateAuthForm(currentAuthMode);
  if (!ok) {
    // restore button state and stop; user will see inline messages
    buttonText.style.display = "inline";
    buttonIcon.style.display = "inline";
    spinner.style.display = "none";
    submitButton.disabled = false;
    return;
  }
  // UI: loading state
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

  // Attach Turnstile token for signup/forgot
  if (currentAuthMode === "signup" || currentAuthMode === "forgot") {
    const token =
      typeof turnstile !== "undefined" && turnstileWidgetId
        ? turnstile.getResponse(turnstileWidgetId)
        : null;

    if (!token) {
      alert("Please complete the captcha.");
      // restore UI now and bail
      buttonText.style.display = "inline";
      buttonIcon.style.display = "inline";
      spinner.style.display = "none";
      submitButton.disabled = false;
      return;
    }
    payload.turnstile_token = token;
  }

  try {
    // const res = await csrfFetch(url, {
    //   method: "POST",
    //   headers: { "Content-Type": "application/json" },
    //   credentials: "include", // <-- important for cookies
    //   body: JSON.stringify(payload),
    // });

    // // Try to parse JSON even on non-2xx
    // const data = await res.json().catch(() => ({}));
    // if (!res.ok) {
    //   throw new Error(data.msg || data.message || "Request failed");
    // }
    // // --- MFA gate (server returns 202 when MFA is required) ---
    // if (
    //   res.status === 202 &&
    //   (data.mfa_required || data.message === "MFA_REQUIRED")
    // ) {
    //   const verifyUrl = data.verify_url || "/auth/verify-mfa";
    //   // 1) full page redirect is simplest and mirrors OAuth callback behavior
    //   window.location.href = verifyUrl;
    //   return;
    // }

    // if (currentAuthMode === "login") {
    //   // cookies set by server; just load the user
    //   const meRes = await fetch("/auth/me", {
    //     method: "GET",
    //     credentials: "include",
    //   });
    //   if (!meRes.ok) throw new Error("Failed to load user");
    //   const me = await meRes.json();
    //   showUser(me);
    //   closeAuth();
    // } else if (currentAuthMode === "signup") {
    //   // If your /auth/signup also logs in (sets cookies), do the same as login:
    //   const meRes = await fetch("/auth/me", {
    //     method: "GET",
    //     credentials: "include",
    //   });
    //   if (meRes.ok) {
    //     const me = await meRes.json();
    //     showUser(me);
    //     closeAuth();
    //   }
    //   else {
    //     // Otherwise, keep modal or show success message:
    //     alert("Account created! Check your email to confirm.");
    //     closeAuth();
    //   }
    // } else if (currentAuthMode === "forgot") {
    //   // Generic response to avoid user enumeration — show friendly toast
    //   alert(
    //     data.message ||
    //       "If that email is registered, you'll receive a reset link."
    //   );
    //   closeAuth();
    // }

    const { ok, status, data } = await postJSON(url, payload, {
      refresh: false,
      silent: true,
    });
    if (!ok) {
      throw new Error(data?.msg || data?.message || "Request failed");
    }

    // --- MFA gate (server returns 202 when MFA is required) ---
    if (
      status === 202 &&
      (data?.mfa_required || data?.message === "MFA_REQUIRED")
    ) {
      const verifyUrl = data.verify_url || "/auth/verify-mfa";
      window.location.href = verifyUrl;
      return;
    }

    if (currentAuthMode === "login") {
      const { ok: meOk, data: me } = await getJSON("/auth/me");
      if (!meOk) throw new Error("Failed to load user");
      showUser(me);
      closeAuth();
    } else if (currentAuthMode === "signup") {
      const { ok: meOk, data: me } = await getJSON("/auth/me");
      if (meOk) {
        showUser(me);
        closeAuth();
      } else {
        alert("Account created! Check your email to confirm.");
        closeAuth();
      }
    } else if (currentAuthMode === "forgot") {
      alert(
        data?.message ||
          "If that email is registered, you'll receive a reset link."
      );
      closeAuth();
    }
  } catch (err) {
    alert(err.message || "Something went wrong");
  } finally {
    // UI: restore button state
    buttonText.style.display = "inline";
    buttonIcon.style.display = "inline";
    spinner.style.display = "none";
    submitButton.disabled = false;

    // Reset captcha token (one-time use)
    if (typeof turnstile !== "undefined" && turnstileWidgetId) {
      try {
        turnstile.reset(turnstileWidgetId);
      } catch (_) {}
    }
  }
}

async function initOAuth() {
  try {
    const sess = await getJSON("/auth/me", { refresh: false, silent: true });
    if (sess.ok) return;
    // Ask backend for provider start URLs (+ client id), include ?next= so we return here post-login
    const next = encodeURIComponent(
      window.location.pathname + window.location.search
    );

    const { ok, data: providers } = await getJSON(
      `/auth/providers?next=${next}`
    );
    if (!ok) throw new Error("Failed to load OAuth providers");

    renderOAuthButtons(providers);
    initGoogleOneTap(providers.google_client_id); // safe to call if GIS hasn’t loaded yet; we’ll guard below
  } catch (e) {
    console.error("OAuth init failed", e);
  }
}

function renderOAuthButtons(providers) {
  const box = document.getElementById("oauthButtons");
  if (!box) return;

  box.innerHTML = `
                <!-- Social Login Buttons -->
                <div class="social-login">
                    <div class="social-divider">
                        <span>or continue with</span>
                    </div>
                    <div class="social-buttons">
                        <button type="button" id="googleOAuthBtn" class="social-btn google-btn">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                            </svg>
                            <span>Google</span>
                        </button>
                        <button type="button" id="githubOAuthBtn" class="social-btn github-btn">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                            </svg>
                            <span>GitHub</span>
                        </button>
                    </div>
                </div>
            </div>
  `;

  document.getElementById("googleOAuthBtn").onclick = () => {
    // full-page redirect to begin Google OAuth code flow
    window.location.href = providers.google;
  };
  document.getElementById("githubOAuthBtn").onclick = () => {
    // full-page redirect to begin GitHub OAuth code flow
    window.location.href = providers.github;
  };
}

function initGoogleOneTap(clientId) {
  if (!clientId) return;

  // Wait for Google script if not yet loaded
  if (!window.google || !window.google.accounts || !window.google.accounts.id) {
    setTimeout(() => initGoogleOneTap(clientId), 300);
    return;
  }

  google.accounts.id.initialize({
    client_id: clientId,
    callback: async (response) => {
      try {
        const { ok, status, data } = await postJSON("/auth/token-signin", {
          credential: response.credential,
        });

        if (
          status === 202 &&
          (data?.mfa_required || data?.message === "MFA_REQUIRED")
        ) {
          const verifyUrl = data.verify_url || "/auth/verify-mfa";
          window.location.href = verifyUrl;
          return;
        }
        if (!ok)
          throw new Error(
            data?.msg || data?.message || "Google sign-in failed"
          );

        const { ok: meOk, data: me } = await getJSON("/auth/me");
        if (!meOk) throw new Error("Failed to load user");
        showUser(me);
        closeAuth();
      } catch (err) {
        console.error("One-Tap login failed:", err);
      }
    },
    // UX tuning
    auto_select: false,
    cancel_on_tap_outside: true,
    itp_support: true,
  });

  // Render a prompt in the modal only (avoid surprising users on landing)
  google.accounts.id.prompt((notification) => {
    // optionally inspect notification.getMomentType()
  });
}

async function initAuth() {
  try {
    // Do not auto-refresh; we only want current state
    const { ok, data: user } = await getJSON("/auth/me", {
      refresh: false,
      silent: true,
    });

    if (ok && user && (user.id || user.username || user.email)) {
      showUser(user);
    } else {
      showLoggedOut();
    }
  } catch (_) {
    showLoggedOut();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initAuth();
  initOAuth();
  document
    .getElementById("authForm")
    .addEventListener("submit", handleAuthSubmit);

  // NEW: close modal without inline onclick
  const backdrop = document.querySelector(".modal-backdrop");
  if (backdrop) backdrop.addEventListener("click", closeAuth);

  // NEW: password toggles without inline onclick
  document.querySelectorAll("button.password-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.target;
      if (target) togglePassword(target);
    });
  });
  document
    .getElementById("loginButton")
    ?.addEventListener("click", () => showAuth("login"));
  document
    .getElementById("navToggle")
    ?.addEventListener("click", toggleMobileMenu);

  // Delegate auth links (rendered by updateAuthModal)
  const authLinks = document.getElementById("authLinks");
  if (authLinks) {
    authLinks.addEventListener("click", (e) => {
      const a = e.target.closest("a.auth-link");
      if (!a) return;
      e.preventDefault();
      const mode = a.dataset.mode;
      if (mode) updateAuthMode(mode);
    });
  }
});
