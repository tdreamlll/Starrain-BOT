# -*- coding: utf-8 -*-
"""
Starrain-BOT Debug Helper
Help script for start_debug.bat to display Chinese messages
"""

import sys
import os

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"[成功] {text}")

def print_error(text):
    print(f"[错误] {text}")

def print_warning(text):
    print(f"[警告] {text}")

def main():
    if len(sys.argv) < 2:
        print("Usage: debug_helper.py <message_type> [args...]")
        return
    
    msg_type = sys.argv[1].lower()
    
    if msg_type == 'header':
        if len(sys.argv) >= 3:
            print_header(sys.argv[2])
    
    elif msg_type == 'success':
        if len(sys.argv) >= 3:
            print_success(sys.argv[2])
    
    elif msg_type == 'error':
        if len(sys.argv) >= 3:
            print_error(sys.argv[2])
    
    elif msg_type == 'warning':
        if len(sys.argv) >= 3:
            print_warning(sys.argv[2])
    
    elif msg_type == 'python_not_found':
        print("错误: Python未安装或未添加到PATH环境变量")
        print("请从 https://www.python.org/ 安装 Python 3.8 或更高版本")
    
    elif msg_type == 'venv_failed':
        print("错误: 创建虚拟环境失败")
        print("可能的原因:")
        print("- Python未正确安装")
        print("- 权限不足")
        print("- 杀毒软件阻止操作")
    
    elif msg_type == 'activate_failed':
        print("错误: 激活虚拟环境失败")
        print("venv\\Scripts\\activate.bat 文件可能已损坏")
        print("请尝试删除 venv 文件夹后重新运行此脚本")
    
    elif msg_type == 'pip_warning':
        print("警告: pip可能无法正常工作")
    
    elif msg_type == 'config_not_found':
        print("错误: 未找到 config\\config.yaml 文件!")
        print("请将 config.yaml.example 复制为 config.yaml 并进行配置")
    
    elif msg_type == 'bot_start':
        print("正在启动机器人...")
        print("\n" + "=" * 50)
        print("按 Ctrl+C 可以停止机器人")
        print("=" * 50 + "\n")
    
    elif msg_type == 'bot_exited':
        exit_code = sys.argv[2] if len(sys.argv) >= 3 else "unknown"
        print(f"\n{'='*50}")
        print(f"机器人已退出，退出代码: {exit_code}")
        print(f"{'='*50}\n")
    
    elif msg_type == 'ask_install':
        print("是否要安装或更新依赖包 [Y/N]?")
    
    elif msg_type == 'install_deps':
        print("正在安装依赖包...")
    
    else:
        print(' '.join(sys.argv[1:]))

if __name__ == '__main__':
    main()
