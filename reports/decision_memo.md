# Executive Decision Memo

## Recommendation: STOP

**Business question:** Should a $2 peak-hour courier bonus be launched without harming marketplace unit economics?

**Primary effect:** -4.509 [-5.501, -3.516]

**Recommended launch cities:** None

## Guardrails

- Cancellation-rate effect: -0.017 [-0.038, 0.004]
- P90 delivery-time effect: 2.275 [-0.213, 4.763]
- Courier earnings/hour effect: 1.558 [1.180, 1.936]

## Decision rules

- Primary CI lower bound above zero: False
- Cancellation increase upper bound below 0.5pp:
  True
- City findings corrected at FDR q = 0.10

## Interpretation

The recommendation is based on intent-to-treat assignment, not bonus receipt. This avoids
post-treatment bias. Results are generated from a semi-synthetic benchmark and must not
be interpreted as evidence about a real marketplace.
