"""
visualizer.py
-------------
Renders the Grid and Robots using matplotlib.
Completely separate from simulation logic.
"""

from __future__ import annotations

import os
from copy import deepcopy

import matplotlib.patches as patches
import matplotlib.pyplot as plt

from src.directories import plots_path

COLOR_OBSTACLE = "#000000"
COLOR_FREE = "#f5f5f0"
COLOR_GRID_LINE = "#cccccc"
COLOR_ROBOT_A = "#e80d1f"
COLOR_ROBOT_B = "#122fd3"
COLOR_LABEL = "white"
COLOR_ARROW_A = "#ff4639"  # arrow color when A moves
COLOR_ARROW_B = "#11c0df"  # arrow color when B moves
COLOR_BLOCKER_WALL = "#ff8800"  # wall cell currently constraining a robot
COLOR_BLOCKER_FACE = "#ff8800"  # robot face in contact with a wall
COLOR_BLOCKER_ROBOT = "#aa00aa"  # robot face in contact with the other robot
COLOR_BLOCKER_EDGE = "#888888"  # robot face in contact with grid boundary
ARROW_LW = 3  # arrow line width
ARROW_SCALE = 25  # arrowhead size
ROBOT_FONTSIZE = 20  # robot label font size
FACE_LW = 4  # blocker-face highlight line width (robot edge in contact)


def draw(grid, robots=None, title="Workspace", ax=None, show=True):
    """
    Draw the grid and any robots on top.

    Parameters
    ----------
    grid   : Grid instance
    robots : list of Robot instances (optional)
    title  : plot title string
    ax     : matplotlib Axes to draw on (creates new figure if None)
    show   : call plt.show() if True
    """
    rows = grid.rows
    cols = grid.cols

    if ax is None:
        fig, ax = plt.subplots(figsize=(cols * 0.6 + 1, rows * 0.6 + 1))

    ax.set_aspect("equal")
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.invert_yaxis()
    ax.axis("off")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=8)

    for r in range(rows):
        for c in range(cols):
            color = COLOR_FREE if grid.tiles[r][c] == 0 else COLOR_OBSTACLE
            ax.add_patch(
                patches.Rectangle(
                    (c, r), 1, 1, linewidth=0.5, edgecolor=COLOR_GRID_LINE, facecolor=color
                )
            )

    if robots:
        _cmap = {r.label: col for r, col in zip(robots, [COLOR_ROBOT_A, COLOR_ROBOT_B])}
        for robot in robots:
            color = _cmap.get(robot.label, "#888888")
            r, c = robot.row, robot.col
            n = robot.n
            ax.add_patch(
                patches.Rectangle(
                    (c, r),
                    n,
                    n,
                    linewidth=2,
                    edgecolor="white",
                    facecolor=color,
                    alpha=0.85,
                    zorder=3,
                )
            )
            ax.text(
                c + n / 2,
                r + n / 2,
                robot.label,
                ha="center",
                va="center",
                fontsize=ROBOT_FONTSIZE * robot.n,
                fontweight="bold",
                color=COLOR_LABEL,
                zorder=4,
            )

    ax.set_xticks([c + 0.5 for c in range(cols)])
    ax.set_xticklabels([str(c) for c in range(cols)], fontsize=7)
    ax.set_yticks([r + 0.5 for r in range(rows)])
    ax.set_yticklabels([str(r) for r in range(rows)], fontsize=7)
    ax.tick_params(left=True, bottom=True, labelleft=True, labelbottom=True)
    ax.axis("on")
    ax.spines[:].set_visible(False)

    if show:
        plt.tight_layout()
        plt.show()

    return ax


