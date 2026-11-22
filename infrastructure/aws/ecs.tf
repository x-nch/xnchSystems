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

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "xnch-cluster"
  tags = local.common_tags

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ECS Task Definition: xnch
resource "aws_ecs_task_definition" "xnch" {
  family                   = "xnch"
  cpu                      = "256"
  memory                   = "512"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "xnch"
      image     = aws_ecr_repository.xnch.repository_url
      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]
      essential = true
      environment = [
        {
          name  = "XNCH_LLM_MODEL_ID"
          value = "nexi-default"
        },
        {
          name  = "XNCH_LANGGRAPH_PIPELINE"
          value = "true"
        },
        {
          name  = "XNCH_MEMORY_EMBEDDED"
          value = "false"
        },
        {
          name  = "XNCH_DB_PATH"
          value = ""
        },
        {
          name  = "XNCH_NEXI_BASE_URL"
          value = "https://nexi.api.x-nch.com"
        },
        {
          name  = "XNCH_SELF_BASE_URL"
          value = "https://xnch.api.x-nch.com"
        },
      ]
      secrets = [
        {
          name      = "XNCH_POSTGRES_URL"
          valueFrom = aws_secretsmanager_secret.db_credentials.arn
        },
        {
          name      = "XNCH_REDIS_URL"
          valueFrom = aws_secretsmanager_secret.auth_secret.arn
        },
        {
          name      = "XNCH_AUTH_SECRET"
          valueFrom = aws_secretsmanager_secret.auth_secret.arn
        },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_xnch.name
          "awslogs-region"        = "ap-south-1"
          "awslogs-stream-prefix" = "xnch"
        }
      }
      ulimits = [
        {
          name = "nofile"
          softLimit = 65535
          hardLimit = 65535
        }
      ]
    }
  ])

  tags = local.common_tags
}

# ECS Task Definition: nexi
resource "aws_ecs_task_definition" "nexi" {
  family                   = "nexi"
  cpu                      = "256"
  memory                   = "512"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  runtime_platform {
    cpu_architecture        = "ARM64"
    operating_system_family = "LINUX"
  }

  container_definitions = jsonencode([
    {
      name      = "nexi"
      image     = aws_ecr_repository.nexi.repository_url
      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]
      essential = true
      environment = [
        {
          name  = "NEXI_XNCH_BASE_URL"
          value = "https://xnch.api.x-nch.com"
        },
        {
          name  = "NEXI_OPENROUTER_DEFAULT_MODEL"
          value = "anthropic/claude-sonnet-4"
        },
        {
          name  = "NEXI_NEXI_DEFAULT_RESOLVES_TO"
          value = "openrouter"
        },
        {
          name  = "NEXI_REFLECTION_ENABLED"
          value = "true"
        },
        {
          name  = "NEXI_CAPABILITY_AUTO_REFRESH"
          value = "true"
        },
        {
          name  = "NEXI_PERSONA_AUTO_REFRESH"
          value = "true"
        },
      ]
      secrets = [
        {
          name      = "NEXI_REDIS_URL"
          valueFrom = aws_secretsmanager_secret.auth_secret.arn
        },
        {
          name      = "NEXI_OPENROUTER_API_KEY"
          valueFrom = aws_secretsmanager_secret.openrouter_key.arn
        },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_nexi.name
          "awslogs-region"        = "ap-south-1"
          "awslogs-stream-prefix" = "nexi"
        }
      }
      ulimits = [
        {
          name = "nofile"
          softLimit = 65535
          hardLimit = 65535
        }
      ]
    }
  ])

  tags = local.common_tags
}

# Security Group: ALB
resource "aws_security_group" "alb" {
  name        = "xnch-alb-sg"
  description = "Security group for ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Allow HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = merge(local.common_tags, {
    Name = "xnch-alb-sg"
  })
}

# ALB
resource "aws_lb" "main" {
  name               = "xnch-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  enable_deletion_protection = false

  tags = local.common_tags
  timeouts {
    create = "10m"
    delete = "10m"
  }
}

# Target Group: xnch
resource "aws_lb_target_group" "xnch" {
  name        = "xnch-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    protocol            = "HTTP"
  }

  tags = local.common_tags
}

# Target Group: nexi
resource "aws_lb_target_group" "nexi" {
  name        = "nexi-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled         = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    protocol            = "HTTP"
  }

  tags = local.common_tags
}

# ALB Listener: HTTP port 80
resource "aws_lb_listener" "main" {
  load_balancer_arn = aws_lb.main.id
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.xnch.id
  }
}

# Listener Rule: xnch host header
resource "aws_lb_listener_rule" "xnch" {
  listener_arn = aws_lb_listener.main.id
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.xnch.id
  }

  condition {
    host_header {
      values = ["xnch.api.x-nch.com"]
    }
  }
}

# Listener Rule: nexi host header
resource "aws_lb_listener_rule" "nexi" {
  listener_arn = aws_lb_listener.main.id
  priority     = 20

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nexi.id
  }

  condition {
    host_header {
      values = ["nexi.api.x-nch.com"]
    }
  }
}

# ECS Service: xnch
resource "aws_ecs_service" "xnch" {
  name            = "xnch-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.xnch.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.xnch.arn
    container_name   = "xnch"
    container_port   = 8080
  }

  depends_on = [
    aws_lb_listener_rule.xnch,
  ]

  tags = local.common_tags
}

# ECS Service: nexi
resource "aws_ecs_service" "nexi" {
  name            = "nexi-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.nexi.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.nexi.arn
    container_name   = "nexi"
    container_port   = 8080
  }

  depends_on = [
    aws_lb_listener_rule.nexi,
  ]

  tags = local.common_tags
}