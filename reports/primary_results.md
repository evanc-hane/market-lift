# Primary Experiment Results

## Contribution margin per zone-cluster block

| Estimator | Effect and 95% CI |
| --- | ---: |
| Naive difference | -4.497 [-5.625, -3.369] |
| Cluster-robust OLS | -4.507 [-5.499, -3.515] |
| CUPED + cluster-robust OLS | -4.509 [-5.501, -3.516] |
| Known simulator ground truth | -3.200 |

- CUPED variance reduction: 0.00%
- Minimum detectable effect: 1.639
- CUPED absolute estimation error: -1.309

## City heterogeneity

| City | Maturity | Estimate | CI low | CI high | FDR p-value | Ground truth |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Toronto | mature | -5.968 | -10.177 | -1.758 | 0.0125 | -5.667 |
| Vancouver | mature | -6.043 | -9.833 | -2.254 | 0.0071 | -5.240 |
| Montreal | growth | -4.332 | -7.437 | -1.226 | 0.0125 | -2.795 |
| Calgary | growth | -2.179 | -4.954 | 0.597 | 0.1240 | -2.328 |
| Ottawa | growth | -3.380 | -6.066 | -0.695 | 0.0207 | -2.565 |
| Edmonton | new | -3.420 | -6.191 | -0.649 | 0.0207 | -1.893 |
| Winnipeg | new | -3.497 | -6.591 | -0.402 | 0.0306 | -2.195 |
| Halifax | new | -7.157 | -9.919 | -4.395 | 0.0000 | -2.920 |

Segment results use Benjamini-Hochberg correction. City-level findings are exploratory
unless the segment and decision rule were declared before analysis.
