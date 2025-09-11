// Global state
let currentSession = 1;
let sessions = {
    1: { name: 'Session 1', tools: [], connections: [], tabs: 1 }
};
let workflowBoxes = [];
let draggedTool = null;
let selectedTool = null;
let boxCounter = 0;
let isSpacePressed = false;
let isPanning = false;
let panStart = { x: 0, y: 0, scrollLeft: 0, scrollTop: 0 };
// Zoom / pan state
let zoom = 1;
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 2.5;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    initializeParticles();
    initializeWorkflowBoxes();
      // Force horizontal flow for nodes (row, no wrap)
  const wrap = document.getElementById('workflowBoxes');
  if (wrap) {
    wrap.style.display = 'flex';
    wrap.style.flexDirection = 'row';
    wrap.style.flexWrap = 'nowrap';
  }
    initializePanZoomHandlers();
    bindConnectorUpdates();

}
function slugify(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function normalizeApiData(payload) {
  if (!payload || !payload.categories) return [];

  const c = payload.categories;

  // Case A: already an array of categories
  if (Array.isArray(c)) {
    return c.map(cat => ({
      id: cat.id,
      slug: cat.slug || slugify(cat.name),
      name: cat.name || "",
      tools: Array.isArray(cat.tools) ? cat.tools.map(t => ({
        id: t.id,
        slug: t.slug,
        name: t.name,
        description: t.description || (t.meta_info && t.meta_info.description) || "",
        estimated_time: t.estimated_time || (t.meta_info && t.meta_info.estimated_time) || "",
        type: t.type || (t.meta_info && t.meta_info.type) || ""
      })) : []
    }));
  }

  // Case B: object map { "Category Name": [tools...] }
  if (typeof c === "object") {
    return Object.entries(c).map(([name, tools]) => ({
      slug: slugify(name),
      name,
      tools: (tools || []).map(t => ({
        slug: t.slug,
        name: t.name,
        description: t.desc || t.description || "",
        estimated_time: t.time || t.estimated_time || "",
        type: t.type || ""
      }))
    }));
  }

  return [];
}

function setupEventListeners() {
    // Tool search
    document.getElementById('toolSearch').addEventListener('input', filterTools);
    
    // Canvas events
    const canvas = document.getElementById('workflowCanvas');
    setupDragAndDrop();
    
    // Click outside to close dropdowns
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.session-dropdown')) {
            closeSessionDropdown();
        }
    });
}

function initializeWorkflowBoxes() {
    // Initialize with one empty box
    workflowBoxes = [];
    boxCounter = 0;
    updateCanvasStats();
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

function setupDragAndDrop() {
    const toolItems = document.querySelectorAll('.tool-item');
    
    toolItems.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragend', handleDragEnd);
    });
}

function toggleCategory(categoryName) {
    const categorySection = document.querySelector(`#${categoryName}-tools`).parentElement;
    const categoryTools = document.getElementById(`${categoryName}-tools`);
    const arrow = categorySection.querySelector('.category-arrow');
    
    if (categoryTools.classList.contains('active')) {
        categoryTools.classList.remove('active');
        categorySection.classList.add('collapsed');
    } else {
        categoryTools.classList.add('active');
        categorySection.classList.remove('collapsed');
    }
}

function handleDragStart(e) {
    draggedTool = {
        name: e.target.querySelector('.tool-name').textContent,
        description: e.target.querySelector('.tool-desc').textContent,
        time: e.target.querySelector('.tool-time').textContent,
        type: e.target.querySelector('.tool-type').textContent,
        tool: e.target.dataset.tool,
        category: e.target.dataset.category
    };
    
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'copy';
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    draggedTool = null;
}