def _extract_turns(snapshots, titles):
    """
    Collapse snapshots into one entry per turn (between switches).
    The FIRST turn is the first actual move — no separate initial-state panel.
    Turns are numbered from 1.

    Each turn dict:
        title         : "{turn_num}: {robot_label}"   (e.g. "1: A")
        waypoints     : list[(col,row)]  centers of moving robot at each step
        moving_end    : Robot            moving robot at end of turn
        stationary    : Robot            the other robot (did not move)
        moving_start  : Robot            moving robot at start of turn
    """
    turns = []
    n = len(snapshots)
    start = 0
    turn_num = 0

    for i in range(1, n):
        is_switch = "switch" in titles[i].lower()
        is_last = i == n - 1

        if is_switch or is_last:
            end = i if is_last and not is_switch else i - 1

            a_s, b_s = snapshots[start]
            a_e, b_e = snapshots[end]

            a_moved = a_s.row != a_e.row or a_s.col != a_e.col
            b_moved = b_s.row != b_e.row or b_s.col != b_e.col

            if not a_moved and not b_moved:
                start = i
                continue

            # collect waypoints (center of moving robot) at each step in this turn
            waypoints = []
            for k in range(start, end + 1):
                ra, rb = snapshots[k]
                robot = ra if a_moved else rb
                waypoints.append((robot.col + robot.n / 2, robot.row + robot.n / 2))

            turn_num += 1
            moved_robot = a_e if a_moved else b_e

            turns.append(
                {
                    "title": f"{turn_num}: {moved_robot.label}",
                    "waypoints": waypoints,
                    "moving_end": deepcopy(a_e if a_moved else b_e),
                    "stationary": deepcopy(b_e if a_moved else a_e),
                    "moving_start": deepcopy(a_s if a_moved else b_s),
                }
            )

            start = i

    return turns


def _compute_contact_at(grid, r, c, n, stationary):
    """
    For an n*n robot whose top-left is (r, c), determine what's touching
    each of its 4 sides (N/S/E/W).

    Returns (face_status, face_walls) — same semantics as _compute_contact.
    """
    sr, sc, sn = stationary.row, stationary.col, stationary.n
    R, C = grid.rows, grid.cols

    sides = {
        "N": [(r - 1, c + i) for i in range(n)],
        "S": [(r + n, c + i) for i in range(n)],
        "W": [(r + i, c - 1) for i in range(n)],
        "E": [(r + i, c + n) for i in range(n)],
    }

    face_walls = {"N": [], "S": [], "E": [], "W": []}
    face_status = {}

    for side, cells in sides.items():
        hit_wall = False
        hit_robot = False
        hit_boundary = False
        for cr, cc in cells:
            if cr < 0 or cr >= R or cc < 0 or cc >= C:
                hit_boundary = True
                continue
            if sr <= cr < sr + sn and sc <= cc < sc + sn:
                hit_robot = True
                continue
            if grid.tiles[cr][cc] != 0:  # any obstacle (boundary wall OR interior hole)
                hit_wall = True
                face_walls[side].append((cr, cc))

        if hit_wall:
            face_status[side] = "wall"
        elif hit_robot:
            face_status[side] = "robot"
        elif hit_boundary:
            face_status[side] = "boundary"
        else:
            face_status[side] = "free"

    return face_status, face_walls


def _compute_contact(grid, moving, stationary):
    """Back-compat shim: compute contact at the moving robot's current position."""
    return _compute_contact_at(grid, moving.row, moving.col, moving.n, stationary)


def _positions_along_turn(turn):
    """
    Reconstruct (row, col) robot top-left positions at each intermediate step
    during a turn, from the waypoints (which store centers).
    """
    n = turn["moving_end"].n
    return [(int(round(y - n / 2)), int(round(x - n / 2))) for (x, y) in turn["waypoints"]]


def _contact_along_turn(grid, turn):
    """
    Aggregate contact across every step in the turn (not just the endpoint).
    Returns (wall_counts, face_counts):
      wall_counts : dict (row, col) -> how many times a wall was touched
      face_counts : dict (row, col, wall_side) -> how many times that face of
                    the wall cell touched a robot face.
    """
    wall_counts = {}
    face_counts = {}
    stationary = turn["stationary"]
    n = turn["moving_end"].n
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    for r, c in _positions_along_turn(turn):
        _, face_walls = _compute_contact_at(grid, r, c, n, stationary)
        for robot_side, walls in face_walls.items():
            wall_side = opposite[robot_side]
            for wc in walls:
                wall_counts[wc] = wall_counts.get(wc, 0) + 1
                key = (wc[0], wc[1], wall_side)
                face_counts[key] = face_counts.get(key, 0) + 1
    return wall_counts, face_counts


