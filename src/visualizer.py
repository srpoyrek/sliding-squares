"""
visualizer.py
-------------
Renders the Grid and Robots using matplotlib.
Completely separate from simulation logic.
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from directories import plots_path



# ── Colors ──────────────────────────────────────────────
COLOR_OBSTACLE  = '#2b2b2b'   # dark grey
COLOR_FREE      = '#f5f5f0'   # off white
COLOR_GRID_LINE = '#cccccc'   # light grey
COLOR_ROBOT_A   = '#e63946'   # red
COLOR_ROBOT_B   = '#1d7cbd'   # blue
COLOR_LABEL     = 'white'


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

    ax.set_aspect('equal')
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.invert_yaxis()           # (0,0) top-left, matching grid convention
    ax.axis('off')
    ax.set_title(title, fontsize=12, fontweight='bold', pad=8)

    # ── Draw tiles ──────────────────────────────────────
    for r in range(rows):
        for c in range(cols):
            color = COLOR_OBSTACLE if grid.tiles[r][c] == 1 else COLOR_FREE
            rect = patches.Rectangle(
                (c, r), 1, 1,
                linewidth=0.5,
                edgecolor=COLOR_GRID_LINE,
                facecolor=color
            )
            ax.add_patch(rect)

    # ── Draw robots ─────────────────────────────────────
    if robots:
        robot_colors = {'A': COLOR_ROBOT_A, 'B': COLOR_ROBOT_B}

        for robot in robots:
            color = robot_colors.get(robot.label, '#888888')
            r, c  = robot.row, robot.col
            n     = robot.n

            # Robot body
            rect = patches.Rectangle(
                (c, r), n, n,
                linewidth=2,
                edgecolor='white',
                facecolor=color,
                alpha=0.85,
                zorder=3
            )
            ax.add_patch(rect)

            # Label in center
            ax.text(
                c + n / 2, r + n / 2,
                robot.label,
                ha='center', va='center',
                fontsize=14, fontweight='bold',
                color=COLOR_LABEL,
                zorder=4
            )

    # ── Row / col index ticks ────────────────────────────
    ax.set_xticks([c + 0.5 for c in range(cols)])
    ax.set_xticklabels([str(c) for c in range(cols)], fontsize=7)
    ax.set_yticks([r + 0.5 for r in range(rows)])
    ax.set_yticklabels([str(r) for r in range(rows)], fontsize=7)
    ax.tick_params(left=True, bottom=True, labelleft=True, labelbottom=True)
    ax.axis('on')
    ax.spines[:].set_visible(False)

    if show:
        plt.tight_layout()
        plt.show()

    return ax


def draw_sequence(grid, snapshots, titles=None, cols_per_row=5, save_path=None):
    """
    Draw multiple snapshots side by side — useful for showing a move sequence.

    Parameters
    ----------
    grid        : Grid instance (shared across all snapshots)
    snapshots   : list of [Robot, ...] lists — one per step
    titles      : list of title strings (optional)
    cols_per_row: how many snapshots per row
    save_path   : if given, save figure to this path instead of showing
    """
    n_steps = len(snapshots)
    n_cols  = min(n_steps, cols_per_row)
    n_rows  = (n_steps + n_cols - 1) // n_cols

    fig, axes = plt.subplots(
        n_rows, n_cols,
        figsize=(n_cols * (grid.cols * 0.55 + 0.5),
                 n_rows * (grid.rows * 0.55 + 0.5))
    )

    # Flatten axes array for easy indexing
    if n_rows == 1 and n_cols == 1:
        axes = [[axes]]
    elif n_rows == 1:
        axes = [axes]
    elif n_cols == 1:
        axes = [[a] for a in axes]

    for i, robots in enumerate(snapshots):
        r = i // n_cols
        c = i  % n_cols
        title = titles[i] if titles and i < len(titles) else f"step {i}"
        draw(grid, robots, title=title, ax=axes[r][c], show=False)

    # Hide unused axes
    for i in range(n_steps, n_rows * n_cols):
        r = i // n_cols
        c = i  % n_cols
        axes[r][c].set_visible(False)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved to {save_path}")
    else:
        plt.show()


# ── Demo ────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
 
    from grid  import Grid
    from robot import Robot
    from copy  import deepcopy
 
    tiles = [
        [1, 1, 0, 1, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1],
    ]
    grid = Grid(tiles)
    a = Robot('A', 1, 1, 1)
    b = Robot('B', 1, 1, 3)
 
    # ── Single frame ────────────────────────────────────
    draw(grid, robots=[a, b], title="Start — A=(1,1)  B=(1,3)", show=False)
    out1 = plots_path('workspace_start.png')
    plt.savefig(out1, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved {out1}")
 
    # ── Move sequence ───────────────────────────────────
    snapshots, titles = [], []
 
    def snap(a, b, label):
        snapshots.append([deepcopy(a), deepcopy(b)])
        titles.append(label)
 
    snap(a, b, "0: start")
    b.col -= 1;  snap(a, b, "1: B left")
    b.row -= 1;  snap(a, b, "2: B up  [sw1]")
    a.col += 1;  snap(a, b, "3: A right")
    a.col += 1;  snap(a, b, "4: A right  [sw2]")
    b.row += 1;  snap(a, b, "5: B down")
    b.col -= 1;  snap(a, b, "6: B left  [sw3]")
 
    out2 = plots_path('workspace_sequence.png')
    draw_sequence(grid, snapshots, titles=titles, save_path=out2)
    print(f"Saved {out2}")
