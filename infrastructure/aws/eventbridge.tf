resource "aws_lambda_function" "cron_pattern_extractor" {
  function_name = "xnch-cron-pattern-extractor"
  role          = aws_iam_role.lambda_cron.arn
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"
  filename      = "${path.module}/lambda_cron/pattern_extractor.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda_cron/pattern_extractor.zip")
  timeout       = 300
  memory_size   = 256
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = {
      XNCH_BASE_URL = "https://${local.xnch_domain}"
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "cron_weight_evolver" {
  function_name = "xnch-cron-weight-evolver"
  role          = aws_iam_role.lambda_cron.arn
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"
  filename      = "${path.module}/lambda_cron/weight_evolver.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda_cron/weight_evolver.zip")
  timeout       = 300
  memory_size   = 256
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = {
      XNCH_BASE_URL = "https://${local.xnch_domain}"
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "cron_policy_evolver" {
  function_name = "xnch-cron-policy-evolver"
  role          = aws_iam_role.lambda_cron.arn
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"
  filename      = "${path.module}/lambda_cron/policy_evolver.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda_cron/policy_evolver.zip")
  timeout       = 300
  memory_size   = 256
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = {
      XNCH_BASE_URL = "https://${local.xnch_domain}"
    }
  }
  tags = local.common_tags
}

resource "aws_lambda_function" "cron_policy_candidates" {
  function_name = "xnch-cron-policy-candidates"
  role          = aws_iam_role.lambda_cron.arn
  runtime       = "python3.13"
  handler       = "lambda_function.lambda_handler"
  filename      = "${path.module}/lambda_cron/policy_candidates.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda_cron/policy_candidates.zip")
  timeout       = 300
  memory_size   = 256
  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
  environment {
    variables = {
      XNCH_BASE_URL = "https://${local.xnch_domain}"
    }
  }
  tags = local.common_tags
}

resource "aws_cloudwatch_event_rule" "pattern_extractor" {
  name                = "xnch-cron-pattern-extractor"
  description         = "Run pattern extractor every 6 hours"
  schedule_expression = "cron(0 */6 * * ? *)"
  state = "ENABLED"
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_rule" "weight_evolver" {
  name                = "xnch-cron-weight-evolver"
  description         = "Run weight evolver every 6 hours at :30"
  schedule_expression = "cron(30 */6 * * ? *)"
  state = "ENABLED"
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_rule" "policy_evolver" {
  name                = "xnch-cron-policy-evolver"
  description         = "Run policy evolver every 6 hours at :45"
  schedule_expression = "cron(45 */6 * * ? *)"
  state = "ENABLED"
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_rule" "policy_candidates" {
  name                = "xnch-cron-policy-candidates"
  description         = "Run policy candidates every 6 hours at :50"
  schedule_expression = "cron(50 */6 * * ? *)"
  state = "ENABLED"
  tags                = local.common_tags
}

resource "aws_cloudwatch_event_target" "pattern_extractor" {
  rule      = aws_cloudwatch_event_rule.pattern_extractor.name
  arn       = aws_lambda_function.cron_pattern_extractor.arn
  input     = jsonencode({ job = "pattern_extractor" })
}

resource "aws_cloudwatch_event_target" "weight_evolver" {
  rule      = aws_cloudwatch_event_rule.weight_evolver.name
  arn       = aws_lambda_function.cron_weight_evolver.arn
  input     = jsonencode({ job = "weight_evolver" })
}

resource "aws_cloudwatch_event_target" "policy_evolver" {
  rule      = aws_cloudwatch_event_rule.policy_evolver.name
  arn       = aws_lambda_function.cron_policy_evolver.arn
  input     = jsonencode({ job = "policy_evolver" })
}

resource "aws_cloudwatch_event_target" "policy_candidates" {
  rule      = aws_cloudwatch_event_rule.policy_candidates.name
  arn       = aws_lambda_function.cron_policy_candidates.arn
  input     = jsonencode({ job = "policy_candidates" })
}

resource "aws_lambda_permission" "pattern_extractor" {
  statement_id  = "allow-eventbridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cron_pattern_extractor.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pattern_extractor.arn
}

resource "aws_lambda_permission" "weight_evolver" {
  statement_id  = "allow-eventbridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cron_weight_evolver.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weight_evolver.arn
}

resource "aws_lambda_permission" "policy_evolver" {
  statement_id  = "allow-eventbridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cron_policy_evolver.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.policy_evolver.arn
}

resource "aws_lambda_permission" "policy_candidates" {
  statement_id  = "allow-eventbridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cron_policy_candidates.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.policy_candidates.arn
}