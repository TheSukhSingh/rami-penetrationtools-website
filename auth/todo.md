# 🔴 Urgent (security/blockers)

## CSRF for anonymous routes
Ensure all public POSTs (signup, forgot) include <meta name="csrf-token" content="{{ csrf_token() }}"> and your fetch attaches X-CSRF-TOKEN. Never auto-refresh on these routes (refresh:false or a public-route whitelist).
## CSP hardened + nonce
Add nonced script-src, allow Cloudflare Turnstile in script-src | frame-src | connect-src, add frame-ancestors 'none'. Remove generic 'unsafe-inline' JS.
## Cookie hardening
Access/refresh/CSRF cookies: Secure, HttpOnly (except CSRF), SameSite=Lax (or Strict where possible), correct domain and path. Rotate keys on deploy.
## Rate limiting / brute-force
Login, signup, forgot, verify, token endpoints — IP and account keyed (short window + daily cap). Lockout/backoff using LocalAuth.failed_logins/last_failed_at.
## Email verification enforcement
Gate local login until verified; throttle “resend verify” (e.g., max 3/day).
## Password reset flow safety
Single-use (already), short TTL (10–15m), generic responses, audit log on request + completion, invalidate all sessions after reset.
## OAuth state/PKCE
Use state (and PKCE for Google if using OAuth code flow). Verify email, handle missing/duplicate emails, and link/unlink flows safely.
## CORS
If any cross-origin UI hits your API, pin origins to your domains with supports_credentials=True; no wildcards with cookies.
## Error handling
No raw tracebacks; JSON errors with stable shape; log stack traces server-side.
## Admin bypasses
Enforce is_blocked/is_deactivated and email-verified checks at login and in any @login_required-style gate.





# 🟡 Required (prod-ready)

## Refresh-token lifecycle
Implement /auth/refresh + rotation (rotate-on-use), revocation on logout/reset/password change, TTL (e.g., 30d) with sliding window, store hashed refresh tokens (you already have RefreshToken).
## Session management UI
“Active sessions/devices” page (list refresh tokens), revoke single/all. Use TrustedDevice for “remember this device”.
## MFA (TOTP)
Enable/disable, QR provisioning (otpauth://), step-up on risky actions, backup recovery codes (hashed, one-time), trusted device skip window.
## Audit & logs
Persist LoginEvent, IP/device (your UserIPLog), password changes, email changes, MFA enable/disable, role changes; expose to admins.
## Email sending
SPF/DKIM/DMARC configured; queue + retry (Celery/RQ) so forgot/reset/verify aren’t request-blocking; templated, localized emails.
## Account management
Change email flow (verify new email before switch), change password flow (requires current password + MFA if enabled).
## Resend/verification UX
Pages/modals for “verify email sent”, resend with cooldown, banners for “email not verified”.
## Unified validation
Align client rules with server rules (length, classes, no triple repeats, no personal info, blacklist). You’ve got both—ensure messages match.
## Admin/RBAC ops
Pages or CLI to assign/remove roles, view audits; seed roles already present—add guards so non-admins can’t reach admin routes.
## Security headers
HSTS (preload), X-Content-Type-Options: nosniff, Referrer-Policy: strict-origin-when-cross-origin, Permissions-Policy sane defaults, Cache-Control on auth pages (no-store).
## Background cleanup
Cron to purge expired PasswordReset / revoked RefreshToken, stale login events, etc.
## Testing
Unit + integration tests for: signup→verify→login, bad CSRF, brute-force lockout, refresh rotation/revocation, reset-password, OAuth state/PKCE, MFA happy/sad paths.






# 🟢 Nice-to-have / polish

- New device / unusual sign-in emails (+ optional “block” link).
- Geo “impossible travel” check → require MFA step-up.
- “Remember me” toggle controlling refresh TTL.
- Magic-link / passwordless (email) as alternative login.
- Google One-Tap gated by UI context (you already scaffold).
- Admin impersonation (secure, audited) for support.
- User export/delete (GDPR-style); soft-delete (you have flags).
- Invite system (signed invite tokens with role).
- Security page in user settings: change password, MFA, sessions, recovery codes.
- Analytics (minimal, privacy-safe) on auth funnels.





# Quick implement pointers (based on your code)

- Public fetches: ensure postJSON(url, body, { refresh:false, silent:true }) for signup/forgot.
- Reset page: you fixed template paths; keep CSRF input and show server flashes.
- Login flow: increment LocalAuth.failed_logins, add lockout window; reset on success.
- After password reset: revoke all refresh tokens for that user (logout everywhere).
- Turnstile: server verify with client IP, handle errors gracefully; update CSP connect-src to https://challenges.cloudflare.com.
- Cookies: set flags and short access TTL (e.g., 10–15 min).
- Middlewares: central guard that denies is_blocked/is_deactivated and unverified users.
- OAuth: verify state; for GitHub, fetch primary verified email; for Google, verify JWT (if One-Tap) or code exchange securely.
- Sentry/Logging: add Sentry (or similar), log auth decisions with correlation IDs.