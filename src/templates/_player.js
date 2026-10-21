{# _player.js — THE board renderer and player, shared verbatim by the report
   pages and the solvability pages so robots, arrows, labels, viewports and
   controls are identical everywhere. Included inside a page's <script> after
   it has defined LAB ({a,b} robot labels) and CELL (default cell px). The
   page's <style> must carry the board palette variables (--wall, --free,
   --grid, --a, --b, --arrow-a, --arrow-b, --hot, --label) and the viewport
   CSS (.boardbox/.board/.boardzoom/.zoomctl/.controls), as report.html.j2
   defines them. #}
// One SVG per board, drawn straight from the wall bitstring -- no image step,
// so a frame costs a string concat rather than a matplotlib render.
// `opts.path` is the turn's waypoint centers and `opts.color` the mover's colour.
function board(walls, rows, cols, a, b, size, opts={}){
  const s = opts.cell || CELL, W = cols*s, H = rows*s, p = [];
  p.push(`<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img">`);
  for(let r=0;r<rows;r++) for(let c=0;c<cols;c++){
    const wall = walls[r*cols+c] === '1';
    p.push(`<rect x="${c*s}" y="${r*s}" width="${s}" height="${s}"
      fill="${wall?'var(--wall)':'var(--free)'}" stroke="var(--grid)" stroke-width=".5"/>`);
  }
  // Layering follows visualizer._draw_turn exactly: wall highlights, then the
  // faded ghost of where the mover started, then the robots, then the route on
  // top. Labels are drawn last -- the one deviation, so the arrow crossing a
  // square cannot hide which robot it is.
  const box = (pos, fill, op, lw) =>
    `<rect x="${pos[1]*s}" y="${pos[0]*s}" width="${size*s}" height="${size*s}"
      fill="${fill}" fill-opacity="${op}" stroke="#fff" stroke-width="${lw}"/>`;

  // Walls touched during this turn, shaded by how often (alpha .25 -> .75).
  if(opts.hits && opts.hits.length){
    const top = Math.max(...opts.hits.map(h => h[2])) || 1;
    for(const [r,c,n] of opts.hits)
      p.push(`<rect x="${c*s}" y="${r*s}" width="${s}" height="${s}" fill="var(--hot)"
        fill-opacity="${(0.25 + 0.50*(n/top)).toFixed(3)}"/>`);
  }
  if(opts.ghost) p.push(box(opts.ghost, opts.color2 || 'var(--a)', .25, 1));
  if(a) p.push(box(a, 'var(--a)', a === opts.mover ? .90 : .85, 2));
  if(b) p.push(box(b, 'var(--b)', b === opts.mover ? .90 : .85, 2));

  // The route, on top, with the head only on the final leg -- as the PNG does.
  if(opts.path && opts.path.length > 1){
    const pts = opts.path.map(([x,y]) => [x*s, y*s]);
    // Proportions taken from the PNGs rather than guessed. There ARROW_LW is 3
    // POINTS at dpi=150 on a ~105px cell, i.e. about 0.055 of a cell -- a thin
    // line, not the heavy one a naive pixel conversion produces.
    const lw = Math.max(1.5, 0.055 * size * s);
    if(pts.length > 2)
      p.push(`<polyline points="${pts.slice(0,-1).map(q=>q.join(',')).join(' ')}"
        fill="none" stroke="${opts.color}" stroke-width="${lw}" stroke-linecap="round"
        stroke-linejoin="round"/>`);
    // Head drawn as a polygon rather than a marker: marker fill cannot follow
    // the stroke colour reliably across browsers, and this scales with the robot
    // the way matplotlib's mutation_scale does.
    const [x0,y0] = pts[pts.length-2], [x1,y1] = pts[pts.length-1];
    const dx=x1-x0, dy=y1-y0, len=Math.hypot(dx,dy) || 1;
    // Head sized off the cell, not off the line width, so it stays a slim
    // triangle instead of the stubby wedge a lw-multiple gives.
    const ux=dx/len, uy=dy/len;
    const hl=Math.min(len*0.9, 0.26*size*s), hw=0.13*size*s;
    const bx=x1-ux*hl, by=y1-uy*hl;      // base of the head, back along the line
    p.push(`<line x1="${x0}" y1="${y0}" x2="${bx}" y2="${by}" stroke="${opts.color}"
      stroke-width="${lw}" stroke-linecap="butt"/>`);
    p.push(`<polygon points="${x1},${y1} ${bx-uy*hw},${by+ux*hw} ${bx+uy*hw},${by-ux*hw}"
      fill="${opts.color}"/>`);
  }

  const label = (pos, text) => pos ? `<text x="${(pos[1]+size/2)*s}"
    y="${(pos[0]+size/2)*s}" fill="var(--label)" stroke="rgba(0,0,0,.45)"
    stroke-width="${Math.max(.8,s*0.035)}" paint-order="stroke"
    font-size="${Math.max(11,s*0.72)}" font-weight="700" text-anchor="middle"
    dominant-baseline="central">${text}</text>` : '';
  p.push(label(a, LAB.a), label(b, LAB.b));
  p.push('</svg>');
  return p.join('');
}

