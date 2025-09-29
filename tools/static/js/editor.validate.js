// tools/static/js/editor.validate.js
// Compatibility-matrix + cycle checks + friendly banner warnings

export function attachValidate(editor) {
  // --- helpers ----------------------------------------------------
  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));

  function getIO(slug) {
    // tool meta comes from /tools/api/tools (attached in editor.view.js)
    // expect { io_policy: { consumes:[], emits:[] } }
    const meta = editor.toolMetaBySlug?.[slug] || {};
    const io = meta.io_policy || meta.io || {};
    const consumes = Array.isArray(io.consumes) ? io.consumes : [];
    const emits = Array.isArray(io.emits) ? io.emits : [];
    return { consumes, emits };
  }

  function bucketCompat(fromSlug, toSlug) {
    const { emits } = getIO(fromSlug);
    const { consumes } = getIO(toSlug);
    // If IO policy is missing on either side, don't *hard* block here:
    // we'll warn in validateWorkflow(), but allow edge so the user can fix.
    if (!emits.length || !consumes.length) return { ok: true, overlap: [] };
    const overlap = emits.filter((b) => consumes.includes(b));
    return { ok: overlap.length > 0, overlap };
  }

  // --- structural checks ------------------------------------------
  editor.hasPath = function (startId, goalId) {
    const adj = {};
    this.connections.forEach((c) => (adj[c.from] ||= []).push(c.to));
    const seen = new Set([startId]);
    const q = [startId];
    while (q.length) {
      const v = q.shift();
      if (v === goalId) return true;
      (adj[v] || []).forEach((n) => {
        if (!seen.has(n)) {
          seen.add(n);
          q.push(n);
        }
      });
    }
    return false;
  };

  editor.pathWouldCreateCycle = function (srcId, dstId) {
    return this.hasPath(dstId, srcId);
  };

  // Edge guard the DnD layer can call before creating a connection
  editor.allowedEdge = function (fromNode, toNode) {
    if (fromNode.id === toNode.id) return { ok: false, reason: "Can't connect a node to itself" };
    if (fromNode.type === "end") return { ok: false, reason: "Cannot output from an End node" };
    if (toNode.type === "start") return { ok: false, reason: "Cannot input into a Start node" };
    if (this.pathWouldCreateCycle?.(fromNode.id, toNode.id)) return { ok: false, reason: "Would create a cycle" };

    const bc = bucketCompat(fromNode.tool_slug, toNode.tool_slug);
    if (!bc.ok) {
      const ioFrom = getIO(fromNode.tool_slug);
      const ioTo = getIO(toNode.tool_slug);
      return {
        ok: false,
        reason: `${fromNode.name} → ${toNode.name} has no compatible buckets (emits: ${ioFrom.emits.join(", ") || "∅"} / consumes: ${ioTo.consumes.join(", ") || "∅"})`,
      };
    }
    return { ok: true, reason: "" };
  };

  // Run full validation and show/hide the yellow banner
  editor.validateWorkflow = function () {
    const warnings = [];

    // Degrees (simple linear chain expectation)
    const ids = new Set(this.nodes.map((n) => n.id));
    const inDeg = {};
    const outDeg = {};
    this.nodes.forEach((n) => ((inDeg[n.id] = 0), (outDeg[n.id] = 0)));
    this.connections.forEach((c) => {
      if (ids.has(c.from) && ids.has(c.to)) {
        outDeg[c.from]++;
        inDeg[c.to]++;
      }
    });

    const starts = this.nodes.filter((n) => inDeg[n.id] === 0);
    const ends = this.nodes.filter((n) => outDeg[n.id] === 0);
    if (starts.length !== 1) warnings.push("Workflow must have exactly one start (no incoming).");
    if (ends.length !== 1) warnings.push("Workflow must have exactly one end (no outgoing).");

    this.nodes.forEach((n) => {
      const indeg = inDeg[n.id],
        outdeg = outDeg[n.id];
      const ok =
        (indeg === 0 && outdeg === 1) || // head
        (indeg === 1 && outdeg === 1) || // middle
        (indeg === 1 && outdeg === 0); // tail
      if (!ok) warnings.push(`${n.name}: invalid degree (needs linear chain).`);
    });

    // Reachability (single chain, no islands)
    if (starts[0]) {
      const adj = {};
      this.connections.forEach((c) => (adj[c.from] ||= []).push(c.to));
      const seen = new Set();
      const q = [starts[0].id];
      while (q.length) {
        const v = q.shift();
        if (seen.has(v)) continue;
        seen.add(v);
        (adj[v] || []).forEach((n) => q.push(n));
      }
      if (seen.size !== this.nodes.length) warnings.push("All nodes must form a single chain (no islands).");
    }

    // Bucket compatibility for every edge
    this.connections.forEach((e) => {
      const from = this.nodes.find((n) => n.id === e.from);
      const to = this.nodes.find((n) => n.id === e.to);
      if (!from || !to) return;
      const { ok, overlap } = bucketCompat(from.tool_slug, to.tool_slug);
      if (!ok) {
        warnings.push(`${from.name} → ${to.name} has no compatible buckets.`);
      } else if (overlap.length) {
        // Optional: show what bucket(s) will flow
        // warnings.push(`${from.name} → ${to.name} via [${overlap.join(", ")}]`);
      }
    });

    // Missing IO policy on any node (soft warning)
    this.nodes.forEach((n) => {
      const io = getIO(n.tool_slug);
      if (!io.emits.length && !io.consumes.length) {
        warnings.push(`${n.name}: missing IO policy in catalog; check tool policy.`);
      }
    });

    // Paint banner
    const banner = document.getElementById("warningBanner");
    const text = document.getElementById("warningText");
    if (banner && text) {
      if (warnings.length) {
        text.innerHTML = warnings.map(esc).join("<br>");
        banner.classList.remove("hidden");
      } else {
        banner.classList.add("hidden");
        text.textContent = "";
      }
    }
    return warnings;
  };
}
