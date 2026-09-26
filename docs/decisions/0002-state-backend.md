# 0002. Terraform state backend: pre-created S3 bucket with native locking

- **Status:** Accepted
- **Date:** 2026-09-27

## Context

Terraform needs somewhere durable to keep state for the forecast platform. Local state is not an option: it lives on one laptop, is lost with that laptop, and cannot be shared with CI in Phase 5. The project runs in AWS (`ap-southeast-2`), so S3 is the natural backend.

Three questions came up while setting it up. Who creates the bucket? What protects the state file from being lost or corrupted? And how are concurrent runs prevented from writing state at the same time?

## Decision

State is stored in a single S3 bucket, `<bucket-name>`, at key `forecast-platform/infra.tfstate`. The bucket is created by hand with the AWS CLI (Task 1, Part A), not by Terraform. It has versioning enabled. Locking uses Terraform's S3-native lockfile (`use_lockfile = true`); there is no DynamoDB lock table.

### Why the bucket is created outside Terraform

The backend has to exist before `terraform init` can run, because Terraform reads its state before it evaluates any configuration. A Terraform configuration cannot create the bucket that its own state is stored in: on the very first run there is nowhere to record that the bucket was created.

It is possible to work around this. One option is to apply once with local state and then migrate the state into the new bucket. The result is worse than the problem, though. The bucket becomes a resource in the state it holds, so `terraform destroy` would try to delete the bucket containing the state of the destroy in progress. Task 8 runs a full destroy on purpose, so this would be a live risk, not a theoretical one. `prevent_destroy` would block that, but it would also make every full destroy fail, and it would be one lifecycle flag away from disaster.

A separate bootstrap Terraform configuration with its own local state was also considered. It is the right answer when there are many accounts or environments to bootstrap. For one bucket in one account, it adds a second root module and a second state file that must itself be kept somewhere safe, which only moves the problem.

So the bucket is treated as infrastructure *for* Terraform rather than infrastructure *managed by* Terraform. It is created once, by hand, and outlives every apply and destroy.

### Why versioning matters

The state file is a single object that is overwritten on every apply. Without versioning, any bad write replaces the only copy. Bad writes can come from several places: an apply interrupted mid-write, a mistaken `terraform state rm`, a manual edit, or a run against the wrong workspace. Once the state is lost, Terraform no longer knows which real resources it owns. Those resources keep running and billing, but Terraform can neither plan changes to them nor destroy them.

With versioning, every previous state is kept as a noncurrent version and can be restored with a single `aws s3api` call. It also protects against the object being deleted outright, because a delete only adds a delete marker.

Versioning is cheap here: state files are small, and apply frequency is low.

### Why there is no DynamoDB table

Until Terraform 1.10, the S3 backend could only lock through a separate DynamoDB table. That meant a second resource to bootstrap by hand, extra IAM permissions, and one more thing to find and clean up.

Terraform 1.10 added native S3 locking. With `use_lockfile = true`, Terraform writes a lock object (`forecast-platform/infra.tfstate.tflock`) next to the state using an S3 conditional write. The write only succeeds if the object does not already exist, so a second concurrent run fails to acquire the lock instead of racing. DynamoDB-based locking has since been deprecated.

`versions.tf` constrains Terraform to `~> 1.16`, so native locking is guaranteed to be available. A DynamoDB table would add cost, permissions, and bootstrap steps while providing nothing the lockfile doesn't.

## Consequences

- **The bucket is invisible to Terraform.** Drift in its settings (versioning turned off, public access unblocked) will not appear in any plan. Its configuration is recorded here and in the Part A commands, and it must be checked by hand if in doubt.
- **The bucket survives `terraform destroy` by design.** Task 8's leftover hunt filters on `Project = forecast-platform`. If the bucket carries that tag, it will show up in the results; that is expected, and it should not be deleted as a leftover.
- **Noncurrent versions accumulate.** This is negligible at this scale. A lifecycle rule expiring noncurrent versions after a set period can be added if it ever matters.
- **Stale locks need manual clearing.** If a run is killed while holding the lock, the `.tflock` object remains. Clear it with `terraform force-unlock <LOCK_ID>`, and only after confirming no other run is active.
- **The credentials used need write and delete access to the lock key**, not just to the state key. Any IAM policy scoped to the state object must also cover `*.tflock`.
- **Final teardown is manual.** When the project ends, the bucket must be emptied of all object versions and delete markers before it can be deleted. A plain `aws s3 rb --force` does not remove versions.
- **Backend values are literals.** In Phase 5, CI may need a different profile or credentials for the backend. That must be supplied with `terraform init -backend-config=...`, not with variables.