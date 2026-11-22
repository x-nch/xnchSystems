output "vpc_id" {
  value       = aws_vpc.main.id
  description = "VPC ID"
}

output "rds_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "RDS PostgreSQL endpoint"
  sensitive   = true
}

output "rds_port" {
  value       = aws_db_instance.postgres.port
  description = "RDS PostgreSQL port"
}

output "route53_zone_id" {
  value       = aws_route53_zone.main.id
  description = "Route53 hosted zone ID"
}

output "secrets_db_credentials_arn" {
  value       = aws_secretsmanager_secret.db_credentials.arn
  description = "Secrets Manager ARN for DB credentials"
}

output "secrets_auth_secret_arn" {
  value       = aws_secretsmanager_secret.auth_secret.arn
  description = "Secrets Manager ARN for auth secret"
}

output "secrets_openrouter_key_arn" {
  value       = aws_secretsmanager_secret.openrouter_key.arn
  description = "Secrets Manager ARN for OpenRouter API key"
}

output "ecr_repository_xnch_url" {
  value       = aws_ecr_repository.xnch.repository_url
  description = "ECR repository URL for xnch image"
}

output "ecr_repository_nexi_url" {
  value       = aws_ecr_repository.nexi.repository_url
  description = "ECR repository URL for nexi image"
}

output "xnch_domain" {
  value       = local.xnch_domain
  description = "xnch custom domain"
}

output "nexi_domain" {
  value       = local.nexi_domain
  description = "nexi custom domain"
}

output "alb_dns_name" {
  value       = aws_lb.main.dns_name
  description = "ALB DNS name for xnch API and nexi API"
}