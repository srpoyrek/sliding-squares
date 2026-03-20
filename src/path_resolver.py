"""
path_resolver.py
----------------
Converts compact path strings into flat command lists.

Input formats:
    "12R2US"        -> 12x R, 2x U, 1x S
    "3DURLS"        -> 3x D, 1x U, 1x R, 1x L, 1x S
    "12R2US,3DURLS" -> combines both sequences

Rules:
    - A number before a command repeats it that many times
    - No number means 1 repetition
    - Comma separates independent sequences (all get combined)
    - Valid commands: U D L R S
"""

from __future__ import annotations

import re


class PathResolver:
    def __init__(self, valid_commands: set[str]):
        self.valid_commands = {c.upper() for c in valid_commands}

    def resolve(self, *args) -> list[str]:
        """
        Convert compact path string(s) to flat command list.

        Accepts:
            resolve("12R2US")
            resolve("12R2US", "3DURLS")
            resolve(["12R2US", "3DURLS", "5LD"])

        Returns
        -------
        list of single command strings
        """
        # flatten args into a list of segment strings
        segments = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                segments.extend(arg)
            else:
                segments.append(arg)

        commands = []
        for segment in segments:
            # each segment may itself contain commas
            for part in segment.split(","):
                commands.extend(self._parse_segment(part.strip()))
        return commands

    def _parse_segment(self, segment: str) -> list[str]:
        """Parse a single segment like '12R2US'."""
        commands = []
        tokens = re.findall(r"(\d*)([A-Za-z])", segment)

        for count_str, cmd in tokens:
            cmd = cmd.upper()
            if cmd not in self.valid_commands:
                raise ValueError(f"Invalid command '{cmd}' in segment '{segment}'")
            count = int(count_str) if count_str else 1
            commands.extend([cmd] * count)

        return commands


# ── Sanity check ────────────────────────────────────────

if __name__ == "__main__":
    resolver = PathResolver(valid_commands={"U", "D", "L", "R", "S"})

    cases = [
        "12R2US",
        "3DURLS",
        "12R2US,3DURLS",
        "U",
        "5L3D2R",
    ]

    for case in cases:
        result = resolver.resolve(case)
        print(f"{case!r:25} -> {result}")
