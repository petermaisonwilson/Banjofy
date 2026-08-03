BANJOFY SONG ANALYSIS LABORATORY 027

Build 027 implements the whole-song musical interpretation architecture.

Instead of selecting meter, grid and phase independently, it creates complete
musical candidates combining:

pulse family
half-time/as-detected/double-time interpretation
3/4 or 4/4 meter
downbeat phase
whole-song rhythmic evidence
harmonic boundary evidence
bar-level chord-pattern repetition
chord-change/beat alignment
tempo plausibility

One complete musical explanation wins.

Only after that decision is fixed does Build 027 read manual_truth_023.json to
measure PASS/FAIL. Truth is never used to choose the candidate.

The winning candidate also generates a complete bar/beat/chord timeline suitable
for a future moving Practice grid.

No song analysis is overwritten.
