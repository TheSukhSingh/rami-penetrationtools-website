/* tools/static/js/tools.js */
/* eslint-disable no-unused-vars */
(() => {
  'use strict';

  // ---------- DOM ----------
  const el = {
    canvas: document.getElementById('canvas'),
    content: document.getElementById('canvasContent'),
    boxes: document.getElementById('workflowBoxes'),
    svg: document.getElementById('connectionLayer'),
    zoomPct: document.getElementById('zoomPct'),
    term: document.getElementById('terminalOutput'),
    library: document.getElementById('toolCategories'),
    chainBadge: document.getElementById('chainBadge'),
    chainReason: document.getElementById('chainReason'),
    toast: document.getElementById('toast'),
  };

  window.__hackerTools__ = { renderVersion: Date.now() };

  // ---------- State ----------
  const state = {
    camera: { x: 0, y: 0, scale: 1, min: 0.25, max: 2 },
    nodes: new Map(),   // id -> {id, x, y, width, height, el, handles, name, toolKey, config}
    edges: new Map(),   // id -> {id, fromId, toId, pathEl}
    needsRender: true,
    draggingNode: null,
    panning: null,
    connecting: null,   // { fromId, rubber?: SVGPathElement }
    idCounter: 1,
    selectedEdgeId: null,
    currentWorkflowId: null,
    dirty: false,
    autosaveTimer: null,
    catalogBySlug: new Map(), // slug -> {slug,name,desc,type,time}

    // runs / events
    currentRunId: null,
    eventSource: null,

    // selection
    selectedNodeId: null,
  };

  const genId = (prefix='n') => `${prefix}${state.idCounter++}`;

  function setStatus(msg) {
    const s = document.getElementById('wfStatus');
    if (s) s.textContent = msg || '';
  }

  function getCookie(name) {
    return document.cookie.split('; ').find(r => r.startsWith(name + '='))?.split('=')[1] || '';
  }
  function getCsrf() {
    try { return decodeURIComponent(getCookie('csrf_access_token') || ''); } catch { return ''; }
  }

  function markDirty() {
    state.dirty = true;
    setStatus('Unsaved changes…');
    if (state.autosaveTimer) clearTimeout(state.autosaveTimer);
    if (state.currentWorkflowId) {
      state.autosaveTimer = setTimeout(() => saveWorkflow(false), 1000);
    }
  }

  // ---------- Math: world/screen transforms ----------
  function screenToWorld(sx, sy) {
    const { x, y, scale } = state.camera;
    return { x: (sx / scale) + x, y: (sy / scale) + y };
  }
  function worldToScreen(wx, wy) {
    const { x, y, scale } = state.camera;
    return { x: (wx - x) * scale, y: (wy - y) * scale };
  }

  // ---------- Terminal ----------
  function log(line, level='info') {
    if (!el.term) return;
    const div = document.createElement('div');
    div.className = 'terminal-line';
    div.innerHTML = `
      <span class="terminal-prompt">$</span>
      <span class="terminal-text">${escapeHtml(line)}</span>
    `;
    if (level === 'error') div.querySelector('.terminal-text').classList.add('terminal-error');
    el.term.appendChild(div);
    el.term.scrollTop = el.term.scrollHeight;
  }
  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  // ---------- Toast ----------
  let toastTimer = null;
  function showToast(msg, ms = 2500) {
    if (!el.toast) return;
    el.toast.textContent = msg;
    el.toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.toast.classList.remove('show'), ms);
  }

  // ---------- Library (left panel) ----------
  async function loadAndRenderLibrary() {
    const container = document.getElementById('toolCategories');
    if (!container) {
      console.warn('[tools] #toolCategories not found');
      log('Library container missing (#toolCategories).', 'error');
      return;
    }
    let data = null;
    try {
      const res = await fetch('/tools/api/tools', { credentials: 'same-origin', cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      data = await res.json();
      log('Loaded tools catalog from /tools/api/tools', 'info');
    } catch (err) {
      console.error('[tools] fetch catalog failed:', err);
      container.innerHTML = '<div style="padding:12px;color:var(--hack-magenta)">Failed to load tools. Check console/network.</div>';
      log(`Failed to load tools: ${err.message}`, 'error');
      return;
    }

    container.innerHTML = '';

    let categories = [];
    if (data && data.categories && typeof data.categories === 'object' && !Array.isArray(data.categories)) {
      categories = Object.entries(data.categories).map(([name, tools]) => ({ name, tools }));
    } else if (data && Array.isArray(data.categories)) {
      categories = data.categories.map(c => ({ name: c.name || c.slug || 'Category', tools: c.tools || [] }));
    }

    state.catalogBySlug.clear();

    categories.forEach(cat => {
      const sec = document.createElement('div');
      sec.className = 'category-section';

      const header = document.createElement('div');
      header.className = 'category-header';
      header.innerHTML = `
        <div class="category-info">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/>
          </svg>
          <span>${cat.name}</span>
        </div>
        <span class="category-count">${(cat.tools || []).length}</span>
        <span class="category-arrow">▾</span>
      `;
      sec.appendChild(header);

      const list = document.createElement('div');
      list.className = 'category-tools active';

      (cat.tools || []).forEach(t => {
        const slug = t.slug || t.key || t.name;
        state.catalogBySlug.set(slug, { slug, name: t.name || slug, desc: t.desc || '', type: t.type || '', time: t.time || '' });

        const item = document.createElement('div');
        item.className = 'tool-item';
        item.dataset.toolKey  = slug;
        item.dataset.toolName = t.name || slug;
        item.dataset.toolType = t.type || '';
        item.dataset.toolTime = t.time || '';
        item.dataset.toolDesc = t.desc || '';
        item.innerHTML = `
          <div class="tool-icon">${(t.name || slug || 'T').charAt(0).toUpperCase()}</div>
          <div class="tool-info">
            <div class="tool-name">${t.name || slug}</div>
            <div class="tool-desc">${t.desc || ''}</div>
          </div>
          <div class="tool-meta">
            <div class="tool-time">${t.time || ''}</div>
            <div class="tool-type">${(t.type || '').toUpperCase()}</div>
          </div>
        `;
        list.appendChild(item);
      });

      sec.appendChild(list);
      container.appendChild(sec);

      header.addEventListener('click', () => {
        sec.classList.toggle('collapsed');
        list.classList.toggle('active');
      });
    });

    setupLibrary();
  }

  function setupLibrary() {
    if (!el.library) return;
    el.library.querySelectorAll('.tool-item').forEach(item => {
      item.setAttribute('draggable', 'true');
      item.addEventListener('dragstart', (e) => {
        e.dataTransfer.setData('application/x-tool', JSON.stringify({
          key: item.dataset.toolKey,
          name: item.dataset.toolName,
          type: item.dataset.toolType,
          time: item.dataset.toolTime,
          desc: item.dataset.toolDesc,
        }));
        e.dataTransfer.effectAllowed = 'copy';
      });
    });

    el.canvas.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      el.canvas.classList.add('drag-over');
    });
    el.canvas.addEventListener('dragleave', () => el.canvas.classList.remove('drag-over'));
    el.canvas.addEventListener('drop', (e) => {
      e.preventDefault();
      el.canvas.classList.remove('drag-over');

      const data = e.dataTransfer.getData('application/x-tool');
      if (!data) return;
      const toolMeta = JSON.parse(data);

      const rect = el.canvas.getBoundingClientRect();
      const screen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      const world = screenToWorld(screen.x, screen.y);

      const node = createNodeFromTool(toolMeta, world.x - 40, world.y - 40);
      log(`Added node: ${node.name}`);
    });
  }

  // ---------- Node creation ----------
  function createNodeFromTool(toolMeta, worldX, worldY) {
    const id = genId('node_');
    const nodeEl = document.createElement('div');
    nodeEl.className = 'workflow-node workflow-box filled';
    nodeEl.dataset.nodeId = id;
    nodeEl.style.position = 'absolute';

    const initial = {
      slug: (toolMeta.slug || toolMeta.key || toolMeta.toolKey || toolMeta.name),
      name: toolMeta.name || toolMeta.slug || toolMeta.key || 'Tool',
      desc: toolMeta.desc || '',
      type: toolMeta.type || '',
      time: toolMeta.time || ''
    };

    nodeEl.innerHTML = `
      <div class="box-content">
        <div class="box-tool">
          <div class="box-tool-header">
            <div class="box-tool-info">
              <div class="box-tool-icon">${(initial.name || 'T').charAt(0).toUpperCase()}</div>
              <div class="box-tool-name">${initial.name}</div>
            </div>
            <div class="box-tool-actions">
              <button class="box-action-btn delete" title="Delete">✕</button>
            </div>
          </div>
          <div class="box-tool-desc">${initial.desc}</div>
          <div class="box-tool-time">${initial.time} ${(initial.type || '').toUpperCase()}</div>
        </div>
      </div>
      <div class="connection-handles">
        <div class="connection-handle input" data-handle="input"></div>
        <div class="connection-handle output" data-handle="output"></div>
      </div>
    `;
    el.boxes.appendChild(nodeEl);

    const width  = nodeEl.offsetWidth;
    const height = nodeEl.offsetHeight;
    const handles = {
      input:  { ox: 0,      oy: height / 2 },
      output: { ox: width,  oy: height / 2 },
    };

    const node = {
      id, x: worldX, y: worldY, width, height, el: nodeEl, handles,
      toolKey: initial.slug, name: initial.name, config: {},
    };
    state.nodes.set(id, node);

    // Events
    nodeEl.addEventListener('pointerdown', (e) => onNodePointerDown(e, node));
    nodeEl.querySelector('.box-action-btn.delete')?.addEventListener('click', () => {
      deleteNode(id);
      updateChainValidity();
      markDirty();
    });
    nodeEl.querySelector('.connection-handle.input')?.addEventListener('click', (e) => onHandleClick(e, node, 'input'));
    nodeEl.querySelector('.connection-handle.output')?.addEventListener('click', (e) => onHandleClick(e, node, 'output'));
    nodeEl.addEventListener('click', (e) => {
      e.stopPropagation();
      state.selectedNodeId = id;
      openConfigPanel();
    });

    state.needsRender = true;
    updateChainValidity();
    markDirty();
    return node;
  }

  function deleteNode(id) {
    [...state.edges.values()].forEach(edge => {
      if (edge.fromId === id || edge.toId === id) removeEdge(edge.id);
    });
    const node = state.nodes.get(id);
    if (node?.el?.parentNode) node.el.parentNode.removeChild(node.el);
    state.nodes.delete(id);
    state.needsRender = true;
  }

  // ---------- Graph helpers ----------
  function degreeMaps(extraEdge = null) {
    const inDeg = new Map(), outDeg = new Map();
    state.nodes.forEach((_, nid) => { inDeg.set(nid, 0); outDeg.set(nid, 0); });
    state.edges.forEach(e => {
      inDeg.set(e.toId, (inDeg.get(e.toId) || 0) + 1);
      outDeg.set(e.fromId, (outDeg.get(e.fromId) || 0) + 1);
    });
    if (extraEdge) {
      inDeg.set(extraEdge.toId, (inDeg.get(extraEdge.toId) || 0) + 1);
      outDeg.set(extraEdge.fromId, (outDeg.get(extraEdge.fromId) || 0) + 1);
    }
    return { inDeg, outDeg };
  }
  function inDegree(nodeId)  { let c=0; state.edges.forEach(e=>{ if(e.toId===nodeId) c++;}); return c; }
  function outDegree(nodeId) { let c=0; state.edges.forEach(e=>{ if(e.fromId===nodeId) c++;}); return c; }

  function wouldCreateCycle(fromId, toId) {
    const adj = new Map(); state.nodes.forEach((_, k) => adj.set(k, []));
    state.edges.forEach(e => adj.get(e.fromId).push(e.toId));
    adj.get(fromId).push(toId);
    const stack = [toId];
    const seen = new Set();
    while (stack.length) {
      const cur = stack.pop();
      if (cur === fromId) return true;
      if (seen.has(cur)) continue;
      seen.add(cur);
      (adj.get(cur) || []).forEach(n => stack.push(n));
    }
    return false;
  }

  function computeChainOrder() {
    const inDeg = new Map(); state.nodes.forEach((_, id) => inDeg.set(id, 0));
    state.edges.forEach(e => inDeg.set(e.toId, (inDeg.get(e.toId) || 0) + 1));
    const start = [...inDeg.entries()].find(([id, deg]) => deg === 0)?.[0];
    const nextOf = new Map(); state.edges.forEach(e => nextOf.set(e.fromId, e.toId));
    const order = [];
    let cur = start, seen = new Set();
    while (cur && !seen.has(cur)) { order.push(cur); seen.add(cur); cur = nextOf.get(cur); }
    state.nodes.forEach((_, id) => { if (!order.includes(id)) order.push(id); });
    return order;
  }
  function stepIndexToNodeId(index) {
    const order = computeChainOrder();
    return order[index] || null;
  }

  function clearNodeStatuses() {
    state.nodes.forEach(n => n.el.classList.remove('node-running','node-complete','node-failed'));
  }
  function paintStepStatus(stepIndex, status) {
    const nid = stepIndexToNodeId(stepIndex);
    if (!nid) return;
    const node = state.nodes.get(nid);
    if (!node) return;
    node.el.classList.remove('node-running','node-complete','node-failed');
    if (status === 'RUNNING') node.el.classList.add('node-running');
    else if (status === 'COMPLETED') node.el.classList.add('node-complete');
    else if (status === 'FAILED') node.el.classList.add('node-failed');
  }

  // ---------- Edge creation / deletion ----------
  function beginConnect(fromNodeId) {
    cancelConnect();
    if (outDegree(fromNodeId) >= 1) { showToast('Only one outbound connection allowed.'); return; }
    const rubber = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    rubber.setAttribute('opacity', '0.6');
    el.svg.appendChild(rubber);
    state.connecting = { fromId: fromNodeId, rubber };
  }
  function finishConnect(toNodeId) {
    if (!state.connecting) return;
    const fromId = state.connecting.fromId;
    if (fromId === toNodeId) { cancelConnect(); return; }
    if (inDegree(toNodeId) >= 1)  { showToast('Only one inbound connection allowed.'); cancelConnect(); return; }
    if (wouldCreateCycle(fromId, toNodeId)) { showToast('This connection would create a cycle.'); cancelConnect(); return; }

    const id = genId('edge_');
    const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathEl.addEventListener('click', () => selectEdge(id));
    el.svg.appendChild(pathEl);
    state.edges.set(id, { id, fromId, toId: toNodeId, pathEl });

    el.svg.removeChild(state.connecting.rubber);
    state.connecting = null;
    state.needsRender = true;
    updateChainValidity();
    markDirty();
  }
  function cancelConnect() {
    if (state.connecting?.rubber?.parentNode) state.connecting.rubber.parentNode.removeChild(state.connecting.rubber);
    state.connecting = null;
    state.needsRender = true;
  }
  function removeEdge(id) {
    const edge = state.edges.get(id);
    if (edge?.pathEl?.parentNode) edge.pathEl.parentNode.removeChild(edge.pathEl);
    if (state.selectedEdgeId === id) state.selectedEdgeId = null;
    state.edges.delete(id);
    state.needsRender = true;
    markDirty();
  }
  function selectEdge(id) {
    if (state.selectedEdgeId && state.edges.get(state.selectedEdgeId)?.pathEl) {
      state.edges.get(state.selectedEdgeId).pathEl.classList.remove('selected');
    }
    state.selectedEdgeId = id;
    const e = state.edges.get(id);
    if (e?.pathEl) e.pathEl.classList.add('selected');
  }
  document.addEventListener('keydown', (ev) => {
    if ((ev.key === 'Delete' || ev.key === 'Backspace') && state.selectedEdgeId) {
      removeEdge(state.selectedEdgeId);
      updateChainValidity();
    }
  });

  // ---------- Graph <-> Canvas ----------
  function serializeGraph() {
    const nodes = [...state.nodes.values()].map(n => ({
      id: n.id,
      tool_slug: n.toolKey,
      x: n.x, y: n.y,
      config: n.config || {}
    }));
    const edges = [...state.edges.values()].map(e => ({ from: e.fromId, to: e.toId }));
    return { nodes, edges };
  }

  function clearCanvas() {
    [...state.edges.values()].forEach(e => e?.pathEl?.parentNode?.removeChild(e.pathEl));
    state.edges.clear();
    [...state.nodes.values()].forEach(n => n?.el?.parentNode?.removeChild(n.el));
    state.nodes.clear();
    state.needsRender = true;
    updateChainValidity();
  }

  function createNodeFromSaved(savedNode) {
    const meta = state.catalogBySlug?.get?.(savedNode.tool_slug) || {
      slug: savedNode.tool_slug, name: savedNode.tool_slug, desc: '', type: '', time: ''
    };
    const node = createNodeFromTool(meta, savedNode.x, savedNode.y);
    if (node.id !== savedNode.id) {
      const oldId = node.id;
      node.id = savedNode.id;
      node.el.dataset.nodeId = node.id;
      state.nodes.delete(oldId);
      state.nodes.set(node.id, node);
    }
    node.config = savedNode.config || {};
    return node;
  }

  function createEdgeByIds(fromId, toId) {
    const id = genId('edge_');
    const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathEl.addEventListener('click', () => selectEdge(id));
    el.svg.appendChild(pathEl);
    state.edges.set(id, { id, fromId, toId, pathEl });
    state.needsRender = true;
  }

  function renderGraph(graph) {
    clearCanvas();
    const nodesById = new Map();
    (graph.nodes || []).forEach(n => {
      const node = createNodeFromSaved(n);
      nodesById.set(node.id, node);
    });
    (graph.edges || []).forEach(e => {
      if (nodesById.has(e.from) && nodesById.has(e.to)) createEdgeByIds(e.from, e.to);
    });
    updateChainValidity();
    log(`Workflow loaded: ${nodesById.size} nodes, ${state.edges.size} edges`);
  }

  function chainValidity() {
    const n = state.nodes.size;
    if (n === 0) return { valid: false, reason: 'Add at least one node.' };
    if (n === 1) return { valid: true, reason: 'Single node acts as start & end.' };

    const { inDeg, outDeg } = degreeMaps();
    let starts = [], ends = [];
    let multiIn = null, multiOut = null;

    state.nodes.forEach((_, id) => {
      const i = inDeg.get(id) || 0;
      const o = outDeg.get(id) || 0;
      if (i === 0) starts.push(id);
      if (o === 0) ends.push(id);
      if (i > 1 && !multiIn)  multiIn  = id;
      if (o > 1 && !multiOut) multiOut = id;
    });

    if (multiIn)  return { valid: false, reason: 'Node has more than one input.' };
    if (multiOut) return { valid: false, reason: 'Node has more than one output.' };
    if (starts.length !== 1) return { valid: false, reason: `Requires exactly one start node (found ${starts.length}).` };
    if (ends.length   !== 1) return { valid: false, reason: `Requires exactly one end node (found ${ends.length}).` };

    // connectivity
    const start = starts[0];
    const nextOf = new Map(); state.edges.forEach(e => { nextOf.set(e.fromId, e.toId); });
    const visited = new Set();
    let cur = start; let steps = 0;
    while (cur && steps <= n) { visited.add(cur); cur = nextOf.get(cur); steps++; }
    if (steps > n) return { valid: false, reason: 'Cycle detected in chain.' };
    if (visited.size !== n) return { valid: false, reason: 'All nodes must be connected in a single path.' };

    return { valid: true, reason: 'Chain is valid.' };
  }

  function updateChainValidity() {
    const { valid, reason } = chainValidity();
    if (el.chainBadge) {
      el.chainBadge.textContent = valid ? 'Valid' : 'Invalid';
      el.chainBadge.classList.toggle('badge-valid', valid);
      el.chainBadge.classList.toggle('badge-invalid', !valid);
    }
    if (el.chainReason) el.chainReason.textContent = reason || '';
    return valid;
  }

  // ---------- Node drag (Pointer Events) ----------
  function onNodePointerDown(e, node) {
    const target = e.target;
    if (target.closest('.node-action-btn') || target.classList.contains('connection-handle')) return;
    if (e.button !== 0) return;

    node.el.setPointerCapture(e.pointerId);
    node.el.classList.add('dragging');

    const startMouseWorld = screenToWorld(e.clientX, e.clientY);
    state.draggingNode = {
      id: node.id,
      pointerId: e.pointerId,
      startMouseWorld,
      startNode: { x: node.x, y: node.y },
    };

    node.el.addEventListener('pointermove', onNodePointerMove);
    node.el.addEventListener('pointerup', onNodePointerUp);
    node.el.addEventListener('pointercancel', onNodePointerUp);
  }
  function onNodePointerMove(e) {
    const drag = state.draggingNode;
    if (!drag || e.pointerId !== drag.pointerId) return;
    const node = state.nodes.get(drag.id);
    if (!node) return;

    const cur = screenToWorld(e.clientX, e.clientY);
    node.x = drag.startNode.x + (cur.x - drag.startMouseWorld.x);
    node.y = drag.startNode.y + (cur.y - drag.startMouseWorld.y);
    state.needsRender = true;
  }
  function onNodePointerUp(e) {
    const drag = state.draggingNode;
    if (!drag) return;
    const node = state.nodes.get(drag.id);
    if (node) {
      node.el.classList.remove('dragging');
      node.el.releasePointerCapture(drag.pointerId);
      node.el.removeEventListener('pointermove', onNodePointerMove);
      node.el.removeEventListener('pointerup', onNodePointerUp);
      node.el.removeEventListener('pointercancel', onNodePointerUp);
    }
    state.draggingNode = null;
    markDirty();
  }

  // ---------- Handle clicks (connect) ----------
  function onHandleClick(e, node, kind) {
    e.stopPropagation();
    if (kind === 'output') {
      beginConnect(node.id);
      log(`Connecting from ${node.name}…`);
    } else if (kind === 'input' && state.connecting) {
      if (state.connecting.fromId === node.id) { cancelConnect(); return; }
      finishConnect(node.id);
      log(`Connected → ${node.name}`);
    }
  }

  // ---------- Canvas pan / zoom ----------
  function onCanvasPointerDown(e) {
    const isPanButton = (e.button === 1) || (e.button === 2);
    if (!isPanButton && !el.canvas.classList.contains('panning')) return;

    el.canvas.setPointerCapture(e.pointerId);
    state.panning = {
      pointerId: e.pointerId,
      startScreen: { x: e.clientX, y: e.clientY },
      startCam: { x: state.camera.x, y: state.camera.y },
    };
    el.canvas.addEventListener('pointermove', onCanvasPointerMove);
    el.canvas.addEventListener('pointerup', onCanvasPointerUp);
    el.canvas.addEventListener('pointercancel', onCanvasPointerUp);
    e.preventDefault();
  }
  function onCanvasPointerMove(e) {
    const pan = state.panning;
    if (!pan || e.pointerId !== pan.pointerId) return;
    const dx = (e.clientX - pan.startScreen.x) / state.camera.scale;
    const dy = (e.clientY - pan.startScreen.y) / state.camera.scale;
    state.camera.x = pan.startCam.x - dx;
    state.camera.y = pan.startCam.y - dy;
    state.needsRender = true;
  }
  function onCanvasPointerUp(e) {
    const pan = state.panning;
    if (!pan) return;
    el.canvas.releasePointerCapture(pan.pointerId);
    el.canvas.removeEventListener('pointermove', onCanvasPointerMove);
    el.canvas.removeEventListener('pointerup', onCanvasPointerUp);
    el.canvas.removeEventListener('pointercancel', onCanvasPointerUp);
    state.panning = null;
  }
  function onWheelZoom(e) {
    e.preventDefault();
    const oldScale = state.camera.scale;
    const delta = Math.sign(e.deltaY);
    const zoomFactor = (delta > 0) ? 0.9 : 1.1;
    const newScale = clamp(oldScale * zoomFactor, state.camera.min, state.camera.max);

    const rect = el.canvas.getBoundingClientRect();
    const mouseScreen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    const pre = screenToWorld(mouseScreen.x, mouseScreen.y);

    state.camera.scale = newScale;

    const post = screenToWorld(mouseScreen.x, mouseScreen.y);
    state.camera.x += (pre.x - post.x);
    state.camera.y += (pre.y - post.y);

    el.zoomPct && (el.zoomPct.textContent = `${Math.round(newScale * 100)}%`);
    state.needsRender = true;
  }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

  document.addEventListener('keydown', (e) => { if (e.code === 'Space') el.canvas.classList.add('panning'); });
  document.addEventListener('keyup', (e) => { if (e.code === 'Space') el.canvas.classList.remove('panning'); });
  el.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  el.canvas.addEventListener('pointerdown', onCanvasPointerDown);
  el.canvas.addEventListener('wheel', onWheelZoom, { passive: false });

  // ---------- Render loop ----------
  function edgePath(fromId, toId) {
    const a = state.nodes.get(fromId);
    const b = state.nodes.get(toId);
    if (!a || !b) return null;

    const p1w = { x: a.x + a.handles.output.ox, y: a.y + a.handles.output.oy };
    const p2w = { x: b.x + b.handles.input.ox,  y: b.y + b.handles.input.oy  };
    const p1 = worldToScreen(p1w.x, p1w.y);
    const p2 = worldToScreen(p2w.x, p2w.y);

    const dx = Math.max(40, Math.abs(p2.x - p1.x) * 0.35);
    const c1x = p1.x + dx, c1y = p1.y;
    const c2x = p2.x - dx, c2y = p2.y;
    return `M ${p1.x} ${p1.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`;
  }

  let lastMouseScreen = null;
  el.canvas.addEventListener('pointermove', (e) => {
    const rect = el.canvas.getBoundingClientRect();
    lastMouseScreen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    if (state.connecting) state.needsRender = true;
  });

  function render() {
    if (state.needsRender) {
      // nodes
      state.nodes.forEach(node => {
        const { x, y } = worldToScreen(node.x, node.y);
        node.el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${state.camera.scale})`;
        node.el.style.transformOrigin = `0 0`;
      });
      // edges
      state.edges.forEach(edge => {
        const d = edgePath(edge.fromId, edge.toId);
        if (d) edge.pathEl.setAttribute('d', d);
      });
      // rubber
      if (state.connecting?.rubber) {
        const from = state.nodes.get(state.connecting.fromId);
        if (from) {
          const p1w = { x: from.x + from.handles.output.ox, y: from.y + from.handles.output.oy };
          const p1  = worldToScreen(p1w.x, p1w.y);
          const p2  = lastMouseScreen || p1;
          const dx  = Math.max(40, Math.abs(p2.x - p1.x) * 0.35);
          const c1x = p1.x + dx, c1y = p1.y;
          const c2x = p2.x - dx, c2y = p2.y;
          state.connecting.rubber.setAttribute('d', `M ${p1.x} ${p1.y} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${p2.x} ${p2.y}`);
        }
      }
      state.needsRender = false;
    }
    requestAnimationFrame(render);
  }

  // ---------- API helpers ----------
  async function apiFetch(url, opts = {}) {
    const headers = new Headers(opts.headers || {});
    headers.set('Content-Type','application/json');
    headers.set('X-CSRF-Token', getCsrf());
    const res = await fetch(url, { credentials:'same-origin', ...opts, headers });
    if (!res.ok) {
      const msg = await res.text();
      throw new Error(`HTTP ${res.status}: ${msg}`);
    }
    return res.json().catch(() => ({}));
  }

  async function saveWorkflow(asNew=false) {
    const graph = serializeGraph();
    try {
      if (asNew || !state.currentWorkflowId) {
        const title = (prompt('Workflow title?') || '').trim();
        if (!title) { showToast('Save cancelled'); return; }
        const body = { title, description:'', is_shared:false, graph };
        const data = await apiFetch('/tools/api/workflows', { method:'POST', body: JSON.stringify(body) });
        state.currentWorkflowId = data?.workflow?.id;
        state.dirty = false;
        setStatus(`Saved as #${state.currentWorkflowId}`);
        showToast(`Saved new workflow #${state.currentWorkflowId}`);
        localStorage.setItem('lastWorkflowId', state.currentWorkflowId);
      } else {
        const id = state.currentWorkflowId;
        const data = await apiFetch(`/tools/api/workflows/${id}`, { method:'PUT', body: JSON.stringify({ graph }) });
        state.dirty = false;
        setStatus(`Saved #${id} (v${data?.workflow?.version ?? ''})`);
      }
    } catch (e) {
      console.error(e);
      showToast(`Save failed: ${e.message}`);
      setStatus('Save failed');
    }
  }

  async function cloneWorkflow() {
    if (!state.currentWorkflowId) { showToast('Load a workflow first'); return; }
    try {
      const title = (prompt('Clone title?', 'Clone of ' + state.currentWorkflowId) || '').trim();
      const data = await apiFetch(`/tools/api/workflows/${state.currentWorkflowId}/clone`, {
        method:'POST', body: JSON.stringify({ title })
      });
      state.currentWorkflowId = data?.workflow?.id;
      setStatus(`Cloned to #${state.currentWorkflowId}`);
      showToast(`Cloned → #${state.currentWorkflowId}`);
      localStorage.setItem('lastWorkflowId', state.currentWorkflowId);
    } catch (e) {
      console.error(e);
      showToast(`Clone failed: ${e.message}`);
    }
  }

  async function loadWorkflow(id) {
    try {
      const data = await apiFetch(`/tools/api/workflows/${id}`);
      const wf = data?.workflow;
      if (!wf) throw new Error('No workflow in response');
      state.currentWorkflowId = wf.id;
      renderGraph(wf.graph || {nodes:[], edges:[]});
      state.dirty = false;
      setStatus(`Loaded #${wf.id} (v${wf.version})`);
      localStorage.setItem('lastWorkflowId', wf.id);
    } catch (e) {
      console.error(e);
      showToast(`Load failed: ${e.message}`);
      setStatus('Load failed');
    }
  }

  // ---------- Presets (drawer) ----------
  function toggleDrawer(node, show) { node.classList.toggle('hidden', !show); }
  async function fetchPresets(q='') {
    const mine = '/tools/api/workflows?mine=true&shared=true' + (q ? `&q=${encodeURIComponent(q)}` : '');
    const data = await apiFetch(mine);
    return data.items || [];
  }
  function renderPresets(items) {
    const list = document.getElementById('presetsList');
    list.innerHTML = '';
    items.forEach(w => {
      const card = document.createElement('div');
      card.className = 'preset-card';
      card.innerHTML = `
        <div>
          <div class="title">${w.title}</div>
          <div class="meta">#${w.id} • v${w.version} • ${w.is_shared ? 'shared' : 'private'}</div>
        </div>
        <div class="actions">
          <button class="glass-button" data-act="load"  data-id="${w.id}">Load</button>
          <button class="glass-button" data-act="run"   data-id="${w.id}">Run</button>
          <button class="glass-button" data-act="clone" data-id="${w.id}">Clone</button>
          <button class="danger-button" data-act="archive" data-id="${w.id}">Archive</button>
        </div>
      `;
      list.appendChild(card);
    });

    list.querySelectorAll('button').forEach(btn => {
      const id = parseInt(btn.dataset.id, 10);
      btn.addEventListener('click', async () => {
        const act = btn.dataset.act;
        try {
          if (act === 'load') { await loadWorkflow(id); localStorage.setItem('lastWorkflowId', id); }
          if (act === 'clone') {
            const title = prompt('New title?', 'Clone of #' + id) || '';
            await apiFetch(`/tools/api/workflows/${id}/clone`, { method:'POST', body: JSON.stringify({ title }) });
            showToast('Cloned');
          }
          if (act === 'archive') {
            await apiFetch(`/tools/api/workflows/${id}`, { method:'DELETE' });
            showToast('Archived');
            const items = await fetchPresets(document.getElementById('presetsSearch').value.trim());
            renderPresets(items);
          }
          if (act === 'run') {
            const run = await startRunByWorkflow(id);
            attachToRun(run.id);
            openOutputDrawer();
          }
        } catch (e) { showToast(e.message); }
      });
    });
  }
  async function openPresetsDrawer() {
    const drawer = document.getElementById('presetsDrawer');
    toggleDrawer(drawer, true);
    const items = await fetchPresets(document.getElementById('presetsSearch').value.trim());
    renderPresets(items);
  }

  // ---------- Config side panel ----------
  function openConfigPanel() {
    const p = document.getElementById('configPanel');
    const title = document.getElementById('configNodeTitle');
    const ta = document.getElementById('configJson');
    const node = state.nodes.get(state.selectedNodeId);
    if (!node) { toggleDrawer(p, false); return; }
    title.textContent = `Node ${node.name} (${node.toolKey})`;
    ta.value = JSON.stringify(node.config || {}, null, 2);
    toggleDrawer(p, true);
  }
  function applyConfig() {
    const node = state.nodes.get(state.selectedNodeId);
    if (!node) return;
    const ta = document.getElementById('configJson');
    try {
      const obj = ta.value.trim() ? JSON.parse(ta.value) : {};
      node.config = obj;
      showToast('Config applied');
      markDirty();
    } catch (e) { showToast('Invalid JSON: ' + e.message); }
  }
  function resetConfig() {
    const ta = document.getElementById('configJson');
    ta.value = '{}';
  }

  // ---------- Runs: controls + SSE ----------
  async function startRunByWorkflow(wfId) {
    const data = await apiFetch(`/tools/api/workflows/${wfId}/run`, { method:'POST', body: JSON.stringify({}) });
    const run = data.run;
    if (!run) throw new Error('No run in response');
    localStorage.setItem('lastRunId', run.id);
    setStatus(`Run #${run.id}: ${run.status} • ${run.progress_pct}%`);
    return run;
  }
  async function pauseRun(runId)  { await apiFetch(`/tools/api/runs/${runId}/pause`,  { method:'POST', body: '{}' }); }
  async function resumeRun(runId) { await apiFetch(`/tools/api/runs/${runId}/resume`, { method:'POST', body: '{}' }); }
  async function cancelRun(runId) { await apiFetch(`/tools/api/runs/${runId}/cancel`, { method:'POST', body: '{}' }); }
  async function retryRunAt(runId, stepIndex) {
    await apiFetch(`/tools/api/runs/${runId}/retry`, { method:'POST', body: JSON.stringify({ step_index: stepIndex }) });
  }

  function setProgress(pct, statusText) {
    const bar = document.querySelector('#runProgress .bar');
    const lbl = document.querySelector('#runProgressLabel');
    if (bar) bar.style.width = `${Math.max(0, Math.min(100, pct || 0))}%`;
    if (lbl) lbl.textContent = statusText || '';
  }

  function attachToRun(runId) {
    if (state.eventSource) { state.eventSource.close(); state.eventSource = null; }
    state.currentRunId = runId;
    localStorage.setItem('lastRunId', runId);
    setStatus(`Attaching to run #${runId}…`);

    const url = `/tools/api/runs/${runId}/events`;
    const es = new EventSource(url, { withCredentials: true });
    state.eventSource = es;

    es.addEventListener('snapshot', (ev) => {
      try {
        const payload = JSON.parse(ev.data);
        const run = payload.run;
        clearNodeStatuses();
        (run.steps || []).forEach(s => paintStepStatus(s.step_index, s.status));
        setStatus(`Run #${run.id}: ${run.status} • ${run.progress_pct}%`);
        setProgress(run.progress_pct || 0, `Run #${run.id}: ${run.status}`);
        populateOutputStepSelect(run.total_steps || (run.steps || []).length || 0);
        log(`Attached: run=${run.id} status=${run.status}`);
      } catch(e){ console.error(e); }
    });

    es.addEventListener('update', (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'step') {
          paintStepStatus(msg.step_index, msg.status);
          log(`Step ${msg.step_index}: ${msg.status}`);
        } else if (msg.type === 'run') {
          setStatus(`Run #${msg.run_id || runId}: ${msg.status} • ${msg.progress_pct}%`);
          setProgress(msg.progress_pct || 0, `Run #${msg.run_id || runId}: ${msg.status}`);
        }
      } catch(e){ console.error(e); }
    });

    es.onerror = () => { setStatus(`Run #${runId}: connection lost, retrying…`); };
  }

  // ---------- Output drawer ----------
  function openOutputDrawer() { toggleDrawer(document.getElementById('outputDrawer'), true); }
  function closeOutputDrawer() { toggleDrawer(document.getElementById('outputDrawer'), false); }
  function populateOutputStepSelect(totalSteps) {
    const sel = document.getElementById('outputStepSelect');
    sel.innerHTML = '';
    for (let i = 0; i < totalSteps; i++) {
      const opt = document.createElement('option');
      opt.value = i; opt.textContent = `Step ${i+1}`;
      sel.appendChild(opt);
    }
  }
  async function refreshOutput() {
    if (!state.currentRunId) { showToast('Attach to a run first'); return; }
    const sel = document.getElementById('outputStepSelect');
    const stepIndex = parseInt(sel.value, 10);
    try {
      const data = await apiFetch(`/tools/api/runs/${state.currentRunId}/steps/${stepIndex}`);
      const step = data.step || {};
      const pre = document.getElementById('outputPre');
      pre.textContent = JSON.stringify(step.output_manifest || step || {}, null, 2);

      const links = document.getElementById('outputLinks');
      links.innerHTML = '';
      if (step.tool_scan_history_id) {
        const a = document.createElement('a');
        a.href = `/tools/scan-history/${step.tool_scan_history_id}`;
        a.textContent = `Open Scan History #${step.tool_scan_history_id}`;
        links.appendChild(a);
      }
    } catch (e) {
      showToast('Output fetch failed: ' + e.message);
    }
  }

  // ---------- Boot ----------
  async function boot() {
    await loadAndRenderLibrary();
    requestAnimationFrame(render);
    updateChainValidity();
    log('Chain rules: ≤1 input & ≤1 output per node, single start & end, linear path only.');
    log('Tip: Click an edge to select; press Delete to remove.');

    // Save/Load/Clone
    document.getElementById('wfSaveBtn')?.addEventListener('click', () => saveWorkflow(false));
    document.getElementById('wfSaveAsBtn')?.addEventListener('click', () => saveWorkflow(true));
    document.getElementById('wfCloneBtn')?.addEventListener('click', () => cloneWorkflow());
    document.getElementById('wfLoadBtn')?.addEventListener('click', () => {
      const idStr = document.getElementById('wfIdInput')?.value?.trim();
      const id = parseInt(idStr, 10);
      if (!id) { showToast('Enter a valid ID'); return; }
      loadWorkflow(id);
    });

    // Presets drawer
    document.getElementById('presetsOpenBtn')?.addEventListener('click', openPresetsDrawer);
    document.getElementById('presetsCloseBtn')?.addEventListener('click', () => toggleDrawer(document.getElementById('presetsDrawer'), false));
    document.getElementById('presetsSearchBtn')?.addEventListener('click', openPresetsDrawer);

    // Config panel
    document.getElementById('configCloseBtn')?.addEventListener('click', () => toggleDrawer(document.getElementById('configPanel'), false));
    document.getElementById('configApplyBtn')?.addEventListener('click', applyConfig);
    document.getElementById('configResetBtn')?.addEventListener('click', resetConfig);

    // Output drawer
    document.getElementById('outputRefreshBtn')?.addEventListener('click', refreshOutput);
    document.getElementById('outputCloseBtn')?.addEventListener('click', () => toggleDrawer(document.getElementById('outputDrawer'), false));

    // Run controls
    document.getElementById('runStartBtn')?.addEventListener('click', async () => {
      const id = state.currentWorkflowId || parseInt(document.getElementById('wfIdInput')?.value || '0', 10);
      if (!id) return showToast('Save or load a workflow first');
      const run = await startRunByWorkflow(id);
      attachToRun(run.id);
      openOutputDrawer();
    });
    document.getElementById('runPauseBtn')?.addEventListener('click', async () => {
      if (!state.currentRunId) return showToast('No run attached');
      await pauseRun(state.currentRunId);
    });
    document.getElementById('runResumeBtn')?.addEventListener('click', async () => {
      if (!state.currentRunId) return showToast('No run attached');
      await resumeRun(state.currentRunId);
    });
    document.getElementById('runCancelBtn')?.addEventListener('click', async () => {
      if (!state.currentRunId) return showToast('No run attached');
      await cancelRun(state.currentRunId);
    });
    document.getElementById('runRetryBtn')?.addEventListener('click', async () => {
      if (!state.currentRunId) return showToast('No run attached');
      let idx = -1;
      if (state.selectedNodeId) {
        const order = computeChainOrder();
        idx = order.indexOf(state.selectedNodeId);
      }
      if (idx < 0) {
        const sel = document.getElementById('outputStepSelect');
        idx = parseInt(sel.value || '0', 10);
      }
      await retryRunAt(state.currentRunId, idx);
      openOutputDrawer();
    });

    // Attach by input
    document.getElementById('runAttachBtn')?.addEventListener('click', () => {
      const v = document.getElementById('runIdInput')?.value?.trim();
      const id = parseInt(v, 10);
      if (!id) { showToast('Enter a valid Run ID'); return; }
      attachToRun(id);
    });

    // Restore last session (if URL params absent)
    const params = new URLSearchParams(location.search);
    const wfParam = params.get('wf');
    const runParam = params.get('run');
    if (!wfParam) {
      const lastWf = parseInt(localStorage.getItem('lastWorkflowId') || '0', 10);
      if (lastWf) loadWorkflow(lastWf);
    } else if (/^\d+$/.test(wfParam)) {
      loadWorkflow(parseInt(wfParam, 10));
    }
    if (!runParam) {
      const lastRun = parseInt(localStorage.getItem('lastRunId') || '0', 10);
      if (lastRun) attachToRun(lastRun);
    } else if (/^\d+$/.test(runParam)) {
      attachToRun(parseInt(runParam, 10));
    }
  }

  // ---------- Kick ----------
  boot();

})();
