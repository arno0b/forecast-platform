data "aws_availability_zones" "available" {
  state = "available"

  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

locals {
  azs = slice(
    data.aws_availability_zones.available.names,
    0,
    var.public_subnet_count,
  )

  subnet_newbits = 20 - tonumber(split("/", var.vpc_cidr)[1])

  public_subnets = {
    for idx, az in local.azs :
    az => cidrsubnet(var.vpc_cidr, local.subnet_newbits, idx)
  }
}

resource "aws_vpc" "this" {
  cidr_block = var.vpc_cidr

  # EKS will not function without both of these.
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "${var.name}-vpc"
  })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-igw"
  })
}

resource "aws_subnet" "public" {
  for_each = local.public_subnets

  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = each.value

  # No NAT gateway, so nodes need public IPs to reach the EKS control plane and ECR.
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "${var.name}-public-${each.key}"

    # How the AWS Load Balancer Controller discovers where to place public LBs.
    "kubernetes.io/role/elb" = "1"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  tags = merge(var.tags, {
    Name = "${var.name}-public"
  })
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}