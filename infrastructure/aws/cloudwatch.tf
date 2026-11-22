resource "aws_cloudwatch_log_group" "lambda_cron" {
  name              = "/aws/lambda/xnch-cron"
  retention_in_days = 7
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "ecs_xnch" {
  name              = "/aws/ecs/xnch"
  retention_in_days = 7
  tags              = local.common_tags
}

resource "aws_cloudwatch_log_group" "ecs_nexi" {
  name              = "/aws/ecs/nexi"
  retention_in_days = 7
  tags              = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "xnch_high_cpu" {
  alarm_name          = "xnch-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "xnch ECS service CPU is high"
  alarm_actions       = []
  dimensions = {
    ServiceName = "xnch-service"
    ClusterName = "xnch-cluster"
  }
  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "nexi_high_cpu" {
  alarm_name          = "nexi-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "nexi ECS service CPU is high"
  alarm_actions       = []
  dimensions = {
    ServiceName = "nexi-service"
    ClusterName = "xnch-cluster"
  }
  tags = local.common_tags
}