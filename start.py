# -*- coding: utf-8 -*-
"""
Starrain-BOT 启动脚本
检测环境并启动机器人
"""
import sys
import subprocess
import os
from pathlib import Path

class Colors:
    """终端颜色"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    """打印标题"""
    print(Colors.HEADER + "\n" + "=" * 60)
    print(f"        {text}")
    print("=" * 60 + Colors.ENDC + "\n")

def print_success(text):
    """打印成功信息"""
    print(Colors.OKGREEN + f"✓ {text}" + Colors.ENDC)

def print_error(text):
    """打印错误信息"""
    print(Colors.FAIL + f"✗ {text}" + Colors.ENDC)

def print_warning(text):
    """打印警告信息"""
    print(Colors.WARNING + f"⚠ {text}" + Colors.ENDC)

def print_info(text):
    """打印信息"""
    print(Colors.OKCYAN + f"ℹ {text}" + Colors.ENDC)

def pause():
    """暂停等待用户确认"""
    if os.name == 'nt':
        os.system('pause')
    else:
        input("按回车键退出...")

def detect_python_executable():
    """检测 Python 解释器"""
    python_exe = "python"
    venv_found = False

    if os.name == 'nt':
        venv_paths = [
            "venv\\Scripts\\python.exe",
            ".venv\\Scripts\\python.exe"
        ]
    else:
        venv_paths = [
            "venv/bin/python",
            ".venv/bin/python"
        ]

    # 检查虚拟环境
    for venv_path in venv_paths:
        if Path(venv_path).exists():
            python_exe = venv_path
            venv_found = True
            print_info(f"使用虚拟环境: {venv_path}")
            break

    if not venv_found:
        print_warning("未检测到虚拟环境，使用系统 Python")

    return python_exe, venv_found

def check_python_version(python_exe):
    """检查 Python 版本"""
    try:
        result = subprocess.run(
            [python_exe, "--version"],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print_info(f"Python 版本: {version}")
            return True
    except:
        pass
    return False

def check_configuration():
    """检查配置文件"""
    config_file = Path("config/config.yaml")
    if not config_file.exists():
        print_error("未找到配置文件 config/config.yaml!")
        print()
        print_info("请先运行以下命令进行初始化配置:")
        print("  Windows: install.bat")
        print("  Linux/Mac: python setup.py")
        return False
    
    print_success("配置文件已存在")
    return True

def check_main_file():
    """检查主程序文件"""
    main_file = Path("src/main.py")
    if not main_file.exists():
        print_error("未找到主程序 src/main.py!")
        return False
    
    print_success("主程序文件已存在")
    return True

def prepare_directories():
    """准备必要的目录"""
    directories = ["logs", "cache", "save"]
    prepared = False
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                print_info(f"目录已创建: {dir_name}/")
                prepared = True
            except Exception as e:
                print_warning(f"创建目录失败 {dir_name}: {e}")
    
    return True

def start_bot(python_exe):
    """启动机器人"""
    print_info("正在启动机器人...")
    print()
    print("按 Ctrl+C 可停止机器人")
    print("=" * 60)
    print()

    try:
        result = subprocess.run([python_exe, "src/main.py"])
        return result.returncode
    except KeyboardInterrupt:
        print("\n\n机器人已停止")
        return 0
    except Exception as e:
        print_error(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    """主函数"""
    print_header("Starrain-BOT 快速启动")

    # 检测 Python 解释器
    python_exe, venv_found = detect_python_executable()
    
    # 检查 Python 版本
    if not check_python_version(python_exe):
        print_error("Python 未找到或版本不兼容")
        pause()
        sys.exit(1)
    
    print()

    # 检查配置文件
    if not check_configuration():
        pause()
        sys.exit(1)
    
    # 检查主程序文件
    if not check_main_file():
        pause()
        sys.exit(1)
    
    # 准备目录
    prepare_directories()
    print()

    # 启动机器人
    exit_code = start_bot(python_exe)
    
    # 显示退出信息
    print()
    print("=" * 60)
    if exit_code == 0:
        print_success("机器人已正常停止")
    else:
        print_warning(f"机器人已停止 (退出代码: {exit_code})")
    print("=" * 60)
    print()

    # 如果错误退出则暂停
    if exit_code != 0:
        pause()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print_error(f"未能预期的错误: {e}")
        import traceback
        traceback.print_exc()
        pause()
        sys.exit(1)