function initializePanZoomHandlers() {
  const canvas = document.getElementById('workflowCanvas');
  const content = document.getElementById('canvasContent');
  if (!canvas || !content) return;

  content.style.transformOrigin = '0 0';

  // ---- PANNING (drag on empty canvas only) ----
  let isPanning = false;
  let panStart = { x: 0, y: 0, scrollLeft: 0, scrollTop: 0 };

  canvas.addEventListener('mousedown', (e) => {
    // Only start pan if mouse is NOT down on a workflow box
    if (e.button !== 0) return;
    if (e.target.closest('.workflow-box')) return;

    isPanning = true;
    panStart = {
      x: e.clientX,
      y: e.clientY,
      scrollLeft: canvas.scrollLeft,
      scrollTop: canvas.scrollTop
    };
    canvas.classList.add('panning');
  });

  document.addEventListener('mousemove', (e) => {
    if (!isPanning) return;
    const dx = e.clientX - panStart.x;
    const dy = e.clientY - panStart.y;
    canvas.scrollLeft = panStart.scrollLeft - dx;
    canvas.scrollTop  = panStart.scrollTop  - dy;
    // keep connectors aligned while panning
    updateConnectionsRAF();
  }, { passive: true });

  document.addEventListener('mouseup', () => {
    isPanning = false;
    canvas.classList.remove('panning');
  });

  // ---- ZOOMING (mouse wheel anywhere on canvas) ----
  canvas.addEventListener('wheel', (e) => {
    // We take over the wheel for zoom (no Ctrl needed)
    e.preventDefault();

    // Smooth exponential zoom factor
    const factor = Math.exp(-e.deltaY * 0.0015);
    const target = clampZoom(zoom * factor);
    setZoomAtPoint(target, e.clientX, e.clientY);
  }, { passive: false });

  // Optional: double-click to reset zoom
  canvas.addEventListener('dblclick', (e) => {
    setZoomAtPoint(1, e.clientX, e.clientY);
  });
}

function clampZoom(z) {
  return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));
}

function setZoomAtPoint(newZoom, clientX, clientY) {
  const canvas = document.getElementById('workflowCanvas');
  const content = document.getElementById('canvasContent');
  if (!canvas || !content) return;

  const rect = canvas.getBoundingClientRect();

  // Convert the mouse position to content coords in current zoom
  const px = (canvas.scrollLeft + (clientX - rect.left)) / zoom;
  const py = (canvas.scrollTop  + (clientY - rect.top )) / zoom;

  zoom = clampZoom(newZoom);
  content.style.transform = `scale(${zoom})`;

  // Keep the same content point under the cursor after zoom
  canvas.scrollLeft = px * zoom - (clientX - rect.left);
  canvas.scrollTop  = py * zoom - (clientY - rect.top);

  updateConnectionsRAF();
}


function endPan(canvas) {
  if (!isPanning) {
    canvas.classList.remove('pannable');
    return;
  }
  isPanning = false;
  canvas.classList.remove('panning');
  canvas.classList.remove('pannable');
}

// Setup drag and drop for workflow boxes
function setupWorkflowBoxDragDrop() {
    const boxes = document.querySelectorAll('.workflow-box');
    
    boxes.forEach(box => {
        box.addEventListener('dragover', handleBoxDragOver);
        box.addEventListener('drop', handleBoxDrop);
        box.addEventListener('dragleave', handleBoxDragLeave);
    });
}

function handleBoxDragOver(e) {
    e.preventDefault();
    if (e.currentTarget.classList.contains('empty')) {
        e.dataTransfer.dropEffect = 'copy';
        e.currentTarget.classList.add('drag-over');
    }
}

function handleBoxDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

function handleBoxDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    
    if (draggedTool && e.currentTarget.classList.contains('empty')) {
        const boxIndex = parseInt(e.currentTarget.dataset.boxIndex);
        addToolToBox(draggedTool, boxIndex);
    }
}

