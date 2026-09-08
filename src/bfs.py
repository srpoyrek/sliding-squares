"""
bfs.py
------
Core BFS logic for the sliding squares problem.

Public API:
    flood_fill            — all positions the current robot can reach without switching
    bfs                   — unidirectional layered BFS (forward only)
    bfs_mirror            — single-tree layered BFS using the A<->B relabelling
    bfs_bidirectional     — bidirectional layered BFS (forward + backward in lockstep)

All three BFS entry points share the same per-layer expansion helper
`_expand_layer` and the same flood-fill cache, so memoization carries across
halves inside a single bidirectional run.

State = (pos_a, pos_b, ctrl) — ctrl is the robot that just moved.
Parent tuple convention (unified across fwd and bwd): (prev_state, target_idx, mover)
    - prev_state None ⇒ this state is at layer 0 (no preceding switch).
    - target_idx      is the mover's end-of-segment placement as a sid index,
                      row * col_span + col — the unit `flood_fill` returns, so
                      no (row, col) tuple is built on the hot path.
    - mover           is the Robot that moved in this segment.
"""

from __future__ import annotations

from collections import deque

from src.lru import LRUCache
from src.state import State
from src.visualizer import draw_bfs_frontier
from src.workspace import COMMANDS, DIRECTIONS

# ---------------------------------------------------------------------------
# Memoization caches — shared between unidirectional and bidirectional BFS.
# Keys include `free_key` — an int bitmask where bit (r*cols + c) is 1 iff
# cell (r, c) is free — so each cache entry is a pure function of its inputs.
# No per-solve clearing is required: entries remain valid across any number
# of solve calls on any grid topology, and LRU bounds control memory.
#
# _VALID_POS_CACHE   key: (free_key, n)                          -> BitGrid of valid placements
# _USABLE_CACHE      key: (free_key, pos_static, n)              -> BitGrid of usable placements
#
# Placement sets are BitGrids (src/bitgrid.py) throughout — one bit per
# placement in the placement index space (row * col_span + col, the same
# flattening the packed state ids use), never a set of (row, col) tuples. The
# free_key is the grid's own free BitGrid, so it is always current.
# _REACH_CACHE       key: (free_key, pos_static, n, pos_moving)  -> reachable placements,
#                         a tuple of sid indices (row * col_span + col)
#
# The reach cache holds the *set* a flood reaches and nothing else. The parent
# map that produced it is not kept: a search asks for thousands of floods, and
# only path reconstruction ever reads a parent map — one per segment of the
# answer — so caching one for every flood made this cache the bulk of a solve's
# memory, spent on data that was never read. `_parent_map` recomputes the few
# that are.
# ---------------------------------------------------------------------------
_VALID_POS_CACHE: LRUCache = LRUCache(maxsize=1024)
_USABLE_CACHE: LRUCache = LRUCache(maxsize=4096)
_REACH_CACHE: LRUCache = LRUCache(maxsize=8192)

# ── Cache-sizing model (used by configure_caches_for_grid) ──────────────────
# Every cache entry holds O(valid block positions) cells, so its byte cost is
# modelled as  slope * valid_positions + base.  A reach entry is a tuple of
# ints — one pointer per placement plus the int object where the index is too
# large to be interned. A valid or usable entry is one to three bitmasks, a
# bit per placement each, so its slope is a fraction of a byte and those two
# caches are cheap enough that their caps rarely bind. Numbers are coarse RAM
# estimates; they only need to be the right order of magnitude — the runtime
# MemoryGuard is the actual safety net.
_REACH_ENTRY_BYTES_PER_CELL = 40
_MASK_ENTRY_BYTES_PER_CELL = 0.5
_ENTRY_BYTES_OVERHEAD = 200

# How the per-worker byte budget is split across the three caches. The reach
# cache takes the most lookups, so it gets the lion's share.
_REACH_BUDGET_SHARE = 0.70
_USABLE_BUDGET_SHARE = 0.25
_VALID_BUDGET_SHARE = 0.05

# Smallest cap allowed per cache. Caching is pure memoization, so a small cap
# only means more recomputation — never a wrong answer. Reach entries are
# small, so their floor can be generous; the set caches stay tight because one
# entry on a large grid is already sizeable.
_REACH_MIN_ENTRIES = 256
_USABLE_MIN_ENTRIES = 16
_VALID_MIN_ENTRIES = 8


