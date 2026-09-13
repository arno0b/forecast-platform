# forecast-platform

Short-term electricity demand forecasting for the Australian National Electricity Market, served as an
API on EKS, with the infrastructure provisioned entirely in Terraform.

**Status: design approved, Phase 1 not started.** Phase 0 (data source verification) is complete.

This is a portfolio project built on public data. It is not production, and it is not research.

## What it does

Ingests live demand data from AEMO, serves a forecast over HTTP, and reports on its own accuracy and
input drift alongside the usual latency and error-rate metrics.

The model is an online learner: it adapts as new observations arrive rather than being retrained on a
schedule. Concept drift detection and adaptation is the interesting part, and the reason the service
exposes a drift metric next to its latency histogram.

## Data

AEMO National Electricity Market, public and unauthenticated, 5 minute dispatch intervals.

| Field | Use |
| --- | --- |
| `TOTALDEMAND` | Forecast target, MW |
| `PRICE` | Exogenous feature, $/MWh |
| `SCHEDULEDGENERATION` | Dispatchable generation, MW |
| `SEMISCHEDULEDGENERATION` | Wind and solar, MW |
| `NETINTERCHANGE` | Inter-region flow, MW |

Starting with NSW1 and a 30 minute horizon, six dispatch intervals ahead.

## Planned architecture

```
AEMO (public)
     |
     |  Phase 1: GitHub Actions on a cron
     |  Phase 2: EventBridge --> Lambda, every 5 min
     v
   S3 (raw + curated observations)
     |
     |  read on startup, catch up the gap
     v
 EKS cluster (brought up on demand)
     |-- forecast-api (FastAPI, online model)
     |-- kube-prometheus-stack
     |-- Argo CD
     |-- replay CronJob
     |
     v
   ALB --> public endpoint
```

Ingestion is deliberately decoupled from compute. The cluster is ephemeral and torn down between
working sessions to keep the cost near zero; ingestion runs continuously regardless, because an
upstream feed with no history cannot be backfilled once a gap opens.

## Phases

| Phase | Delivers |
| --- | --- |
| 0 | Data source verified. **Complete** |
| 1 | Terraform, VPC, EKS, ECR, baseline forecaster, cron ingestion |
| 2 | Argo CD, ingestion migrated to Lambda and S3 |
| 3 | Prometheus, Grafana, accuracy and drift metrics, alerting |
| 4 | Online transformer, checkpointing, model versioning and rollback |
| 5 | CI on pull requests, security scanning, an SLO and a burn-rate alert |

The API contract is fixed in Phase 1 with a seasonal naive baseline behind it, so the platform can be
built and finished independently of the model work.

## Cost

Roughly USD 5 to 6 a month at about 20 hours of cluster uptime, in `ap-southeast-2`. The cluster is
created and destroyed with Terraform rather than left running.

## Licence

MIT.
