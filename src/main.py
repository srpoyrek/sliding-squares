"""
Sliding Squares Simulator
=========================
Two n×n square robots (A and B) must swap positions in a grid workspace.
Goal: count the minimum number of control switches required.

Usage:
    python sliding_squares_simulator.py
"""

from collections import deque

# ─────────────────────────────────────────────
# Core Data Structures
# ─────────────────────────────────────────────

class Workspace:
    """Grid workspace. 0=free, 1=obstacle."""

    def __init__(self, grid):
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0])

    def is_obstacle(self, r, c):
        if r < 0 or r >= self.rows or c < 0 or c >= self.cols:
            return True
        return self.grid[r][c] == 1

    def robot_fits(self, r, c, n):
        """Check if n×n robot with top-left at (r,c) fits without obstacle overlap."""
        for dr in range(n):
            for dc in range(n):
                if self.is_obstacle(r + dr, c + dc):
                    return False
        return True

    def display(self, state, n):
        """Print workspace with robots A (red) and B (blue) shown as letters."""
        display = [['.' if self.grid[r][c] == 0 else '#'
                    for c in range(self.cols)]
                   for r in range(self.rows)]

        ar, ac = state.pos_a
        br, bc = state.pos_b

        for dr in range(n):
            for dc in range(n):
                if 0 <= br+dr < self.rows and 0 <= bc+dc < self.cols:
                    display[br+dr][bc+dc] = 'B'
                if 0 <= ar+dr < self.rows and 0 <= ac+dc < self.cols:
                    display[ar+dr][ac+dc] = 'A'

        print("  " + "".join(str(c % 10) for c in range(self.cols)))
        for r, row in enumerate(display):
            print(f"{r % 10} " + "".join(row))


class State:
    """Snapshot: positions of both robots + which is currently controlled."""

    def __init__(self, pos_a, pos_b, current='A'):
        self.pos_a = pos_a      # (row, col) top-left of robot A
        self.pos_b = pos_b      # (row, col) top-left of robot B
        self.current = current  # 'A' or 'B'

    def to_tuple(self):
        return (self.pos_a, self.pos_b, self.current)

    def copy(self):
        return State(self.pos_a, self.pos_b, self.current)

    def __hash__(self):
        return hash(self.to_tuple())

    def __eq__(self, other):
        return self.to_tuple() == other.to_tuple()


# ─────────────────────────────────────────────
# Simulator
# ─────────────────────────────────────────────

DIRECTIONS = {'U': (-1,0), 'D': (1,0), 'L': (0,-1), 'R': (0,1)}

class Simulator:
    """
    Simulates two sliding n×n square robots.

    Commands:
        'U','D','L','R'  — move current robot one tile
        'S'              — switch to other robot (+1 control switch)
    """

    def __init__(self, workspace, n, start_a, start_b, goal_a, goal_b):
        self.ws       = workspace
        self.n        = n
        self.start_state = State(start_a, start_b, 'A')
        self.goal_a   = goal_a
        self.goal_b   = goal_b

    def robots_overlap(self, pos_a, pos_b):
        ar, ac = pos_a; br, bc = pos_b
        return not (ar+self.n <= br or br+self.n <= ar or
                    ac+self.n <= bc or bc+self.n <= ac)

    def is_goal(self, state):
        return state.pos_a == self.goal_a and state.pos_b == self.goal_b

    def apply_move(self, state, cmd):
        """Returns new State, or None if move is invalid."""
        ns = state.copy()

        if cmd == 'S':
            ns.current = 'B' if state.current == 'A' else 'A'
            return ns

        if cmd not in DIRECTIONS:
            return None

        dr, dc = DIRECTIONS[cmd]

        if state.current == 'A':
            nr, nc = state.pos_a[0]+dr, state.pos_a[1]+dc
            if not self.ws.robot_fits(nr, nc, self.n): return None
            if self.robots_overlap((nr,nc), state.pos_b): return None
            ns.pos_a = (nr, nc)
        else:
            nr, nc = state.pos_b[0]+dr, state.pos_b[1]+dc
            if not self.ws.robot_fits(nr, nc, self.n): return None
            if self.robots_overlap(state.pos_a, (nr,nc)): return None
            ns.pos_b = (nr, nc)

        return ns

    def run_sequence(self, commands, verbose=True):
        """
        Execute a list of commands from start.
        Returns: {success, switches, steps, final_state, error}
        """
        state = self.start_state.copy()
        switches = steps = 0

        if verbose:
            print(f"\n{'='*44}")
            print(f"Start | controlling [{state.current}] | "
                  f"Goal: A→{self.goal_a}  B→{self.goal_b}")
            self.ws.display(state, self.n)

        for i, cmd in enumerate(commands):
            ns = self.apply_move(state, cmd)
            if ns is None:
                if verbose:
                    print(f"\n❌ Invalid command '{cmd}' at index {i}")
                return {'success':False,'switches':switches,
                        'steps':steps,'final_state':state,
                        'error':f"Invalid '{cmd}' at #{i}"}

            if cmd == 'S':
                switches += 1
                if verbose:
                    print(f"\n[{i}] SWITCH → [{ns.current}]  "
                          f"(total switches: {switches})")
            else:
                steps += 1
                if verbose:
                    print(f"\n[{i}] Move {state.current} {cmd}")

            if verbose:
                self.ws.display(ns, self.n)
            state = ns

        ok = self.is_goal(state)
        if verbose:
            print(f"\n{'='*44}")
            if ok:
                print(f"✅ SUCCESS — switches={switches}  move_steps={steps}")
            else:
                print(f"❌ Not at goal.  A@{state.pos_a}(want {self.goal_a})  "
                      f"B@{state.pos_b}(want {self.goal_b})")

        return {'success':ok,'switches':switches,
                'steps':steps,'final_state':state,'error':None}


