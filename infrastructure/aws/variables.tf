variable "domain" {
  description = "Root domain for DNS"
  type        = string
  default     = "x-nch.com"
}

variable "subdomain" {
  description = "API subdomain prefix"
  type        = string
  default     = "api"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "trial"
}

variable "app_runner_cpu" {
  description = "App Runner vCPU (e.g. \"0.25 vCPU\")"
  type        = string
  default     = "0.25 vCPU"
}

variable "app_runner_memory" {
  description = "App Runner memory (e.g. \"1 GB\")"
  type        = string
  default     = "1 GB"
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_allocated_storage" {
  description = "RDS storage in GB"
  type        = number
  default     = 20
}

variable "github_repo_owner" {
  description = "GitHub repository owner"
  type        = string
}

variable "github_repo_xnch" {
  description = "GitHub xnch repo name"
  type        = string
  default     = "xnchSystems"
}

variable "github_repo_nexi" {
  description = "GitHub nexi repo name"
  type        = string
  default     = "xnchSystems"
}

variable "github_branch" {
  description = "GitHub branch for auto-deploy"
  type        = string
  default     = "main"
}

variable "openrouter_api_key" {
  description = "OpenRouter API key"
  type        = string
  sensitive   = true
}

variable "upstash_redis_url" {
  description = "Upstash Redis URL"
  type        = string
}

variable "upstash_redis_password" {
  description = "Upstash Redis password"
  type        = string
  sensitive   = true
}