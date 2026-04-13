#!/bin/bash
set -e

echo "安装 Python 依赖..."

cd "$(dirname "$0")/.."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "错误：未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

# Check if pip is installed
if ! command -v pip &> /dev/null; then
    echo "错误：未找到 pip，请先安装 pip"
    exit 1
fi

# Create virtual environment (optional but recommended)
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "激活虚拟环境..."
source venv/bin/activate

# Upgrade pip
echo "升级 pip..."
pip install --upgrade pip

# Install Python dependencies
echo "安装 Python 包..."
pip install -r requirements.txt

echo ""
echo "Python 依赖安装完成！"
echo ""
echo "可选：激活虚拟环境"
echo "  source venv/bin/activate  # Linux/macOS"
echo "  venv\\Scripts\\activate     # Windows"
