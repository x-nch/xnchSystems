resource "aws_db_subnet_group" "rds" {
  name       = "xnch-rds-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = local.common_tags
}

resource "aws_db_instance" "postgres" {
  identifier       = "xnch-postgres"
  instance_class   = var.rds_instance_class
  engine           = "postgres"
  engine_version   = "16.3"
  allocated_storage = var.rds_allocated_storage
  storage_type     = "gp3"
  db_name          = "xnch"
  username         = "xnch"
  password         = random_password.rds_password.result
  port             = 5432
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.rds.name
  backup_retention_period = 0
  multi_az               = false
  skip_final_snapshot    = true
  deletion_protection    = false
  tags = local.common_tags
}

resource "random_password" "rds_password" {
  length  = 16
  special = true
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "xnch/db-credentials"
  description = "Database credentials for xnch and nexi"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id     = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    host     = aws_db_instance.postgres.address
    port     = 5432
    dbname   = "xnch"
    username = "xnch"
    password = random_password.rds_password.result
  })
}

resource "aws_secretsmanager_secret" "auth_secret" {
  name        = "xnch/auth-secret"
  description = "Auth secret for xnch control plane"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "auth_secret" {
  secret_id     = aws_secretsmanager_secret.auth_secret.id
  secret_string = random_password.auth_secret.result
}

resource "random_password" "auth_secret" {
  length  = 64
  special = true
}

resource "aws_secretsmanager_secret" "openrouter_key" {
  name        = "nexi/openrouter-api-key"
  description = "OpenRouter API key for nexi model router"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "openrouter_key" {
  secret_id     = aws_secretsmanager_secret.openrouter_key.id
  secret_string = var.openrouter_api_key
}