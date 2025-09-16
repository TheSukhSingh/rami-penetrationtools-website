/* tools/static/js/tools.js */
/* eslint-disable no-unused-vars */

(() => {
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

  // ---------- State ----------
  const state = {
    camera: { x: 0, y: 0, scale: 1, min: 0.25, max: 2 },
    nodes: new Map(),    // id -> {id, x, y, width, height, el, handles, name, toolKey}
    edges: new Map(),    // id -> {id, fromId, toId, pathEl}
    needsRender: true,
    draggingNode: null,
    panning: null,
    connecting: null,    // { fromId, rubber?: SVGPathElement }
    idCounter: 1,
    selectedEdgeId: null,
  };

  const genId = (prefix='n') => `${prefix}${state.idCounter++}`;

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
async function loadAndRenderLibrary() {
  if (!el.library) return;

  let data = null;
  try {
    const res = await fetch('/tools/api/tools', { credentials: 'same-origin' });
    if (res.ok) data = await res.json();
  } catch (_) {}

  const container = el.library;
  container.innerHTML = '';

  let categories = [];
  if (data && Array.isArray(data.categories)) {
    categories = data.categories.map(c => ({ name: c.name || c.slug || 'Category', tools: c.tools || [], count: (c.tools||[]).length }));
  } else if (data && data.categories && typeof data.categories === 'object') {
    // dict: { "CategoryName": [tools...] }
    categories = Object.entries(data.categories).map(([name, tools]) => ({
      name, tools, count: (tools||[]).length
    }));
  }

  if (!categories.length) {
    const empty = document.createElement('div');
    empty.style.cssText = 'padding:12px;color:var(--text-mute);font-size:14px;';
    empty.textContent = 'No tools found. Seed with:  flask tools seed';
    container.appendChild(empty);
    return;
  }

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
      <span class="category-count">${cat.count ?? (cat.tools?.length || 0)}</span>
      <span class="category-arrow">▾</span>
    `;
    sec.appendChild(header);

    const list = document.createElement('div');
    list.className = 'category-tools active';

    (cat.tools || []).forEach(t => {
      const item = document.createElement('div');
      item.className = 'tool-item';
      item.dataset.toolKey  = t.slug || t.key || t.name;
      item.dataset.toolName = t.name || t.slug;
      item.dataset.toolType = t.type || '';
      item.dataset.toolTime = t.time || '';
      item.dataset.toolDesc = t.desc || '';
      item.innerHTML = `
        <div class="tool-icon">${(t.name || t.slug || 'T').charAt(0).toUpperCase()}</div>
        <div class="tool-info">
          <div class="tool-name">${t.name || t.slug}</div>
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

  // attach drag handlers to freshly rendered items
  setupLibrary();
}

  // ---------- Node creation ----------
  function createNodeFromTool(toolMeta, worldX, worldY) {
    const id = genId('node_');

    const nodeEl = document.createElement('div');
    nodeEl.className = 'workflow-node';
    nodeEl.dataset.nodeId = id;
    nodeEl.innerHTML = `
      <div class="node-header">
        <div class="node-title">${toolMeta.name}</div>
        <div class="node-actions">
          <button class="node-action-btn delete" title="Delete">✕</button>
        </div>
      </div>
      <div class="node-body">
        <div class="node-icon">${toolMeta.name[0]?.toUpperCase() ?? 'T'}</div>
        <div class="node-info">
          <div class="node-description">${toolMeta.desc || ''}</div>
          <div class="node-meta">
            <span class="node-time">${toolMeta.time || ''}</span>
            <span class="node-type">${toolMeta.type || ''}</span>
          </div>
        </div>
      </div>
      <div class="connection-handles">
        <div class="connection-handle input" data-handle="input"></div>
        <div class="connection-handle output" data-handle="output"></div>
      </div>
    `;
    el.boxes.appendChild(nodeEl);

    // Cache metrics once
    const width  = nodeEl.offsetWidth;
    const height = nodeEl.offsetHeight;
    const handles = {
      input:  { ox: 0,      oy: height / 2 },
      output: { ox: width,  oy: height / 2 },
    };

    const node = {
      id, x: worldX, y: worldY, width, height, el: nodeEl, handles,
      toolKey: toolMeta.key, name: toolMeta.name, config: {},
    };
    state.nodes.set(id, node);

    // Events
    nodeEl.addEventListener('pointerdown', (e) => onNodePointerDown(e, node));
    nodeEl.querySelector('.node-action-btn.delete')?.addEventListener('click', () => {
      deleteNode(id);
      updateChainValidity();
    });
    nodeEl.querySelector('.connection-handle.input')?.addEventListener('click', (e) => onHandleClick(e, node, 'input'));
    nodeEl.querySelector('.connection-handle.output')?.addEventListener('click', (e) => onHandleClick(e, node, 'output'));

    state.needsRender = true;
    updateChainValidity();
    return node;
  }

  function deleteNode(id) {
    // remove edges attached
    [...state.edges.values()].forEach(edge => {
      if (edge.fromId === id || edge.toId === id) removeEdge(edge.id);
    });
    const node = state.nodes.get(id);
    if (node?.el?.parentNode) node.el.parentNode.removeChild(node.el);
    state.nodes.delete(id);
    state.needsRender = true;
  }

  // ---------- Edge helpers (rules/graph) ----------
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

  function wouldCreateCycle(fromId, toId) {
    // cycle if there is a path from toId back to fromId (considering new edge)
    const adj = new Map(); state.nodes.forEach((_, k) => adj.set(k, []));
    state.edges.forEach(e => adj.get(e.fromId).push(e.toId));
    adj.get(fromId).push(toId); // prospective edge

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
      if (i > 1 && !multiIn) multiIn = id;
      if (o > 1 && !multiOut) multiOut = id;
    });

    if (multiIn)  return { valid: false, reason: `Node has more than one input.` };
    if (multiOut) return { valid: false, reason: `Node has more than one output.` };
    if (starts.length !== 1) return { valid: false, reason: `Requires exactly one start node (found ${starts.length}).` };
    if (ends.length   !== 1) return { valid: false, reason: `Requires exactly one end node (found ${ends.length}).` };

    // connectivity: walk from the start along unique out-edges
    const start = starts[0];
    const nextOf = new Map();
    state.edges.forEach(e => { nextOf.set(e.fromId, e.toId); });
    const visited = new Set();
    let cur = start;
    let steps = 0;
    while (cur && steps <= n) {
      visited.add(cur);
      cur = nextOf.get(cur);
      steps++;
    }
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

  // ---------- Edge creation / deletion ----------
  function beginConnect(fromNodeId) {
    cancelConnect(); // one at a time
    // Rule: only one outbound per node
    if (outDegree(fromNodeId) >= 1) {
      showToast('Only one outbound connection allowed.');
      return;
    }
    const rubber = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    rubber.setAttribute('opacity', '0.6');
    el.svg.appendChild(rubber);
    state.connecting = { fromId: fromNodeId, rubber };
  }

  function finishConnect(toNodeId) {
    if (!state.connecting) return;
    const fromId = state.connecting.fromId;

    if (fromId === toNodeId) { cancelConnect(); return; }

    // Rule: only one inbound per node
    if (inDegree(toNodeId) >= 1) {
      showToast('Only one inbound connection allowed.');
      cancelConnect();
      return;
    }
    // Rule: no cycles
    if (wouldCreateCycle(fromId, toNodeId)) {
      showToast('This connection would create a cycle.');
      cancelConnect();
      return;
    }

    const id = genId('edge_');
    const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathEl.addEventListener('click', () => selectEdge(id));
    el.svg.appendChild(pathEl);
    state.edges.set(id, { id, fromId, toId: toNodeId, pathEl });

    el.svg.removeChild(state.connecting.rubber);
    state.connecting = null;
    state.needsRender = true;
    updateChainValidity();
  }

  function cancelConnect() {
    if (state.connecting?.rubber?.parentNode) {
      state.connecting.rubber.parentNode.removeChild(state.connecting.rubber);
    }
    state.connecting = null;
    state.needsRender = true;
  }

  function removeEdge(id) {
    const edge = state.edges.get(id);
    if (edge?.pathEl?.parentNode) edge.pathEl.parentNode.removeChild(edge.pathEl);
    if (state.selectedEdgeId === id) state.selectedEdgeId = null;
    state.edges.delete(id);
    state.needsRender = true;
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

  function inDegree(nodeId) {
    let c = 0; state.edges.forEach(e => { if (e.toId === nodeId) c++; });
    return c;
    // (fast path; for bulk queries use degreeMaps())
  }
  function outDegree(nodeId) {
    let c = 0; state.edges.forEach(e => { if (e.fromId === nodeId) c++; });
    return c;
  }

  // ---------- Node drag (Pointer Events + capture) ----------
  function onNodePointerDown(e, node) {
    // Left button only, ignore when clicking handles/buttons
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
  }

  // ---------- Handle clicks (start/finish connect) ----------
  function onHandleClick(e, node, kind) {
    e.stopPropagation();
    if (kind === 'output') {
      beginConnect(node.id);
      log(`Connecting from ${node.name}…`);
    } else if (kind === 'input' && state.connecting) {
      if (state.connecting.fromId === node.id) {
        cancelConnect();
        return;
      }
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
    let newScale = clamp(oldScale * zoomFactor, state.camera.min, state.camera.max);

    // anchor under cursor:
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

  document.addEventListener('keydown', (e) => {
    if (e.code === 'Space') el.canvas.classList.add('panning');
  });
  document.addEventListener('keyup', (e) => {
    if (e.code === 'Space') el.canvas.classList.remove('panning');
  });

  el.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
  el.canvas.addEventListener('pointerdown', onCanvasPointerDown);
  el.canvas.addEventListener('wheel', onWheelZoom, { passive: false });

  // ---------- Render loop (single rAF) ----------
  function render() {
    if (state.needsRender) {
      // Nodes
      state.nodes.forEach(node => {
        const { x, y } = worldToScreen(node.x, node.y);
        node.el.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${state.camera.scale})`;
        node.el.style.transformOrigin = `0 0`;
      });

      // Edges
      state.edges.forEach(edge => {
        const d = edgePath(edge.fromId, edge.toId);
        if (d) edge.pathEl.setAttribute('d', d);
      });

      if (state.connecting?.rubber) {
        const from = state.nodes.get(state.connecting.fromId);
        if (from) {
          const p1w = {
            x: from.x + from.handles.output.ox,
            y: from.y + from.handles.output.oy,
          };
          const p1 = worldToScreen(p1w.x, p1w.y);
          const p2 = lastMouseScreen || p1;
          const d = cubicPath(p1.x, p1.y, p2.x, p2.y);
          state.connecting.rubber.setAttribute('d', d);
        }
      }

      state.needsRender = false;
    }
    requestAnimationFrame(render);
  }

  function edgePath(fromId, toId) {
    const a = state.nodes.get(fromId);
    const b = state.nodes.get(toId);
    if (!a || !b) return null;

    const p1w = { x: a.x + a.handles.output.ox, y: a.y + a.handles.output.oy };
    const p2w = { x: b.x + b.handles.input.ox,  y: b.y + b.handles.input.oy  };
    const p1 = worldToScreen(p1w.x, p1w.y);
    const p2 = worldToScreen(p2w.x, p2w.y);

    return cubicPath(p1.x, p1.y, p2.x, p2.y);
  }
  function cubicPath(x1, y1, x2, y2) {
    const dx = Math.max(40, Math.abs(x2 - x1) * 0.35);
    const c1x = x1 + dx, c1y = y1;
    const c2x = x2 - dx, c2y = y2;
    return `M ${x1} ${y1} C ${c1x} ${c1y}, ${c2x} ${c2y}, ${x2} ${y2}`;
  }

  // Track last mouse position for rubber band
  let lastMouseScreen = null;
  el.canvas.addEventListener('pointermove', (e) => {
    const rect = el.canvas.getBoundingClientRect();
    lastMouseScreen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
    if (state.connecting) state.needsRender = true;
  });

  // Click on empty canvas cancels connection & deselect edge
  el.canvas.addEventListener('click', (e) => {
    if (e.target === el.canvas || e.target === el.content) {
      cancelConnect();
      if (state.selectedEdgeId && state.edges.get(state.selectedEdgeId)?.pathEl) {
        state.edges.get(state.selectedEdgeId).pathEl.classList.remove('selected');
      }
      state.selectedEdgeId = null;
    }
  });

  // ---------- Library drag→create ----------
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

  // ---------- Boot ----------
  async  function boot() {
    await loadAndRenderLibrary(); 
    setupLibrary();
    requestAnimationFrame(render);
    updateChainValidity?.();
    log('Chain rules active: ≤1 input & ≤1 output per node, single start & end, linear path only.');
    log('Tip: Select an edge by clicking it; press Delete to remove.');
  }

  boot();
})();
