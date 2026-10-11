# 0001. No NAT gateway

Date: 2026-10-09

## Status

Accepted

## Context

The cluster needs outbound internet access so that nodes can reach the EKS
control plane endpoint, pull images from ECR, and fetch OS and add-on updates.

The conventional layout is private subnets for nodes plus a NAT gateway per AZ
for egress. In ap-southeast-2 a NAT gateway costs USD 0.059 per hour plus USD
0.059 per GB processed. Those figures come from the AWS Pricing API filtered on
regionCode, not from the VPC pricing page, which shows US East (Ohio) rates
unless the region selector is changed. That is about USD 43 per month each
before any traffic, so the standard three-AZ layout is roughly USD 129 per
month. The hourly
charge accrues whether or not the cluster is doing anything, and NAT gateways
are not covered by the free tier.

This is a personal learning environment funded by a small credit balance. It
holds no production data and no third-party data. A single month of three NAT
gateways would exceed the entire budget for the project.

## Decision

No NAT gateways. Nodes run in public subnets with
`map_public_ip_on_launch = true` and route to the internet directly through an
internet gateway.

## Consequences

Egress costs nothing beyond standard data transfer, which keeps the project
inside its budget.

Nodes receive public IP addresses and are reachable from the internet at the
network layer. Security groups become the only barrier, so they must stay
tightly scoped. Nothing should permit `0.0.0.0/0` inbound except a load
balancer, and SSH to nodes should be closed entirely in favour of SSM Session
Manager.

There are no private subnets, so anything that assumes one will need the layout
revisited. That includes RDS subnet groups, VPC endpoints for private API
access, and any workload subject to a compliance rule requiring private
addressing.

Public subnets are tagged `kubernetes.io/role/elb = "1"` so the load balancer
controller can place internet-facing load balancers. Internal load balancers
would need private subnets tagged `kubernetes.io/role/internal-elb` and are
therefore unavailable.

This is not a production pattern. Moving to private subnets later means adding
the subnets, a NAT gateway or a cheaper alternative such as a NAT instance or
VPC endpoints, and recreating the node group. The node group recreation is the
expensive part, so the decision is worth revisiting before anything real runs
here.