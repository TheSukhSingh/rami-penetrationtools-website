# one-click seed for a single blog post

from datetime import datetime
from extensions import db

# --- import models (this path matches your repo: /srv/web/blog/models.py) ---
try:
    from blog.models import Category, Tag, Post, PostStatus
except Exception as e:
    raise RuntimeError(f"Import failed. Make sure models are in blog/models.py. Error: {e}")

# --- tiny helper ---
def get_or_create(model, **filters_and_defaults):
    lookup = {k: v for k, v in filters_and_defaults.items() if k in model.__table__.c}
    obj = model.query.filter_by(**{k: lookup[k] for k in lookup if k != 'description'}).first()
    if obj:
        return obj
    obj = model(**filters_and_defaults)
    db.session.add(obj)
    return obj

# --- ensure category + tags exist ---
cat = get_or_create(Category, name="Guides", slug="guides", description="in-depth how-tos and playbooks")
tag_osint = get_or_create(Tag, name="osint", slug="osint")
tag_recon = get_or_create(Tag, name="recon", slug="recon")
db.session.flush()

# --- create ONE dummy post ---
post = Post(
    title="Random Testing",
    slug=None,  # let before_insert generate from title
    summary="A concise workflow to enumerate hosts, services, and endpoints.",
    body_md="""















# Random Testing – OSINT Attack Surface Quick Start

Modern security testing is no longer limited to scanning a single host with a handful of tools. The internet has grown too large, and digital footprints are too complex. If you want to enumerate your attack surface like a pro, you need a structured workflow, repeatable steps, and a toolbox of reliable open-source utilities.  

This guide is a **concise workflow** to enumerate hosts, services, and endpoints effectively. It blends theory with hands-on snippets you can try right away.

---

## Table of Contents

1. [Why Random Testing Matters](#why-random-testing-matters)  
2. [Setting Up Your Environment](#setting-up-your-environment)  
3. [Host Discovery](#host-discovery)  
4. [Service Enumeration](#service-enumeration)  
5. [Web Endpoint Enumeration](#web-endpoint-enumeration)  
6. [Automating Workflows](#automating-workflows)  
7. [Interpreting Results](#interpreting-results)  
8. [Sample Attack Surface Workflow](#sample-attack-surface-workflow)  
9. [Best Practices & Pitfalls](#best-practices--pitfalls)  
10. [Conclusion](#conclusion)  

---

## Why Random Testing Matters

Security professionals often fall into the trap of **only scanning what they know**. But the true risk lies in what you don’t know—forgotten servers, staging systems exposed to the internet, or APIs left unprotected.

Consider this:

- 70% of organizations admit they don’t have a full inventory of their external assets.  
- Attackers are **lazy but systematic**: they use automated reconnaissance to find weak points.  
- “Random” doesn’t mean *reckless*. It means probing beyond the obvious—enumerating neighbors, DNS records, misconfigured cloud buckets, and forgotten endpoints.  

In short: **You can’t defend what you don’t see.**

---

## Setting Up Your Environment

Before running tools, you need a stable workspace. A typical setup includes:

- **Linux distribution**: Kali, Parrot, or Ubuntu server.  
- **Package manager**: `apt`, `brew`, or `pipx`.  
- **Programming basics**: Python or Go, since most modern tools are written in these languages.

### Install Core Tools

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Go and Python
sudo apt install golang python3 python3-pip -y

# Install Git
sudo apt install git -y
Recommended Tools
Category	Tool Examples	Purpose
Host Discovery	amass, subfinder, assetfinder	Enumerate domains/subdomains
Port Scanning	nmap, naabu, masscan	Identify open ports
Web Enumeration	httpx, ffuf, gau, katana	Collect URLs and probe endpoints
Vulnerability Scans	nuclei, wpscan, whatweb	Detect misconfigurations
Data Extraction	linkfinder, waybackurls	Extract hidden endpoints

Host Discovery
Passive Enumeration
Passive means collecting data without touching the target directly. Examples:

bash
Copy
Edit
subfinder -d example.com -o subs.txt
amass enum -passive -d example.com
Sources include certificate transparency logs, DNS records, and third-party APIs.

Active Enumeration
Once you have a list of domains, verify which are alive:

bash
Copy
Edit
httpx -l subs.txt -status-code -title -o live.txt
This step weeds out dead hosts and focuses efforts.

Service Enumeration
Identifying open services reveals the attack surface.

Using Naabu
bash
Copy
Edit
naabu -list live.txt -ports full -o ports.txt
This produces a clean list of IPs with open ports.

Deep Scan with Nmap
bash
Copy
Edit
nmap -iL ports.txt -A -oN nmap_output.txt
Flags like -A enable OS detection, service versions, and traceroutes.

Web Endpoint Enumeration
Web apps are usually the juiciest target.

Gather URLs
bash
Copy
Edit
gau example.com | tee urls.txt
Or using Katana:

bash
Copy
Edit
katana -u https://example.com -o katana_urls.txt
Filter Endpoints
Pipe URLs to grep or custom scripts:

bash
Copy
Edit
cat urls.txt | grep ".php" > php_endpoints.txt
Fuzzing Hidden Paths
bash
Copy
Edit
ffuf -u https://example.com/FUZZ -w /usr/share/wordlists/dirb/common.txt
This brute-forces directories and files.

Automating Workflows
Running tools manually is fine for practice, but professionals automate.

Bash Script Example
bash
Copy
Edit
#!/bin/bash
domain=$1
mkdir $domain && cd $domain

subfinder -d $domain -o subs.txt
httpx -l subs.txt -o live.txt
naabu -list live.txt -o ports.txt
nmap -iL ports.txt -A -oN nmap_output.txt
gau $domain | tee urls.txt
Run it with:

bash
Copy
Edit
chmod +x recon.sh
./recon.sh example.com
Interpreting Results
Data is useless unless interpreted correctly.

Group hosts by role – prod, staging, dev.

Prioritize based on risk – focus on exposed admin panels, old versions, or misconfigured cloud storage.

Document findings – screenshots, logs, and proof of concept.

Pro tip: Store results in a database or at least structured folders for easy review.

Sample Attack Surface Workflow
Here’s a sample one-click pipeline:

bash
Copy
Edit
# Enumerate subdomains
subfinder -d example.com -silent > subs.txt

# Verify live hosts
httpx -l subs.txt -silent > live.txt

# Scan ports
naabu -list live.txt -o ports.txt

# Run nuclei templates
nuclei -l live.txt -t cves/ -o vulns.txt
Flowchart (text-based):

css
Copy
Edit
[Domain] -> [Subfinder] -> [HTTPX] -> [Naabu] -> [Nmap/Nuclei] -> [Findings]
Best Practices & Pitfalls
Do’s
Always respect scope – only test assets you’re authorized for.

Keep tools updated.

Automate repetitive steps.

Validate false positives manually.

Don’ts
Don’t hammer a server with uncontrolled scans.

Don’t rely on a single tool.

Don’t ignore passive data sources.

Don’t publish sensitive findings carelessly.

Code Snippets for Quick Wins
Python: Extracting Unique Domains
python
Copy
Edit
with open("urls.txt") as f:
    domains = {url.split("/")[2] for url in f if "http" in url}

with open("unique_domains.txt", "w") as out:
    for d in sorted(domains):
        out.write(d + "\n")
Go: Simple Port Scanner
go
Copy
Edit
package main
import (
    "fmt"
    "net"
    "time"
)

func main() {
    target := "scanme.nmap.org"
    ports := []int{21,22,80,443}
    for _, port := range ports {
        address := fmt.Sprintf("%s:%d", target, port)
        conn, err := net.DialTimeout("tcp", address, 2*time.Second)
        if err == nil {
            fmt.Printf("Open: %d\n", port)
            conn.Close()
        }
    }
}
Advanced Tips
Chain Tools: Pipe results (subfinder → httpx → nuclei).

Use Docker: Isolate tools and avoid dependency hell.

Cloud Recon: Search for open S3 buckets or GCP buckets.

Graph Data: Import results into tools like Maltego or Neo4j.

Conclusion
Random testing isn’t about chaos—it’s about widening the lens. By enumerating domains, scanning services, probing endpoints, and automating workflows, you uncover the hidden parts of the attack surface.

This quick-start workflow gives you everything you need to move from theory to practice. With the right discipline, your reconnaissance will reveal risks long before attackers exploit them.

Happy hunting, and may your scans be fruitful.



























""",
    status=PostStatus.PUBLISHED.value,   # or "published" if you prefer raw string
    published_at=datetime.utcnow(),
    category=cat,
    cover_alt="Graph of domains and services",
    og_title="OSINT Attack Surface – Quick Start",
    og_description="Enumerate, probe, and prioritize like a pro.",
    author_id=None,  # set to a real user id if available
    featured=False,
)

# attach tags and persist
post.tags = [tag_osint, tag_recon]
db.session.add(post)
db.session.commit()

# verify
(post.id, post.slug, post.status, post.published_at, post.reading_time)