function addToolToBox(tool, boxIndex) {
  const box = document.getElementById(`box-${boxIndex}`);
  if (!box || !box.classList.contains('empty')) return;

  // Create tool data
  const toolData = {
    ...tool,
    boxIndex,
    configured: false,
    status: 'Ready',
    config: { domain: '', silent: false }
  };
  workflowBoxes[boxIndex] = toolData;

  // compute step number = count of filled boxes
  const stepNumber = workflowBoxes.filter(Boolean).length;

  // Update box appearance
  box.classList.remove('empty');
  box.classList.add('filled');

  // Update box content (adds step badge + status pill)
  box.innerHTML = `
    <div class="step-badge">${stepNumber}</div>
    <div class="status-pill">${toolData.status}</div>
    <div class="box-content">
      <div class="box-tool">
        <div class="box-tool-header">
          <div class="box-tool-info">
            <div class="box-tool-icon">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polygon points="13,2 3,14 12,14 11,22 21,10 12,10 13,2"></polygon>
              </svg>
            </div>
            <div>
              <div class="box-tool-name">${tool.name}</div>
              <div class="box-tool-time">${tool.time}</div>
            </div>
          </div>
          <div class="box-tool-actions">
            <button class="box-action-btn" onclick="configureBox(${boxIndex})" title="Configure">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1 1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </svg>
            </button>
            <button class="box-action-btn delete" onclick="removeToolFromBox(${boxIndex})" title="Remove">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3,6 5,6 21,6"></polyline>
                <path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2V6"></path>
              </svg>
            </button>
          </div>
        </div>
        <div class="box-tool-desc">${tool.description}</div>
      </div>
    </div>
  `;

  // Auto-connect previous filled node → this node
  const prevIndex = findLastFilledIndex(boxIndex - 1);
  if (prevIndex !== -1) {
    sessions[currentSession].connections.push({ from: prevIndex, to: boxIndex });
  }

  addNextEmptyBox();
  updateCanvasStats();
  addToTerminal(`Added ${tool.name} to workflow`, 'success');
  updateConnections();  // draw/redraw lines
}

function findLastFilledIndex(start) {
  for (let i = start; i >= 0; i--) {
    if (workflowBoxes[i]) return i;
  }
  return -1;
}

function addNextEmptyBox() {
    const workflowBoxesContainer = document.getElementById('workflowBoxes');
    const nextIndex = workflowBoxes.length;
    
    const newBox = document.createElement('div');
    newBox.className = 'workflow-box empty';
    newBox.id = `box-${nextIndex}`;
    newBox.dataset.boxIndex = nextIndex;
    
    newBox.innerHTML = `
        <div class="box-content">
            <div class="box-placeholder">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="12" y1="5" x2="12" y2="19"></line>
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
                <span>Drop tool here</span>
            </div>
        </div>
    `;
    
    workflowBoxesContainer.appendChild(newBox);
    
    // Setup drag and drop for the new box
    newBox.addEventListener('dragover', handleBoxDragOver);
    newBox.addEventListener('drop', handleBoxDrop);
    newBox.addEventListener('dragleave', handleBoxDragLeave);
}

function removeToolFromBox(boxIndex) {
  const box = document.getElementById(`box-${boxIndex}`);
  if (!box) return;

  delete workflowBoxes[boxIndex];

  // reset box…
  box.classList.remove('filled');
  box.classList.add('empty');
  box.innerHTML = `
    <div class="box-content">
      <div class="box-placeholder">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
        <span>Drop tool here</span>
      </div>
    </div>
  `;

  // prune connections and tidy empties
  sessions[currentSession].connections = sessions[currentSession].connections
    .filter(c => c.from !== boxIndex && c.to !== boxIndex);

  removeEmptyBoxesAfter(boxIndex);
  updateCanvasStats();
  addToTerminal(`Removed tool from workflow`, 'info');
  updateConnections();
}

let _rafConn = null;
let _moConn = null;
let _roConn = null;

function bindConnectorUpdates() {
  const canvas = document.getElementById('workflowCanvas');
  const boxesWrap = document.getElementById('workflowBoxes');
  if (!canvas || !boxesWrap) return;

  // redraw on resize / scroll
  window.addEventListener('resize', updateConnectionsRAF);
  canvas.addEventListener('scroll', updateConnectionsRAF, { passive: true });

  // observe DOM/layout changes in boxes
  _moConn?.disconnect?.();
  _roConn?.disconnect?.();

  _moConn = new MutationObserver(updateConnectionsRAF);
  _moConn.observe(boxesWrap, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['class', 'style']
  });

  _roConn = new ResizeObserver(updateConnectionsRAF);
  _roConn.observe(boxesWrap);

  // first draw
  updateConnectionsRAF();
}

