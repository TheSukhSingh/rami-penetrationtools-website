// Cycle checks + linear-chain validation + small helpers
import { state } from "./editor.state.js";

export function validateAllNodes() {
  const errors = [];
  state.nodes.forEach(n => {
    const tool = state.toolsById.get(n.tool_id);
    (tool.schema || []).forEach(f => {
      if (f.required && (n.config?.[f.name] === undefined || n.config?.[f.name] === "")) {
        errors.push(`Node ${tool.name}: "${f.label || f.name}" is required`);
      }
    });
    // Example: if input_method=manual then require value
    if ((n.config?.input_method || "manual") === "manual" && !n.config?.value) {
      errors.push(`Node ${tool.name}: value required when input_method=manual`);
    }
  });
  return errors;
}

export function attachValidate(editor) {
  editor.hasPath = function(startId, goalId) {
    const adj = {};
    this.connections.forEach(c => (adj[c.from] ||= []).push(c.to));
    const seen = new Set([startId]);
    const q = [startId];
    while (q.length) {
      const v = q.shift();
      if (v === goalId) return true;
      (adj[v] || []).forEach(n => { if (!seen.has(n)) { seen.add(n); q.push(n); }});
    }
    return false;
  };
  editor.pathWouldCreateCycle = function(srcId, dstId) { return this.hasPath(dstId, srcId); };

  editor.validateWorkflow = function() {
    const warnings = [];
    const ids = new Set(this.nodes.map(n => n.id));
    const inDeg = {}, outDeg = {};
    this.nodes.forEach(n => (inDeg[n.id]=0, outDeg[n.id]=0));
    this.connections.forEach(c => { if (ids.has(c.from) && ids.has(c.to)) { outDeg[c.from]++; inDeg[c.to]++; }});

    const starts = this.nodes.filter(n => inDeg[n.id] === 0);
    const ends   = this.nodes.filter(n => outDeg[n.id] === 0);
    if (starts.length !== 1) warnings.push('Workflow must have exactly one start (no incoming).');
    if (ends.length   !== 1) warnings.push('Workflow must have exactly one end (no outgoing).');

    this.nodes.forEach(n => {
      const indeg = inDeg[n.id], outdeg = outDeg[n.id];
      const ok = (indeg === 0 && outdeg === 1) || (indeg === 1 && outdeg === 1) || (indeg === 1 && outdeg === 0);
      if (!ok) warnings.push(`${n.name}: invalid degree (needs linear chain).`);
    });

    if (starts[0]) {
      const adj = {};
      this.connections.forEach(c => (adj[c.from] ||= []).push(c.to));
      const seen = new Set();
      const q = [starts[0].id];
      while (q.length) { const v = q.shift(); if (seen.has(v)) continue; seen.add(v); (adj[v]||[]).forEach(n => q.push(n)); }
      if (seen.size !== this.nodes.length) warnings.push('All nodes must form a single chain (no islands).');
    }

    const banner = document.getElementById('warningBanner');
    const text   = document.getElementById('warningText');
    if (warnings.length) { text.textContent = warnings.join(' '); banner.classList.remove('hidden'); }
    else { banner.classList.add('hidden'); }
  };
}
