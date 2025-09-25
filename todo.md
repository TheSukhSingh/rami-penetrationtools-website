Total things pending
1. Blog
2. Subscription
3. User Dashboard
4. Admin dashboard
5. Auth (Bugs)
6. Report Generation
7. AI Chatbot
8. Mini pages (privacy policy/ terms and conditions/ etc)
9. Whole website UI

week 1   (sep  1 -  6) : Tools page, User dashboard, 2 mini pages
week 2   (sep  7 - 13) : Tools page, Subscription, other mini pages
week 3   (sep 14 - 20) : Tools page, Report Generation, AI Chatbot
week 4   (sep 21 - 27) : AI Chatbot, 
ending   (sep 28 - 31) : AI Chatbot, Bugs and other fixes

# BUGS/UPDATES
## AUTH
- user deactivated logic to be written in local_routes
- mfa not set yet
- cron to revoke expired tokens
- On register (fe), create checks on frontend too so backend does little work (like pw checks, both pw same, etc)
- refresh token not working 
- refresh tokens are not revoking, revoke at 1. when it expired we got to know 2. cron job revoking regularly
- Google one tap not working
- Auth when pressed login button, it becomes dark and not visible
- csrf on cookie flows (since jwt is in cookies, enable csrf protection on all required endpoints)
- rate limits set up for all endpoints (signin, verify mfa, forgot, reset pw, refresh)
- email queueing so it's not blocked by smtp
- throttle resend verify
- login event is in db, make it work so we know the active users per day per month more easily rather than calculating every time...
## FOOTER
- Add social links
## LANDING PAGE
- hero section touching navbar in laptop screen
- Why hunters love us --> that heart does not look interesting
- Choose your arsenal needs to be updated - tools are no longer served solo differently
- Watch demo button not required, maybe replace it or remove it and fix design bcoz the other button will not be looking good after removing this
- A section in which we show how we can use tools (a little gif or quick vid)
- Change scrollbar color
## TOOLS
- Launch button pressed multiple times without changing parameters is throwing errors
- use celery to run the processes in backend
- Files are being saved in app.py's folder on server
- Make these dynamic 
 - tools category
 - tools list per category
 - tool count per category
 - workflow canvas state
 - config forms per tool
 - terminal stream
 - session list 
## ADMIN PAGE
- Auth page for admin section (somewhat made in testing folder)
- Unauthorized users's can see a page saying "You are not authorized for this page, redirecting in 3..2..1 " - then they get sent back to home page 
- Page - analytics
- Page - tools
- Page - blogs
- Page - admins
- Page - audit logs
- Page - settings
- Show admin user details in the left panel rather than static details
- Grant user some credits
- Give user pro memberships (from admin panel)
## BLOG
- Like functionality
- Comment functionality
- View Functionality
- Blog detail UI fix
- Blog list UI fix
## ROLES
- Check and confirm all the roles
- Enforce all the roles
## FINAL UPDATES
- Change db from sqlite to postgresql and update the models to use postgre 
- Using the in-memory storage for tracking rate limits as no storage was explicitly specified. -- solve this warning we receive in terminal when we run the server
## CREDENTIAL UPDATES REQUIRED
- Github oauth id/secret
- Google oauth id/secret
- cloudflare turnstile creds
- mail id pw 
## OVERALL
- add meta for author as me
- add readme file
- add copyright as this is my code developed
- have timezone for user specific
## IN-WEBSITE CURRENCY
- enable credits
    - 10 per day (reset everyday, no rollover, used first)
    - Paid includes 
        - 100 monthly credits (pro version - $25/month)
        - Top-up packs
            - $25 - 100 credits
            - $40 - 200 credits
            - $90 - 500 credits
## MAILS
- check both mails (functioning good?)
## NAVBAR
- link user dashboard
- link billing and plan
- link help

## ACCOUNT SETTINGS PAGE    
- redesigning of the page (page design available)
- email change delivery
    - wire real miler + HTML template, env configs, proper sender
    - Notify old email, invalidate other sessions on change, configurable token TTL/domain
- MFA / TOTP + backup codes
    - Enroll/verify/disable endpoints, QR/secret generation, backup code issuance/revoke
    - Optional re-auth requirement to toggle
- OAuth connections management
    - List/link/unlink providers; guard against unlinking the last login method (if no pw)
    - Audit + email alerts on link/unlink
- Privacy actions
    - Implement celery jobs for export (data bundle _ signed download link) and delete (grace window, final purge)
    - Admin hold/cancel path, confirmation emails, and audit entries
- Notifications Integration
    - Sync prefs to ESP/CRM (eg Mailgun/SendGrid) + per-user unsubscribe token handling
    - Defaulting/seeding policy and enforcement across outbound email
- Sessions hardening
    - Capture and persist device/IP/UA/last-seen at login, show in list
    - Optionally protect currentt session from 'revoke-all', rotate refresh tokens on sensitive changes
- Re-auth window
    - Implement a 10-15 min re-auth grace (claim/flag) so sensitive endpoints don't require pw every POST
- Rate limits on sensitive routes
    - Add limiter.limit() for pw/email/mfa/exports/deletes (align with your tools pattern)
- Security alerts and audit log
    - Emit events + persist audit rows for - pw changed, email changed, mfa toggled, sessions revoked, export/delete requested
- API parity (optional)
    - JSON endpoints mirroring the HTML flows for SPA/mobile clients
- DB migrations
    - Add indexes for session lookups (user_id, revoked, expires_at)
## BILLING AND PLAN PAGE
- complete set up
## HELP PAGE
- complete set up






# TODO DONE LIST
## FOOTER
- Footer bg needs to be a little darker, just like navbar
## LANDING PAGE
- The overlay (opacity change) flowing down is too fast, slow the speed (for all pages)
- Launch scan button should lead to tools page
## AUTH
- unable to logout
- Auth login/register the input sections are not same size
## ADMIN
- Logout button not working
## NAVBAR
- Dropdown needs user dashboard
- Dropdown from User needs design update
- Dropdown needs complete restyling like this image
- link account settings
- remove margin-top from page-wrapper class in navbar.css (line 816) - css file has -> ("/* TODO - REMOVE MARGIN-TOP  --- ONLY FOR DEBUGGING */")
## MAILS
- Confirm mail design update required
- Reset Password mail design update required