function updateConnectionsRAF() {
  if (_rafConn) return;
  _rafConn = requestAnimationFrame(() => {
    _rafConn = null;
    updateConnections();
  });
}

function updateConnections() {
  const canvas = document.getElementById('workflowCanvas');
  const svg = document.getElementById('connectionLayer');
  if (!canvas || !svg) return;

  // ensure structure
  const w = Math.max(canvas.scrollWidth, canvas.clientWidth);
  const h = Math.max(canvas.scrollHeight, canvas.clientHeight);
  svg.setAttribute('width', w);
  svg.setAttribute('height', h);
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.innerHTML = '';

  // arrowhead marker
  const defs = document.createElementNS('http://www.w3.org/2000/svg','defs');
  const marker = document.createElementNS('http://www.w3.org/2000/svg','marker');
  marker.setAttribute('id','arrow');
  marker.setAttribute('viewBox','0 0 10 10');
  marker.setAttribute('refX','8'); marker.setAttribute('refY','5');
  marker.setAttribute('markerWidth','6'); marker.setAttribute('markerHeight','6');
  marker.setAttribute('orient','auto-start-reverse');
  const tip = document.createElementNS('http://www.w3.org/2000/svg','path');
  tip.setAttribute('d','M 0 0 L 10 5 L 0 10 z');
  tip.setAttribute('fill','currentColor');
  marker.appendChild(tip);
  defs.appendChild(marker);
  svg.appendChild(defs);

  const conns = (sessions[currentSession].connections || []);
  if (!conns.length) return;

  conns.forEach(({ from, to }) => {
    const a = document.getElementById(`box-${from}`);
    const b = document.getElementById(`box-${to}`);
    if (!a || !b || a.classList.contains('empty') || b.classList.contains('empty')) return;

    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('vector-effect','non-scaling-stroke');
    path.setAttribute('marker-end','url(#arrow)');

    const d = buildOrthogonalPath(a, b, canvas);
    path.setAttribute('d', d);

    svg.appendChild(path);
  });
}

function rectInCanvas(el, canvas) {
  const r = el.getBoundingClientRect();
  const c = canvas.getBoundingClientRect();

  // Convert from screen(=scaled) coords to unscaled canvas coords
  return {
    left:  ((r.left - c.left) + canvas.scrollLeft) / zoom,
    top:   ((r.top  - c.top ) + canvas.scrollTop ) / zoom,
    width:  r.width  / zoom,
    height: r.height / zoom
  };
}

function centerPoint(rect) {
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
}

function anchorPoint(rect, side, pad = 10) {
  switch (side) {
    case 'E': return { x: rect.left + rect.width - pad, y: rect.top + rect.height / 2 };
    case 'W': return { x: rect.left + pad,             y: rect.top + rect.height / 2 };
    case 'S': return { x: rect.left + rect.width / 2,  y: rect.top + rect.height - pad };
    case 'N': return { x: rect.left + rect.width / 2,  y: rect.top + pad };
    default:  return centerPoint(rect);
  }
}

function classifyRelation(aRect, bRect) {
  const aRight = aRect.left + aRect.width;
  const bRight = bRect.left + bRect.width;

  const overlapX = Math.min(aRight, bRight) - Math.max(aRect.left, bRect.left);
  const minW = Math.min(aRect.width, bRect.width);

  const sameColumn = overlapX > (minW * 0.30); // ≥30% horizontal overlap → treat as same column
  const leftToRight = bRect.left > aRect.left;

  return { sameColumn, leftToRight };
}

function gutterX(aRect, bRect, leftToRight) {
  // midpoint of the horizontal gap between the two boxes (the "lane" / gutter)
  const leftEdge  = leftToRight ? (aRect.left + aRect.width) : (bRect.left + bRect.width);
  const rightEdge = leftToRight ? bRect.left : aRect.left;
  return leftEdge + (rightEdge - leftEdge) / 2;
}

