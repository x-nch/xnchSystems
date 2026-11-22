locals {
  app_runner_port = "8080"

  xnch_service_name  = "xnch"
  nexi_service_name  = "nexi"

  xnch_subdomain  = "xnch"
  nexi_subdomain  = "nexi"

  xnch_domain  = "${local.xnch_subdomain}.${var.subdomain}.${var.domain}"
  nexi_domain  = "${local.nexi_subdomain}.${var.subdomain}.${var.domain}"

  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "xnch"
  }
}