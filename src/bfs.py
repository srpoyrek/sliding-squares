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
from typing import Any, Dict, List, Optional, Tuple

from src.state import State
from src.visualizer import draw_bfs_frontier
from src.workspace import COMMANDS, DIRECTIONS

# ---------------------------------------------------------------------------
# Memoization cache
# key: (pos_static, n)
# value: dict { pos_moving: list of (pos, [cmds]) }
# ---------------------------------------------------------------------------
_FLOOD_CACHE: Dict[Tuple, Dict] = {}


def _original_flood_fill(workspace, pos_moving, pos_static, n) -> list[tuple]:
    """
    Find all positions the moving robot can reach without switching.
    Returns list of (pos, commands_to_get_there) tuples.

    Parameters
    ----------
    workspace  : Workspace instance
    pos_moving : (row, col) current position of moving robot
    pos_static : (row, col) position of the stationary robot
    n          : robot size

    Returns
    -------
    list of ( (row,col), [cmd, cmd, ...] ) — position + moves to reach it
    """
    # visited: pos -> list of commands from pos_moving to reach it
    visited = {pos_moving: []}
    queue = deque([pos_moving])

    while queue:
        pos = queue.popleft()
        row, col = pos

        for name, (dr, dc) in DIRECTIONS.items():
            nr, nc = row + dr, col + dc
            npos = (nr, nc)

            if npos in visited:
                continue
            if not all(workspace.grid.is_free(nr + r, nc + c) for r in range(n) for c in range(n)):
                continue
            if workspace.robots_overlap(nr, nc, n, pos_static[0], pos_static[1], n):
                continue

            visited[npos] = visited[pos] + [name]
            queue.append(npos)

    return list(visited.items())  # [(pos, [cmds]), ...]


def _build_cache(workspace, pos_static, n) -> dict:
    result = {}
    for r in range(workspace.grid.rows):
        for c in range(workspace.grid.cols):
            start = (r, c)
            if not all(
                workspace.grid.is_free(r + dr, c + dc) for dr in range(n) for dc in range(n)
            ):
                continue
            if workspace.robots_overlap(r, c, n, pos_static[0], pos_static[1], n):
                continue
            result[start] = _original_flood_fill(workspace, start, pos_static, n)
    return result


def flood_fill(workspace, pos_moving, pos_static, n) -> list[tuple]:
    cache_key = (pos_static, n)
    if cache_key not in _FLOOD_CACHE:
        _FLOOD_CACHE[cache_key] = _build_cache(workspace, pos_static, n)
    return _FLOOD_CACHE[cache_key].get(pos_moving, [])


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
    n = workspace.robot_a.n
    start_state = workspace.get_state()
    start_a, start_b = start_state.pos_a, start_state.pos_b
    # ── Layer 0: flood fill A from start ────────────────
    parent: Dict[State, Tuple[Optional[Tuple[Any, Any, int]], List[str]]] = {
        start_state: (None, [])
    }
    visited = {}
    frontier = set()

    for pos_a, cmds in flood_fill(workspace, start_a, start_b, n):
        state = State(pos_a, start_b, workspace.robot_a)
        visited[state] = 0
        if state not in parent:
            parent[state] = (start_state, cmds)
        frontier.add(state)

    switches = 0

    # ── Check goal at layer 0 ────────────────────────────
    for state in frontier:
        if state.pos_a == goal_a and state.pos_b == goal_b:
            return {
                "switches": switches,
                "path": _reconstruct(parent, state),
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

            for new_pos, move_cmds in flood_fill(workspace, pos_moving, pos_static, n):
                if next_robot == workspace.robot_b:
                    new_state = State(state.pos_a, new_pos, workspace.robot_b)
                else:
                    new_state = State(new_pos, state.pos_b, workspace.robot_a)
                if new_state in visited:
                    continue
                visited[new_state] = switches
                parent[new_state] = (state, [COMMANDS["CONTROL_SWITCH"]] + move_cmds)
                next_frontier.add(new_state)

        # check goal
        for state in next_frontier:
            if state.pos_a == goal_a and state.pos_b == goal_b:
                return {
                    "switches": switches,
                    "path": _reconstruct(parent, state),
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


def _reconstruct(parent: dict, goal_state: State) -> list[str]:
    """Backtrack through parent dict to build command list."""
    path = []
    state = goal_state

    while parent.get(state) is not None:
        prev_state, cmds = parent[state]
        path = cmds + path
        state = prev_state

    return path
