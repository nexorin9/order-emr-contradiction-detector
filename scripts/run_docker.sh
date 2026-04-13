#!/bin/bash
set -e

echo "使用 Docker 运行项目..."

cd "$(dirname "$0")/.."

# Check if Dockerfile exists
if [ ! -f "Dockerfile" ]; then
    echo "错误：未找到 Dockerfile"
    exit 1
fi

# Build Docker image
echo "构建 Docker 镜像..."
docker build -t order-emr-detector .

# Run container
echo "启动容器..."
docker run -p 3000:3000 order-emr-detector
