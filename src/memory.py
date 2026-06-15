"""
memory.py
---------
Process-memory measurement and a guard that keeps a single process's resident
set under a fixed byte budget.

find_hardest_workspace.py uses this to enforce a hard *total* RAM ceiling across
the whole multiprocessing tree, independent of grid size or worker count:

  - the orchestrator divides the total budget into a per-process ceiling and
    refuses to spawn more workers than the budget can afford (see `plan_budget`);
  - each process that grows unbounded structures (the dig-search queue / visited
    set, plus the bfs LRU caches) holds a `MemoryGuard`. The guard polls the
    *real* RSS in the hot loop and, when memory climbs toward the ceiling, first
    drops the disposable caches and then tells the caller to stop growing — so
    the search degrades to a partial result instead of OOM-killing the machine.

Measurement prefers psutil (accurate current RSS on every platform). If psutil
is missing it falls back to OS calls so the guard always has a real number to
act on rather than a byte estimate.
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile

MB = 1024 * 1024

# ── RSS measurement ─────────────────────────────────────────────────────────

try:
    import psutil

    _PROC = psutil.Process()

    def rss_bytes() -> int:
        """Current resident set size of this process, in bytes."""
        return _PROC.memory_info().rss

    def tree_rss_bytes(pid: int | None = None) -> int:
        """RSS of `pid` (default: this process) plus all descendants, in bytes.

        Best-effort: processes that vanish mid-walk are skipped. Used by the
        orchestrator to log/verify the whole-tree footprint."""
        try:
            proc = psutil.Process(pid) if pid is not None else _PROC
            procs = [proc] + proc.children(recursive=True)
        except Exception:
            return rss_bytes()
        total = 0
        for p in procs:
            try:
                total += p.memory_info().rss
            except Exception:
                pass
        return total

except Exception:  # pragma: no cover - psutil should be installed
    psutil = None  # type: ignore

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        def rss_bytes() -> int:
            counters = _PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            )
            return int(counters.WorkingSetSize) if ok else 0

    else:

        def rss_bytes() -> int:
            import resource

            kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # ru_maxrss is bytes on macOS, kilobytes on Linux. It is a *peak*,
            # not current, value — conservative (over-reports), which is safe
            # for a ceiling guard.
            return int(kb) if sys.platform == "darwin" else int(kb) * 1024

    def tree_rss_bytes(pid: int | None = None) -> int:
        return rss_bytes()


# ── Budget planning ─────────────────────────────────────────────────────────

# A spawned worker re-imports the project; this is the resident floor before any
# search work. Measured empirically (~35 MB with lazy matplotlib). Used only as
# a fallback when a live measurement isn't supplied.
DEFAULT_BASELINE_MB = 40
# Minimum working room (caches + queue/visited) we insist each worker gets above
# its baseline. Below this the worker can't make progress, so we drop a process.
MIN_WORKING_MB = 24


def plan_budget(total_mb, requested_procs, baseline_mb=DEFAULT_BASELINE_MB):
    """Split a total RAM budget across worker processes.

    Returns (nproc, per_proc_ceiling_mb, cache_mb):
      - nproc:               worker count, capped so the budget is honourable.
      - per_proc_ceiling_mb: absolute RSS ceiling for one worker — the value to
                             hand a MemoryGuard. Sum over workers (+ the idle
                             orchestrator's baseline) stays within total_mb.
      - cache_mb:            target for that worker's bfs LRU caches (a slice of
                             the working room; the rest is left for queue/visited).

    The orchestrator process keeps ~baseline_mb resident while idle, so we carve
    that out first and divide the remainder among workers.
    """
    total_mb = max(1.0, float(total_mb))
    baseline_mb = max(1.0, float(baseline_mb))
    requested = max(1, int(requested_procs))

    workers_room = max(0.0, total_mb - baseline_mb)  # reserve main's baseline
    affordable = int(workers_room // (baseline_mb + MIN_WORKING_MB))
    nproc = max(1, min(requested, affordable))

    per_proc_ceiling = workers_room / nproc
    working = max(0.0, per_proc_ceiling - baseline_mb)
    # Give caches half the working room; queue/visited get the other half.
    cache_mb = max(4.0, working * 0.5)
    return nproc, per_proc_ceiling, cache_mb


# ── Guard ────────────────────────────────────────────────────────────────────


class MemoryGuard:
    """Keeps the current process under `budget_bytes` of RSS using *lossless*
    relief only — it never tells the caller to drop search work.

    Call `tick()` in the hot loop (it's cheap — it only measures RSS once every
    `poll_every` calls). When RSS crosses the soft threshold the guard runs its
    relief callbacks, which must be loss-free for the final result: clearing or
    shrinking memoization caches forces *recomputation*, not a wrong/partial
    answer. The relief list is escalated one extra callback at a time on each
    successive breach, so transient pressure clears the caches and sustained
    pressure also shrinks their caps.

    `over_hard` is a diagnostics-only flag: it means relief wasn't enough to get
    back under the hard line (the irreducible structures — queue / visited — are
    the pressure). The caller does not truncate on it; the orchestrator sizes
    `nproc` and the per-process budget so those structures fit.
    """

    def __init__(
        self,
        budget_bytes,
        relief=(),
        poll_every=512,
        soft=0.82,
        hard=0.93,
    ):
        self.budget = max(1, int(budget_bytes))
        self.relief = list(relief)
        self.poll_every = max(1, int(poll_every))
        self.soft_bytes = int(self.budget * soft)
        self.hard_bytes = int(self.budget * hard)
        self.over_hard = False  # diagnostics: still over hard after relief

        self._n = 0
        self._escalation = 1  # how many relief callbacks to run on a breach
        # Prime an initial reading so a short search that never trips the poll
        # interval still reports a real peak instead of 0.
        self.peak_rss = rss_bytes()
        self.measures = 0
        self.relief_runs = 0
        self.hard_breaches = 0  # times relief failed to get back under hard

    def tick(self) -> None:
        """Advance the guard one step. Measures RSS only every `poll_every`
        calls; runs lossless relief if over the soft threshold."""
        self._n += 1
        if self._n % self.poll_every == 0:
            self._evaluate()

    def _evaluate(self) -> None:
        rss = rss_bytes()
        self.measures += 1
        if rss > self.peak_rss:
            self.peak_rss = rss

        if rss < self.soft_bytes:
            self.over_hard = False
            self._escalation = 1  # pressure relieved; reset escalation
            return

        # Over the soft line: run the first `_escalation` relief callbacks
        # (clear caches first, then also shrink their caps on repeated breaches).
        for cb in self.relief[: self._escalation]:
            try:
                cb()
            except Exception:
                pass
            self.relief_runs += 1
        if self._escalation < len(self.relief):
            self._escalation += 1

        rss = rss_bytes()
        if rss > self.peak_rss:
            self.peak_rss = rss
        self.over_hard = rss >= self.hard_bytes
        if self.over_hard:
            self.hard_breaches += 1

    def stats(self) -> str:
        return (
            f"peak_rss={self.peak_rss / MB:.1f}MB "
            f"budget={self.budget / MB:.1f}MB "
            f"measures={self.measures} relief_runs={self.relief_runs} "
            f"hard_breaches={self.hard_breaches}"
        )


# ── Disk-spilling set ────────────────────────────────────────────────────────


class SpillableSet:
    """A set whose resident memory is bounded: it keeps an in-RAM buffer and,
    once that buffer exceeds `ram_cap` entries, flushes it to an on-disk sqlite
    table and clears it. So no matter how many distinct elements are added, the
    RAM it holds stays near `ram_cap` keys plus a small sqlite page cache.

    Supports exactly the two operations the dig-search dedup needs:
        key in s        # membership — checks the RAM buffer, then disk
        s.add(key)      # insert (caller guarantees the key is new)

    Membership is EXACT (complete dedup) — spilling only makes lookups slower,
    never wrong. Keys must be repr-stable; tuples of ints qualify.

    A search whose distinct-key count never exceeds `ram_cap` never opens the
    database, so it is exactly as fast as a plain `set`. Call `close()` when done
    to drop the temp file (it is reused across placements in one worker).
    """

    def __init__(self, ram_cap=1_000_000, tmp_dir=None):
        self.ram_cap = max(1, int(ram_cap))
        self._buf: set = set()
        self._db = None
        self._path = None
        self._tmp_dir = tmp_dir
        self.spills = 0
        self.disk_active = False

    def __contains__(self, key) -> bool:
        if key in self._buf:
            return True
        if self._db is None:
            return False
        row = self._db.execute("SELECT 1 FROM seen WHERE k = ? LIMIT 1", (repr(key),)).fetchone()
        return row is not None

    def add(self, key) -> None:
        self._buf.add(key)
        if len(self._buf) >= self.ram_cap:
            self._spill()

    def _open(self) -> None:
        fd, self._path = tempfile.mkstemp(suffix=".visited.sqlite", dir=self._tmp_dir)
        os.close(fd)
        self._db = sqlite3.connect(self._path)
        # Durability is irrelevant — this is a scratch dedup table — so disable
        # journaling/fsync for speed, and cap the page cache so the DB's own RAM
        # use stays bounded too (~16 MB).
        self._db.execute("PRAGMA journal_mode = OFF")
        self._db.execute("PRAGMA synchronous = OFF")
        self._db.execute("PRAGMA cache_size = -16384")
        self._db.execute("CREATE TABLE IF NOT EXISTS seen (k TEXT PRIMARY KEY)")
        self.disk_active = True

    def _spill(self) -> None:
        if self._db is None:
            self._open()
        self._db.executemany(
            "INSERT OR IGNORE INTO seen(k) VALUES (?)", ((repr(k),) for k in self._buf)
        )
        self._db.commit()
        self._buf.clear()
        self.spills += 1

    def close(self) -> None:
        if self._db is not None:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None
            if self._path and os.path.exists(self._path):
                try:
                    os.remove(self._path)
                except Exception:
                    pass
            self._path = None
        self._buf.clear()