def _draw_face_highlight(ax, row, col, n, side, color):
    """Draw a thick colored line on one side (N/S/E/W) of an n*n robot block."""
    if side == "N":
        ax.plot(
            [col, col + n], [row, row], color=color, lw=FACE_LW, zorder=6, solid_capstyle="butt"
        )
    elif side == "S":
        ax.plot(
            [col, col + n],
            [row + n, row + n],
            color=color,
            lw=FACE_LW,
            zorder=6,
            solid_capstyle="butt",
        )
    elif side == "W":
        ax.plot(
            [col, col], [row, row + n], color=color, lw=FACE_LW, zorder=6, solid_capstyle="butt"
        )
    elif side == "E":
        ax.plot(
            [col + n, col + n],
            [row, row + n],
            color=color,
            lw=FACE_LW,
            zorder=6,
            solid_capstyle="butt",
        )


def _draw_turn(ax, grid, turn, color_map, arrow_map, robot_size):
    draw(grid, robots=None, title=turn["title"], ax=ax, show=False)

    st = turn["stationary"]
    ax.add_patch(
        patches.Rectangle(
            (st.col, st.row),
            st.n,
            st.n,
            linewidth=2,
            edgecolor="white",
            facecolor=color_map.get(st.label, "#888"),
            alpha=0.85,
            zorder=3,
        )
    )
    ax.text(
        st.col + st.n / 2,
        st.row + st.n / 2,
        st.label,
        ha="center",
        va="center",
        fontsize=ROBOT_FONTSIZE * robot_size,
        fontweight="bold",
        color=COLOR_LABEL,
        zorder=4,
    )

    ms = turn["moving_start"]
    ax.add_patch(
        patches.Rectangle(
            (ms.col, ms.row),
            ms.n,
            ms.n,
            linewidth=1,
            edgecolor="white",
            facecolor=color_map.get(ms.label, "#888"),
            alpha=0.25,
            zorder=3,
        )
    )

    me = turn["moving_end"]
    ax.add_patch(
        patches.Rectangle(
            (me.col, me.row),
            me.n,
            me.n,
            linewidth=2,
            edgecolor="white",
            facecolor=color_map.get(me.label, "#888"),
            alpha=0.90,
            zorder=4,
        )
    )
    ax.text(
        me.col + me.n / 2,
        me.row + me.n / 2,
        me.label,
        ha="center",
        va="center",
        fontsize=ROBOT_FONTSIZE * robot_size,
        fontweight="bold",
        color=COLOR_LABEL,
        zorder=5,
    )

    # Highlight walls contacted at ANY step during the slide (not just endpoint).
    # Stronger alpha = more contact during this turn.
    wall_counts, _face_counts = _contact_along_turn(grid, turn)
    max_hits = max(wall_counts.values()) if wall_counts else 1
    for (wr, wc), hits in wall_counts.items():
        alpha = 0.25 + 0.50 * (hits / max_hits)
        ax.add_patch(
            patches.Rectangle(
                (wc, wr),
                1,
                1,
                linewidth=0,
                facecolor=COLOR_BLOCKER_WALL,
                alpha=alpha,
                zorder=2,
            )
        )

    # On the final position of the robot, color each face by what it's touching
    face_status, _ = _compute_contact(grid, me, st)
    status_color = {
        "wall": COLOR_BLOCKER_FACE,
        "robot": COLOR_BLOCKER_ROBOT,
        "boundary": COLOR_BLOCKER_EDGE,
    }
    for side, status in face_status.items():
        if status in status_color:
            _draw_face_highlight(ax, me.row, me.col, me.n, side, status_color[status])

    wpts = turn["waypoints"]
    arrow_color = arrow_map.get(ms.label, COLOR_ARROW_A)
    if len(wpts) > 1:
        for k in range(len(wpts) - 1):
            x0, y0 = wpts[k]
            x1, y1 = wpts[k + 1]
            if k == len(wpts) - 2:
                ax.annotate(
                    "",
                    xy=(x1, y1),
                    xytext=(x0, y0),
                    arrowprops=dict(
                        arrowstyle="->",
                        lw=ARROW_LW * robot_size,
                        mutation_scale=ARROW_SCALE * robot_size,
                        color=arrow_color,
                    ),
                    zorder=6,
                )
            else:
                ax.plot([x0, x1], [y0, y1], color=arrow_color, lw=ARROW_LW * robot_size, zorder=6)