# ─────────────────────────────────────────────
# BFS Solver — minimum control switches
# ─────────────────────────────────────────────

class BFSSolver:
    """
    Finds minimum control switches to swap A and B.

    Strategy (switch-level BFS):
      - Level 0: all positions reachable by robot A from start (free moves)
      - Level k+1: switch control, then expand all free moves for other robot
      - A 'switch' costs +1; movements within a turn are free.
    """

    def __init__(self, simulator):
        self.sim = simulator

    def _free_reach(self, state):
        """BFS over movement-only from state. Returns all reachable states."""
        visited = {state.to_tuple()}
        q = deque([state])
        out = [state]
        while q:
            s = q.popleft()
            for cmd in ('U','D','L','R'):
                ns = self.sim.apply_move(s, cmd)
                if ns is None: continue
                k = ns.to_tuple()
                if k not in visited:
                    visited.add(k)
                    q.append(ns)
                    out.append(ns)
        return out

    def solve(self, max_switches=40, verbose=True):
        """
        Returns {switches, frontier_states} or None if unsolvable.
        """
        start = self.sim.start_state.copy()

        # Level 0 frontier: all positions reachable without any switch
        frontier = self._free_reach(start)
        global_visited = {s.to_tuple(): 0 for s in frontier}

        if verbose:
            print(f"🔍 BFS — max_switches={max_switches}")

        for sw in range(max_switches + 1):
            if verbose:
                print(f"   Level {sw}: {len(frontier)} states in frontier")

            # Check goal
            for s in frontier:
                if self.sim.is_goal(s):
                    if verbose:
                        print(f"✅ Minimum switches = {sw}")
                    return {'switches': sw, 'example_state': s}

            # Expand next level: switch + free moves
            next_frontier = []
            next_visited  = set()

            for s in frontier:
                switched = self.sim.apply_move(s, 'S')
                reachable = self._free_reach(switched)
                for ns in reachable:
                    k = ns.to_tuple()
                    if k not in global_visited or global_visited[k] > sw+1:
                        if k not in next_visited:
                            global_visited[k] = sw+1
                            next_visited.add(k)
                            next_frontier.append(ns)

            if not next_frontier:
                if verbose: print("❌ No solution found.")
                return None

            frontier = next_frontier

        if verbose: print(f"❌ Exceeded max_switches={max_switches}")
        return None


# ─────────────────────────────────────────────
# Built-in Workspaces
# ─────────────────────────────────────────────

def make_trivial_1x1():
    """
    1×1 robots. Pocket above center allows the swap.
    Minimum = 3 switches.

    Layout:
      ##.##
      #A.B#
      #####
    """
    grid = [
        [1,1,0,1,1],
        [1,0,0,0,1],
        [1,1,1,1,1],
    ]
    return Simulator(Workspace(grid), 1,
                     start_a=(1,1), start_b=(1,3),
                     goal_a=(1,3),  goal_b=(1,1))


