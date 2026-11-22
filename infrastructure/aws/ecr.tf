resource "aws_ecr_repository" "xnch" {
  name                 = "xnch/xnch"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.common_tags
}

resource "aws_ecr_repository" "nexi" {
  name                 = "xnch/nexi"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = local.common_tags
}