def draw_sequence(
    grid, snapshots, titles=None, cols_per_row=5, save_path=None, save_dir=None, robot_size=1
):
    """
    Draw one panel per turn (between control switches).

    Each panel shows:
      - stationary robot at its position
      - moving robot faded at start, full at end
      - arrow from start position to end position

    Parameters
    ----------
    grid        : Grid instance
    snapshots   : list of [Robot, Robot] lists — one per step from validator
    titles      : list of title strings — one per step from validator
    cols_per_row: panels per row
    save_path   : save to this path if given, else show interactively
    """
    titles = titles or [f"step {i}" for i in range(len(snapshots))]
    turns = _extract_turns(snapshots, titles)

    # +1 for the start panel (initial state, no highlights)
    n_steps = len(turns) + 1
    n_cols = min(n_steps, cols_per_row)
    n_rows = (n_steps + n_cols - 1) // n_cols

    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(n_cols * (grid.cols * 0.7 + 0.5), n_rows * (grid.rows * 0.7 + 0.5)),
    )

    if n_rows == 1 and n_cols == 1:
        axes = [[axes]]
    elif n_rows == 1:
        axes = [list(axes)]
    elif n_cols == 1:
        axes = [[a] for a in axes]

    # color map built from snapshot order — first robot = COLOR_ROBOT_A, second = COLOR_ROBOT_B
    first, second = snapshots[0]
    color_map = {first.label: COLOR_ROBOT_A, second.label: COLOR_ROBOT_B}
    arrow_map = {first.label: COLOR_ARROW_A, second.label: COLOR_ARROW_B}

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        # Initial-state panel: both robots at start, no wall/face highlights.
        a_0, b_0 = snapshots[0]
        fig, ax = plt.subplots(figsize=(grid.cols * 0.7 + 0.5, grid.rows * 0.7 + 0.5))
        draw(grid, robots=[a_0, b_0], title="start", ax=ax, show=False)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, "start.png"), dpi=150, bbox_inches="tight")
        plt.close()

        # One file per turn of actual movement, numbered from 1
        for i, turn in enumerate(turns):
            fig, ax = plt.subplots(figsize=(grid.cols * 0.7 + 0.5, grid.rows * 0.7 + 0.5))
            _draw_turn(ax, grid, turn, color_map, arrow_map, robot_size)
            plt.tight_layout()
            plt.savefig(
                os.path.join(save_dir, f"turn_{i + 1:02d}.png"), dpi=150, bbox_inches="tight"
            )
            plt.close()
        # Aggregate heatmap: how many times each wall blocked a robot face
        draw_blocker_heatmap(
            grid,
            turns,
            save_path=os.path.join(save_dir, "blocker_heatmap.png"),
            robot_size=robot_size,
        )
        return

    # Panel 0: initial state, no highlights
    a_0, b_0 = snapshots[0]
    draw(grid, robots=[a_0, b_0], title="start", ax=axes[0][0], show=False)

    for i, turn in enumerate(turns):
        idx = i + 1  # panel 0 is the start
        r = idx // n_cols
        c = idx % n_cols
        ax = axes[r][c]
        _draw_turn(ax, grid, turn, color_map, arrow_map, robot_size)

    for i in range(n_steps, n_rows * n_cols):
        axes[i // n_cols][i % n_cols].set_visible(False)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()

    plt.close()


def draw_blocker_heatmap(grid, turns, save_path=None, robot_size=1):
    """
    Aggregate view across all turns: color each wall cell by how many times
    it was in contact with a robot face. Shows which walls are "load-bearing"
    in the puzzle vs. scenery.
    """
    counts = {}
    face_counts = {}  # (row, col, side) -> count, for the side of the wall touching the robot
    for turn in turns:
        turn_walls, turn_faces = _contact_along_turn(grid, turn)
        for cell, hits in turn_walls.items():
            counts[cell] = counts.get(cell, 0) + hits
        for key, hits in turn_faces.items():
            face_counts[key] = face_counts.get(key, 0) + hits

    fig, ax = plt.subplots(figsize=(grid.cols * 0.7 + 0.5, grid.rows * 0.7 + 0.5))
    draw(grid, robots=None, title="Blocker heatmap (walls by contact count)", ax=ax, show=False)

    max_count = max(counts.values()) if counts else 1
    for (r, c), n_hits in counts.items():
        intensity = 0.3 + 0.6 * (n_hits / max_count)
        ax.add_patch(
            patches.Rectangle(
                (c, r),
                1,
                1,
                linewidth=0,
                facecolor=COLOR_BLOCKER_WALL,
                alpha=intensity,
                zorder=2,
            )
        )
        ax.text(
            c + 0.5,
            r + 0.5,
            str(n_hits),
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
            color="white",
            zorder=5,
        )

    # Draw per-face tick marks on each wall: which side(s) of the wall got hit
    for (wr, wc, wall_side), n_hits in face_counts.items():
        _draw_face_highlight(ax, wr, wc, 1, wall_side, COLOR_BLOCKER_FACE)

    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.show()


def draw_bfs_frontier(grid, frontier, switch_num, robot_size, save_dir=None):
    """
    Draw all states in a BFS frontier on a single plot.
    Each state = one panel showing where A and B are.
    """
    from src.robot import Robot

    states = list(frontier)
    n = len(states)
    if n == 0:
        return

    cols = min(n, 5)
    rows = (n + cols - 1) // cols

    fig, axes = plt.subplots(
        rows, cols, figsize=(cols * (grid.cols * 0.4 + 0.5), rows * (grid.rows * 0.4 + 0.5))
    )

    if rows == 1 and cols == 1:
        axes = [[axes]]
    elif rows == 1:
        axes = [list(axes)]
    elif cols == 1:
        axes = [[a] for a in axes]

    for i, state in enumerate(states):
        r, c = i // cols, i % cols
        ax = axes[r][c]

        title = f"S{switch_num} | A={state.pos_a} B={state.pos_b} ctrl={state.control.label}"
        draw(grid, robots=None, title=title, ax=ax, show=False)

        ra = Robot("A", robot_size, state.pos_a[0], state.pos_a[1])
        ax.add_patch(
            patches.Rectangle(
                (ra.col, ra.row),
                ra.n,
                ra.n,
                linewidth=2,
                edgecolor="white",
                facecolor=COLOR_ROBOT_A,
                alpha=0.85,
                zorder=3,
            )
        )
        ax.text(
            ra.col + ra.n / 2,
            ra.row + ra.n / 2,
            "A",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="white",
            zorder=4,
        )

        rb = Robot("B", robot_size, state.pos_b[0], state.pos_b[1])
        ax.add_patch(
            patches.Rectangle(
                (rb.col, rb.row),
                rb.n,
                rb.n,
                linewidth=2,
                edgecolor="white",
                facecolor=COLOR_ROBOT_B,
                alpha=0.85,
                zorder=3,
            )
        )
        ax.text(
            rb.col + rb.n / 2,
            rb.row + rb.n / 2,
            "B",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color="white",
            zorder=4,
        )

    for i in range(n, rows * cols):
        axes[i // cols][i % cols].set_visible(False)

    plt.suptitle(f"BFS Switch {switch_num} — {n} states", fontsize=14, fontweight="bold")
    plt.tight_layout()

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, f"switch_{switch_num:02d}.png")
        plt.savefig(save_path, dpi=100, bbox_inches="tight")
        print(f"Saved {save_path}")
    else:
        plt.show()
    plt.close()


# ── Demo ────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from src.grid import Grid
    from src.robot import Robot
    from src.validator import Validator
    from src.workspace import Workspace

    tiles = [
        [1, 1, 0, 1, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1],
    ]
    grid = Grid(tiles)
    a = Robot("A", 1, 1, 1)
    b = Robot("B", 1, 1, 3)
    ws = Workspace(grid, a, b)

    validator = Validator(ws, goal_a=(1, 3), goal_b=(1, 1))
    path = ["S", "L", "U", "S", "R", "R", "S", "D", "L"]
    result = validator.run(path)

    snapshots = [[a, b] for a, b in result.snapshots]

    out = plots_path("turns.png")
    draw_sequence(grid, snapshots, titles=result.titles, save_path=out)
    print(f"Saved {out}")
