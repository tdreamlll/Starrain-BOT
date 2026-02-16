#!/bin/bash

echo "================================"
echo "Starrain-BOT 一键启动"
echo "================================"

# 检查虚拟环境
if [ ! -f "venv/bin/activate" ]; then
    echo "[警告] 虚拟环境不存在或不完整，正在运行 setup.py..."
    python3 setup.py
    if [ $? -ne 0 ]; then
        echo "[错误] 虚拟环境创建失败"
        exit 1
    fi
fi

# 再次检查激活脚本
if [ ! -f "venv/bin/activate" ]; then
    echo "[错误] 虚拟环境激活脚本不存在"
    exit 1
fi

# 激活虚拟环境并运行
source venv/bin/activate
python3 main.py