function chooseSides(aRect, bRect) {
  const { sameColumn, leftToRight } = classifyRelation(aRect, bRect);

  if (sameColumn) {
    // vertical chain inside the same column
    const bBelow = (bRect.top + bRect.height / 2) >= (aRect.top + aRect.height / 2);
    return { from: bBelow ? 'S' : 'N', to: bBelow ? 'N' : 'S', mode: 'vhv', leftToRight };
  }

  // cross-column → always side-to-side via the gutter (no “fly over the stack”)
  return { from: leftToRight ? 'E' : 'W', to: leftToRight ? 'W' : 'E', mode: 'hvh', leftToRight };
}

function buildOrthogonalPath(aEl, bEl, canvas) {
  const aRect = rectInCanvas(aEl, canvas);
  const bRect = rectInCanvas(bEl, canvas);

  const pick = chooseSides(aRect, bRect);
  const P1 = anchorPoint(aRect, pick.from, 10);
  const P4 = anchorPoint(bRect, pick.to, 10);

  let d;

  if (pick.mode === 'hvh') {
    // side → gutter → side (always runs through the empty lane)
    const mx = gutterX(aRect, bRect, pick.leftToRight);
    d = `M ${P1.x} ${P1.y}
         L ${mx} ${P1.y}
         L ${mx} ${P4.y}
         L ${P4.x} ${P4.y}`;
  } else {
    // top/bottom → midRow → top/bottom (stays between rows)
    const aBottom = aRect.top + aRect.height;
    const bTop    = bRect.top;
    const aTop    = aRect.top;
    const bBottom = bRect.top + bRect.height;
    const bBelow  = (P4.y >= P1.y);

    // mid y placed in the corridor between the two boxes
    const my = bBelow
      ? (aBottom + bTop) / 2
      : (bBottom + aTop) / 2;

    d = `M ${P1.x} ${P1.y}
         L ${P1.x} ${my}
         L ${P4.x} ${my}
         L ${P4.x} ${P4.y}`;
  }

  return d.replace(/\s+/g, ' ');
}

function centerInCanvasCoords(el, canvas) {
  const r = el.getBoundingClientRect();
  const c = canvas.getBoundingClientRect();
  return {
    x: (r.left - c.left) + canvas.scrollLeft + r.width / 2,
    y: (r.top  - c.top ) + canvas.scrollTop  + r.height / 2
  };
}

function cubicPath(x1, y1, x2, y2, isHorizontal) {
  if (isHorizontal) {
    const dx = Math.max(40, Math.abs(x2 - x1) / 2);
    const c1x = x1 + (x2 >= x1 ? dx : -dx), c1y = y1;
    const c2x = x2 - (x2 >= x1 ? dx : -dx), c2y = y2;
    return `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`;
  } else {
    const dy = Math.max(40, Math.abs(y2 - y1) / 2);
    const c1x = x1, c1y = y1 + (y2 >= y1 ? dy : -dy);
    const c2x = x2, c2y = y2 - (y2 >= y1 ? dy : -dy);
    return `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`;
  }
}

function removeEmptyBoxesAfter(startIndex) {
    const workflowBoxesContainer = document.getElementById('workflowBoxes');
    const boxes = workflowBoxesContainer.querySelectorAll('.workflow-box');
    
    // Remove empty boxes after the removed tool
    for (let i = boxes.length - 1; i > startIndex; i--) {
        const box = boxes[i];
        if (box.classList.contains('empty') && !workflowBoxes[i]) {
            box.remove();
        } else {
            break;
        }
    }
    
    // Ensure we always have at least one empty box at the end
    const remainingBoxes = workflowBoxesContainer.querySelectorAll('.workflow-box');
    const lastBox = remainingBoxes[remainingBoxes.length - 1];
    
    if (!lastBox || !lastBox.classList.contains('empty')) {
        addNextEmptyBox();
    }
}

function configureBox(boxIndex) {
    const tool = workflowBoxes[boxIndex];
    if (!tool) return;
    
    selectedTool = tool;
    
    // Open configuration modal
    document.getElementById('configToolName').textContent = `${tool.name} Configuration`;
    document.getElementById('configDomain').value = tool.config.domain || '';
    document.getElementById('configSilent').checked = tool.config.silent || false;
    
    document.getElementById('toolConfigModal').classList.add('active');
}

