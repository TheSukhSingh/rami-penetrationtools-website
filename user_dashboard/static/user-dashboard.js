// Global state
let currentTab = 'overview';
let currentPeriod = '7d';

// Sample data for charts
const sampleData = {
    scansOverTime: {
        '7d': [45, 52, 38, 67, 73, 89, 94],
        '30d': Array.from({length: 30}, () => Math.floor(Math.random() * 50) + 30),
        '90d': Array.from({length: 90}, () => Math.floor(Math.random() * 50) + 30)
    },
    toolsUsage: {
        labels: ['Subfinder', 'Naabu', 'Httpx', 'Katana', 'Dnsx'],
        data: [234, 189, 156, 123, 98]
    },
    successRate: {
        success: 824,
        failed: 23
    }
};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    initializeParticles();
    initializeCharts();
    updateStats();
}

function setupEventListeners() {
    // Tab navigation
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            const tabName = this.dataset.tab;
            switchTab(tabName);
        });
    });

    // Time filter buttons
    const timeFilters = document.querySelectorAll('.time-filter');
    timeFilters.forEach(filter => {
        filter.addEventListener('click', function() {
            const period = this.dataset.period;
            switchTimePeriod(period);
        });
    });

    // Search and filter functionality
    setupSearchAndFilters();
}

function initializeParticles() {
    const particlesContainer = document.getElementById('particles');
    
    for (let i = 0; i < 15; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = `${Math.random() * 100}%`;
        particle.style.top = `${Math.random() * 100}%`;
        particle.style.animationDelay = `${Math.random() * 3}s`;
        particle.style.animationDuration = `${2 + Math.random() * 2}s`;
        particlesContainer.appendChild(particle);
    }
}

function switchTab(tabName) {
    // Update navigation
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(tabName).classList.add('active');

    currentTab = tabName;

    // Initialize charts if switching to analytics
    if (tabName === 'analytics') {
        setTimeout(initializeCharts, 100);
    }
}

function switchTimePeriod(period) {
    // Update filter buttons
    document.querySelectorAll('.time-filter').forEach(filter => {
        filter.classList.remove('active');
    });
    document.querySelector(`[data-period="${period}"]`).classList.add('active');

    currentPeriod = period;
    updateStats();
    
    // Update charts if on analytics tab
    if (currentTab === 'analytics') {
        updateCharts();
    }
}

function updateStats() {
    const stats = {
        '7d': { scans: 847, successRate: '97.3%', avgDuration: '2.4s', failures: 23 },
        '30d': { scans: 3247, successRate: '96.8%', avgDuration: '2.6s', failures: 104 },
        '90d': { scans: 9834, successRate: '97.1%', avgDuration: '2.5s', failures: 285 },
        'all': { scans: 15672, successRate: '96.9%', avgDuration: '2.7s', failures: 486 }
    };

    const currentStats = stats[currentPeriod];
    
    document.getElementById('totalScans').textContent = currentStats.scans.toLocaleString();
    document.getElementById('successRate').textContent = currentStats.successRate;
    document.getElementById('avgDuration').textContent = currentStats.avgDuration;
    document.getElementById('failures').textContent = currentStats.failures;
}

function initializeCharts() {
    // Initialize scans over time chart
    const scansCanvas = document.getElementById('scansTimeChart');
    if (scansCanvas) {
        drawLineChart(scansCanvas, sampleData.scansOverTime[currentPeriod], 'Scans Over Time');
    }

    // Initialize tools usage chart
    const toolsCanvas = document.getElementById('toolsChart');
    if (toolsCanvas) {
        drawBarChart(toolsCanvas, sampleData.toolsUsage.data, sampleData.toolsUsage.labels);
    }

    // Initialize success rate chart
    const successCanvas = document.getElementById('successChart');
    if (successCanvas) {
        drawDonutChart(successCanvas, [sampleData.successRate.success, sampleData.successRate.failed], ['Success', 'Failed']);
    }
}

function updateCharts() {
    initializeCharts();
}

