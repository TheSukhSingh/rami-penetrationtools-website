// Global state
let currentPage = 'home';
let currentTestimonial = 0;
let currentAuthMode = 'login';
let likedPosts = new Set();
let currentBlogPost = null;

// Sample data
const testimonials = [
    {
        name: 'Alex Chen',
        role: 'Senior Penetration Tester • CyberSec Corp',
        content: 'Hunter\'s Terminal has revolutionized our reconnaissance process. The automated chains save us hours of manual work while maintaining the precision we need.',
        avatar: '🥷',
        specialty: 'Network Security'
    },
    {
        name: 'Sarah Rodriguez',
        role: 'Bug Hunter • Independent',
        content: 'The solo tools are incredibly powerful. I\'ve discovered vulnerabilities that other platforms missed. The stealth capabilities are unmatched.',
        avatar: '🕵️',
        specialty: 'Web Application Security'
    },
    {
        name: 'Marcus Johnson',
        role: 'CISO • TechGuard Solutions',
        content: 'Our team\'s productivity has increased 300% since implementing Hunter\'s Terminal. The reporting features are enterprise-grade.',
        avatar: '👨‍💼',
        specialty: 'Enterprise Security'
    },
    {
        name: 'Emma Thompson',
        role: 'Red Team Lead • DefenseFirst',
        content: 'The intelligence gathering capabilities are phenomenal. We can now correlate data from multiple sources seamlessly.',
        avatar: '🔍',
        specialty: 'Threat Intelligence'
    }
];

