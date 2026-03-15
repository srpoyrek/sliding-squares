"""
state.py
--------
A frozen snapshot of the entire system at one moment.

Used by BFS to:
  - track which situations have already been visited
  - compare two situations

Does NOT hold the grid (grid never changes).
Does NOT hold robot objects (those live in workspace).
Just the minimum data needed to uniquely describe a situation.
"""

from src.robot import Robot


class State:
    """
    Immutable snapshot of the system.

    Fields:
        pos_a   : (row, col) of robot A's top-left corner
        pos_b   : (row, col) of robot B's top-left corner
        control : Robot — which robot is currently being controlled
    """

    def __init__(self, pos_a: tuple[int, int], pos_b: tuple[int, int], control: Robot):
        self.pos_a = pos_a
        self.pos_b = pos_b
        self.control = control  # A or B robot

    # ── Hashable + comparable (required for BFS sets/dicts) ──

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, State):
            return NotImplemented
        return (
            self.pos_a == other.pos_a
            and self.pos_b == other.pos_b
            and self.control == other.control
        )

    def __hash__(self) -> int:
        return hash((self.pos_a, self.pos_b, self.control))

    # ── Dunder ───────────────────────────────────────────

    def __repr__(self):
        return f"State(A={self.pos_a}, B={self.pos_b}, " f"control={self.control!r})"


# ── Sanity check ─────────────────────────────────────────

if __name__ == "__main__":
    A = Robot(label="A", n=2, row=1, col=1)
    B = Robot(label="B", n=2, row=1, col=3)

    s1 = State(pos_a=(1, 1), pos_b=(1, 3), control=A)
    s2 = State(pos_a=(1, 1), pos_b=(1, 3), control=A)
    s3 = State(pos_a=(1, 2), pos_b=(1, 3), control=B)

    print(s1)
    print("s1 == s2:", s1 == s2)  # True  — same situation
    print("s1 == s3:", s1 == s3)  # False — different

    # Works as a dict key and in a set (needed for BFS)
    visited = {s1, s2, s3}
    print("unique states in set:", len(visited))  # 2

    visited_dict = {s1: 0, s3: 3}
    print("switches to reach s1:", visited_dict[s2])  # 0 (s2 == s1)
