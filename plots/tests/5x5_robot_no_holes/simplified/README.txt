5x5_robot_no_holes — simplification recipes
original: 200 walls, 13 control switches

Each subfolder is one recipe, holding its own summary.png, solved
sequence and simplification.txt. Ranked by fewest walls surviving.

recipe                       walls  removed  status
------------------------------------------------------------------------
black_uncrossable               17      138  PRESERVED
black_relative_uncrossable      17      175  PRESERVED
uncrossable                     17       93  PRESERVED
black_relative                  20      172  PRESERVED

Simplification recipes (folder name -> what it does):

  black_relative              Baseline + keep contact peaks plus enough extra cells that no gap
                              along a run exceeds n-1, so an n x n robot still cannot slip
                              past.

  black_uncrossable           Baseline + exact pass: free every remaining wall whose removal
                              opens no new n x n robot placement. Thins lines to a picket at
                              spacing n without guessing.

  black_relative_uncrossable  black_relative, then the exact pass. The spacing rule and the
                              placement rule agree on straight runs, so this mostly shows what
                              the exact pass finds that the gap heuristic misses at corners.

  uncrossable                 The only PROVABLY lossless recipe: nothing is removed but walls
                              the robot could never cross, so the state space — and therefore
                              the switch count — cannot move. Always reports PRESERVED.