// ── framed boards ──
// Every board is drawn into a fixed-size viewport and scaled to fit it (the CSS
// width/height on the svg override its pixel attributes, and the viewBox keeps
// the aspect). Zoom and pan are a transform on the wrapper, keyed per board, so
// a redraw -- the player stepping, the comparison re-rendering -- restores the
// view instead of resetting it.
const VIEW = {};
const view = key => VIEW[key] || (VIEW[key] = {z: 1, x: 0, y: 0});
const tf = st => `translate(${st.x}px,${st.y}px) scale(${st.z})`;

function frame(svg, {key, h=420, w=null}){
  const st = view(key);
  const size = `--bh:${h}px${w ? `;--bw:${w}px` : ''}`;
  return `<div class="boardbox${w ? '' : ' wide'}" data-zk="${key}" style="${size}">
    <div class="board"><div class="boardzoom" style="transform:${tf(st)}">${svg}</div></div>
    <div class="zoomctl"><button data-z="-" title="zoom out">&minus;</button>
      <span class="zpct">${Math.round(st.z*100)}%</span>
      <button data-z="+" title="zoom in">+</button>
      <button data-z="0" title="fit to box">fit</button>
      <span class="muted">drag to pan &middot; ctrl+wheel to zoom</span></div></div>`;
}

// Clamp so the board never leaves the box: smaller than the box it stays
// centred, larger than the box its edges never come inside the box's edges.
function applyView(box){
  const st = view(box.dataset.zk), vp = box.querySelector('.board');
  const W = vp.clientWidth, H = vp.clientHeight, cw = W*st.z, ch = H*st.z;
  st.x = cw <= W ? (W-cw)/2 : Math.min(0, Math.max(W-cw, st.x));
  st.y = ch <= H ? (H-ch)/2 : Math.min(0, Math.max(H-ch, st.y));
  box.querySelector('.boardzoom').style.transform = tf(st);
  box.querySelector('.zpct').textContent = Math.round(st.z*100) + '%';
}

// Zoom keeping the content under (cx, cy) -- box-relative -- where it is, so
// wheel zoom goes towards the pointer and button zoom towards the centre.
function zoomAt(box, factor, cx, cy){
  const st = view(box.dataset.zk);
  const nz = factor === null ? 1 : Math.max(0.25, Math.min(8, st.z*factor));
  st.x = cx - (cx - st.x) * (nz/st.z);
  st.y = cy - (cy - st.y) * (nz/st.z);
  st.z = nz;
  applyView(box);
}

