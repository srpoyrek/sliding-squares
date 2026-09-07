2x2_robot_holes — simplification recipes
original: 119 walls, 13 control switches

Each subfolder is one recipe, holding its own summary.png, solved
sequence and simplification.txt. Ranked by fewest walls surviving.

recipe                       walls  removed  status
------------------------------------------------------------------------
black_peaks_uncrossable         14      100  FAILED (3)
black_peaks                     15       99  FAILED (3)
black_alternate                 16       89  FAILED (3)
black_uncrossable               19       72  PRESERVED
black_relative_uncrossable      19       86  PRESERVED
black_relative                  20       85  PRESERVED
uncrossable                     24       41  PRESERVED
black                           33       58  PRESERVED

Simplification recipes (folder name -> what it does):

  black                       Baseline. Drop only the walls the solution never touched; keep
                              every touched wall as-is.

  black_alternate             Baseline + drop every other touched wall in row-major order.
                              Crude control: thins without looking at where contact happened.

  black_peaks                 Baseline + on each straight run of touched wall, keep only the
                              cell the robot pressed hardest. Most aggressive heuristic.

  black_relative              Baseline + keep contact peaks plus enough extra cells that no gap
                              along a run exceeds n-1, so an n x n robot still cannot slip
                              past.

  black_uncrossable           Baseline + exact pass: free every remaining wall whose removal
                              opens no new n x n robot placement. Thins lines to a picket at
                              spacing n without guessing.

  black_peaks_uncrossable     black_peaks, then the exact pass on whatever survived. The
                              smallest wall set of the set, but inherits the peak heuristic's
                              risk.

  black_relative_uncrossable  black_relative, then the exact pass. The spacing rule and the
                              placement rule agree on straight runs, so this mostly shows what
                              the exact pass finds that the gap heuristic misses at corners.

  uncrossable                 The only PROVABLY lossless recipe: nothing is removed but walls
                              the robot could never cross, so the state space — and therefore
                              the switch count — cannot move. Always reports PRESERVED.