function drawLineChart(canvas, data, title) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Calculate dimensions
    const padding = 40;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;
    
    const maxValue = Math.max(...data);
    const minValue = Math.min(...data);
    const valueRange = maxValue - minValue || 1;
    
    // Draw grid lines
    ctx.strokeStyle = 'rgba(0, 255, 224, 0.1)';
    ctx.lineWidth = 1;
    
    // Horizontal grid lines
    for (let i = 0; i <= 5; i++) {
        const y = padding + (chartHeight / 5) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
    }
    
    // Vertical grid lines
    for (let i = 0; i <= data.length - 1; i++) {
        const x = padding + (chartWidth / (data.length - 1)) * i;
        ctx.beginPath();
        ctx.moveTo(x, padding);
        ctx.lineTo(x, height - padding);
        ctx.stroke();
    }
    
    // Draw line chart
    ctx.strokeStyle = '#00FFE0';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    data.forEach((value, index) => {
        const x = padding + (chartWidth / (data.length - 1)) * index;
        const y = height - padding - ((value - minValue) / valueRange) * chartHeight;
        
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    
    ctx.stroke();
    
    // Draw area under curve
    ctx.fillStyle = 'rgba(0, 255, 224, 0.1)';
    ctx.beginPath();
    
    data.forEach((value, index) => {
        const x = padding + (chartWidth / (data.length - 1)) * index;
        const y = height - padding - ((value - minValue) / valueRange) * chartHeight;
        
        if (index === 0) {
            ctx.moveTo(x, height - padding);
            ctx.lineTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    
    ctx.lineTo(width - padding, height - padding);
    ctx.closePath();
    ctx.fill();
    
    // Draw data points
    ctx.fillStyle = '#00FFE0';
    data.forEach((value, index) => {
        const x = padding + (chartWidth / (data.length - 1)) * index;
        const y = height - padding - ((value - minValue) / valueRange) * chartHeight;
        
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fill();
    });
}

function drawBarChart(canvas, data, labels) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Calculate dimensions
    const padding = 40;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;
    
    const maxValue = Math.max(...data);
    const barWidth = chartWidth / data.length * 0.8;
    const barSpacing = chartWidth / data.length * 0.2;
    
    // Colors for different tools
    const colors = ['#00FFE0', '#A12DFF', '#FF8C42', '#FF007A', '#6CFF57'];
    
    // Draw bars
    data.forEach((value, index) => {
        const barHeight = (value / maxValue) * chartHeight;
        const x = padding + index * (barWidth + barSpacing) + barSpacing / 2;
        const y = height - padding - barHeight;
        
        // Create gradient
        const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
        gradient.addColorStop(0, colors[index % colors.length]);
        gradient.addColorStop(1, colors[index % colors.length] + '40');
        
        ctx.fillStyle = gradient;
        ctx.fillRect(x, y, barWidth, barHeight);
        
        // Draw border
        ctx.strokeStyle = colors[index % colors.length];
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, barWidth, barHeight);
    });
}

function drawDonutChart(canvas, data, labels) {
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 2 - 20;
    const innerRadius = radius * 0.6;
    
    const total = data.reduce((sum, value) => sum + value, 0);
    const colors = ['#6CFF57', '#FF007A'];
    
    let currentAngle = -Math.PI / 2;
    
    data.forEach((value, index) => {
        const sliceAngle = (value / total) * 2 * Math.PI;
        
        // Draw outer arc
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, currentAngle, currentAngle + sliceAngle);
        ctx.arc(centerX, centerY, innerRadius, currentAngle + sliceAngle, currentAngle, true);
        ctx.closePath();
        
        ctx.fillStyle = colors[index];
        ctx.fill();
        
        currentAngle += sliceAngle;
    });
    
    // Draw center text
    ctx.fillStyle = '#E5F1FF';
    ctx.font = '16px Space Grotesk';
    ctx.textAlign = 'center';
    ctx.fillText(`${((data[0] / total) * 100).toFixed(1)}%`, centerX, centerY);
}

function setupSearchAndFilters() {
    const scanSearch = document.getElementById('scanSearch');
    const statusFilter = document.getElementById('statusFilter');
    const toolFilter = document.getElementById('toolFilter');

    if (scanSearch) {
        scanSearch.addEventListener('input', filterScans);
    }
    if (statusFilter) {
        statusFilter.addEventListener('change', filterScans);
    }
    if (toolFilter) {
        toolFilter.addEventListener('change', filterScans);
    }
}

function filterScans() {
    // This would normally filter the scans table based on search and filter criteria
    console.log('Filtering scans...');
}

function viewScanDetail(scanId) {
    const modal = document.getElementById('scanDetailModal');
    const title = document.getElementById('scanDetailTitle');
    const body = document.getElementById('scanDetailBody');
    
    title.textContent = `Scan Details - ${scanId}`;
    body.innerHTML = `
        <div class="scan-detail">
            <div class="detail-section">
                <h3>Scan Information</h3>
                <div class="detail-grid">
                    <div class="detail-item">
                        <label>Scan ID:</label>
                        <span>${scanId}</span>
                    </div>
                    <div class="detail-item">
                        <label>Tool:</label>
                        <span class="tool-badge subfinder">Subfinder</span>
                    </div>
                    <div class="detail-item">
                        <label>Target:</label>
                        <span>example.com</span>
                    </div>
                    <div class="detail-item">
                        <label>Status:</label>
                        <span class="status-badge completed">Completed</span>
                    </div>
                    <div class="detail-item">
                        <label>Duration:</label>
                        <span>2.1s</span>
                    </div>
                    <div class="detail-item">
                        <label>Started:</label>
                        <span>2025-01-15 14:30:25</span>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <h3>Results</h3>
                <div class="results-summary">
                    <div class="result-stat">
                        <span class="stat-value">47</span>
                        <span class="stat-label">Subdomains Found</span>
                    </div>
                    <div class="result-stat">
                        <span class="stat-value">12</span>
                        <span class="stat-label">New Discoveries</span>
                    </div>
                    <div class="result-stat">
                        <span class="stat-value">2.1s</span>
                        <span class="stat-label">Execution Time</span>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <h3>Actions</h3>
                <div class="detail-actions">
                    <button class="cyber-button">Download Results</button>
                    <button class="glass-button">Generate Report</button>
                    <button class="glass-button">Re-run Scan</button>
                </div>
            </div>
        </div>
    `;
    
    modal.classList.add('active');
}

function closeScanDetail() {
    const modal = document.getElementById('scanDetailModal');
    modal.classList.remove('active');
}

function editProfile() {
    const inputs = document.querySelectorAll('.profile-form .form-input');
    const button = document.querySelector('.profile-card .glass-button');
    
    if (button.textContent === 'Edit Profile') {
        inputs.forEach(input => {
            if (input.type !== 'email') { // Keep email readonly for security
                input.removeAttribute('readonly');
                input.style.background = 'transparent';
                input.style.cursor = 'text';
            }
        });
        button.textContent = 'Save Changes';
        button.classList.remove('glass-button');
        button.classList.add('cyber-button');
    } else {
        inputs.forEach(input => {
            input.setAttribute('readonly', true);
            input.style.background = 'rgba(0, 255, 224, 0.05)';
            input.style.cursor = 'not-allowed';
        });
        button.textContent = 'Edit Profile';
        button.classList.remove('cyber-button');
        button.classList.add('glass-button');
    }
}

function changePassword() {
    alert('Password change functionality would be implemented here');
}

function manage2FA() {
    alert('2FA management functionality would be implemented here');
}

function manageSessions() {
    alert('Session management functionality would be implemented here');
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = 'index.html';
    }
}

