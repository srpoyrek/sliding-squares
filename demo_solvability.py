"""
demo_solvability.py
-------------------
Prints the union-find structure behind `SwapSolvability`. First a board small
enough to show whole — the raw parent array, every legal slot's pointer chain
to its root, the islands as pictures, and the one comparison `solvable` makes —
then the corridor with and without a pocket, where two islands fuse into one,
and finally every real test case: its slot and island counts and the actual
chains its start and goal walk to their roots. The real arrays are printed in
summary because they cannot be read whole: the 5x5 case alone holds 135,424
slots.

Run:
    python demo_solvability.py
"""

from __future__ import annotations

from run_tests import discover_test_cases
from src.bitgrid import BitGrid
from src.solvability import SwapSolvability


def _chain(sol: SwapSolvability, slot: int) -> list[int]:
    """The pointer walk from `slot` to its root, read without compressing, so
    printing the structure does not rewrite the thing being printed."""
    out = [slot]
    while sol._parent[slot] != slot:
        slot = sol._parent[slot]
        out.append(slot)
    return out


def _picture(sol: SwapSolvability, state: int, cols: int) -> str:
    """A one-row board as [A][B][.] brackets — readable in a terminal."""
    (_ra, ca), (_rb, cb) = sol._pair(state)
    row = ["."] * cols
    row[ca] = "A"
    row[cb] = "B"
    return "[" + "][".join(row) + "]"


def _label(sol: SwapSolvability, state: int) -> str:
    a, b = sol._pair(state)
    return f"A{a} B{b}"


def main() -> None:
    print("=== 1x3 corridor, 1x1 robots: the whole structure ===")
    sol = SwapSolvability(1, 3, BitGrid.full(1, 3), 1)
    legal = list(sol._all_states())
    print(
        f"placements: {sol.valid.count()}   legal states: {len(legal)} of {len(sol._parent)} slots"
    )
    print()

    print("parent array after the build, slot: parent. A slot pointing at itself")
    print("is a root; the untouched slots are the illegal same-cell pairs:")
    print("  " + "  ".join(f"{i}:{p}" for i, p in enumerate(sol._parent)))
    print()

    print("every legal slot, its pointer chain, its root:")
    for s in legal:
        hops = _chain(sol, s)
        arrow = " -> ".join(str(h) for h in hops)
        print(f"  slot {s} ({_label(sol, s)}):  {arrow}   root {hops[-1]}")
    print()

    print("the islands — one tree each, shown as the pictures its states are:")
    by_root: dict[int, list[int]] = {}
    for s in legal:
        by_root.setdefault(_chain(sol, s)[-1], []).append(s)
    for root, members in sorted(by_root.items()):
        pics = "   ".join(_picture(sol, s, 3) for s in members)
        print(f"  root {root}:  {pics}")
    print()

    s0 = sol._state((0, 0), (0, 1))
    g0 = sol._exchange(s0)
    print(f"the start A(0,0) B(0,1) is slot {s0}, root {_chain(sol, s0)[-1]}")
    print(f"its exchange — the goal — is slot {g0}, root {_chain(sol, g0)[-1]}")
    print(f"roots equal? -> solvable((0,0),(0,1)) = {sol.solvable((0, 0), (0, 1))}")
    print()

    print("=== the pocket: watch two islands fuse into one ===")
    boards = (
        ("1x5 corridor          ", 1, 5, BitGrid.full(1, 5)),
        ("same + pocket at (1,2)", 2, 5, {(0, c) for c in range(5)} | {(1, 2)}),
    )
    for name, rows, cols, free in boards:
        sol = SwapSolvability(rows, cols, free, 1)
        states = list(sol._all_states())
        roots = {sol._find(s) for s in states}
        good = sum(1 for s in states if sol._find(s) == sol._find(sol._exchange(s)))
        print(f"  {name}:  islands = {len(roots)}   solvable starts = {good} of {len(states)}")
    print("  the pocket is the square where the robots pass; its cliques share")
    print("  pictures with both trees, so union points one root at the other.")
    print()

    print("=== the real test cases: same structure, printed in summary ===")
    for case in sorted(discover_test_cases(), key=lambda c: c.name):
        ws, _goal_a, _goal_b = case().setup()
        sol = SwapSolvability.for_workspace(ws)
        start_a, start_b = ws.robot_a.position(), ws.robot_b.position()
        s0 = sol._state(start_a, start_b)
        g0 = sol._exchange(s0)
        # Chains read before any find() call, which would compress them away.
        chain_s = " -> ".join(str(h) for h in _chain(sol, s0))
        chain_g = " -> ".join(str(h) for h in _chain(sol, g0))
        states = list(sol._all_states())
        islands = len({sol._find(s) for s in states})
        print(
            f"\n  {case.name}: {len(sol._parent):,} slots, {len(states):,} legal states, "
            f"{islands} island(s)"
        )
        print(f"    start {_label(sol, s0)}:  slot {chain_s}")
        print(f"    goal  {_label(sol, g0)}:  slot {chain_g}")
        print(f"    same root, so solvable = {sol.solvable(start_a, start_b)}")


if __name__ == "__main__":
    main()
