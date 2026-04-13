#!/bin/bash
set -e

echo "开始构建 TypeScript 项目..."

# Navigate to project directory
cd "$(dirname "$0")/.."

# Install Node.js dependencies if node_modules doesn't exist
if [ ! -d "node_modules" ]; then
    echo "安装 Node.js 依赖..."
    npm install
fi

# Build TypeScript
echo "编译 TypeScript..."
npm run build

echo "构建完成！"
echo ""
echo "可执行以下命令："
echo "  npm start        - 启动 Web 服务器"
echo "  npm run dev      - 开发模式运行"
echo "  npm run cli      - 安装 CLI 为全局命令"