// Add CSS for scan detail modal
const style = document.createElement('style');
style.textContent = `
    .scan-detail {
        display: flex;
        flex-direction: column;
        gap: 24px;
    }
    
    .detail-section h3 {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 18px;
        font-weight: 600;
        color: var(--text-main);
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--glass-border);
    }
    
    .detail-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
    }
    
    .detail-item {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    
    .detail-item label {
        font-size: 12px;
        color: var(--text-mute);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .detail-item span {
        font-size: 14px;
        color: var(--text-main);
        font-weight: 500;
    }
    
    .results-summary {
        display: flex;
        gap: 32px;
        justify-content: center;
        padding: 24px;
        background: rgba(0, 255, 224, 0.05);
        border-radius: 8px;
        border: 1px solid var(--glass-border);
    }
    
    .result-stat {
        text-align: center;
    }
    
    .result-stat .stat-value {
        display: block;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 24px;
        font-weight: 700;
        color: var(--cyber-cyan);
        margin-bottom: 4px;
    }
    
    .result-stat .stat-label {
        font-size: 12px;
        color: var(--text-mute);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .detail-actions {
        display: flex;
        gap: 16px;
        justify-content: center;
    }
    
    @media (max-width: 768px) {
        .detail-grid {
            grid-template-columns: 1fr;
        }
        
        .results-summary {
            flex-direction: column;
            gap: 16px;
        }
        
        .detail-actions {
            flex-direction: column;
        }
    }
`;
document.head.appendChild(style);