// One set of delegated handlers covers every board, including those rendered
// later (the recipe player), so nothing needs wiring per instance.
document.addEventListener('click', e => {
  const b = e.target.closest('[data-z]'); if(!b) return;
  const box = b.closest('.boardbox'), vp = box.querySelector('.board');
  const f = b.dataset.z === '+' ? 1.25 : b.dataset.z === '-' ? 1/1.25 : null;
  zoomAt(box, f, vp.clientWidth/2, vp.clientHeight/2);
});
document.addEventListener('wheel', e => {
  if(!e.ctrlKey) return;
  const vp = e.target.closest('.board'); if(!vp) return;
  e.preventDefault();
  const r = vp.getBoundingClientRect();
  zoomAt(vp.closest('.boardbox'), e.deltaY < 0 ? 1.15 : 1/1.15,
         e.clientX - r.left, e.clientY - r.top);
}, {passive:false});
document.addEventListener('pointerdown', e => {
  const vp = e.target.closest('.board'); if(!vp || e.button !== 0) return;
  const box = vp.closest('.boardbox'), st = view(box.dataset.zk);
  const sx = e.clientX, sy = e.clientY, ox = st.x, oy = st.y;
  vp.setPointerCapture(e.pointerId);
  vp.classList.add('dragging');
  const move = ev => { st.x = ox + (ev.clientX - sx); st.y = oy + (ev.clientY - sy); applyView(box); };
  const up = () => {
    vp.removeEventListener('pointermove', move);
    vp.removeEventListener('pointerup', up);
    vp.removeEventListener('pointercancel', up);
    vp.classList.remove('dragging');
  };
  vp.addEventListener('pointermove', move);
  vp.addEventListener('pointerup', up);
  vp.addEventListener('pointercancel', up);
  e.preventDefault();
});
// The corner handle resizes the box; re-clamp so a zoomed board recentres.
if(window.ResizeObserver){
  const ro = new ResizeObserver(es => es.forEach(en => applyView(en.target.closest('.boardbox'))));
  document.addEventListener('pointerenter', e => {
    const vp = e.target.closest && e.target.closest('.board');
    if(vp && !vp.dataset.ro){ vp.dataset.ro = 1; ro.observe(vp); }
  }, true);
}

// A self-contained player mounted into `host`, so the main solve and any recipe
// can each have one without the controls being tied to fixed element ids. The
// frame is built once and only its contents are redrawn per step, so the zoom
// and the viewport size survive stepping.
function makePlayer(host, grid, steps, size, cell, key){
  host.innerHTML = `${frame('', {key: key || host.id || 'player', h: 440})}
    <div class="controls">
      <button data-a="prev">&larr;</button><button data-a="play">Play</button>
      <button data-a="next">&rarr;</button>
      <input type="range" min="0" value="0"><span class="muted pos"></span>
    </div><div class="muted cap"></div>`;
  const stage = host.querySelector('.boardzoom'), scrub = host.querySelector('input'),
        pos = host.querySelector('.pos'), cap = host.querySelector('.cap'),
        playBtn = host.querySelector('[data-a=play]');
  let i = 0, timer = null;
  scrub.max = steps.length - 1;
  function show(k){
    i = Math.max(0, Math.min(steps.length-1, k));
    const st = steps[i];
    stage.innerHTML = board(grid.walls, grid.rows, grid.cols, st.a, st.b, size,
      {cell, path: st.path, color: st.color, color2: st.color2,
       hits: st.hits, ghost: st.ghost, mover: st.mover});
    // The turn's own U/D/L/R sequence, so the moves behind the route are visible
    // rather than only its shape.
    cap.innerHTML = st.title
      + (st.moves ? ` &middot; <span class="seg">${st.moves}</span>` : '');
    pos.textContent = `${i} / ${steps.length-1} switches`;
    scrub.value = i;
  }
  host.querySelector('[data-a=next]').onclick = () => show(i+1);
  host.querySelector('[data-a=prev]').onclick = () => show(i-1);
  scrub.oninput = e => show(+e.target.value);
  playBtn.onclick = () => {
    if(timer){ clearInterval(timer); timer=null; playBtn.textContent='Play'; return; }
    playBtn.textContent = 'Pause';
    timer = setInterval(() => {
      if(i >= steps.length-1){ clearInterval(timer); timer=null; playBtn.textContent='Play'; return; }
      show(i+1);
    }, 700);
  };
  show(0);
  return {show, step: () => i};
}