const blogPosts = [
    {
        id: '1',
        title: 'Advanced Port Scanning Techniques for 2025',
        excerpt: 'Discover the latest stealth scanning methods that bypass modern firewalls and intrusion detection systems.',
        content: `# Advanced Port Scanning Techniques for 2025

In the ever-evolving landscape of cybersecurity, port scanning remains one of the fundamental reconnaissance techniques. However, traditional scanning methods are increasingly detected by modern security systems.

## Stealth Scanning Evolution

The art of stealth scanning has evolved significantly. Modern techniques include:

### 1. Timing-Based Evasion
By carefully controlling the timing between packets, we can avoid triggering rate-limiting mechanisms:

\`\`\`bash
nmap -sS -T1 --scan-delay 10s target.com
\`\`\`

### 2. Fragmented Packet Scanning
Breaking packets into smaller fragments can bypass some firewall rules:

\`\`\`bash
nmap -f -f target.com
\`\`\`

### 3. Decoy Scanning
Using multiple decoy IP addresses to mask the real source:

\`\`\`bash
nmap -D RND:10 target.com
\`\`\`

## Advanced Techniques

### SYN Flood Protection Bypass
Many modern systems implement SYN flood protection. Here's how to work around it:

1. **Connection Recycling**: Reuse existing connections when possible
2. **Source Port Randomization**: Vary source ports to appear as legitimate traffic
3. **Protocol Switching**: Alternate between TCP and UDP scans

### Machine Learning Evasion
With AI-powered security systems becoming common, we need to adapt:

- **Behavioral Mimicry**: Make scan patterns resemble normal user behavior
- **Traffic Blending**: Mix scanning traffic with legitimate requests
- **Adaptive Timing**: Adjust scan speed based on target response patterns

## Conclusion

The future of port scanning lies in intelligent, adaptive techniques that can evolve with defensive measures. Stay ahead by continuously updating your methodology and tools.`,
        author: 'Alex Chen',
        date: '2025-01-15',
        readTime: '8 min read',
        views: 2847,
        likes: 156,
        comments: 23,
        tags: ['Port Scanning', 'Stealth', 'Nmap', 'Evasion'],
        category: 'Reconnaissance'
    },
    {
        id: '2',
        title: 'Building Automated Reconnaissance Chains',
        excerpt: 'Learn how to create powerful automation workflows that chain multiple tools together for comprehensive target analysis.',
        content: `# Building Automated Reconnaissance Chains

Automation is the key to scaling reconnaissance operations. By chaining tools together, we can create powerful workflows that provide comprehensive target analysis.

## The Chain Philosophy

Think of reconnaissance as a pipeline where each tool's output becomes the next tool's input:

\`\`\`
Domain → Subdomain Enum → Port Scan → Service Detection → Vulnerability Assessment
\`\`\`

## Essential Chain Components

### 1. Discovery Phase
Start with broad discovery:

\`\`\`bash
# Subdomain enumeration
subfinder -d target.com | httpx -silent | nuclei -t exposures/
\`\`\`

### 2. Analysis Phase
Deep dive into discovered assets:

\`\`\`bash
# Port scanning and service detection
nmap -sV -sC -oA scan_results discovered_hosts.txt
\`\`\`

### 3. Exploitation Phase
Identify potential attack vectors:

\`\`\`bash
# Vulnerability scanning
nuclei -l discovered_hosts.txt -t vulnerabilities/
\`\`\`

## Automation Frameworks

### Custom Bash Scripts
Simple but effective for basic chains:

\`\`\`bash
#!/bin/bash
target=$1
echo "[+] Starting recon chain for $target"

# Phase 1: Discovery
subfinder -d $target -o subdomains.txt
httpx -l subdomains.txt -o live_hosts.txt

# Phase 2: Scanning
nmap -iL live_hosts.txt -oA nmap_results

# Phase 3: Analysis
nuclei -l live_hosts.txt -o vulnerabilities.txt
\`\`\`

### Python Orchestration
For more complex logic and error handling:

\`\`\`python
import subprocess
import json

class ReconChain:
    def __init__(self, target):
        self.target = target
        self.results = {}
    
    def run_discovery(self):
        # Subdomain enumeration
        result = subprocess.run(['subfinder', '-d', self.target], 
                              capture_output=True, text=True)
        self.results['subdomains'] = result.stdout.split('\\n')
    
    def run_analysis(self):
        # Port scanning
        for subdomain in self.results['subdomains']:
            if subdomain:
                self.scan_host(subdomain)
\`\`\`

## Best Practices

1. **Error Handling**: Always include proper error handling and logging
2. **Rate Limiting**: Respect target resources and avoid detection
3. **Data Correlation**: Link findings across different tools
4. **Reporting**: Generate comprehensive reports with actionable insights

## Conclusion

Automated reconnaissance chains multiply your effectiveness while reducing manual effort. Start simple and gradually build more sophisticated workflows as your needs evolve.`,
        author: 'Sarah Rodriguez',
        date: '2025-01-12',
        readTime: '12 min read',
        views: 1923,
        likes: 89,
        comments: 15,
        tags: ['Automation', 'Reconnaissance', 'Workflows', 'Python'],
        category: 'Automation'
    },
    {
        id: '3',
        title: 'OSINT Gathering in the Age of Privacy',
        excerpt: 'Navigate the challenges of modern OSINT collection while respecting privacy boundaries and legal constraints.',
        content: `# OSINT Gathering in the Age of Privacy

Open Source Intelligence (OSINT) gathering has become increasingly challenging as privacy awareness grows and platforms implement stronger protections.

## The Changing Landscape

### Platform Restrictions
Major platforms have implemented significant restrictions:

- **LinkedIn**: Rate limiting and bot detection
- **Twitter/X**: API restrictions and paid tiers
- **Facebook**: Reduced public data availability
- **Instagram**: Limited scraping capabilities

### Legal Considerations
Always ensure your OSINT activities comply with:

1. **Terms of Service**: Respect platform ToS
2. **Local Laws**: Understand your jurisdiction's regulations
3. **International Law**: Consider cross-border implications
4. **Ethical Guidelines**: Maintain professional standards

## Modern OSINT Techniques

### 1. Passive Collection
Focus on publicly available information:

\`\`\`bash
# DNS enumeration
dig target.com ANY
nslookup -type=MX target.com

# Certificate transparency logs
curl -s "https://crt.sh/?q=%.target.com&output=json" | jq
\`\`\`

### 2. Social Media Intelligence
Ethical social media reconnaissance:

- **Public Posts**: Only collect publicly visible content
- **Metadata Analysis**: Extract location and timing data
- **Network Mapping**: Identify connections and relationships
- **Sentiment Analysis**: Understand public perception

### 3. Technical Intelligence
Infrastructure and technical footprinting:

\`\`\`bash
# Shodan queries
shodan search "org:target-company"

# Google dorking
site:target.com filetype:pdf
site:target.com inurl:admin
\`\`\`

## Privacy-Respecting Tools

### Recommended OSINT Tools
1. **theHarvester**: Email and subdomain collection
2. **Maltego**: Visual link analysis
3. **Recon-ng**: Modular reconnaissance framework
4. **SpiderFoot**: Automated OSINT collection

### Custom Solutions
Build your own tools with privacy in mind:

\`\`\`python
import requests
import time

class EthicalOSINT:
    def __init__(self):
        self.session = requests.Session()
        self.rate_limit = 1  # 1 second between requests
    
    def collect_data(self, target):
        # Implement rate limiting
        time.sleep(self.rate_limit)
        
        # Only collect public data
        response = self.session.get(f"https://api.example.com/public/{target}")
        return response.json()
\`\`\`

## Best Practices

### Ethical Guidelines
1. **Minimize Data Collection**: Only collect what you need
2. **Respect Privacy**: Avoid personal/private information
3. **Secure Storage**: Protect collected data appropriately
4. **Regular Cleanup**: Delete data when no longer needed

### Technical Considerations
- **Use VPNs**: Protect your identity and location
- **Rotate User Agents**: Avoid detection patterns
- **Implement Delays**: Respect server resources
- **Monitor Legal Changes**: Stay updated on regulations

## Conclusion

OSINT remains a powerful technique when conducted ethically and legally. Focus on publicly available information, respect privacy boundaries, and always consider the legal implications of your activities.

The future of OSINT lies in balancing effectiveness with ethical responsibility.`,
        author: 'Marcus Johnson',
        date: '2025-01-10',
        readTime: '10 min read',
        views: 3156,
        likes: 201,
        comments: 31,
        tags: ['OSINT', 'Privacy', 'Ethics', 'Intelligence'],
        category: 'Intelligence'
    }
];

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    initializeHero();
    initializeWireframeGlobe();
    initializeTestimonials();
    initializeRevealAnimation();
    initializeParticles();
    initializeBlog();
    
    // Handle scroll events
    window.addEventListener('scroll', handleScroll);
}

