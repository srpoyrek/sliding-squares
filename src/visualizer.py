"""
visualizer.py
-------------
Renders the Grid and Robots using matplotlib.
Completely separate from simulation logic.
"""

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
ARROW_LW = 3  # arrow line width
ARROW_SCALE = 25  # arrowhead size
ROBOT_FONTSIZE = 20  # robot label font size


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
    From snapshots collapse into one entry per turn (between switches).

    Each turn:
        title         : str        label for the panel
        waypoints     : list[(col,row)]  centers of moving robot at each step
        moving_end    : Robot      moving robot at end of turn
        stationary    : Robot      the other robot (does not move)
    """
    turns = []
    n = len(snapshots)
    start = 0

    # always show initial state as first panel
    a_0, b_0 = snapshots[0]
    turns.append(
        {
            "title": titles[0],
            "waypoints": [(a_0.col + a_0.n / 2, a_0.row + a_0.n / 2)],
            "moving_end": deepcopy(a_0),
            "stationary": deepcopy(b_0),
            "moving_start": deepcopy(a_0),
        }
    )

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

            turns.append(
                {
                    "title": titles[start],
                    "waypoints": waypoints,
                    "moving_end": deepcopy(a_e if a_moved else b_e),
                    "stationary": deepcopy(b_e if a_moved else a_e),
                    "moving_start": deepcopy(a_s if a_moved else b_s),
                }
            )

            start = i

    return turns


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

    n_steps = len(turns)
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
        for i, turn in enumerate(turns):
            fig, ax = plt.subplots(figsize=(grid.cols * 0.7 + 0.5, grid.rows * 0.7 + 0.5))
            _draw_turn(ax, grid, turn, color_map, arrow_map, robot_size)
            plt.tight_layout()
            plt.savefig(os.path.join(save_dir, f"turn_{i:02d}.png"), dpi=150, bbox_inches="tight")
            plt.close()
        return

    for i, turn in enumerate(turns):
        r = i // n_cols
        c = i % n_cols
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