def configure_caches_for_grid(rows: int, cols: int, n: int, target_mb: int = 150) -> None:
    """Resize module-level LRU caches so total memory scales with grid area.

    Each reach / usable / valid_pos entry stores O(valid_positions) cells;
    per-entry size grows roughly linearly with grid area. At a fixed cache
    count, 30x30 uses ~50x more memory than 4x4. This sizes the caps so the
    per-worker footprint stays near `target_mb`.
    """
    global _VALID_POS_CACHE, _USABLE_CACHE, _REACH_CACHE
    valid_positions = max(1, (rows - n + 1) * (cols - n + 1))
    reach_bytes_per_entry = valid_positions * _REACH_ENTRY_BYTES_PER_CELL + _ENTRY_BYTES_OVERHEAD
    mask_bytes_per_entry = valid_positions * _MASK_ENTRY_BYTES_PER_CELL + _ENTRY_BYTES_OVERHEAD

    budget_bytes = target_mb * 1024 * 1024

    reach_cap = max(
        _REACH_MIN_ENTRIES, int(budget_bytes * _REACH_BUDGET_SHARE / reach_bytes_per_entry)
    )
    usable_cap = max(
        _USABLE_MIN_ENTRIES, int(budget_bytes * _USABLE_BUDGET_SHARE / mask_bytes_per_entry)
    )
    valid_cap = max(
        _VALID_MIN_ENTRIES, int(budget_bytes * _VALID_BUDGET_SHARE / mask_bytes_per_entry)
    )

    _VALID_POS_CACHE = LRUCache(maxsize=valid_cap)
    _USABLE_CACHE = LRUCache(maxsize=usable_cap)
    _REACH_CACHE = LRUCache(maxsize=reach_cap)


def shrink_caches(factor: float = 0.5) -> None:
    """Escalating lossless relief: scale every LRU cap by `factor` and evict
    down. Entries are pure memoization, so this only forces recomputation."""
    _VALID_POS_CACHE.set_maxsize(int(_VALID_POS_CACHE.maxsize * factor))
    _USABLE_CACHE.set_maxsize(int(_USABLE_CACHE.maxsize * factor))
    _REACH_CACHE.set_maxsize(int(_REACH_CACHE.maxsize * factor))


_INVERSE_CMD = {"U": "D", "D": "U", "L": "R", "R": "L"}


def _clear_caches():
    _USABLE_CACHE.clear()
    _REACH_CACHE.clear()
    _VALID_POS_CACHE.clear()


# ---------------------------------------------------------------------------
# Flood fill
# ---------------------------------------------------------------------------


def _original_flood_fill(usable, pos_moving) -> dict:
    """Queue BFS inside one robot's reach (other robot static). Returns a
    parent_map {pos: (prev_pos, cmd_to_reach_pos)}; cmd paths are rebuilt
    lazily by callers.

    Used only where parent pointers are wanted — `_parent_map`, for turning a
    finished path's segments into moves. The search itself asks `flood_fill`
    for the reachable *set*, which `BitGrid.flood` computes bit-parallel.
    `usable` is a BitGrid; its membership test bounds-checks before forming
    an index, so off-grid neighbours fall out naturally.
    """
    parent_map = {pos_moving: (None, None)}
    queue = deque([pos_moving])
    while queue:
        pos = queue.popleft()
        row, col = pos
        for name, (dr, dc) in DIRECTIONS.items():
            npos = (row + dr, col + dc)
            if npos in parent_map:
                continue
            if npos not in usable:
                continue
            parent_map[npos] = (pos, name)  # type: ignore
            queue.append(npos)
    return parent_map


def _cmds_from_parent_map(parent_map: dict, pos_moving, target) -> list:
    """Walk parent_map from target back to pos_moving to rebuild the cmd list."""
    cmds = []
    curr = target
    while curr != pos_moving:
        curr, cmd = parent_map[curr]
        cmds.append(cmd)
    cmds.reverse()
    return cmds


def _workspace_free_key(workspace) -> int:
    """The grid's free-cell bitmask — the value every cache keys on.

    It is the grid's own storage, not a derived copy, so it is always current:
    a caller that swaps the free set (the dig search does, once per candidate)
    has nobody to notify.
    """
    return workspace.grid.free.bits


