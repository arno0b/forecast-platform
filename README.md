# forecast-platform

Short-term electricity demand forecasting for the Australian National Electricity Market, served as an
API on EKS, with the infrastructure provisioned entirely in Terraform.

**Status: Phase 1b complete.** The application runs on EKS, on infrastructure provisioned entirely by
Terraform, and the whole stack has been destroyed and rebuilt from code three times. Phase 2 (Argo CD,
ingestion moved to Lambda and S3) is next.

**The public endpoint is not always live.** The cluster is destroyed between working sessions, because
an idle EKS control plane bills at USD 0.10/hour whether or not anything runs on it. `terraform apply`
brings the whole stack back in about 15 minutes.

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

## Running it locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest
.venv/Scripts/python -m uvicorn forecast_platform.api:app --reload
```

Ingest one interval by hand:

```bash
PYTHONPATH=src .venv/Scripts/python -m forecast_platform.ingest --data-dir data
```

Or run the container:

```bash
docker build -t forecast-platform:dev .
docker run --rm -p 8000:8000 forecast-platform:dev
```

## Infrastructure

Provisioned by Terraform in `ap-southeast-2`, with remote state in S3 using native lockfile locking.
Three modules: `network` (VPC, three public subnets across three AZs, internet gateway), `ecr`
(immutable tags, scan on push, lifecycle policy), and `cluster` (EKS 1.36, managed node group on
t3.small spot instances).

**No NAT gateway.** One costs USD 43/month in this region and a conventional one-per-AZ layout is USD
129/month, against a USD 10 budget. Nodes run in public subnets with security groups instead. The
trade-off is written up in `docs/decisions/0001-no-nat-gateway.md`.

**The Service is a Classic Load Balancer, not an NLB.** This account is under an AWS new-account block
on Elastic Load Balancing v2: `CreateLoadBalancer` returns `OperationNotPermitted` while the v1 API
works. Quotas are not the cause. Restoring the `aws-load-balancer-type: "nlb"` annotation is a one-line
change once the restriction lifts; an ALB behind an Ingress is Phase 2.

## What it cost

Measured, not estimated. Phase 1b took **6.2 cluster-hours across three builds** and cost about
**USD 0.80**:

| | |
| --- | --- |
| EKS control plane | USD 0.10/hour |
| 2 x t3.small spot | USD 0.019/hour |
| Classic load balancer | USD 0.0252/hour |
| Running total while up | **USD 0.145/hour** |

Destroying between sessions is the whole reason that number is small. Left running continuously the
same stack is about USD 105/month.

## Known limitation

**The seasonal model does not currently fire, and this is measured rather than assumed.**

Ingestion runs on a GitHub Actions cron set to 30 minutes. Measured over 40.8 hours, 11 of roughly 82
scheduled runs actually executed, a 13 percent delivery rate with a mean gap of 3.7 hours. GitHub
documents its scheduler as best effort and deprioritises cron on low-activity repositories.

The seasonal lookup matches an observation within 15 minutes of the same time one week earlier. At 3.7
hour spacing that lookup effectively never lands inside the tolerance, so every request falls through
to the persistence fallback while still returning HTTP 200 with healthy-looking metrics. Tested against
8 days of real accumulated data: 0 of 6 forecast steps found a seasonal match.

Phase 2 moves ingestion to EventBridge and Lambda, which restores the full five-minute resolution. It
was originally planned as a demonstration of migrating a working pipeline onto managed services. The
measurement above reclassified it as a prerequisite.

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
