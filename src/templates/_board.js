{# _board.js — the shared board renderer and clique helpers, included inside a
   page's <script> after it has defined: D (the record, with D.palette, D.valid,
   D.steps), ROWS, COLS, N, RS, CS, MAXPOS, CELL, WALLS, HOLES, and pr(). One
   definition for drawing cells, robots, routes with arrows, wall-contact heat,
   state thumbnails — and for the clique machinery every journey view uses:
   regions, segments, the greedy shortcut, the exact breadth-first walk. #}
  const SVGNS = "http://www.w3.org/2000/svg";
  function el(name, attrs) { const e = document.createElementNS(SVGNS, name); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }
  function makeBoard(containerId, pxCap, clickable) {
    // Scale the board up to fill the column, capped so a wide grid fits and a
    // tiny one does not balloon; the viewBox keeps the contents proportional.
    // Class "flat": these are the page's static boards; "board" is the shared
    // player's zoomable viewport and must not restyle a bare svg.
    const px = Math.min(pxCap || 880, Math.max(COLS * 32, 420));
    const svg = el("svg", { class: "flat", viewBox: "0 0 " + (COLS * CELL) + " " + (ROWS * CELL), width: px });
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
      const i = r * COLS + c;
      const wall = WALLS[i] === "1", hole = HOLES[i] === "1";
      const rect = el("rect", { x: c * CELL, y: r * CELL, width: CELL, height: CELL,
        fill: wall ? "var(--wall)" : "var(--free)", stroke: "var(--grid)", "stroke-width": 0.5 });
      if (clickable) { rect.dataset.r = r; rect.dataset.c = c; rect.style.cursor = "pointer"; }
      svg.appendChild(rect);
      if (hole) svg.appendChild(el("circle", { cx: c * CELL + CELL / 2, cy: r * CELL + CELL / 2, r: 2.4, fill: "#ffffff", opacity: 0.9 }));
    }
    const overlay = el("g", {});
    svg.appendChild(overlay);
    document.getElementById(containerId).appendChild(svg);
    return { svg, overlay };
  }
  function clearOverlay(b) { while (b.overlay.firstChild) b.overlay.removeChild(b.overlay.firstChild); }
  function markCorner(b, idx, color, radius) {
    const [r, c] = pr(idx);
    const m = el("rect", { x: c * CELL + CELL / 2 - radius, y: r * CELL + CELL / 2 - radius,
      width: radius * 2, height: radius * 2, rx: 1.5, fill: color });
    const tip = el("title", {});
    tip.textContent = "placement (" + r + ", " + c + ")";
    m.appendChild(tip);
    b.overlay.appendChild(m);
  }
  function drawRobot(b, idx, color, label, opacity) {
    // Same box and label the shared player's board() draws, so robots look
    // identical on the static boards and in the player.
    const [r, c] = pr(idx);
    b.overlay.appendChild(el("rect", { x: c * CELL, y: r * CELL, width: N * CELL, height: N * CELL,
      fill: color, "fill-opacity": opacity === undefined ? 0.85 : opacity,
      stroke: "#fff", "stroke-width": 2 }));
    if (!label) return;
    const t = el("text", { x: (c + N / 2) * CELL, y: (r + N / 2) * CELL,
      fill: "var(--label)", stroke: "rgba(0,0,0,.45)",
      "stroke-width": Math.max(0.8, CELL * 0.035), "paint-order": "stroke",
      "font-size": Math.max(11, CELL * 0.72), "font-weight": 700,
      "text-anchor": "middle", "dominant-baseline": "central" });
    t.textContent = label;
    b.overlay.appendChild(t);
  }
  const dots = b => { for (const v of D.valid) markCorner(b, v, "#374151", 2.6); };

  // A state drawn as a small picture: the whole board on a canvas, both
  // robots in place. Canvas, not SVG, so hundreds of thumbnails stay cheap.
  const stateTitle = s => "A (" + pr(Math.floor(s / MAXPOS)) + "), B (" + pr(s % MAXPOS) + ")";
  function thumb(s, mark) {
    const a = Math.floor(s / MAXPOS), b = s % MAXPOS;
    const cpx = COLS > 24 ? 4 : COLS > 14 ? 6 : 10;
    const cv = document.createElement("canvas");
    cv.width = COLS * cpx; cv.height = ROWS * cpx;
    cv.className = "thumb" + (mark ? " " + mark : "");
    cv.title = stateTitle(s);
    const ctx = cv.getContext("2d");
    for (let r = 0; r < ROWS; r++) for (let c = 0; c < COLS; c++) {
      ctx.fillStyle = WALLS[r * COLS + c] === "1" ? D.palette.wall : D.palette.free;
      ctx.fillRect(c * cpx, r * cpx, cpx, cpx);
    }
    const block = (idx, color) => {
      const rr = Math.floor(idx / CS), cc = idx % CS;
      ctx.fillStyle = color;
      ctx.fillRect(cc * cpx + 1, rr * cpx + 1, N * cpx - 2, N * cpx - 2);
    };
    block(a, D.palette.a);
    block(b, D.palette.b);
    return cv;
  }

  // ── cliques, segments, routes — shared by the trail views and the query ──
  const PIECES = new Map();
  for (const st of D.steps) PIECES.set(st.parked, st.regions.map(reg => new Set(reg)));
  const pieceIdx = (parked, cell) => {
    const ps = PIECES.get(parked) || [];
    for (let i = 0; i < ps.length; i++) if (ps[i].has(cell)) return i;
    return -1;
  };
  const sameRegion = (parked, x, y) => {
    const i = pieceIdx(parked, x);
    return i >= 0 && PIECES.get(parked)[i].has(y);
  };
  // (src, dst) state pairs — each inside one clique — to segments, merging
  // consecutive hops around the same parked robot, dropping empty ones.
  const segsFromPairs = pairs => {
    const out = [];
    for (const [src, dst] of pairs) {
      if (src === dst) continue;
      const sa = Math.floor(src / MAXPOS), sb = src % MAXPOS;
      const da = Math.floor(dst / MAXPOS), db = dst % MAXPOS;
      const parkedIsA = sa === da;
      const seg = { mover: parkedIsA ? "B" : "A", from: parkedIsA ? sb : sa,
                    to: parkedIsA ? db : da, parked: parkedIsA ? sa : sb };
      const last = out[out.length - 1];
      if (last && last.mover === seg.mover && last.parked === seg.parked) last.to = seg.to;
      else out.push(seg);
    }
    return out;
  };
  const boundaries = (s0, segs) => {
    const out = [s0];
    for (const g of segs) out.push(g.mover === "A" ? g.to * MAXPOS + g.parked : g.parked * MAXPOS + g.to);
    return out;
  };
  // The greedy shortcut: jump to the farthest later boundary one slide away.
  const shortcutSegs = (s0, segs) => {
    let cur = segs, changed = true;
    while (changed) {
      changed = false;
      const st = boundaries(s0, cur), pairs = [];
      let i = 0;
      while (i < st.length - 1) {
        let jb = i + 1;
        for (let j = st.length - 1; j > i; j--) {
          const a1 = Math.floor(st[i] / MAXPOS), b1 = st[i] % MAXPOS;
          const a2 = Math.floor(st[j] / MAXPOS), b2 = st[j] % MAXPOS;
          if ((a1 === a2 && sameRegion(a1, b1, b2)) || (b1 === b2 && sameRegion(b1, a1, a2))) {
            jb = j; break;
          }
        }
        if (jb > i + 1) changed = true;
        pairs.push([st[i], st[jb]]);
        i = jb;
      }
      cur = segsFromPairs(pairs);
    }
    return cur;
  };
  // The exact one: breadth-first over cliques, both start cliques seeded,
  // either goal clique accepted — first arrival is the minimum.
  const shortestSegs = (s0, g0) => {
    if (s0 === g0) return [];
    const sA = Math.floor(s0 / MAXPOS), sB = s0 % MAXPOS;
    const gA = Math.floor(g0 / MAXPOS), gB = g0 % MAXPOS;
    const key = c => c[0] + ":" + c[1] + ":" + c[2];
    const holdsGoal = c => c[0] === 0
      ? (c[1] === gB && PIECES.get(c[1])[c[2]].has(gA))
      : (c[1] === gA && PIECES.get(c[1])[c[2]].has(gB));
    const parentC = new Map();
    const q = [];
    let hit = null;
    for (const cid of [[0, sB, pieceIdx(sB, sA)], [1, sA, pieceIdx(sA, sB)]]) {
      const k = key(cid);
      if (parentC.has(k)) continue;
      parentC.set(k, null);
      if (holdsGoal(cid)) { hit = cid; break; }
      q.push(cid);
    }
    let qi = 0;
    while (!hit && qi < q.length) {
      const cid = q[qi++];
      const fromK = key(cid);
      for (const member of PIECES.get(cid[1])[cid[2]]) {
        const ncid = [1 - cid[0], member, pieceIdx(member, cid[1])];
        const nk = key(ncid);
        if (parentC.has(nk)) continue;
        const via = cid[0] === 0 ? member * MAXPOS + cid[1] : cid[1] * MAXPOS + member;
        parentC.set(nk, { fromK, via });
        if (holdsGoal(ncid)) { hit = ncid; break; }
        q.push(ncid);
      }
    }
    if (!hit) return null;
    const vias = [];
    let k = key(hit);
    while (parentC.get(k)) { const p = parentC.get(k); vias.push(p.via); k = p.fromK; }
    vias.reverse();
    const wp = [s0, ...vias, g0];
    const pairs = [];
    for (let i = 0; i + 1 < wp.length; i++) pairs.push([wp[i], wp[i + 1]]);
    return segsFromPairs(pairs);
  };
  // One shortest cell route per segment — the same rule the report renderer
  // applies — walked inside the mover's region around the parked robot.
  const routeCells = (parked, from, to) => {
    if (from === to) return [from];
    const region = PIECES.get(parked)[pieceIdx(parked, from)];
    const prev = new Map([[from, null]]);
    const q = [from];
    let qi = 0;
    while (qi < q.length) {
      const v = q[qi++];
      if (v === to) break;
      const r = Math.floor(v / CS), c = v % CS;
      for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const nr = r + dr, nc = c + dc;
        if (nr < 0 || nc < 0 || nr >= RS || nc >= CS) continue;
        const nv = nr * CS + nc;
        if (!region.has(nv) || prev.has(nv)) continue;
        prev.set(nv, v);
        q.push(nv);
      }
    }
    const path = [to];
    let cur = to;
    while (prev.get(cur) !== null) { cur = prev.get(cur); path.push(cur); }
    return path.reverse();
  };
  const stepCmd = (a, b) => {
    const dr = Math.floor(b / CS) - Math.floor(a / CS), dc = (b % CS) - (a % CS);
    return dr === 1 ? "D" : dr === -1 ? "U" : dc === 1 ? "R" : "L";
  };
  const segCmds = g => {
    const cells = routeCells(g.parked, g.from, g.to);
    let s = "";
    for (let i = 0; i + 1 < cells.length; i++) s += stepCmd(cells[i], cells[i + 1]);
    return s;
  };
  const pathString = segs => segs.map((g, i) => i + segCmds(g)).join(" S ");
  // Wall contacts along a segment, as the per-cell counts the shared player's
  // board() shades — the mover's faces at every route step, plus the parked
  // robot's at every step, matching the report's heat semantics.
  const segHits = g => {
    const counts = new Map();
    const addBlock = idx => {
      const r0 = Math.floor(idx / CS), c0 = idx % CS;
      for (let dr = 0; dr < N; dr++) for (let dc = 0; dc < N; dc++) {
        const r = r0 + dr, c = c0 + dc;
        for (const off of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const nr = r + off[0], nc = c + off[1];
          if (nr < 0 || nc < 0 || nr >= ROWS || nc >= COLS) continue;
          const i = nr * COLS + nc;
          if (WALLS[i] === "1") counts.set(i, (counts.get(i) || 0) + 1);
        }
      }
    };
    for (const p of routeCells(g.parked, g.from, g.to)) { addBlock(p); addBlock(g.parked); }
    return [...counts.entries()].map(([i, n]) => [Math.floor(i / COLS), i % COLS, n]);
  };
  // One player step per segment, in exactly the shape report's makePlayer
  // consumes: entry 0 the start, entry k the board after segment k with the
  // route, ghost, mover emphasis and contact shading spanning that segment.
  const playerSteps = (s0, segs) => {
    const a0 = Math.floor(s0 / MAXPOS), b0 = s0 % MAXPOS;
    const out = [{ a: pr(a0), b: pr(b0), title: "start", moves: "", path: null }];
    for (let k = 0; k < segs.length; k++) {
      const g = segs[k];
      const route = routeCells(g.parked, g.from, g.to);
      const to = pr(g.to), parked = pr(g.parked);
      const isA = g.mover === "A";
      out.push({
        a: isA ? to : parked,
        b: isA ? parked : to,
        title: (k === 0 ? "opening segment" : "switch " + String(k).padStart(2, "0")) +
          " · " + (isA ? LAB.a : LAB.b) + " moved · " + (route.length - 1) + " moves",
        moves: segCmds(g),
        path: route.map(i => [i % CS + N / 2, Math.floor(i / CS) + N / 2]),
        hits: segHits(g),
        ghost: pr(g.from),
        mover: to,
        color: isA ? "var(--arrow-a)" : "var(--arrow-b)",
        color2: isA ? "var(--a)" : "var(--b)",
      });
    }
    return out;
  };
