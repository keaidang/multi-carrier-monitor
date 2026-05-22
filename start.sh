#!/bin/bash
# 多运营商套餐监控系统 - Linux/Mac 启动脚本

echo ""
echo "============================================================"
echo "多运营商套餐监控系统 - 网页版"
echo "============================================================"
echo ""

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未检测到 Python 3，请先安装 Python"
    exit 1
fi

# 切换到项目目录
cd "$(dirname "$0")"

# 安装依赖
echo "正在检查并自动安装依赖..."
python3 -m pip install -r requirements.txt -q

echo ""
echo "正在启动服务器..."
echo ""
echo "服务器地址: http://localhost:10000"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""

python3 app/api_server.py
