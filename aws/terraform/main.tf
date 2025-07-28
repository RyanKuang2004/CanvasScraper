# =====================================================
# Canvas Scraper Enhanced - AWS Infrastructure
# Terraform configuration for assignments/quizzes integration
# =====================================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # Remote state configuration
  backend "s3" {
    bucket         = "canvas-scraper-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "canvas-scraper-terraform-lock"
  }
}

# =====================================================
# PROVIDER CONFIGURATION
# =====================================================
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "Canvas Scraper Enhanced"
      Environment = var.environment
      Terraform   = "true"
      ManagedBy   = "terraform"
    }
  }
}

# =====================================================
# DATA SOURCES
# =====================================================
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

# =====================================================
# VARIABLES
# =====================================================
variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "canvas-scraper"
}

variable "supabase_url" {
  description = "Supabase project URL"
  type        = string
  sensitive   = true
}

variable "supabase_anon_key" {
  description = "Supabase anonymous key"
  type        = string
  sensitive   = true
}

variable "supabase_service_key" {
  description = "Supabase service role key"
  type        = string
  sensitive   = true
}

variable "canvas_api_token" {
  description = "Canvas API access token"
  type        = string
  sensitive   = true
}

variable "canvas_url" {
  description = "Canvas LMS API URL"
  type        = string
  default     = "https://canvas.lms.unimelb.edu.au/api/v1"
}

# =====================================================
# VPC AND NETWORKING
# =====================================================
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "${var.project_name}-vpc-${var.environment}"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  
  tags = {
    Name = "${var.project_name}-igw-${var.environment}"
  }
}

# Public subnets for ALB
resource "aws_subnet" "public" {
  count = 2
  
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  
  tags = {
    Name = "${var.project_name}-public-${count.index + 1}-${var.environment}"
    Type = "public"
  }
}

# Private subnets for ECS tasks
resource "aws_subnet" "private" {
  count = 2
  
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = {
    Name = "${var.project_name}-private-${count.index + 1}-${var.environment}"
    Type = "private"
  }
}

# NAT Gateways for outbound internet access
resource "aws_eip" "nat" {
  count = 2
  
  domain = "vpc"
  
  tags = {
    Name = "${var.project_name}-nat-eip-${count.index + 1}-${var.environment}"
  }
  
  depends_on = [aws_internet_gateway.main]
}

resource "aws_nat_gateway" "main" {
  count = 2
  
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  
  tags = {
    Name = "${var.project_name}-nat-${count.index + 1}-${var.environment}"
  }
  
  depends_on = [aws_internet_gateway.main]
}

# Route tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  
  tags = {
    Name = "${var.project_name}-public-rt-${var.environment}"
  }
}

resource "aws_route_table" "private" {
  count = 2
  
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }
  
  tags = {
    Name = "${var.project_name}-private-rt-${count.index + 1}-${var.environment}"
  }
}

# Route table associations
resource "aws_route_table_association" "public" {
  count = 2
  
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count = 2
  
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# =====================================================
# SECURITY GROUPS
# =====================================================
resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-${var.environment}"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "${var.project_name}-alb-sg-${var.environment}"
  }
}

resource "aws_security_group" "ecs_tasks" {
  name_prefix = "${var.project_name}-ecs-tasks-${var.environment}"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  
  # Allow tasks to communicate with each other
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "${var.project_name}-ecs-tasks-sg-${var.environment}"
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.project_name}-redis-${var.environment}"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
  
  tags = {
    Name = "${var.project_name}-redis-sg-${var.environment}"
  }
}

# =====================================================
# SQS QUEUES
# =====================================================
resource "aws_sqs_queue" "assessment_processing" {
  name                       = "${var.project_name}-assessment-processing-${var.environment}"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 1209600  # 14 days
  max_message_size          = 262144   # 256 KB
  
  # Dead letter queue configuration
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.assessment_processing_dlq.arn
    maxReceiveCount     = 3
  })
  
  tags = {
    Name = "${var.project_name}-assessment-processing-${var.environment}"
  }
}

resource "aws_sqs_queue" "assessment_processing_dlq" {
  name                      = "${var.project_name}-assessment-processing-dlq-${var.environment}"
  message_retention_seconds = 1209600  # 14 days
  
  tags = {
    Name = "${var.project_name}-assessment-processing-dlq-${var.environment}"
  }
}

resource "aws_sqs_queue" "notifications" {
  name                       = "${var.project_name}-notifications-${var.environment}"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 1209600  # 14 days
  
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = 3
  })
  
  tags = {
    Name = "${var.project_name}-notifications-${var.environment}"
  }
}

resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${var.project_name}-notifications-dlq-${var.environment}"
  message_retention_seconds = 1209600  # 14 days
  
  tags = {
    Name = "${var.project_name}-notifications-dlq-${var.environment}"
  }
}

# =====================================================
# ELASTICACHE REDIS
# =====================================================
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-redis-subnet-group-${var.environment}"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "${var.project_name}-redis-subnet-group-${var.environment}"
  }
}