function setupEventListeners() {
    // Navigation
    document.getElementById('prevTestimonial').addEventListener('click', prevTestimonial);
    document.getElementById('nextTestimonial').addEventListener('click', nextTestimonial);
    
    // Auth form
    document.getElementById('authForm').addEventListener('submit', handleAuthSubmit);
    
    // Auto-advance testimonials
    setInterval(nextTestimonial, 5000);
}

function initializeHero() {
    const typedTextElement = document.getElementById('typedText');
    const fullText = '> scan-the-unseen --deep --stealth';
    let index = 0;
    
    function typeText() {
        if (index < fullText.length) {
            typedTextElement.textContent = fullText.slice(0, index + 1);
            index++;
            setTimeout(typeText, 100);
        } else {
            typedTextElement.classList.add('typing');
        }
    }
    
    typeText();
}

function initializeWireframeGlobe() {
    const canvas = document.getElementById('wireframeGlobe');
    const ctx = canvas.getContext('2d');
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
        
        ctx.strokeStyle = '#00FFE0';
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
    window.addEventListener('resize', resizeCanvas);
    drawGlobe();
}

function initializeTestimonials() {
    updateTestimonial();
}

function updateTestimonial() {
    const testimonial = testimonials[currentTestimonial];
    
    document.getElementById('testimonialText').textContent = `"${testimonial.content}"`;
    document.getElementById('testimonialName').textContent = testimonial.name;
    document.getElementById('testimonialRole').textContent = testimonial.role;
    document.getElementById('testimonialAvatar').textContent = testimonial.avatar;
    document.getElementById('testimonialSpecialty').innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <circle cx="12" cy="16" r="1"></circle>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        </svg>
        <span>${testimonial.specialty}</span>
    `;
    
    // Update dots
    const dots = document.querySelectorAll('.dot');
    dots.forEach((dot, index) => {
        dot.classList.toggle('active', index === currentTestimonial);
    });
}

function nextTestimonial() {
    currentTestimonial = (currentTestimonial + 1) % testimonials.length;
    updateTestimonial();
}

function prevTestimonial() {
    currentTestimonial = (currentTestimonial - 1 + testimonials.length) % testimonials.length;
    updateTestimonial();
}

function setTestimonial(index) {
    currentTestimonial = index;
    updateTestimonial();
}

function initializeRevealAnimation() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
            }
        });
    }, observerOptions);

    const revealElements = document.querySelectorAll('.reveal');
    revealElements.forEach(el => observer.observe(el));
}

function initializeParticles() {
    const particlesContainer = document.getElementById('particles');
    
    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = `${Math.random() * 100}%`;
        particle.style.top = `${Math.random() * 100}%`;
        particle.style.animationDelay = `${Math.random() * 3}s`;
        particle.style.animationDuration = `${2 + Math.random() * 2}s`;
        particlesContainer.appendChild(particle);
    }
}

function initializeBlog() {
    renderBlogGrid();
}

function renderBlogGrid() {
    const blogGrid = document.getElementById('blogGrid');
    if (!blogGrid) return;
    
    blogGrid.innerHTML = blogPosts.map(post => `
        <article class="blog-card glass card-hover" onclick="openBlogPost('${post.id}')">
            <div class="blog-meta">
                <span class="category-badge">${post.category}</span>
                <div class="blog-views">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    <span>${post.views.toLocaleString()}</span>
                </div>
            </div>

            <h2 class="blog-title">${post.title}</h2>
            <p class="blog-excerpt">${post.excerpt}</p>

            <div class="blog-author-info">
                <div class="blog-author">
                    <div class="author-icon glass">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                            <circle cx="12" cy="7" r="4"></circle>
                        </svg>
                    </div>
                    <span>${post.author}</span>
                </div>
                <div class="blog-read-time">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12,6 12,12 16,14"></polyline>
                    </svg>
                    <span>${post.readTime}</span>
                </div>
            </div>

            <div class="blog-engagement">
                <div class="engagement-stats">
                    <div class="stat likes">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                        </svg>
                        <span>${post.likes + (likedPosts.has(post.id) ? 1 : 0)}</span>
                    </div>
                    <div class="stat comments">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                        </svg>
                        <span>${post.comments}</span>
                    </div>
                </div>
                <span class="blog-date">${post.date}</span>
            </div>

            <div class="blog-tags">
                ${post.tags.slice(0, 2).map(tag => `<span class="tag">#${tag}</span>`).join('')}
                ${post.tags.length > 2 ? `<span class="tag">+${post.tags.length - 2}</span>` : ''}
            </div>
        </article>
    `).join('');
}

function openBlogPost(postId) {
    const post = blogPosts.find(p => p.id === postId);
    if (!post) return;
    
    currentBlogPost = post;
    
    // Update views
    post.views += 1;
    
    // Render blog post
    const blogPostContent = document.getElementById('blogPostContent');
    blogPostContent.innerHTML = `
        <div class="blog-post-header">
            <div class="blog-post-meta">
                <span class="category-badge">${post.category}</span>
                <div class="blog-post-date">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                        <line x1="16" y1="2" x2="16" y2="6"></line>
                        <line x1="8" y1="2" x2="8" y2="6"></line>
                        <line x1="3" y1="10" x2="21" y2="10"></line>
                    </svg>
                    <span>${post.date}</span>
                </div>
                <div class="blog-post-read-time">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"></circle>
                        <polyline points="12,6 12,12 16,14"></polyline>
                    </svg>
                    <span>${post.readTime}</span>
                </div>
            </div>
            
            <h1 class="blog-post-title">${post.title}</h1>
            
            <div class="blog-post-author">
                <div class="post-author-info">
                    <div class="post-author-avatar glass">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                            <circle cx="12" cy="7" r="4"></circle>
                        </svg>
                    </div>
                    <div class="post-author-details">
                        <h4>${post.author}</h4>
                        <p>Security Researcher</p>
                    </div>
                </div>
                
                <div class="post-stats">
                    <div class="stat">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                            <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                        <span>${post.views.toLocaleString()}</span>
                    </div>
                    <div class="stat likes">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                        </svg>
                        <span>${post.likes + (likedPosts.has(post.id) ? 1 : 0)}</span>
                    </div>
                    <div class="stat comments">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                        </svg>
                        <span>${post.comments}</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="blog-post-content-text">${post.content}</div>

        <div class="blog-post-tags">
            ${post.tags.map(tag => `<span class="post-tag">#${tag}</span>`).join('')}
        </div>
    `;
    
    // Render interactions
    const blogInteractions = document.getElementById('blogInteractions');
    blogInteractions.innerHTML = `
        <div class="interaction-buttons">
            <button class="interaction-btn ${likedPosts.has(post.id) ? 'liked' : ''}" onclick="toggleLike('${post.id}')">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                </svg>
                <span>${post.likes + (likedPosts.has(post.id) ? 1 : 0)}</span>
            </button>
            
            <button class="interaction-btn">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
                <span>${post.comments}</span>
            </button>
        </div>
        
        <button class="share-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
            </svg>
            <span>Share</span>
        </button>
    `;
    
    // Render comments
    renderComments(post);
    
    showPage('blogPost');
}

function renderComments(post) {
    const sampleComments = [
        { author: 'CyberNinja', content: 'Excellent breakdown of modern evasion techniques. The timing-based approach has been game-changing for my assessments.', time: '2 hours ago' },
        { author: 'RedTeamLead', content: 'Great article! Would love to see a follow-up on IPv6 scanning techniques.', time: '5 hours ago' },
        { author: 'PentestPro', content: 'The decoy scanning section is particularly useful. Thanks for sharing these insights!', time: '1 day ago' }
    ];
    
    const blogComments = document.getElementById('blogComments');
    blogComments.innerHTML = `
        <h3 class="comments-header">Comments (${post.comments})</h3>
        
        <form class="comment-form" onsubmit="handleCommentSubmit(event)">
            <textarea 
                class="comment-textarea" 
                placeholder="Share your thoughts on this technique..."
                id="newComment"
            ></textarea>
            <div class="comment-form-actions">
                <button type="submit" class="cyber-button">Post Comment</button>
            </div>
        </form>

        <div class="comments-list">
            ${sampleComments.map(comment => `
                <div class="comment">
                    <div class="comment-header">
                        <div class="comment-author">
                            <div class="comment-avatar glass">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                                    <circle cx="12" cy="7" r="4"></circle>
                                </svg>
                            </div>
                            <span class="comment-author-name">${comment.author}</span>
                        </div>
                        <span class="comment-time">${comment.time}</span>
                    </div>
                    <p class="comment-content">${comment.content}</p>
                </div>
            `).join('')}
        </div>
    `;
}

function toggleLike(postId) {
    if (likedPosts.has(postId)) {
        likedPosts.delete(postId);
    } else {
        likedPosts.add(postId);
    }
    
    // Update the current blog post view if it's open
    if (currentBlogPost && currentBlogPost.id === postId) {
        openBlogPost(postId);
    }
    
    // Update blog grid if visible
    if (currentPage === 'blog') {
        renderBlogGrid();
    }
}

function handleCommentSubmit(event) {
    event.preventDefault();
    const commentText = document.getElementById('newComment').value.trim();
    
    if (commentText) {
        // Simulate adding comment
        currentBlogPost.comments += 1;
        document.getElementById('newComment').value = '';
        
        // Re-render comments
        renderComments(currentBlogPost);
    }
}

function handleScroll() {
    const navbar = document.getElementById('navbar');
    if (window.scrollY > 20) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
}

function showPage(page) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    
    // Show selected page
    const pageElement = document.getElementById(page + 'Page');
    if (pageElement) {
        pageElement.classList.add('active');
        currentPage = page;
    }
    
    // Scroll to top
    window.scrollTo(0, 0);
}

function scrollToSection(sectionId) {
    if (currentPage !== 'home') {
        showPage('home');
        setTimeout(() => {
            const element = document.getElementById(sectionId);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth' });
            }
        }, 100);
    } else {
        const element = document.getElementById(sectionId);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth' });
        }
    }
}

function toggleMobileMenu() {
    const navMenu = document.getElementById('navMenu');
    const navToggle = document.getElementById('navToggle');
    
    navMenu.classList.toggle('active');
    navToggle.classList.toggle('active');
}

// Auth functions
function showAuth(mode) {
    currentAuthMode = mode;
    updateAuthModal();
    document.getElementById('authModal').classList.add('active');
}

function closeAuth() {
    document.getElementById('authModal').classList.remove('active');
}

function updateAuthModal() {
    const titles = {
        login: 'Access Terminal',
        signup: 'Join the Hunt',
        forgot: 'Reset Access'
    };
    
    const subtitles = {
        login: 'Enter your credentials to continue',
        signup: 'Create your hunter account',
        forgot: 'Recover your terminal access'
    };
    
    const buttonTexts = {
        login: 'Access Terminal',
        signup: 'Create Account',
        forgot: 'Send Reset Link'
    };
    
    document.getElementById('authTitle').textContent = titles[currentAuthMode];
    document.getElementById('authSubtitle').textContent = subtitles[currentAuthMode];
    document.getElementById('authButtonText').textContent = buttonTexts[currentAuthMode];
    
    // Show/hide fields based on mode
    const usernameField = document.getElementById('usernameField');
    const passwordField = document.getElementById('passwordField');
    const confirmPasswordField = document.getElementById('confirmPasswordField');
    
    usernameField.style.display = currentAuthMode === 'signup' ? 'flex' : 'none';
    passwordField.style.display = currentAuthMode === 'forgot' ? 'none' : 'flex';
    confirmPasswordField.style.display = currentAuthMode === 'signup' ? 'flex' : 'none';
    
    // Update links
    const authLinks = document.getElementById('authLinks');
    if (currentAuthMode === 'login') {
        authLinks.innerHTML = `
            <div>
                <a href="#" class="auth-link" onclick="updateAuthMode('forgot')">Forgot your password?</a>
            </div>
            <div class="auth-text">
                New hunter? 
                <a href="#" class="auth-link" onclick="updateAuthMode('signup')">Join the hunt</a>
            </div>
        `;
    } else if (currentAuthMode === 'signup') {
        authLinks.innerHTML = `
            <div class="auth-text">
                Already have an account? 
                <a href="#" class="auth-link" onclick="updateAuthMode('login')">Sign in</a>
            </div>
        `;
    } else if (currentAuthMode === 'forgot') {
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

function togglePassword(fieldId) {
    const field = document.getElementById(fieldId);
    const button = field.nextElementSibling;
    const eyeOpen = button.querySelector('.eye-open');
    const eyeClosed = button.querySelector('.eye-closed');
    
    if (field.type === 'password') {
        field.type = 'text';
        eyeOpen.style.display = 'none';
        eyeClosed.style.display = 'block';
    } else {
        field.type = 'password';
        eyeOpen.style.display = 'block';
        eyeClosed.style.display = 'none';
    }
}

function handleAuthSubmit(event) {
    event.preventDefault();
    
    const submitButton = document.getElementById('authSubmit');
    const buttonText = document.getElementById('authButtonText');
    const buttonIcon = document.getElementById('authButtonIcon');
    const spinner = document.getElementById('authSpinner');
    
    // Show loading state
    buttonText.style.display = 'none';
    buttonIcon.style.display = 'none';
    spinner.style.display = 'block';
    submitButton.disabled = true;
    
    // Simulate API call
    setTimeout(() => {
        // Reset button state
        buttonText.style.display = 'inline';
        buttonIcon.style.display = 'inline';
        spinner.style.display = 'none';
        submitButton.disabled = false;
        
        // Close modal
        closeAuth();
    }, 2000);
}