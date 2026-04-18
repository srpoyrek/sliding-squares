"""
bfs.py
------
Core BFS logic for the sliding squares problem.

Two functions:
    flood_fill  — all positions current robot can reach without switching
    bfs         — layered BFS that finds minimum control switches
                  tracks parent pointers to reconstruct path
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Tuple

from src.state import State
from src.visualizer import draw_bfs_frontier
from src.workspace import COMMANDS, DIRECTIONS

# ---------------------------------------------------------------------------
# Memoization cache
# _FLOOD_CACHE key: (pos_static, n) -> {"usable": set, "flood": {pos_moving: result}}
#   "usable" is the set of positions valid for a robot of size n that also
#   don't overlap the static robot — precomputed once per (pos_static, n).
# _VALID_POS_CACHE key: n -> set of (row, col) where robot of size n fits
# ---------------------------------------------------------------------------
_FLOOD_CACHE: Dict[Tuple, Dict] = {}
_VALID_POS_CACHE: Dict[int, set] = {}


def _original_flood_fill(usable, pos_moving) -> dict:
    """
    Find all positions the moving robot can reach without switching.

    Returns a parent_map: pos -> (previous_pos, command_taken_to_get_here).
    Command paths are NOT reconstructed here — callers rebuild lazily via
    `_cmds_from_parent_map` only for positions they actually keep. This
    avoids O(path_length) work for every reachable cell that BFS drops as
    a duplicate.
    """
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


def _cmds_from_parent_map(parent_map: dict, pos_moving, target) -> list[str]:
    """Walk parent_map from target back to pos_moving to rebuild the cmd list."""
    cmds = []
    curr = target
    while curr != pos_moving:
        curr, cmd = parent_map[curr]
        cmds.append(cmd)
    cmds.reverse()
    return cmds


def flood_fill(workspace, pos_moving, pos_static, n) -> dict:
    """Lazy evaluation wrapper for the flood fill.
    Returns parent_map — a dict {pos: (prev_pos, cmd)}.
    Iterate .keys() for reachable positions; call _cmds_from_parent_map
    to rebuild a specific path.
    """
    cache_key = (pos_static, n)
    if cache_key not in _FLOOD_CACHE:
        # Precompute valid positions for this robot size (ignores the other robot)
        if n not in _VALID_POS_CACHE:
            valid_set = set()
            for r in range(workspace.grid.rows - n + 1):
                for c in range(workspace.grid.cols - n + 1):
                    if all(
                        workspace.grid.is_free(r + dr, c + dc) for dr in range(n) for dc in range(n)
                    ):
                        valid_set.add((r, c))
            _VALID_POS_CACHE[n] = valid_set
        valid_positions = _VALID_POS_CACHE[n]

        # Subtract positions overlapping the static robot — one pass, reused by every flood
        sr, sc = pos_static
        usable = {
            (r, c) for (r, c) in valid_positions if not workspace.robots_overlap(r, c, n, sr, sc, n)
        }
        _FLOOD_CACHE[cache_key] = {"usable": usable, "flood": {}}

    bucket = _FLOOD_CACHE[cache_key]
    if pos_moving not in bucket["flood"]:
        bucket["flood"][pos_moving] = _original_flood_fill(bucket["usable"], pos_moving)
    return bucket["flood"][pos_moving]


def bfs(workspace, goal_a, goal_b, draw=False) -> dict | None:
    """
    Layered BFS — finds minimum control switches and reconstructs path.

    State = (pos_a, pos_b, who_moves)
        who_moves: 0 = A moves, 1 = B moves

    parent[state] = (parent_state, [commands to go from parent to this state])
        commands include the leading CONTROL_SWITCH if a switch happened

    Returns
    -------
    dict with:
        switches : int
        path     : list of commands
        visited  : dict state -> switches count
    or None if no solution.
    """
    _FLOOD_CACHE.clear()  # clear cache to avoid stale entries from previous workspaces
    _VALID_POS_CACHE.clear()
    n = workspace.robot_a.n
    start_state = workspace.get_state()
    start_a, start_b = start_state.pos_a, start_state.pos_b

    # parent[state] = (prev_state, target_pos_of_mover, needs_switch)
    # target_pos_of_mover is the end position of whoever moved in this edge;
    # combined with prev_state it lets us rebuild move cmds from the cache.
    parent = {start_state: (None, None, False)}
    visited = {}
    frontier = set()

    # ── Layer 0: flood fill A from start ────────────────
    pm0 = flood_fill(workspace, start_a, start_b, n)
    for pos_a in pm0:
        state = State(pos_a, start_b, workspace.robot_a)
        visited[state] = 0
        if state not in parent:
            parent[state] = (start_state, pos_a, False)
        frontier.add(state)

    switches = 0

    # ── Check goal at layer 0 ────────────────────────────
    for state in frontier:
        if state.pos_a == goal_a and state.pos_b == goal_b:
            return {
                "switches": switches,
                "path": _reconstruct(parent, state, workspace),
                "visited": visited,
            }

    # ── Layered BFS ──────────────────────────────────────
    while frontier:
        switches += 1
        next_frontier = set()

        for state in frontier:
            next_robot = (
                workspace.robot_b if state.control == workspace.robot_a else workspace.robot_a
            )
            pos_moving = state.pos_b if next_robot == workspace.robot_b else state.pos_a
            pos_static = state.pos_a if next_robot == workspace.robot_b else state.pos_b

            pm = flood_fill(workspace, pos_moving, pos_static, n)
            for new_pos in pm:
                if next_robot == workspace.robot_b:
                    new_state = State(state.pos_a, new_pos, workspace.robot_b)
                else:
                    new_state = State(new_pos, state.pos_b, workspace.robot_a)
                if new_state in visited:
                    continue
                visited[new_state] = switches
                parent[new_state] = (state, new_pos, True)
                next_frontier.add(new_state)

        # check goal
        for state in next_frontier:
            if state.pos_a == goal_a and state.pos_b == goal_b:
                return {
                    "switches": switches,
                    "path": _reconstruct(parent, state, workspace),
                    "visited": visited,
                }

        if draw:
            draw_bfs_frontier(
                workspace.grid,
                next_frontier,
                switches,
                n,
                save_path=f"plots/bfs/switch_{switches:02d}.png",  # type: ignore
            )

        if not next_frontier:
            return None

        frontier = next_frontier

    return None


def _reconstruct(parent: dict, goal_state: State, workspace) -> list[str]:
    """Backtrack through parent dict, rebuilding cmds per-edge from the flood cache."""
    n = workspace.robot_a.n
    robot_b = workspace.robot_b

    path = []
    state = goal_state
    while parent.get(state) is not None:
        prev_state, target_pos, needs_switch = parent[state]
        if prev_state is None:
            break
        # Identify who moved on this edge and derive their start/static positions
        if state.control == robot_b:
            pos_moving_start = prev_state.pos_b
            pos_static = prev_state.pos_a
        else:
            pos_moving_start = prev_state.pos_a
            pos_static = prev_state.pos_b

        parent_map = _FLOOD_CACHE[(pos_static, n)]["flood"][pos_moving_start]
        cmds = _cmds_from_parent_map(parent_map, pos_moving_start, target_pos)

        for cmd in reversed(cmds):
            path.append(cmd)
        if needs_switch:
            path.append(COMMANDS["CONTROL_SWITCH"])
        state = prev_state

    path.reverse()
    return path