resource "aws_elasticache_replication_group" "main" {
  description          = "Redis cluster for Canvas Scraper caching"
  replication_group_id = "${var.project_name}-redis-${var.environment}"
  
  # Node configuration
  node_type = var.environment == "prod" ? "cache.t3.medium" : "cache.t3.micro"
  port      = 6379
  
  # Cluster configuration
  num_cache_clusters = var.environment == "prod" ? 2 : 1
  
  # Parameter group
  parameter_group_name = "default.redis7"
  
  # Networking
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]
  
  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result
  
  # Maintenance
  maintenance_window = "sun:02:00-sun:03:00"
  
  # Backup
  snapshot_retention_limit = var.environment == "prod" ? 7 : 1
  snapshot_window         = "01:00-02:00"
  
  tags = {
    Name = "${var.project_name}-redis-${var.environment}"
  }
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

# =====================================================
# S3 BUCKET FOR FILE STORAGE
# =====================================================
resource "aws_s3_bucket" "file_storage" {
  bucket = "${var.project_name}-file-storage-${var.environment}-${random_id.bucket_suffix.hex}"
  
  tags = {
    Name = "${var.project_name}-file-storage-${var.environment}"
  }
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "file_storage" {
  bucket = aws_s3_bucket.file_storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "file_storage" {
  bucket = aws_s3_bucket.file_storage.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "file_storage" {
  depends_on = [aws_s3_bucket_versioning.file_storage]
  bucket     = aws_s3_bucket.file_storage.id
  
  rule {
    id     = "file_lifecycle"
    status = "Enabled"
    
    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }
    
    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }
    
    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}

# =====================================================
# ECR REPOSITORY
# =====================================================
resource "aws_ecr_repository" "main" {
  name                 = "${var.project_name}-${var.environment}"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name = "${var.project_name}-ecr-${var.environment}"
  }
}

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name
  
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 production images"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = ["prod"]
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 5 staging images"
        selection = {
          tagStatus   = "tagged"
          tagPrefixList = ["staging"]
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 3
        description  = "Expire untagged images older than 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# =====================================================
# ECS CLUSTER
# =====================================================
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster-${var.environment}"
  
  configuration {
    execute_command_configuration {
      logging = "OVERRIDE"
      
      log_configuration {
        cloud_watch_log_group_name = aws_cloudwatch_log_group.ecs_exec.name
      }
    }
  }
  
  tags = {
    Name = "${var.project_name}-cluster-${var.environment}"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name
  
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  
  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }
  
  default_capacity_provider_strategy {
    base              = 0
    weight            = 0
    capacity_provider = "FARGATE_SPOT"
  }
}

# =====================================================
# CLOUDWATCH LOG GROUPS
# =====================================================
resource "aws_cloudwatch_log_group" "ecs_exec" {
  name              = "/ecs/exec/${var.project_name}-${var.environment}"
  retention_in_days = 7
  
  tags = {
    Name = "${var.project_name}-ecs-exec-logs-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "orchestrator" {
  name              = "/ecs/${var.project_name}/orchestrator"
  retention_in_days = var.environment == "prod" ? 30 : 7
  
  tags = {
    Name = "${var.project_name}-orchestrator-logs-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "assessment_processor" {
  name              = "/ecs/${var.project_name}/assessment-processor"
  retention_in_days = var.environment == "prod" ? 30 : 7
  
  tags = {
    Name = "${var.project_name}-assessment-processor-logs-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "notification_service" {
  name              = "/ecs/${var.project_name}/notification-service"
  retention_in_days = var.environment == "prod" ? 30 : 7
  
  tags = {
    Name = "${var.project_name}-notification-service-logs-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "scheduler" {
  name              = "/ecs/${var.project_name}/scheduler"
  retention_in_days = var.environment == "prod" ? 30 : 7
  
  tags = {
    Name = "${var.project_name}-scheduler-logs-${var.environment}"
  }
}

# =====================================================
# OUTPUTS
# =====================================================
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "ecs_cluster_id" {
  description = "ID of the ECS cluster"
  value       = aws_ecs_cluster.main.id
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.main.repository_url
}

output "sqs_assessment_queue_url" {
  description = "URL of the SQS assessment processing queue"
  value       = aws_sqs_queue.assessment_processing.url
}

output "sqs_notification_queue_url" {
  description = "URL of the SQS notification queue"
  value       = aws_sqs_queue.notifications.url
}

output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = aws_elasticache_replication_group.main.configuration_endpoint_address
}

output "redis_auth_token" {
  description = "Redis authentication token"
  value       = random_password.redis_auth.result
  sensitive   = true
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for file storage"
  value       = aws_s3_bucket.file_storage.bucket
}

output "security_group_ecs_tasks_id" {
  description = "ID of the ECS tasks security group"
  value       = aws_security_group.ecs_tasks.id
}