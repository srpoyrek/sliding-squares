"""
validator.py
------------
Given a workspace, a path, and goal positions:
validates every move, counts control switches, and plots the sequence.
"""

from copy import deepcopy
from typing import Optional

from src.directories import plots_path
from src.visualizer import draw_sequence
from src.workspace import COMMANDS, Workspace


class ValidationResult:
    def __init__(self):
        self.valid = False
        self.reached_goal = False
        self.switches = 0
        self.failed_at: Optional[int] = None  # index of first bad command
        self.failed_reason: Optional[str] = None  # why it failed
        self.snapshots = []  # (robot_a, robot_b) clone per step
        self.titles = []  # label per step

    def __repr__(self):
        if self.valid:
            return f"ValidationResult(valid=True, switches={self.switches})"
        return (
            f"ValidationResult(valid=False, "
            f"failed_at={self.failed_at}, reason={self.failed_reason!r})"
        )


class Validator:
    def __init__(self, workspace: Workspace, goal_a: tuple[int, int], goal_b: tuple[int, int]):
        self.ws = workspace
        self.goal_a = goal_a
        self.goal_b = goal_b

    def run(
        self, path: list[str], plot: bool = True, plot_name: str = "validation"
    ) -> ValidationResult:
        result = ValidationResult()
        ws = self.ws

        result.snapshots.append((deepcopy(ws.robot_a), deepcopy(ws.robot_b)))
        result.titles.append("start")

        for i, cmd in enumerate(path):
            if cmd == COMMANDS["CONTROL_SWITCH"]:
                ws._control = (
                    self.ws.robot_b.label
                    if ws._control == self.ws.robot_a.label
                    else self.ws.robot_a.label
                )
                result.switches += 1
                label = f"{i}: switch to {ws._control} (sw={result.switches})"

            elif cmd in COMMANDS.values():
                robot = ws.robot_a if ws._control == self.ws.robot_a.label else ws.robot_b

                if not ws.can_move(robot, cmd):
                    result.failed_at = i
                    result.failed_reason = (
                        f"'{cmd}' invalid for robot {robot.label} " f"at ({robot.row},{robot.col})"
                    )
                    if plot:
                        self._plot(result, plot_name)
                    return result

                ws.do_move(robot, cmd)
                label = f"{i}: {ws._control} {cmd}"

            else:
                result.failed_at = i
                result.failed_reason = f"unknown command '{cmd}'"
                if plot:
                    self._plot(result, plot_name)
                return result

            result.snapshots.append((deepcopy(ws.robot_a), deepcopy(ws.robot_b)))
            result.titles.append(label)

        result.reached_goal = (
            ws.robot_a.position() == self.goal_a and ws.robot_b.position() == self.goal_b
        )
        result.valid = result.reached_goal

        if plot:
            self._plot(result, plot_name)

        return result

    def _plot(self, result: ValidationResult, name: str):
        if not result.snapshots:
            return
        snapshots = [[a, b] for a, b in result.snapshots]
        draw_sequence(
            self.ws.grid, snapshots, titles=result.titles, save_path=plots_path(f"{name}.png")
        )
