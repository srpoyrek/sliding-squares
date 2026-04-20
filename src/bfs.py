"""
bfs.py
------
Core BFS logic for the sliding squares problem.

Public API:
    flood_fill            — all positions the current robot can reach without switching
    bfs                   — unidirectional layered BFS (forward only)
    bfs_bidirectional     — bidirectional layered BFS (forward + backward in lockstep)

Both BFS entry points share the same per-layer expansion helper `_expand_layer`
and the same flood-fill cache, so memoization carries across halves inside a
single bidirectional run.

State = (pos_a, pos_b, ctrl) — ctrl is the robot that just moved.
Parent tuple convention (unified across fwd and bwd): (prev_state, target_pos, mover)
    - prev_state None ⇒ this state is at layer 0 (no preceding switch).
    - target_pos      is the mover's end-of-segment position.
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
# Keys include `free_key` (a frozenset of free-cell positions) so each cache
# entry is a pure function of its inputs. No per-solve clearing is required:
# entries remain valid across any number of solve calls on any grid topology,
# and LRU bounds control memory.
#
# _VALID_POS_CACHE   key: (free_key, n)                          -> valid positions
# _USABLE_CACHE      key: (free_key, pos_static, n)              -> usable positions
# _PARENT_MAP_CACHE  key: (free_key, pos_static, n, pos_moving)  -> parent_map dict
# ---------------------------------------------------------------------------
_VALID_POS_CACHE: LRUCache = LRUCache(maxsize=1024)
_USABLE_CACHE: LRUCache = LRUCache(maxsize=4096)
_PARENT_MAP_CACHE: LRUCache = LRUCache(maxsize=8192)


def configure_caches_for_grid(rows: int, cols: int, n: int, target_mb: int = 150) -> None:
    """Resize module-level LRU caches so total memory scales with grid area.

    Each parent_map / usable / valid_pos entry stores O(valid_positions)
    cell tuples; per-entry size grows roughly linearly with grid area. At a
    fixed cache count, 30x30 uses ~50x more memory than 4x4. This sizes the
    caps so the per-worker footprint stays near `target_mb`.
    """
    global _VALID_POS_CACHE, _USABLE_CACHE, _PARENT_MAP_CACHE
    valid_positions = max(1, (rows - n + 1) * (cols - n + 1))
    pm_bytes_per_entry = valid_positions * 160 + 200
    usable_bytes_per_entry = valid_positions * 60 + 200
    valid_bytes_per_entry = valid_positions * 60 + 200

    budget_bytes = target_mb * 1024 * 1024
    pm_share, usable_share, valid_share = 0.70, 0.25, 0.05

    pm_cap = max(256, int(budget_bytes * pm_share / pm_bytes_per_entry))
    usable_cap = max(128, int(budget_bytes * usable_share / usable_bytes_per_entry))
    valid_cap = max(64, int(budget_bytes * valid_share / valid_bytes_per_entry))

    _VALID_POS_CACHE = LRUCache(maxsize=valid_cap)
    _USABLE_CACHE = LRUCache(maxsize=usable_cap)
    _PARENT_MAP_CACHE = LRUCache(maxsize=pm_cap)


_INVERSE_CMD = {"U": "D", "D": "U", "L": "R", "R": "L"}


def _clear_caches():
    _USABLE_CACHE.clear()
    _PARENT_MAP_CACHE.clear()
    _VALID_POS_CACHE.clear()


# ---------------------------------------------------------------------------
# Flood fill (unchanged, set-based)
# ---------------------------------------------------------------------------


def _original_flood_fill(usable, pos_moving) -> dict:
    """BFS inside one robot's reach (other robot static). Returns parent_map:
    {pos: (prev_pos, cmd_to_reach_pos)}. Cmd paths are rebuilt lazily by callers."""
    parent_map = {pos_moving: (None, None)}
    queue = deque([pos_moving])
    while queue:
        pos = queue.popleft()
        row, col = pos
        for name, (dr, dc) in DIRECTIONS.items():
            nr, nc = row + dr, col + dc
            npos = (nr, nc)
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


def _workspace_free_key(workspace):
    """Frozen identifier of the workspace's free-cell set. Preferred path is
    the `_free_key` attribute set by callers that know the frozen set already
    (e.g. find_hardest_workspace). Falls back to computing it from tiles."""
    key = getattr(workspace, "_free_key", None)
    if key is not None:
        return key
    tiles = workspace.grid.tiles
    free = frozenset(
        (r, c)
        for r in range(workspace.grid.rows)
        for c in range(workspace.grid.cols)
        if tiles[r][c] == 0
    )
    workspace._free_key = free
    return free


def flood_fill(workspace, pos_moving, pos_static, n) -> dict:
    free_key = _workspace_free_key(workspace)

    valid_key = (free_key, n)
    valid_positions = _VALID_POS_CACHE.get(valid_key)
    if valid_positions is None:
        valid_set = set()
        for r in range(workspace.grid.rows - n + 1):
            for c in range(workspace.grid.cols - n + 1):
                if all(
                    workspace.grid.is_free(r + dr, c + dc) for dr in range(n) for dc in range(n)
                ):
                    valid_set.add((r, c))
        valid_positions = valid_set
        _VALID_POS_CACHE[valid_key] = valid_positions

    usable_key = (free_key, pos_static, n)
    usable = _USABLE_CACHE.get(usable_key)
    if usable is None:
        sr, sc = pos_static
        usable = {
            (r, c) for (r, c) in valid_positions if not workspace.robots_overlap(r, c, n, sr, sc, n)
        }
        _USABLE_CACHE[usable_key] = usable

    pm_key = (free_key, pos_static, n, pos_moving)
    parent_map = _PARENT_MAP_CACHE.get(pm_key)
    if parent_map is None:
        parent_map = _original_flood_fill(usable, pos_moving)
        _PARENT_MAP_CACHE[pm_key] = parent_map
    return parent_map


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

    pm = flood_fill(workspace, mover_pos, static_pos, n)
    for new_pos in pm:
        if mover is robot_a:
            new_sid = pack(new_pos, pos_b, new_ctrl)
        else:
            new_sid = pack(pos_a, new_pos, new_ctrl)
        yield new_sid, new_pos, mover


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
):
    """Expand one BFS layer. Mutates visited and parent; returns new frontier set of sids."""
    new_frontier = set()
    for sid in frontier:
        for new_sid, target_pos, mover in _expand_one(workspace, sid, pack, unpack, n, direction):
            if new_sid in visited:
                continue
            visited[new_sid] = layer
            parent[new_sid] = (sid, target_pos, mover)
            new_frontier.add(new_sid)
    return new_frontier


def _seed_fwd(workspace, initial_ctrls, pack) -> dict:
    """Build forward layer-0 frontier by flooding each initial controller from start.

    Returns {"visited", "parent", "frontier"} where keys are sids; parent tuples
    use (None, target_pos, mover) for layer-0 states (no predecessor).
    """
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    start_a = robot_a.position()
    start_b = workspace.robot_b.position()
    visited: dict = {}
    parent: dict = {}
    frontier: set = set()
    for ic in initial_ctrls:
        if ic is robot_a:
            pm = flood_fill(workspace, start_a, start_b, n)
            for new_pa in pm:
                sid = pack(new_pa, start_b, robot_a)
                if sid not in visited:
                    visited[sid] = 0
                    parent[sid] = (None, new_pa, robot_a)
                    frontier.add(sid)
        else:
            pm = flood_fill(workspace, start_b, start_a, n)
            for new_pb in pm:
                sid = pack(start_a, new_pb, workspace.robot_b)
                if sid not in visited:
                    visited[sid] = 0
                    parent[sid] = (None, new_pb, workspace.robot_b)
                    frontier.add(sid)
    return {"visited": visited, "parent": parent, "frontier": frontier}


def _seed_bwd(workspace, goal_a, goal_b, final_ctrls, pack) -> dict:
    """Build backward layer-0: the two goal sids (one per possible final ctrl)."""
    visited: dict = {}
    parent: dict = {}
    frontier: set = set()
    for fc in final_ctrls:
        sid = pack(goal_a, goal_b, fc)
        if sid not in visited:
            visited[sid] = 0
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

    path = []
    sid = end_sid
    while sid in parent:
        prev_sid, target_pos, mover = parent[sid]
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
        pm = flood_fill(workspace, source_pos, static_pos, n)
        cmds = _cmds_from_parent_map(pm, source_pos, target_pos)
        for cmd in reversed(cmds):
            path.append(cmd)
        if prev_sid is not None:
            path.append(COMMANDS["CONTROL_SWITCH"])
        if prev_sid is None:
            break
        sid = prev_sid
    path.reverse()
    return path


def _reconstruct_bwd(bwd_parent: dict, meeting_sid, workspace, unpack) -> list:
    """Walk bwd parent from meeting forward-in-time to goal. Returns cmd list."""
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    path = []
    sid = meeting_sid
    while True:
        bp = bwd_parent.get(sid)
        if bp is None:
            break
        next_sid, new_pos, mover = bp
        next_pa, next_pb, _ = unpack(next_sid)
        if mover is robot_a:
            flood_root = next_pa
            static_pos = next_pb
        else:
            flood_root = next_pb
            static_pos = next_pa
        pm = flood_fill(workspace, flood_root, static_pos, n)
        cmds = []
        curr = new_pos
        while curr != flood_root:
            prev_pos, cmd = pm[curr]
            cmds.append(_INVERSE_CMD[cmd])
            curr = prev_pos
        path.append(COMMANDS["CONTROL_SWITCH"])
        path.extend(cmds)
        sid = next_sid
    return path


# ---------------------------------------------------------------------------
# bfs — unidirectional, forward only, respects workspace._control
# ---------------------------------------------------------------------------


def bfs(workspace, goal_a, goal_b, draw=False):
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    pack, unpack = _make_packers(workspace, n)
    initial_ctrl = workspace.get_state().control
    seeds = _seed_fwd(workspace, [initial_ctrl], pack)
    visited, parent, frontier = seeds["visited"], seeds["parent"], seeds["frontier"]

    goal_sids = {pack(goal_a, goal_b, robot_a), pack(goal_a, goal_b, robot_b)}

    # Layer-0 goal check
    for sid in frontier:
        if sid in goal_sids:
            return {
                "switches": 0,
                "path": _reconstruct_fwd(parent, sid, workspace, unpack),
                "visited": visited,
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


def bfs_bidirectional(workspace, goal_a, goal_b, draw=False):
    n = workspace.robot_a.n
    robot_a = workspace.robot_a
    robot_b = workspace.robot_b
    pack, unpack = _make_packers(workspace, n)

    # Seed both initial and final controllers to cover "either robot may be
    # first/last mover for free".
    fwd = _seed_fwd(workspace, [robot_a, robot_b], pack)
    bwd = _seed_bwd(workspace, goal_a, goal_b, [robot_a, robot_b], pack)

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
                workspace, fwd_frontier, fwd_visited, fwd_parent, fwd_layer, n, "fwd", pack, unpack
            )
            for s in fwd_frontier:
                if s in bwd_visited:
                    total = fwd_visited[s] + bwd_visited[s]
                    if best is None or total < best[1]:
                        best = (s, total)
        else:
            bwd_layer += 1
            bwd_frontier = _expand_layer(
                workspace, bwd_frontier, bwd_visited, bwd_parent, bwd_layer, n, "bwd", pack, unpack
            )
            for s in bwd_frontier:
                if s in fwd_visited:
                    total = fwd_visited[s] + bwd_visited[s]
                    if best is None or total < best[1]:
                        best = (s, total)

    if best is None:
        return None
    meeting_sid, total = best
    path = _reconstruct_fwd(fwd_parent, meeting_sid, workspace, unpack) + _reconstruct_bwd(
        bwd_parent, meeting_sid, workspace, unpack
    )
    visited = dict(fwd_visited)
    for s in bwd_visited:
        visited.setdefault(s, total)
    return {"switches": total, "path": path, "visited": visited}
