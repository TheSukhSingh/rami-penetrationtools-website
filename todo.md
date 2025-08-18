- Fix confirm mail design (Mail received looks bad)

TOOLS
- FE Loading something when tool is run and until we receive the output
- FE Upload file not aligned in center both
- BE Subfinder needs silent all the time - leaking server location and stuff...
- Launch button pressed multiple times without changing parameters is throwing errors
- backend commands are being fixed rn, update frontend command with backend commands
- use celery to run the processes in backend
- Files are being saved in app.py's folder on server

AUTH
- user deactivated logic to be written in local_routes
- mfa not set yet
- On register (fe), create checks on frontend too so backend does little work (like pw checks, both pw same, etc)
- refresh token not working 
- unable to logout

NAVBAR
- Dropdown from User needs design update (Also Dashboard option required)

LANDING PAGE
- hero section touching navbar in laptop screen






Targets:

Authentication
    -D Login with oauth wiring and fixing models and routes to save oauth details properly
    -D Frontend validations for credentials both on signup and register
    -D Refresh Token - auth/refresh-token and auth/refresh both endpoints are different, gotta fix this
    -D login.html posts to auth.login_page instead of auth/signin (check what's wrong here, not sure)
    -D oauth uses json tokens, local uses cookies, fix those (jwt cookies better for csrf protection)
    -D Add security headers (HSTS, CSP with nonces, X-Frame-Options, X-Content-Type-Options, Referrer-Policy). You can do this via a tiny middleware.
    -D Rate Limiting
    -D Add progressive backoff / temporary lock after N failed logins (and reset counters on success—you already reset in jwt_login).
    -D captcha for signup and forgot password
    -D access token - only 5 minutes
    -D is_blocked and is_deactivated check before logging in user
    -D model update for master user, whom no one can touch
    -D "If that email exists, we will send a link"
    - MFA setup
    - HIBP k-ananymity check
    - reset token revoke for admin panel
    - FE - Auth form design completion (pw label is half the width and stuff, fix that)
    - User Deactivation logic to be written in local_routes too
    - Add csrf (exempted in app.py, remove that line and make it csrf and working)
    - reset_pw mail is so boring, fix it (design fixed, gotta fix the links and validations so link details not shared, eg if no {{reseturl}} then don't show, and reset pw button, if can't do, just show failed, don't show this link that link not no etc...)

Admin Section
    - Auth Login page

User dashboard section
    - 

Stripe Integration
    - 

Tools fix + Additional Tools + Other mini fixes
    - 

Blog Section
    - Everything (nothing done at all)








# Authentication

[Fix] OAuth wiring: persist provider ids/emails, link to existing user by verified email → on conflict, prompt account-link flow.
[Fix] Refresh flow: keep POST /auth/refresh (rotating refresh) → delete/redirect /auth/refresh-token, update FE calls.
[Fix] Local vs OAuth tokens: move both to JWT-in-HttpOnly cookies; set Secure, SameSite=Lax, no localStorage.
[Fix] CSRF: enable global CSRF; add per-form token & Turnstile verify on server; remove CSRF exemptions.
[Fix] Rate limiting + backoff: per IP + per user on signin/signup/forgot; temporary lock after N fails; reset on success.
[Fix] Access token TTL: 5 min; refresh ~30–60 days with rotation + reuse-detection → revoke on reuse.
[Fix] Enforce is_blocked/is_deactivated in all login paths (local & oauth) → return generic error.
[Fix] “If email exists” language on forgot; always 200; no user enumeration.
[Fix] Password reset: single-use, short-TTL token; revoke on use; don’t leak token in FE; graceful expired handling.
[Fix] Security headers: HSTS, CSP with nonces, XFO:DENY, XCTO:nosniff, Referrer-Policy, Permissions-Policy.
[Fix] Common-passwords check + strength rules server-side (already have list) → reject weak.
[Create] MFA: TOTP (app) first; optional email code fallback; “remember device” cookie with device binding; recovery codes.
[Create] HIBP k-anonymity check on signup/reset (warn + allow override or block by policy).
[Create] Master user guard: seed + model flag; block delete/role changes by anyone else; log attempts.
[Update] FE validations (signup/login/reset): live rules, password meter, confirm match, email regex, inline errors.
[Update] Auth emails: finalize reset/verify templates with conditional blocks; add plain-text parts & proper DKIM/SPF headers.
[Remove] Any unused auth endpoints, duplicate refresh route, and token-in-JSON responses.

# Admin

[Create] Admin login (separate from user): admin-only auth gate before SPA; JWT cookie + CSRF; 2FA mandatory.
[Fix] RBAC on all admin APIs (overview/users/scans/tools/blog/settings); enforce per-action permissions.
[Fix] Audit log middleware: capture who/when/what for admin mutations; expose filterable table in Admin.
[Update] Overview data endpoints: add pagination/caching; handle empty DB; guard against N+1 queries.
[Update] Admin SPA error/empty/loading states; consistent toasts; 401→redirect to admin login.
[Remove] Dead admin stubs/empty files; unused routes/components.

# User Dashboard (not started)

[Create] Dashboard shell (JWT-protected): tabs for Saved Scans, Scan History, Reports, Workflows, Settings.
[Create] Saved scans & history pages: list + filters + pagination; detail view; re-run; delete/archive.
[Create] Report generation/download (txt/csv/JSON; later PDF); store in S3/local; signed download URLs.
[Create] Background scans & queue view (status/progress/cancel); notifications on completion.
[Create] Presets/Combos/Sequence Mode UI; apply presets to tools form; per-user defaults.
[Create] Settings: profile, security (MFA/devices), API keys (if exposing API), email prefs.
[Update] Tools page: wire “Save scan” + “Run in background” + “Add to workflow” actions; show quotas/limits.
[Remove] Any placeholder dashboard pages.

# Stripe Integration (not started)

[Create] Products/Prices (Pro monthly/yearly) in Stripe; env vars for IDs.
[Create] Checkout or Billing Portal: choose Stripe Checkout + Customer Portal → implement success/cancel routes.
[Create] Webhooks (signed): checkout.session.completed, invoice.payment_*, customer.subscription.* → update local subscription state.
[Create] Entitlements middleware: gate Pro features (multi sessions, save/history, reports, sequences, workflows, background scans).
[Create] Billing page (user): show plan, renewal date, invoices, portal link, cancel/downgrade.
[Update] Models: add customer_id, subscription_id, price_id, status, current_period_end; backfill seeds/migrations.
[Remove] Any mock billing code or hardcoded plan checks.

# Tools Module

[Fix] Uniform validation: domain/file limits, timeouts, threads, stdin/stdout handling; consistent JSON result shape.
[Fix] Input safety: never shell-concat; use arg lists; sanitize file paths; clamp numeric options.
[Fix] Quotas & rate limits per user; max concurrent scans; kill/timeout long runs; clean temp files.
[Fix] File uploads: store under per-user dir; size/type checks; auto-delete after N days (cron).
[Fix] Diagnostics: always record counts, exec_ms, error_reason enums; handle exceptions uniformly.
[Update] Tools UI: progress/spinner, streaming log (optional), copy/download output, error surfaces.
[Update] Add retries/backoff for flaky tools; detect missing binaries; show install hints (admin-only).
[Create] Background queue (Celery/RQ + Redis) for “Run in background”; webhook/event → notify user.
[Create] Additional tools (if in scope): nuclei (vuln scan), waybackurls; wire same pattern.
[Remove] Unused tool flags or dead code paths; empty tool files.

# Blog (not started)

[Create] TinyMCE editor page (role-gated); image upload to /media; slug, tags, summary, cover.
[Create] CRUD with soft delete/versioning; ownership checks; admin moderation + shadow-hide.
[Create] Public blog list + detail + search/filter; pagination; SEO meta; sitemap/RSS.
[Create] Comments (logged-in only), rate-limited; report/ban; email notifications (opt-in).
[Update] Roles/permissions to include blog_author, blog_editor, blog_admin.
[Remove] Placeholder templates/stubs.

# Core App & Security

[Fix] CSP with nonces for inline scripts (navbar/tools/admin/auth); remove inline JS where easy.
[Fix] CORS (if API separated); restrict origins; preflight; credentials true only when needed.
[Fix] Cookies: HttpOnly, Secure, SameSite=Lax; set consistent domain/path; clear on logout.
[Fix] Turnstile verification on server for signup/forgot; rate limit those endpoints.
[Fix] Error handling: uniform JSON error schema for APIs; pretty error pages for HTML.
[Update] Global 404/500 handlers; logging with request id; structured JSON logs.
[Update] Content caching: static asset versioning; long-cache headers; gzip/br.
[Remove] Debug configs, stack traces in prod, unused blueprints.

# Background Jobs & Notifications

[Create] Worker (Celery/RQ) + Redis; queues for scans, report builds, cleanup.
[Create] Periodic jobs: delete old uploads/reports, token cleanup, audit log rotation.
[Create] Email service abstraction (SMTP/provider); templated emails (verify/reset/alerts).

# Observability & QA

[Create] Sentry (or similar) for BE/FE; capture exceptions + performance traces.
[Create] Health checks /healthz & /readyz; uptime monitoring.
[Create] Tests: unit (models/utils), API tests (auth/tools), e2e smoke; pre-commit (black/isort/ruff/mypy).
[Create] Load test scripts for key endpoints (tools run, auth, dashboard); basic baseline numbers.

# Data & DB

[Fix] DB indexes on common filters (user_id, tool, created_at); FKs + cascades.
[Create] Alembic migrations for all new fields; seed master/admin roles safely.
[Create] Data retention: purge PII/logs after N days; GDPR export/delete if needed.

# DevOps & Deployment

[Create] Gunicorn + Nginx + HTTPS (Let’s Encrypt); secure TLS ciphers; proxy headers.
[Create] .env.example & config separation; secrets via env; production config file.
[Create] Build pipeline: lint/test → build → deploy; static collect; cache busting.
[Create] Backup strategy (DB/files); restore runbook; ulimit/file-handles tuning.
[Update] Dockerfile/Compose (web + worker + redis); healthchecks; resource limits.
[Remove] Unused packages; reduce image size; disable debug toolbar.

# Frontend Polish

[Fix] Auth form layout bugs (labels, spacing); consistent focus/aria; keyboard nav.
[Fix] Global toasts/modals accessible; trap focus; escape to close; aria-live regions.
[Update] Navbar/footer responsive; active links; skeleton loaders; empty states.

# Documentation

[Create] README (setup/run/dev/prod), architecture diagram, feature flags.
[Create] API docs (OpenAPI) for auth/tools/admin; Postman collection.
[Create] Admin & Ops runbooks; incident checklist; CHANGELOG.



admin Responsibilities
User & Role Management: create/edit/deactivate users, assign roles/permissions.
Audit Logs: view/filter LoginEvent, PasswordReset, token revocations.
Site Settings: edit email templates, JWT lifetimes, feature toggles.
Metrics Dashboard: count of active users, sign-ups (daily/weekly/monthly), login failures, error rates.
Tools History: number of scans run, per-tool usage, status breakdown.

blog Features
Authoring: users with blog_writer role can create/edit posts; WYSIWYG or Markdown support.
Rich Content: images, code blocks, embeds, text formatting.
Public Views: anyone can browse list/detail pages.
Engagement: logged-in users can like, comment; view count tracking.
Analytics Hooks: track views per post, comment volume, like counts over time (for admin dashboard).

tools Features
Tool Execution: individual tool forms (subfinder, httpx, …), display terminal output in-browser.
Chained Scans: allow selecting multiple tools in sequence; combine & normalize outputs.
History: persist ScanJob (timestamp, user, tools run, parameters), and ScanResult details.
Admin Analytics: number of scans, error rates, avg. runtime per tool, user activity heatmaps.














Authentication

[Fix] OAuth wiring & persistence → link by verified email; fallback to account-link flow.
[Fix] Refresh flow → keep POST /auth/refresh (rotate + reuse-detect), delete/redirect old endpoint.
[Fix] Logout → clear HttpOnly JWT cookies (access+refresh), revoke refresh session, redirect.
[Fix] Local & OAuth tokens → move both to JWT-in-HttpOnly cookies; Secure + SameSite=Lax.
[Fix] CSRF → enable globally; add per-form token; verify Turnstile server-side.
[Fix] Rate limiting/backoff → per IP & per user; lockout after N fails; reset on success.
[Fix] Enforce is_blocked/is_deactivated in local & OAuth paths; generic error.
[Fix] Forgot/Reset → single-use, short-TTL token; revoke on use; always 200 (“If email exists…”).
[Fix] Security headers → HSTS, CSP (nonces), XFO:DENY, XCTO:nosniff, Referrer/Permissions-Policy.
[Fix] Common-passwords + strength rules server-side; reject weak.
[Fix] Confirm/verify email template → final design + plain-text; hide missing vars; DKIM/SPF checks.
[Fix] “login.html posts to wrong route” → point to /auth/signin; align FE/BE names.
[Update] FE validations (signup/login/reset) → email regex, strength meter, confirm match, inline errors.
[Create] MFA (TOTP first; email code fallback) → “remember device” cookie + recovery codes.
[Create] HIBP k-anonymity on signup/reset (warn/block by policy).
[Create] Master user guard → model flag + seed; block role/delete by others; audit attempts.
[Remove] Duplicate refresh route, token-in-JSON responses, CSRF exemptions.

Tools

[Fix] FE: show loading/state until output; disable Run/Launch while executing; re-enable on finish/error.
[Fix] FE: center/align upload inputs (manual/file) on tools page; consistent spacing.
[Fix] Subfinder privacy → force -silent (and safe resolvers if needed); no env/location leak.
[Fix] Double-click/Repeat runs → debounce + disable button; BE idempotency window (hash params for 5–10s).
[Fix] Sync FE “command preview” with BE arg list; single source of truth in JS map.
[Fix] Store uploads under UPLOAD_INPUT_FOLDER/<user_id>/; not app root; auto-clean after N days.
[Fix] Uniform validation (limits, timeouts, threads) + consistent JSON result fields across tools.
[Create] Celery/RQ + Redis → run scans in background; job status API; cancel/timeouts.
[Update] Diagnostics logging everywhere (counts, exec_ms, error_reason); handle FileNotFoundError cleanly.
[Remove] Dead tool flags/empty stubs.

Admin

[Create] Admin login (separate) → JWT cookies + CSRF; 2FA required.
[Fix] RBAC on all admin APIs (overview/users/scans/tools/blog/settings); permission checks per action.
[Fix] Audit log middleware for mutations; list in Admin → filter/search/export.
[Update] Overview endpoints: paginate + cache; handle empty DB; guard N+1 queries.
[Update] Admin SPA UX: proper toasts/empty/loading; 401→redirect to admin login.
[Remove] Empty admin files/components.

User Dashboard (new)

[Create] Shell (JWT-protected) with tabs: Saved Scans, History, Reports, Workflows, Settings.
[Create] History & Saved → list + filters + pagination; detail; re-run; delete/archive.
[Create] Reports → generate (txt/csv/json; later PDF), store, signed downloads.
[Create] Background scans view → status/progress/cancel; notifications.
[Create] Settings → profile, security (MFA/devices), email prefs; API keys (optional).
[Update] Tools page actions → Save, Run in background, Add to workflow; show quotas.
[Remove] Placeholder dashboard pages.

Stripe Integration (new)

[Create] Products/Prices (Pro monthly/yearly) in Stripe; env IDs.
[Create] Checkout + Customer Portal; success/cancel routes; 3-day trial.
[Create] Webhooks (signed): update subscription state; handle failed/paused/canceled.
[Create] Entitlements middleware gating Pro features (sessions, save/history, reports, sequences, workflows, background scans, advanced options).
[Update] Models: customer_id, subscription_id, price_id, status, current_period_end; migrations.
[Remove] Any mock billing checks.

Blog (new)

[Create] TinyMCE editor (role-gated), image uploads, slug/tags/cover; CRUD with soft delete/versioning.
[Create] Public list/detail + search; pagination; SEO meta + sitemap/RSS.
[Create] Comments (logged-in), rate-limited; moderation (shadow-hide, delete).
[Update] Roles/permissions (blog_author, blog_editor, blog_admin).

Navbar & Landing

[Update] Navbar user dropdown design; add “Dashboard” link (role-aware: user vs admin).
[Fix] Landing hero spacing → add top padding/margin under fixed navbar; responsive check.

Legal/Phase-2 Pages

[Create] Privacy Policy & Terms pages (markdown → Jinja template); link in footer & settings.
[Create] Google/GitHub auth enablement (keys, callbacks, scopes); align with OAuth fixes above.

Core App & Security

[Fix] CSP with nonces (auth/tools/admin templates); remove inline JS where easy.
[Fix] Turnstile verification server-side for signup/forgot; rate limit those endpoints.
[Update] Error handling: uniform JSON schema; pretty 4xx/5xx pages; request IDs; structured logs.
[Update] Static assets: versioned filenames; long cache; gzip/br.
[Remove] Debug configs/stack traces in prod.

Background Jobs & Housekeeping

[Create] Worker (Celery/RQ) + scheduler; clean old uploads/reports; rotate audit logs; token cleanup.
[Create] Email service abstraction; templates for verify/reset/alerts.

Observability & QA

[Create] Sentry (FE+BE), /healthz & /readyz, uptime monitoring.
[Create] Tests: unit (models/utils), API (auth/tools), e2e smoke; pre-commit (ruff/black/isort/mypy).
[Create] Simple load tests for scans/auth to baseline capacity.

DevOps & Deployment

[Create] Gunicorn + Nginx + HTTPS; secure TLS; proxy headers; timeouts.
[Create] .env.example + prod config; secrets via env.
[Create] Docker/Compose (web + worker + redis), healthchecks, resource limits.
[Update] Backups (DB/files) + restore runbook; ulimit/file-handle tuning.
[Remove] Unused packages; shrink image; disable debug toolbar.



















TODO TASKS

# Authentication
## DONE
OAuth wiring (persist provider id/email; link by email) + sets JWT cookies on success. 
FE auth validations (email/username/password/confirm, inline errors). 
Refresh endpoint unified → only POST /auth/refresh. 
Login posts to /auth/signin (FE ↔︎ BE aligned). 
Both local & OAuth use JWT-in-HttpOnly cookies (no JSON tokens). 
Security headers: HSTS, CSP, XFO, XCTO, Referrer, Permissions.
Progressive backoff + lockout & reset-on-success for local login. 
Captcha on signup + forgot-password (Turnstile, server-verified). 
Access token TTL = 5 minutes (config). 
Blocked/deactivated checks before issuing tokens. 
“If that email exists…” response (user-enum safe). 
Master/protected user flag present in model. 
Common-passwords + strength rules server-side.

## PARTIAL
Rate limiting not consistently applied (signin limiter is commented). 
CSRF is enabled but auth blueprint is globally exempted. 
Refresh flow lacks rotation + reuse-detection (only new access issued). 
Auth email templates: reset/verify exist, but conditional blocks/Plain-text/DKIM notes not finalized. 
FE auth form polish (minor layout details).

## NOT DONE YET
MFA (TOTP, remember device, recovery codes). (Models exist, flows not wired.) 
HIBP k-anonymity check on signup/reset. (No code yet.)
Admin ability to revoke password-reset tokens on demand (beyond single-use/expiry).

## EXECUTION ORDER
-D Enforce CSRF on auth routes (remove exemptions; wire header check in FE already present). 
Re-enable and tune per-IP + per-user rate limits on /auth/signin//auth/signup//auth/forgot-password. 
-D Refresh rotation + reuse detection: rotate refresh on /auth/refresh, store new JTI, revoke old; on reuse → revoke session. 
MFA (TOTP first), plus “remember device” + recovery codes, gate signin accordingly. 
-D HIBP k-anonymity check on signup/reset (warn/block per policy).
Admin UI/endpoint to list & revoke active password-reset tokens. 
Finalize email templates (verify/reset): conditional blocks, plain-text parts, DNS (SPF/DKIM) checklist. 
FE polish pass on auth modal (spacing/label widths, minor UX).