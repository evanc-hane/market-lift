# Experiment Design

## Intervention

Treatment offers a $2 bonus for each completed delivery between 17:00 and 21:00. Control
operates under normal courier pay.

## Randomization

The unit is a delivery zone cluster during a two-hour block. Assignment is balanced within
city, day, and block. This avoids user-level randomization, which is inappropriate when
courier supply is shared by many customers in the same marketplace.

The analysis is intent-to-treat. It uses randomized assignment rather than whether an
individual courier received a bonus, because receipt occurs after treatment and depends on
the outcome process.

## Analysis plan

1. Stop for SRM p < 0.01 or absolute standardized balance difference > 0.10.
2. Report an unadjusted difference for transparency.
3. Estimate the primary effect with city/hour/day fixed effects and zone-cluster robust SE.
4. Apply CUPED using pre-experiment contribution margin for the same cluster/block hour.
5. Confirm the primary conclusion with a permutation test that reshuffles treatment only
   within the original city × date × block-hour randomization strata.
6. Report cancellation, lateness, delivery-time, and courier-earnings guardrails.
7. Require both experiment-health and relevant guardrail checks before any launch decision.
8. Correct city-level p-values with Benjamini-Hochberg FDR.
9. Compare estimators with hidden simulator ground truth only after estimation.

## Limitations

The simulator simplifies courier movement, pricing, network interference, missing events,
and delayed financial reconciliation. Thirty-two clusters are adequate for demonstration,
not a universal experimental design. A real launch requires cluster-count sensitivity,
pre-registration, interference analysis, and operational review.