function closeToolConfig() {
    document.getElementById('toolConfigModal').classList.remove('active');
    selectedTool = null;
}

function saveToolConfig() {
    if (!selectedTool) return;
    
    selectedTool.config.domain = document.getElementById('configDomain').value;
    selectedTool.config.silent = document.getElementById('configSilent').checked;
    selectedTool.configured = true;
    
    // Update box appearance to show it's configured
    const box = document.getElementById(`box-${selectedTool.boxIndex}`);
    if (selectedTool.config.domain) {
        box.style.borderColor = 'var(--signal-green)';
        box.style.boxShadow = '0 0 12px rgba(108, 255, 87, 0.3)';
    }
    
    closeToolConfig();
    addToTerminal(`Configured ${selectedTool.name} with domain: ${selectedTool.config.domain}`, 'success');
}

function filterTools() {
    const searchTerm = document.getElementById('toolSearch').value.toLowerCase();
    const toolItems = document.querySelectorAll('.tool-item');
    
    toolItems.forEach(item => {
        const toolName = item.querySelector('.tool-name').textContent.toLowerCase();
        const toolDesc = item.querySelector('.tool-desc').textContent.toLowerCase();
        
        if (toolName.includes(searchTerm) || toolDesc.includes(searchTerm)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function showToast(message) {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    
    toastMessage.textContent = `${message} button pressed`;
    toast.classList.add('show');
    
    setTimeout(() => toast.classList.remove('show'), 3000);
}

function toggleSessionDropdown() {
    const dropdown = document.getElementById('sessionDropdown');
    dropdown.classList.toggle('active');
}

function closeSessionDropdown() {
    const dropdown = document.getElementById('sessionDropdown');
    dropdown.classList.remove('active');
}

function createNewSession() {
    const sessionCount = Object.keys(sessions).length + 1;
    const newSessionId = sessionCount;
    
    sessions[newSessionId] = {
        name: `Session ${newSessionId}`,
        tools: [],
        connections: [],
        tabs: 1
    };
    
    // Add to sessions list
    const sessionsList = document.getElementById('sessionsList');
    const sessionItem = document.createElement('div');
    sessionItem.className = 'session-item';
    sessionItem.dataset.session = newSessionId;
    sessionItem.innerHTML = `
        <div class="session-info">
            <span class="session-name">Session ${newSessionId}</span>
            <span class="session-status">Active</span>
        </div>
        <div class="session-meta">
            <span>1 tabs • 0 tools</span>
        </div>
        <div class="session-actions">
            <button class="session-action-btn" onclick="editSession(${newSessionId})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
            </button>
            <button class="session-action-btn" onclick="deleteSession(${newSessionId})">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3,6 5,6 21,6"></polyline>
                    <path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2V6"></path>
                </svg>
            </button>
        </div>
    `;
    
    sessionsList.appendChild(sessionItem);
    closeSessionDropdown();
}

function editSession(sessionId) {
    const newName = prompt('Enter new session name:', sessions[sessionId].name);
    if (newName && newName.trim()) {
        sessions[sessionId].name = newName.trim();
        
        // Update UI
        const sessionItem = document.querySelector(`[data-session="${sessionId}"]`);
        if (sessionItem) {
            sessionItem.querySelector('.session-name').textContent = newName.trim();
        }
        
        if (sessionId == currentSession) {
            document.getElementById('currentSessionName').textContent = newName.trim();
        }
    }
    closeSessionDropdown();
}

function deleteSession(sessionId) {
    if (Object.keys(sessions).length <= 1) {
        alert('Cannot delete the last session');
        return;
    }
    
    if (confirm('Are you sure you want to delete this session?')) {
        delete sessions[sessionId];
        
        // Remove from UI
        const sessionItem = document.querySelector(`[data-session="${sessionId}"]`);
        if (sessionItem) {
            sessionItem.remove();
        }
        
        // Switch to another session if current was deleted
        if (sessionId == currentSession) {
            const remainingSessions = Object.keys(sessions);
            currentSession = remainingSessions[0];
            document.getElementById('currentSessionName').textContent = sessions[currentSession].name;
            loadSession(currentSession);
        }
    }
    closeSessionDropdown();
}

function updateCanvasStats() {
    const toolCount = Object.keys(workflowBoxes).length;
    document.getElementById('toolCount').textContent = `${toolCount} tools`;
}

function addToTerminal(message, type = 'info') {
    const terminalOutput = document.getElementById('terminalOutput');
    const timestamp = new Date().toISOString().slice(11, 19);
    
    const line = document.createElement('div');
    line.className = 'terminal-line';
    
    let promptClass = 'terminal-prompt';
    let textClass = 'terminal-text';
    
    switch (type) {
        case 'command':
            textClass = 'terminal-command';
            break;
        case 'success':
            textClass = 'terminal-output-text';
            break;
        case 'error':
            textClass = 'terminal-error';
            break;
        case 'warning':
            textClass = 'terminal-text';
            break;
    }
    
    line.innerHTML = `
        <span class="${promptClass}">[${timestamp}] root@pentest-suite:~$ </span>
        <span class="${textClass}">${message}</span>
    `;
    
    terminalOutput.appendChild(line);
    
    // Keep only last 20 lines
    while (terminalOutput.children.length > 20) {
        terminalOutput.removeChild(terminalOutput.firstChild);
    }
    
    // Scroll to bottom
    terminalOutput.scrollTop = terminalOutput.scrollHeight;
}

// Add CSS for loading spinner
const style = document.createElement('style');
style.textContent = `
    .loading-spinner {
        width: 16px;
        height: 16px;
        border: 2px solid transparent;
        border-top: 2px solid currentColor;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// Initialize with default open categories
document.addEventListener('DOMContentLoaded', function() {
    // Setup workflow boxes drag and drop
    setupWorkflowBoxDragDrop();
    
    // Open reconnaissance category by default
    const reconTools = document.getElementById('reconnaissance-tools');
    if (reconTools) {
        reconTools.classList.add('active');
    }
});



// ------------------------------
// Dynamic Tool Library rendering
// ------------------------------
(function () {
  const apiRootEl = document.getElementById("toolCategories");
const apiUrl =
  (apiRootEl && apiRootEl.dataset && apiRootEl.dataset.api) ||
  (window.TOOLS_API_URL || "/tools/api/tools");

  const categoriesRoot = document.getElementById("toolCategories");
  const searchInput = document.getElementById("toolSearch");
  const toolCountEl = document.getElementById("toolCount"); // optional (if present)

  if (!apiUrl || !categoriesRoot) return;

  // Small helpers
  const slugify = (s) =>
    (s || "")
      .toString()
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)+/g, "");

  const iconCircle = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10"></circle>
      <circle cx="12" cy="12" r="6"></circle>
      <circle cx="12" cy="12" r="2"></circle>
    </svg>`;

  const iconTag = `
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="13,2 3,14 12,14 11,22 21,10 12,10 13,2"></polygon>
    </svg>`;

  function buildToolItem(tool) {
    const item = document.createElement("div");
    item.className = "tool-item";
    item.setAttribute("draggable", "true");
    item.dataset.tool = tool.slug || "";
    item.dataset.category = (tool.category_slug || "");
    // If your canvas code expects other data attributes, add them here.

    // choose a generic icon by type
    const icon = (tool.type || "").toUpperCase().includes("SUB") ? iconCircle : iconTag;

    const time = tool.estimated_time || tool.meta_info?.estimated_time || "";
    const type = tool.type || tool.meta_info?.type || "";

    item.innerHTML = `
      <div class="tool-icon">${icon}</div>
      <div class="tool-info">
        <span class="tool-name">${tool.name || tool.slug}</span>
        <span class="tool-desc">${tool.description || tool.meta_info?.description || ""}</span>
      </div>
      <div class="tool-meta">
        ${time ? `<span class="tool-time">${time}</span>` : ""}
        ${type ? `<span class="tool-type">${type}</span>` : ""}
      </div>
    `;

    // Optional: wire up any drag handlers your canvas expects
    try {
      // If you already have helpers like initDragForToolItem, call them here:
      // initDragForToolItem(item);
      item.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/plain", JSON.stringify({
          slug: tool.slug,
          name: tool.name,
          type: type
        }));
      });
    } catch (_) {}

    return item;
  }

  function buildCategorySection(category) {
    const catSlug = slugify(category.slug || category.name);
    const wrapper = document.createElement("div");
    wrapper.className = "category-section";

    const count = category.tools?.length || 0;

    wrapper.innerHTML = `
      <div class="category-header" data-target="${catSlug}">
        <div class="category-info">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
          </svg>
          <span>${category.name}</span>
        </div>
        <div class="category-count">${count} ${count === 1 ? "tool" : "tools"}</div>
        <svg class="category-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="6,9 12,15 18,9"></polyline>
        </svg>
      </div>
      <div class="category-tools" id="${catSlug}-tools"></div>
    `;

    // Toggle behavior
    const header = wrapper.querySelector(".category-header");
    const list = wrapper.querySelector(".category-tools");
    header.addEventListener("click", () => {
      list.classList.toggle("active");
    });

    // Tools
    if (Array.isArray(category.tools)) {
      category.tools.forEach((t) => {
        const item = buildToolItem(t);
        list.appendChild(item);
      });
    }

    return wrapper;
  }

