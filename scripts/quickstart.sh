#!/bin/bash
set -e

echo "=========================================="
echo "  门诊医嘱-病程矛盾检测系统 - 快速演示"
echo "=========================================="
echo ""

cd "$(dirname "$0")/.."

# Step 1: Install dependencies
echo "[1/5] 检查 Python 依赖..."
if [ ! -f "requirements.txt" ]; then
    echo "错误：未找到 requirements.txt"
    exit 1
fi

pip install -r requirements.txt -q
echo "      Python 依赖就绪"
echo ""

# Step 2: Install Node.js dependencies
echo "[2/5] 检查 Node.js 依赖..."
if [ ! -d "node_modules" ]; then
    echo "      安装 Node.js 依赖..."
    npm install
fi
echo "      Node.js 依赖就绪"
echo ""

# Step 3: Build TypeScript
echo "[3/5] 编译 TypeScript..."
npm run build
echo "      编译完成"
echo ""

# Step 4: Run detection with sample data
echo "[4/5] 使用示例数据运行矛盾检测..."
echo ""

# Create output directory if not exists
mkdir -p data/output

# Run Python CLI detection
python -m src.py.cli detect \
    --his data/sample/his_orders_sample.csv \
    --emr data/sample/emr_records_sample.csv \
    --output data/output/

echo ""
echo "      检测完成！结果保存在 data/output/"
echo ""

# Step 5: Show statistics
echo "[5/5] 生成统计报表..."
echo ""

python -m src.py.cli stats --input data/output/

echo ""
echo "=========================================="
echo "  演示完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "  1. 查看 Web 可视化仪表盘：npm start"
echo "  2. 查看更多命令帮助：order-emr-detect --help"
echo "  3. 查看 API 文档：docs/api.md"
echo ""
