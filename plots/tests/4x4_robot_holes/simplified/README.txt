4x4_robot_holes — simplification recipes
original: 372 walls, 17 control switches

Each subfolder is one recipe, holding its own summary.png, solved
sequence and simplification.txt. Ranked by fewest walls surviving.

recipe                       walls  removed  status
------------------------------------------------------------------------
black_peaks_uncrossable         24      344  FAILED (9)
black_peaks                     25      343  FAILED (9)
black_relative_uncrossable      29      335  PRESERVED
black_relative                  32      332  PRESERVED
black_uncrossable               32      306  PRESERVED
uncrossable                     38      226  PRESERVED
black_alternate                 50      305  FAILED (2)
black                          101      237  PRESERVED

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
