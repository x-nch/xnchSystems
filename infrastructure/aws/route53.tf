resource "aws_route53_zone" "main" {
  name = var.domain
  tags = local.common_tags
}

# Route53 Alias records pointing to ALB DNS name
resource "aws_route53_record" "xnch" {
  name    = local.xnch_domain
  type    = "A"
  zone_id = aws_route53_zone.main.id
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = false
  }
}

resource "aws_route53_record" "nexi" {
  name    = local.nexi_domain
  type    = "A"
  zone_id = aws_route53_zone.main.id
  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = false
  }
}

# ACM Certificates already exist from previous apply:
#   xnch.api.x-nch.com: arn:aws:acm:ap-south-1:547602847101:certificate/39743269-e255-4c62-acb9-149215e4455b
#   nexi.api.x-nch.com: arn:aws:acm:ap-south-1:547602847101:certificate/1dcfd583-750e-4c61-b754-a33b5b8b7ee7
# DNS validation records exist but certificates may need manual validation in AWS Console.
# To enable HTTPS, add an HTTPS listener to the ALB referencing these certs.