def _geometry(workspace, n: int):
    """(col_span, pos_stride) for index-based state ids — the same numbers
    `_make_packers` derives, so an index from `flood_fill` slots straight into
    a sid with one multiply-add and no (row, col) round trip."""
    col_span = workspace.grid.cols - n + 1
    row_span = workspace.grid.rows - n + 1
    return col_span, row_span * col_span * 2


def _usable(workspace, pos_static, n):
    """The n x n placements the moving robot may occupy while the other stands
    at `pos_static`: every valid placement that does not overlap it, as a
    BitGrid in placement space. Cached per (grid, static position, n); the
    valid placements beneath it per (grid, n).

    Valid placements are one erosion of the grid's free cells — n*n shifts of
    the whole grid, not n*n tests per placement. The usable set is that minus
    the overlap block: two n x n squares overlap exactly when both offsets are
    below n, so the placements colliding with the parked robot are a
    (2n-1) x (2n-1) rectangle of placement indices around it, clipped to the
    grid, and `rect` clears it in a handful of shifts.
    """
    free = workspace.grid.free
    valid_key = (free.bits, n)
    valid = _VALID_POS_CACHE.get(valid_key)
    if valid is None:
        valid = free.erode_window(n)
        _VALID_POS_CACHE[valid_key] = valid

    usable_key = (free.bits, pos_static, n)
    usable = _USABLE_CACHE.get(usable_key)
    if usable is None:
        sr, sc = pos_static
        usable = valid - valid.rect(sr - n + 1, sc - n + 1, 2 * n - 1, 2 * n - 1)
        _USABLE_CACHE[usable_key] = usable
    return usable


def flood_fill(workspace, pos_moving, pos_static, n) -> tuple:
    """Every placement the moving robot can reach from `pos_moving` without a
    switch, with the other robot standing at `pos_static`.

    Returned as a tuple of sid *indices* — ``row * col_span + col`` with
    ``col_span = cols - n + 1``, the flattening the packed state ids already
    use — so an expansion turns each into a successor id with one multiply-add
    and never materialises a (row, col) tuple on the hot path.

    Only this set is cached. The parent map behind it is not: a search asks
    for thousands of floods and path reconstruction reads a parent map for a
    handful of segments, once, at the end. Keeping one for every flood made
    this cache the bulk of a solve's memory for data that was never read.
    `_parent_map` recomputes the few that are.
    """
    usable = _usable(workspace, pos_static, n)
    key = (_workspace_free_key(workspace), pos_static, n, pos_moving)
    reach = _REACH_CACHE.get(key)
    if reach is None:
        reach = usable.flood(usable.index(*pos_moving)).indices()
        _REACH_CACHE[key] = reach
    return reach


def _parent_map(workspace, pos_moving, pos_static, n) -> dict:
    """The flood from `pos_moving` with its parent pointers, for turning one
    segment of a finished path into moves. Deliberately uncached: it is asked
    for once per segment of the answer, and caching it for every flood is what
    made the flood cache the dominant consumer of memory."""
    return _original_flood_fill(_usable(workspace, pos_static, n), pos_moving)


# ---------------------------------------------------------------------------
# Shared expansion + reconstruction primitives
# ---------------------------------------------------------------------------
#
# direction='fwd': successors.  The OTHER robot (not ctrl) floods from its
#                  position; the new state's ctrl becomes that mover.
# direction='bwd': predecessors. The CURRENT ctrl floods from its position
#                  (to find where it came from); the predecessor's ctrl is
#                  the OTHER robot.
#
# Hot-path state representation: each BFS node is a packed int `sid` rather
# than a State tuple. sid = ai * pos_stride + bi * 2 + ctrl_bit, where
# ai, bi flatten (row, col) via `row * col_span + col` and ctrl_bit is 0
# for robot_a, 1 for robot_b. Hashing an int is an order of magnitude
# cheaper than tuple-of-tuples; sid values are reconstructed back to
# (pos_a, pos_b, ctrl) via `unpack` only when reconstruction asks for them.


