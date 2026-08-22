#!/usr/bin/env bash
# 数据整理与特征转换工作台 · Web 版（Linux / macOS 启动脚本）
set -e
cd "$(dirname "$0")/webapp"

echo "============================================================"
echo "  数据整理与特征转换工作台 · Web 版"
echo "  配套「终极版数据集模板 v3」的前置自动化工具"
echo "============================================================"
echo

# 检查 Python
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[错误] 未检测到 Python 3.8+，请先安装。"
    exit 1
fi

# 检查依赖
echo "[1/3] 检查依赖库..."
if ! $PY -c "import numpy, pandas, openpyxl" >/dev/null 2>&1; then
    echo "      正在安装 numpy / pandas / openpyxl ..."
    $PY -m pip install numpy pandas openpyxl
fi
echo "      依赖就绪。"

# 启动服务（自动打开浏览器）
echo "[2/3] 启动服务（端口 8765）..."
echo "[3/3] 浏览器将自动打开 http://127.0.0.1:8765"
echo "      关闭服务：按 Ctrl+C"
echo
exec $PY server.py
