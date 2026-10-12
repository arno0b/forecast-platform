output "cluster_name" {
  description = "Name of the cluster."
  value       = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint."
  value       = aws_eks_cluster.this.endpoint
}


output "cluster_certificate_authority_data" {
  description = "Base64-encoded CA certificate for the API server."
  value       = aws_eks_cluster.this.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "EKS-managed cluster security group. Node security groups must allow traffic to it."
  value       = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL, needed for IRSA in a later task."
  value       = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

output "cluster_iam_role_arn" {
  description = "ARN of the control plane IAM role."
  value       = aws_iam_role.cluster.arn
}

output "cluster_version" {
  description = "Kubernetes version running on the control plane."
  value       = aws_eks_cluster.this.version
}

output "node_iam_role_name" {
  description = "Name of the node IAM role."
  value       = aws_iam_role.node.name
}