def _make_packers(workspace, n: int):
    """Closure pair (pack, unpack) converting between (pos_a, pos_b, ctrl) and sid."""
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    col_span = workspace.grid.cols - n + 1
    row_span = workspace.grid.rows - n + 1
    max_pos = row_span * col_span
    pos_stride = max_pos * 2

    def pack(pos_a, pos_b, ctrl):
        ai = pos_a[0] * col_span + pos_a[1]
        bi = pos_b[0] * col_span + pos_b[1]
        c = 0 if ctrl is robot_a else 1
        return ai * pos_stride + bi * 2 + c

    def unpack(sid):
        c = sid & 1
        rest = sid >> 1
        bi = rest % max_pos
        ai = rest // max_pos
        return (
            (ai // col_span, ai % col_span),
            (bi // col_span, bi % col_span),
            robot_a if c == 0 else robot_b,
        )

    return pack, unpack


def _expand_one(workspace, sid, pack, unpack, n: int, direction: str):
    pos_a, pos_b, ctrl = unpack(sid)
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    other_ctrl = robot_b if ctrl is robot_a else robot_a

    if direction == "fwd":
        mover = other_ctrl
        new_ctrl = mover
    else:
        mover = ctrl
        new_ctrl = other_ctrl

    if mover is robot_a:
        mover_pos, static_pos = pos_a, pos_b
    else:
        mover_pos, static_pos = pos_b, pos_a

    reach = flood_fill(workspace, mover_pos, static_pos, n)
    col_span, pos_stride = _geometry(workspace, n)
    ctrl_bit = 0 if new_ctrl is robot_a else 1
    # The reach is already in sid index units, so a successor id is one
    # multiply-add; the static robot's half of the id is fixed for the loop.
    if mover is robot_a:
        fixed = (pos_b[0] * col_span + pos_b[1]) * 2 + ctrl_bit
        for idx in reach:
            yield idx * pos_stride + fixed, idx, mover
    else:
        fixed = (pos_a[0] * col_span + pos_a[1]) * pos_stride + ctrl_bit
        for idx in reach:
            yield fixed + idx * 2, idx, mover


def _successor_sids(workspace, sid, pack, unpack, n: int, direction: str):
    """Lean successor generator for the switch-count-only path: yields just the
    packed successor sid (no target / mover). Lets the caller expand a layer
    without building parent pointers — which exist only for path reconstruction.
    Mirrors _expand_one minus the per-successor tuple."""
    pos_a, pos_b, ctrl = unpack(sid)
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    other_ctrl = robot_b if ctrl is robot_a else robot_a

    if direction == "fwd":
        mover = other_ctrl
        new_ctrl = mover
    else:
        mover = ctrl
        new_ctrl = other_ctrl

    if mover is robot_a:
        mover_pos, static_pos = pos_a, pos_b
    else:
        mover_pos, static_pos = pos_b, pos_a

    reach = flood_fill(workspace, mover_pos, static_pos, n)
    col_span, pos_stride = _geometry(workspace, n)
    ctrl_bit = 0 if new_ctrl is robot_a else 1
    if mover is robot_a:
        fixed = (pos_b[0] * col_span + pos_b[1]) * 2 + ctrl_bit
        for idx in reach:
            yield idx * pos_stride + fixed
    else:
        fixed = (pos_a[0] * col_span + pos_a[1]) * pos_stride + ctrl_bit
        for idx in reach:
            yield fixed + idx * 2


def _expand_layer(
    workspace,
    frontier,
    visited: dict,
    parent: dict,
    layer: int,
    n: int,
    direction: str,
    pack,
    unpack,
    build_parent: bool = True,
):
    """Expand one BFS layer. Mutates visited (and parent, when build_parent is
    True); returns the new frontier set of sids.

    build_parent=False is the switch-count-only fast path: it skips the parent
    pointers — used only for path reconstruction — and the per-successor tuple,
    saving two allocations and a dict insert on every expanded state."""
    new_frontier = set()
    if build_parent:
        for sid in frontier:
            for new_sid, target_pos, mover in _expand_one(
                workspace, sid, pack, unpack, n, direction
            ):
                if new_sid in visited:
                    continue
                visited[new_sid] = layer
                parent[new_sid] = (sid, target_pos, mover)
                new_frontier.add(new_sid)
    else:
        for sid in frontier:
            for new_sid in _successor_sids(workspace, sid, pack, unpack, n, direction):
                if new_sid in visited:
                    continue
                visited[new_sid] = layer
                new_frontier.add(new_sid)
    return new_frontier


def _seed_fwd(workspace, initial_ctrls, pack, build_parent: bool = True) -> dict:
    """Build forward layer-0 frontier by flooding each initial controller from start.

    Returns {"visited", "parent", "frontier"} where keys are sids; parent tuples
    use (None, target_pos, mover) for layer-0 states (no predecessor). When
    build_parent is False the parent map is left empty (switch-count-only path).
    """
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    start_a = robot_a.position()
    start_b = robot_b.position()
    col_span, pos_stride = _geometry(workspace, n)
    visited: dict = {}
    parent: dict = {}
    frontier: set = set()
    for ic in initial_ctrls:
        if ic is robot_a:
            fixed = (start_b[0] * col_span + start_b[1]) * 2  # ctrl bit 0 = robot_a
            for idx in flood_fill(workspace, start_a, start_b, n):
                sid = idx * pos_stride + fixed
                if sid not in visited:
                    visited[sid] = 0
                    if build_parent:
                        parent[sid] = (None, idx, robot_a)
                    frontier.add(sid)
        else:
            fixed = (start_a[0] * col_span + start_a[1]) * pos_stride + 1  # ctrl bit 1
            for idx in flood_fill(workspace, start_b, start_a, n):
                sid = fixed + idx * 2
                if sid not in visited:
                    visited[sid] = 0
                    if build_parent:
                        parent[sid] = (None, idx, robot_b)
                    frontier.add(sid)
    return {"visited": visited, "parent": parent, "frontier": frontier}


def _seed_bwd(workspace, goal_a, goal_b, final_ctrls, pack, build_parent: bool = True) -> dict:
    """Build backward layer-0: the two goal sids (one per possible final ctrl)."""
    visited: dict = {}
    parent: dict = {}
    frontier: set = set()
    for fc in final_ctrls:
        sid = pack(goal_a, goal_b, fc)
        if sid not in visited:
            visited[sid] = 0
            if build_parent:
                parent[sid] = None
            frontier.add(sid)
    return {"visited": visited, "parent": parent, "frontier": frontier}


def _reconstruct_fwd(parent: dict, end_sid, workspace, unpack) -> list:
    """Walk fwd parent-chain from end_sid back through layer 0. Returns cmd list
    in forward order (start -> end state)."""
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    start_a = robot_a.position()
    start_b = workspace.robot_b.position()
    col_span, _ = _geometry(workspace, n)

    path = []
    sid = end_sid
    while sid in parent:
        prev_sid, target_idx, mover = parent[sid]
        if mover is None:
            break
        if prev_sid is None:
            source_pos = start_a if mover is robot_a else start_b
            static_pos = start_b if mover is robot_a else start_a
        else:
            prev_pa, prev_pb, _ = unpack(prev_sid)
            if mover is robot_a:
                source_pos, static_pos = prev_pa, prev_pb
            else:
                source_pos, static_pos = prev_pb, prev_pa
        pm = _parent_map(workspace, source_pos, static_pos, n)
        cmds = _cmds_from_parent_map(pm, source_pos, divmod(target_idx, col_span))
        for cmd in reversed(cmds):
            path.append(cmd)
        if prev_sid is not None:
            path.append(COMMANDS["CONTROL_SWITCH"])
        if prev_sid is None:
            break
        sid = prev_sid
    path.reverse()
    return path


def _initial_mover(parent: dict, end_sid):
    """The robot that moved in the layer-0 segment of the path ending at
    `end_sid`, or None if there is no such chain.

    Every search reports this alongside the path, because a command string
    cannot be replayed without it: commands name no robot, so a replay has to
    be told who holds control at step 0 and then follows the switches. Reading
    it off the first *move* command instead is wrong whenever the layer-0
    segment is empty — the path then opens with a switch, and the first robot
    to move is the second to hold control.
    """
    sid = end_sid
    while True:
        entry = parent.get(sid)
        if not entry:
            return None
        prev_sid, _target_pos, mover = entry
        if prev_sid is None:
            return mover
        sid = prev_sid


def _reconstruct_bwd(bwd_parent: dict, meeting_sid, workspace, unpack) -> list:
    """Walk bwd parent from meeting forward-in-time to goal. Returns cmd list."""
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    col_span, _ = _geometry(workspace, n)
    path = []
    sid = meeting_sid
    while True:
        bp = bwd_parent.get(sid)
        if bp is None:
            break
        next_sid, new_idx, mover = bp
        next_pa, next_pb, _ = unpack(next_sid)
        if mover is robot_a:
            flood_root = next_pa
            static_pos = next_pb
        else:
            flood_root = next_pb
            static_pos = next_pa
        pm = _parent_map(workspace, flood_root, static_pos, n)
        cmds = []
        curr = divmod(new_idx, col_span)
        while curr != flood_root:
            prev_pos, cmd = pm[curr]
            cmds.append(_INVERSE_CMD[cmd])
            curr = prev_pos
        path.append(COMMANDS["CONTROL_SWITCH"])
        path.extend(cmds)
        sid = next_sid
    return path


# ---------------------------------------------------------------------------
# A<->B relabelling — the symmetry bfs_mirror runs on
# ---------------------------------------------------------------------------


def _make_mirror(workspace, n: int):
    """Closure mapping a packed sid to the sid of its A<->B relabelling.

    `pack` lays a state out as ai * pos_stride + bi * 2 + ctrl_bit, so
    exchanging the robots is exchanging the two position fields and flipping
    the control bit — one divmod, no (row, col) tuples materialised.
    """
    col_span = workspace.grid.cols - n + 1
    row_span = workspace.grid.rows - n + 1
    max_pos = row_span * col_span
    pos_stride = max_pos * 2

    def mirror(sid):
        ai, bi = divmod(sid >> 1, max_pos)
        return bi * pos_stride + ai * 2 + (1 - (sid & 1))

    return mirror


def _fwd_segments(parent: dict, end_sid, workspace, unpack) -> list:
    """The path to `end_sid` as segments, in forward order.

    A segment is ``(mover, source_pos, static_pos, target_pos)`` — one robot
    walking while the other stands still. Producing segments rather than
    commands lets the two halves of a mirrored solve be joined *before* either
    is turned into moves, which is what keeps the join move-minimal.
    """
    robot_a = workspace.robot_a
    start_a = robot_a.position()
    start_b = workspace.robot_b.position()
    col_span, _ = _geometry(workspace, robot_a.n)

    segments = []
    sid = end_sid
    while True:
        entry = parent.get(sid)
        if not entry:
            break
        prev_sid, target_idx, mover = entry
        if mover is None:
            break
        if prev_sid is None:
            source_pos = start_a if mover is robot_a else start_b
            static_pos = start_b if mover is robot_a else start_a
        else:
            prev_pa, prev_pb, _ = unpack(prev_sid)
            if mover is robot_a:
                source_pos, static_pos = prev_pa, prev_pb
            else:
                source_pos, static_pos = prev_pb, prev_pa
        segments.append((mover, source_pos, static_pos, divmod(target_idx, col_span)))
        if prev_sid is None:
            break
        sid = prev_sid
    segments.reverse()
    return segments


def _mirror_segments(parent: dict, mirror_sid, workspace, unpack) -> list:
    """Second half of a mirrored solve, as segments.

    It is the route to the meeting state's label-swapped twin, run backwards
    with the robots exchanged: each segment keeps the squares it walks over and
    the obstacle it walks around, but is driven by the other robot and travelled
    in the opposite direction — so source and target swap and the mover flips.
    """
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    swapped = []
    for mover, source_pos, static_pos, target_pos in _fwd_segments(
        parent, mirror_sid, workspace, unpack
    ):
        other = robot_b if mover is robot_a else robot_a
        swapped.append((other, target_pos, static_pos, source_pos))
    swapped.reverse()
    return swapped


def _join_at_meeting(head: list, tail: list) -> list:
    """Splice the two halves of a mirrored solve into one segment list.

    The halves meet inside a single segment, not between two: the first half
    walks a robot *into* the meeting square and the second walks the same robot
    *out* of it, around the same stationary partner. Left as two segments the
    path detours through the meeting square — which costs moves the solution
    does not need, and would also imply a switch that is not there, inflating
    the count. Merged, the robot goes straight from where it set off to where it
    ends up.
    """
    if not head or not tail:
        return head + tail
    mover, source_pos, static_pos, _ = head[-1]
    tail_mover, _, tail_static, tail_target = tail[0]
    if mover is not tail_mover or static_pos != tail_static:
        raise AssertionError(
            "mirrored halves do not meet inside one segment; the label swap or "
            "the meeting test is wrong"
        )
    return head[:-1] + [(mover, source_pos, static_pos, tail_target)] + tail[1:]


def _render_segments(segments: list, workspace, n: int) -> list:
    """Segments to a command list, one shortest route per segment, switches
    between them. Each route is a fresh flood fill, so a segment that was
    spliced together is re-planned rather than concatenated."""
    path = []
    for index, (_mover, source_pos, static_pos, target_pos) in enumerate(segments):
        if index:
            path.append(COMMANDS["CONTROL_SWITCH"])
        pm = _parent_map(workspace, source_pos, static_pos, n)
        path.extend(_cmds_from_parent_map(pm, source_pos, target_pos))
    return path


# ---------------------------------------------------------------------------
# bfs_mirror — one forward tree; the backward half is that tree, relabelled
# ---------------------------------------------------------------------------


def bfs_mirror(workspace, goal_a, goal_b, need_path=True):
    """Layered BFS over a single forward tree, using the A<->B relabelling.

    Requires the goal to be the start with the robots exchanged (`goal_a` is
    robot B's start, `goal_b` is robot A's start) and raises otherwise; any
    other goal has to go through `bfs_bidirectional`.

    Exchanging the two labels is a symmetry of *every* workspace — the squares
    are identical and the grid does not move — and under it the goal set is
    the image of the start set. The backward half of a bidirectional run is
    therefore the forward half relabelled: the states l switches from the goal
    are exactly the relabelling of the states l switches from the start, at
    every l, so the two trees are the same size at every layer. One tree
    suffices — a state's distance to the goal is read out of the same
    `visited` map by looking up its relabelling — and the tree, its parent
    pointers and its frontier are built once instead of twice.

    Layer h makes exactly two totals newly reachable: 2h-1 (relabelling one
    layer back) and 2h (relabelling in this layer). The whole layer is scanned
    and the smallest total taken before the layer is left, which is what keeps
    the result minimal — arriving at layer h with nothing found already proves
    the optimum is at least 2h-1, so the first total found here is that
    optimum.

    The two halves are joined as segments and only then turned into moves. They
    meet *inside* a segment — one robot walks into the meeting square and the
    same robot walks back out of it — so rendering each half separately would
    route the solution through that square and spend moves the answer does not
    need. Merging first and planning the joined segment once keeps the path move
    -minimal as well as switch-minimal.
    """
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    if goal_a != robot_b.position() or goal_b != robot_a.position():
        raise ValueError(
            "bfs_mirror needs the goal to be the start with the robots exchanged; "
            "use bfs_bidirectional for any other goal"
        )

    pack, unpack = _make_packers(workspace, n)
    mirror = _make_mirror(workspace, n)

    # Both initial controllers are seeded, covering either robot moving first;
    # the relabelling covers either moving last, so one seeding does both.
    seeds = _seed_fwd(workspace, [robot_a, robot_b], pack, build_parent=need_path)
    visited, parent, frontier = seeds["visited"], seeds["parent"], seeds["frontier"]

    layer = 0
    while frontier:
        best = None  # (meeting_sid, mirror_sid, total)
        for sid in frontier:
            mirror_sid = mirror(sid)
            mirror_layer = visited.get(mirror_sid)
            if mirror_layer is None:
                continue
            total = layer + mirror_layer
            if best is None or total < best[2]:
                best = (sid, mirror_sid, total)

        if best is not None:
            meeting_sid, mirror_sid, total = best
            if not need_path:
                return {"switches": total, "path": None, "visited": None}
            segments = _join_at_meeting(
                _fwd_segments(parent, meeting_sid, workspace, unpack),
                _mirror_segments(parent, mirror_sid, workspace, unpack),
            )
            return {
                "switches": total,
                "path": _render_segments(segments, workspace, n),
                "visited": dict(visited),
                "initial_mover": segments[0][0] if segments else None,
            }

        layer += 1
        frontier = _expand_layer(
            workspace,
            frontier,
            visited,
            parent,
            layer,
            n,
            "fwd",
            pack,
            unpack,
            build_parent=need_path,
        )
    return None


# ---------------------------------------------------------------------------
# bfs — unidirectional, forward only, expands all the way to the goal
# ---------------------------------------------------------------------------


def bfs(workspace, goal_a, goal_b, draw=False):
    """Forward-only layered BFS, expanding to depth D rather than meeting in
    the middle. Kept as the baseline the other two searches are measured
    against (see `benchmark_bfs.py`).

    Both initial controllers are seeded, exactly as `bfs_mirror` and
    `bfs_bidirectional` do, so all three answer the same question and any
    disagreement in their switch counts is a real defect rather than a
    difference in what was asked. `draw=True` writes a frontier image per
    layer.
    """
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    pack, unpack = _make_packers(workspace, n)
    seeds = _seed_fwd(workspace, [robot_a, robot_b], pack)
    visited, parent, frontier = seeds["visited"], seeds["parent"], seeds["frontier"]

    goal_sids = {pack(goal_a, goal_b, robot_a), pack(goal_a, goal_b, robot_b)}

    # Layer-0 goal check
    for sid in frontier:
        if sid in goal_sids:
            return {
                "switches": 0,
                "path": _reconstruct_fwd(parent, sid, workspace, unpack),
                "visited": visited,
                "initial_mover": _initial_mover(parent, sid),
            }

    switches = 0
    while frontier:
        switches += 1
        frontier = _expand_layer(
            workspace, frontier, visited, parent, switches, n, "fwd", pack, unpack
        )
        for sid in frontier:
            if sid in goal_sids:
                return {
                    "switches": switches,
                    "path": _reconstruct_fwd(parent, sid, workspace, unpack),
                    "visited": visited,
                    "initial_mover": _initial_mover(parent, sid),
                }
        if draw:
            frontier_states = [State(*unpack(sid)) for sid in frontier]
            draw_bfs_frontier(
                workspace.grid,
                frontier_states,
                switches,
                n,
                save_path=f"plots/bfs/switch_{switches:02d}.png",  # type: ignore
            )
        if not frontier:
            return None
    return None


# ---------------------------------------------------------------------------
# bfs_bidirectional — runs forward and backward in lockstep, shares the cache
# ---------------------------------------------------------------------------


def bfs_bidirectional(workspace, goal_a, goal_b, draw=False, need_path=True):
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    pack, unpack = _make_packers(workspace, n)

    # Seed both initial and final controllers to cover "either robot may be
    # first/last mover for free".
    fwd = _seed_fwd(workspace, [robot_a, robot_b], pack, build_parent=need_path)
    bwd = _seed_bwd(workspace, goal_a, goal_b, [robot_a, robot_b], pack, build_parent=need_path)

    fwd_visited, fwd_parent, fwd_frontier = fwd["visited"], fwd["parent"], fwd["frontier"]
    bwd_visited, bwd_parent, bwd_frontier = bwd["visited"], bwd["parent"], bwd["frontier"]

    best = None  # (meeting_sid, total_switches)
    for s in fwd_frontier:
        if s in bwd_visited:
            total = fwd_visited[s] + bwd_visited[s]
            if best is None or total < best[1]:
                best = (s, total)

    fwd_layer = 0
    bwd_layer = 0
    while True:
        if best is not None and fwd_layer + bwd_layer >= best[1]:
            break
        if not fwd_frontier and not bwd_frontier:
            break
        expand_fwd = bool(fwd_frontier) and (
            not bwd_frontier or len(fwd_frontier) <= len(bwd_frontier)
        )
        if expand_fwd:
            fwd_layer += 1
            fwd_frontier = _expand_layer(
                workspace,
                fwd_frontier,
                fwd_visited,
                fwd_parent,
                fwd_layer,
                n,
                "fwd",
                pack,
                unpack,
                build_parent=need_path,
            )
            for s in fwd_frontier:
                if s in bwd_visited:
                    total = fwd_visited[s] + bwd_visited[s]
                    if best is None or total < best[1]:
                        best = (s, total)
        else:
            bwd_layer += 1
            bwd_frontier = _expand_layer(
                workspace,
                bwd_frontier,
                bwd_visited,
                bwd_parent,
                bwd_layer,
                n,
                "bwd",
                pack,
                unpack,
                build_parent=need_path,
            )
            for s in bwd_frontier:
                if s in fwd_visited:
                    total = fwd_visited[s] + bwd_visited[s]
                    if best is None or total < best[1]:
                        best = (s, total)

    if best is None:
        return None
    meeting_sid, total = best

    # Switch-count-only fast path: callers that just need (solvable, switches)
    # — e.g. find_hardest's millions of solves — skip both the path
    # reconstruction and the O(|states|) visited-dict copy, which they discard.
    if not need_path:
        return {"switches": total, "path": None, "visited": None}

    path = _reconstruct_fwd(fwd_parent, meeting_sid, workspace, unpack) + _reconstruct_bwd(
        bwd_parent, meeting_sid, workspace, unpack
    )
    visited = dict(fwd_visited)
    for s in bwd_visited:
        visited.setdefault(s, total)
    return {
        "switches": total,
        "path": path,
        "visited": visited,
        "initial_mover": _initial_mover(fwd_parent, meeting_sid),
    }
