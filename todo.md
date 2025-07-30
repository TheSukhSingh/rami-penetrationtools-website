AUTH
1. seed.py needs improvements
2. user deactivated logic to be written in local_routes
2. mfa not set yet



admin
Responsibilities

User & Role Management: create/edit/deactivate users, assign roles/permissions.

Audit Logs: view/filter LoginEvent, PasswordReset, token revocations.

Site Settings: edit email templates, JWT lifetimes, feature toggles.

Metrics Dashboard: count of active users, sign-ups (daily/weekly/monthly), login failures, error rates.

Tools History: number of scans run, per-tool usage, status breakdown.










blog
Features

Authoring: users with blog_writer role can create/edit posts; WYSIWYG or Markdown support.

Rich Content: images, code blocks, embeds, text formatting.

Public Views: anyone can browse list/detail pages.

Engagement: logged-in users can like, comment; view count tracking.

Analytics Hooks: track views per post, comment volume, like counts over time (for admin dashboard).








tools
Features

Tool Execution: individual tool forms (subfinder, httpx, …), display terminal output in-browser.

Chained Scans: allow selecting multiple tools in sequence; combine & normalize outputs.

History: persist ScanJob (timestamp, user, tools run, parameters), and ScanResult details.

Admin Analytics: number of scans, error rates, avg. runtime per tool, user activity heatmaps.