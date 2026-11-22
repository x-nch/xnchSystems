resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags = merge(local.common_tags, {
    Name = "xnch-vpc"
  })
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${count.index}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags = merge(local.common_tags, {
    Name = "xnch-public-${count.index}"
    Type = "public"
  })
}

resource "aws_subnet" "private" {
  count         = 2
  vpc_id        = aws_vpc.main.id
  cidr_block    = "10.0.${10 + count.index}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  tags = merge(local.common_tags, {
    Name = "xnch-private-${count.index}"
    Type = "private"
  })
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id
  tags = merge(local.common_tags, {
    Name = "xnch-igw"
  })
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id
  tags = merge(local.common_tags, {
    Name = "xnch-nat"
  })
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags = merge(local.common_tags, {
    Name = "xnch-nat-eip"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  tags = merge(local.common_tags, {
    Name = "xnch-public-rt"
  })
}

resource "aws_route" "public_igw" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id
  tags = merge(local.common_tags, {
    Name = "xnch-private-rt"
  })
}

resource "aws_route" "private_nat" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat.id
}

resource "aws_route_table_association" "private" {
  count          = length(aws_subnet.private)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}