function renderLibrary(payload) {
  categoriesRoot.innerHTML = "";

  const categories = payload?.categories || [];
  let totalTools = 0;

  if (!categories.length) {
    categoriesRoot.innerHTML = `
      <div class="glass" style="padding:12px; border:1px dashed rgba(255,255,255,.15)">
        No tools are configured yet. Add a Tool Category and link tools in the admin, then refresh.
      </div>`;
    if (toolCountEl) toolCountEl.textContent = "0 tools";
    return;
  }

  categories.forEach((cat) => {
    totalTools += (cat.tools?.length || 0);
    const section = buildCategorySection(cat);
    categoriesRoot.appendChild(section);
  });

  if (toolCountEl) toolCountEl.textContent = `${totalTools} ${totalTools === 1 ? "tool" : "tools"}`;
}


  function attachSearch() {
    if (!searchInput) return;
    searchInput.addEventListener("input", () => {
      const q = searchInput.value.trim().toLowerCase();
      const items = categoriesRoot.querySelectorAll(".tool-item");
      items.forEach((el) => {
        const name = (el.querySelector(".tool-name")?.textContent || "").toLowerCase();
        const desc = (el.querySelector(".tool-desc")?.textContent || "").toLowerCase();
        const match = !q || name.includes(q) || desc.includes(q);
        el.style.display = match ? "" : "none";
      });
    });
  }

async function loadTools() {
  try {
    const res = await fetch(apiUrl, { credentials: "same-origin" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // 🔧 convert your API (object) → array of categories the renderer expects
    const categories = normalizeApiData(data);

    // keep renderLibrary’s current signature: { categories: [...] }
    renderLibrary({ categories });

    setupDragAndDrop();   // bind drag handlers on the new .tool-item nodes
    attachSearch();
    openDefaultCategory(categories);   // make Recon (or first) open by default
  } catch (err) {
    console.error("Failed to load tools:", err);
    categoriesRoot.innerHTML = `
      <div class="glass" style="padding:12px; border:1px dashed rgba(255,255,255,.15);">
        Could not load tools. Please refresh.
      </div>`;
  }
}
function openDefaultCategory(categories) {
  if (!Array.isArray(categories) || categories.length === 0) return;
  // Prefer Recon if present, fall back to the first category
  const recon = categories.find(c => (c.slug || slugify(c.name)) === "reconnaissance");
  const target = recon || categories[0];
  const id = `${(target.slug || slugify(target.name))}-tools`;
  const el = document.getElementById(id);
  if (el) el.classList.add("active");
}

  // kick off
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadTools);
  } else {
    loadTools();
  }
})();
