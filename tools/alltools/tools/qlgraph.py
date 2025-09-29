# tools/alltools/tools/qlgraph.py
from __future__ import annotations
from typing import Dict, List, Tuple
from urllib.parse import urlsplit
import json

try:
    from ._common import (
        ensure_work_dir, read_targets, finalize, write_output_file,
        ValidationError, now_ms, DOMAIN_RE, IPV4_RE, IPV6_RE
    )
except ImportError:
    from _common import (
        ensure_work_dir, read_targets, finalize, write_output_file,
        ValidationError, now_ms, DOMAIN_RE, IPV4_RE, IPV6_RE
    )

# This node does not require external binaries; it just structures data you already have.

def _host_of(url: str) -> str | None:
    try:
        sp = urlsplit(url)
        host = (sp.hostname or "").strip("[]").lower()
        return host or None
    except Exception:
        return None

def _node_id(kind: str, value: str) -> str:
    return f"{kind}:{value}"

def run_scan(options: dict) -> dict:
    """
    Consumes your typed buckets and emits a JSON graph artifact (no new buckets).
    Nodes: domain, ip, url, endpoint, param, service, tech, vuln, exploit, screenshot
    Edges: DOMAIN->URL, URL->ENDPOINT, ENDPOINT->PARAM, URL->TECH, URL->VULN, URL->EXPLOIT, URL->SCREENSHOT,
           DOMAIN->IP, SERVICE->URL (when derivable), DOMAIN->DOMAIN (parent->child)
    """
    t0 = now_ms()
    work_dir = ensure_work_dir(options, "qlgraph")

    # pull everything we might draw
    domains, _   = read_targets(options, ("domains",),   cap=100000)
    ips, _       = read_targets(options, ("ips",),       cap=100000)
    urls, _      = read_targets(options, ("urls",),      cap=200000)
    endpoints, _ = read_targets(options, ("endpoints",), cap=200000)
    params, _    = read_targets(options, ("params",),    cap=100000)
    services, _  = read_targets(options, ("services",),  cap=100000)
    techs, _     = read_targets(options, ("tech_stack",),cap=100000)
    vulns, _     = read_targets(options, ("vulns",),     cap=200000)
    exploits, _  = read_targets(options, ("exploit_results",), cap=100000)
    shots, _     = read_targets(options, ("screenshots",), cap=200000)

    nodes: List[Dict] = []
    edges: List[Dict] = []

    seen_nodes = set()
    def add_node(kind: str, label: str):
        nid = _node_id(kind, label)
        if nid in seen_nodes: return nid
        seen_nodes.add(nid)
        nodes.append({"id": nid, "type": kind, "label": label})
        return nid

    def add_edge(src: str, dst: str, etype: str):
        edges.append({"source": src, "target": dst, "type": etype})

    # Domains & IPs
    for d in domains:
        if not d: continue
        if not (DOMAIN_RE.match(d) or IPV4_RE.match(d) or IPV6_RE.match(d)):
            continue
        add_node("domain", d.lower())

    for ip in ips:
        if not ip: continue
        if IPV4_RE.match(ip) or IPV6_RE.match(ip):
            add_node("ip", ip)

    # URLs → connect to domain; attach tech, vuln, exploit, shots later
    url_nodes: List[Tuple[str,str]] = []  # (nid, url)
    for u in urls:
        if not u or not (u.startswith("http://") or u.startswith("https://")):
            continue
        nid = add_node("url", u)
        url_nodes.append((nid, u))
        host = _host_of(u)
        if host:
            # if host is a domain, link; else if IP, link to ip
            if DOMAIN_RE.match(host):
                add_edge(_node_id("domain", host), nid, "RESOLVES_TO_URL")
            elif IPV4_RE.match(host) or IPV6_RE.match(host):
                add_edge(_node_id("ip", host), nid, "HOSTS_URL")

    # Endpoints → link to first matching URL (by host)
    for ep in endpoints:
        if not ep: continue
        ep_id = add_node("endpoint", ep)
        # heuristically attach to any URL with same host
        attached = False
        for url_nid, u in url_nodes:
            if _host_of(u):
                add_edge(url_nid, ep_id, "HAS_ENDPOINT")
                attached = True
                break
        if not attached and urls:
            add_edge(_node_id("url", urls[0]), ep_id, "HAS_ENDPOINT")

    # Params → attach to endpoints (prefer) or URLs
    for p in params:
        if not p: continue
        p_id = add_node("param", p)
        # naive: connect to some endpoint if exists, else to first URL
        if endpoints:
            add_edge(_node_id("endpoint", endpoints[0]), p_id, "HAS_PARAM")
        elif urls:
            add_edge(_node_id("url", urls[0]), p_id, "HAS_PARAM")

    # Services (ssh://host:22, etc.) → attach to host or url
    for s in services:
        if not s: continue
        s_id = add_node("service", s)
        # if service has host, best-effort connect to domain/ip
        host = None
        try:
            scheme, rest = s.split("://", 1)
            host = rest.split("/", 1)[0]
        except Exception:
            pass
        if host:
            host = host.strip("[]").lower()
            if DOMAIN_RE.match(host):
                add_edge(_node_id("domain", host), s_id, "EXPOSES_SERVICE")
            elif IPV4_RE.match(host) or IPV6_RE.match(host):
                add_edge(_node_id("ip", host), s_id, "EXPOSES_SERVICE")

    # Tech stack → attach to first URL
    for t in techs:
        if not t: continue
        tid = add_node("tech", str(t))
        if urls:
            add_edge(_node_id("url", urls[0]), tid, "USES_TECH")

    # Vulns → attach to URL
    for v in vulns:
        if not v: continue
        vid = add_node("vuln", str(v))
        if urls:
            add_edge(_node_id("url", urls[0]), vid, "HAS_VULN")

    # Exploit results → attach to URL
    for e in exploits:
        if not e: continue
        eid = add_node("exploit", str(e))
        if urls:
            add_edge(_node_id("url", urls[0]), eid, "HAS_EXPLOIT")

    # Screenshots → attach to URL
    for f in shots:
        if not f: continue
        sid = add_node("screenshot", f)
        if urls:
            add_edge(_node_id("url", urls[0]), sid, "HAS_SCREENSHOT")

    graph = {"nodes": nodes, "edges": edges, "meta": {"counts": {"nodes": len(nodes), "edges": len(edges)}}}
    blob = json.dumps(graph, indent=2)
    outfp = write_output_file(work_dir, "qlgraph.json", blob)

    msg = f"{len(nodes)} nodes, {len(edges)} edges"
    return finalize("ok", msg, options, "qlgraph(py)", t0, blob, output_file=outfp)