def make_1x1_corridor():
    """
    1×1 robots in a wider corridor. Tests slightly more complex swap.
    """
    grid = [
        [1,1,1,1,1,1],
        [1,0,0,0,0,1],
        [1,0,1,1,0,1],
        [1,0,0,0,0,1],
        [1,1,1,1,1,1],
    ]
    return Simulator(Workspace(grid), 1,
                     start_a=(1,1), start_b=(1,4),
                     goal_a=(1,4),  goal_b=(1,1))


def make_2x2_simple():
    """
    2×2 robots in open space with a pillar.
    Paper reports 6 switches for best 2×2 no-holes workspace.
    """
    grid = [
        [1,1,1,1,1,1,1,1],
        [1,0,0,0,0,0,0,1],
        [1,0,0,0,0,0,0,1],
        [1,0,0,1,1,0,0,1],
        [1,0,0,1,1,0,0,1],
        [1,0,0,0,0,0,0,1],
        [1,0,0,0,0,0,0,1],
        [1,1,1,1,1,1,1,1],
    ]
    return Simulator(Workspace(grid), 2,
                     start_a=(1,1), start_b=(1,5),
                     goal_a=(1,5),  goal_b=(1,1))


def make_custom(grid, n, start_a, start_b, goal_a, goal_b):
    """Build any custom workspace."""
    return Simulator(Workspace(grid), n, start_a, start_b, goal_a, goal_b)


# ─────────────────────────────────────────────
# Interactive Play
# ─────────────────────────────────────────────

def interactive_mode(sim):
    state = sim.start_state.copy()
    switches = steps = 0

    print("\n🎮 INTERACTIVE MODE")
    print("  W=Up  S=Down  A=Left  D=Right  T=Switch  R=Reset  Q=Quit")
    print(f"  Goal: A→{sim.goal_a}  B→{sim.goal_b}")

    while True:
        print(f"\n  Controlling [{state.current}]  "
              f"Switches={switches}  Steps={steps}")
        sim.ws.display(state, sim.n)

        if sim.is_goal(state):
            print(f"\n🎉 DONE!  switches={switches}  steps={steps}")
            break

        raw = input("  cmd> ").strip().upper()

        if   raw == 'Q': break
        elif raw == 'R':
            state = sim.start_state.copy(); switches = steps = 0
        elif raw == 'T': cmd = 'S'
        elif raw in 'WASD':
            cmd = {'W':'U','A':'L','S':'D','D':'R'}[raw]
        else:
            print("  Unknown."); continue

        ns = sim.apply_move(state, cmd)
        if ns is None:
            print("  ❌ Invalid move."); continue

        if cmd == 'S': switches += 1
        else:          steps    += 1
        state = ns


# ─────────────────────────────────────────────
# Main Demo
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  SLIDING SQUARES SIMULATOR")
    print("=" * 50)

    # ── Demo 1: Run a known 3-switch solution ──
    print("\n📦 Demo 1 — trivial 1×1, known 3-switch sequence")
    sim = make_trivial_1x1()
    # Pocket is at (0,2). Strategy:
    #   S  → switch to B (sw=1)
    #   L  → B slides left to (1,2)
    #   U  → B slides up  to (0,2)  [into pocket]
    #   S  → switch to A (sw=2)
    #   R  → A slides right to (1,2)
    #   R  → A slides right to (1,3) [A at goal]
    #   S  → switch to B (sw=3)
    #   D  → B slides down to (1,2)
    #   L  → B slides left to (1,1) [B at goal]
    seq = ['S','L','U','S','R','R','S','D','L']
    sim.run_sequence(seq, verbose=True)

    # ── Demo 2: BFS finds minimum for trivial 1×1 ──
    print("\n📦 Demo 2 — BFS on trivial 1×1")
    sim = make_trivial_1x1()
    sol = BFSSolver(sim).solve(verbose=True)

    # ── Demo 3: BFS on 1×1 L-corridor ──
    print("\n📦 Demo 3 — BFS on 1×1 L-corridor")
    sim = make_1x1_corridor()
    sol = BFSSolver(sim).solve(verbose=True)

    # ── Demo 4: BFS on 2×2 ──
    print("\n📦 Demo 4 — BFS on 2×2 simple workspace")
    sim = make_2x2_simple()
    sol = BFSSolver(sim).solve(max_switches=10, verbose=True)

    # ── Demo 5: Interactive ──
    print("\n📦 Demo 5 — Interactive mode")
    skip = input("Skip interactive? (y/n): ").strip().lower()
    if skip != 'y':
        interactive_mode(make_trivial_1x1())

    print("\n✅ Done. Import and use make_custom() to define your own workspaces.")