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

15 Aug: (Authentication)
    - Login with oauth wiring and fixing models and routes to save oauth details properly
    - User Deactivation logic to be written in local_routes too
    - MFA setup
    - Frontend validations for credentials both on signup and register
    - Refresh Token - auth/refresh-token and auth/refresh both endpoints are different, gotta fix this
    - FE - Auth form design completion (pw label is half the width and stuff, fix that)
    - Add csrf
    - login.html posts to auth.login_page instead of auth/signin (check what's wrong here, not sure)
    - oauth uses json tokens, local uses cookies, fix those (jwt cookies better for csrf protection)
    - Add security headers (HSTS, CSP with nonces, X-Frame-Options, X-Content-Type-Options, Referrer-Policy). You can do this via a tiny middleware.
    - Rate Limiting
    - Add progressive backoff / temporary lock after N failed logins (and reset counters on success—you already reset in jwt_login).
    - captcha for signup and forgot password
    - HIBP k-ananymity check
    - reset token revoke for admin panel
    - access token - only 5 minutes
    - is_blocked and is_deactivated check before logging in user
    - model update for master user, whom no one can touch
    - "If that email exists, we will send a link"

16-17 Aug: (Admin Section)
    - Auth Login page

18 Aug: (User dashboard section)
    - 

19-22 Aug: (Stripe Integration)


23-25 Aug: (Tools fix + Additional Tools + Other mini fixes)


26-30 Aug: (Blog Section)


31 Aug: ()








16 Aug: ()
    1. 












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