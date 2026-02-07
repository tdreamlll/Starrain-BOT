# -*- coding: utf-8 -*-
"""
Starrain-BOT 安装脚本
自动完成环境配置和依赖安装
"""
import sys
import subprocess
import os
from pathlib import Path
import time

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
    UNDERLINE = '\033[4m'

def print_header(text):
    """打印标题"""
    print(Colors.HEADER + "\n" + "=" * 60)
    print(f"    {text}")
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

def print_step(text):
    """打印步骤"""
    print(f"\n>>> {text} ...\n")

def pause():
    """暂停等待用户确认"""
    if os.name == 'nt':
        os.system('pause')
    else:
        input("按回车键继续...")

def check_python_version():
    """检查 Python 版本"""
    print_step("步骤 1/6: 检查 Python 环境")
    
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print_error(f"需要 Python 3.8 或更高版本")
        print_error(f"当前版本: {sys.version.split()[0]}")
        return False
    
    print_success(f"Python 版本: {sys.version.split()[0]}")
    print_success("Python 环境正常")
    return True

def create_virtual_environment():
    """创建虚拟环境"""
    print_step("步骤 2/6: 创建虚拟环境")
    
    venv_path = Path("venv")
    if venv_path.exists():
        print_info("虚拟环境已存在，跳过创建")
        return True
    
    print("正在创建虚拟环境...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", "venv"],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        print_success("虚拟环境已创建")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"创建虚拟环境失败: {e.stderr}")
        print_warning("可能的原因:")
        print("  - Python 未正确安装")
        print("  - 权限不足")
        print("  - 杀毒软件阻止操作")
        return False

def get_venv_python():
    """获取虚拟环境 Python 路径"""
    if os.name == 'nt':
        return "venv/Scripts/python.exe"
    else:
        return "venv/bin/python"

def upgrade_pip():
    """升级 pip"""
    print_step("步骤 3/6: 升级 pip")
    
    venv_python = get_venv_python()
    if not Path(venv_python).exists():
        print_warning("虚拟环境 Python 不存在，跳过 pip 升级")
        return True
    
    print("正在升级 pip...")
    try:
        result = subprocess.run(
            [venv_python, "-m", "pip", "install", "--upgrade", "pip", "--no-cache-dir"],
            check=False,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=120
        )
        
        if result.returncode == 0:
            print_success("pip 已升级到最新版本")
            return True
        else:
            print_warning("pip 升级失败，但不影响后续安装")
            return True
    except Exception as e:
        print_warning(f"pip 升级失败（可忽略）: {e}")
        return True

def parse_requirements():
    """解析 requirements.txt"""
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print_error("requirements.txt 文件未找到!")
        return None
    
    packages = []
    with open(requirements_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                packages.append(line)
    
    return packages

def check_package_installed(venv_python, package_name):
    """检查包是否已安装"""
    import_name = package_name
    if package_name == "Pillow":
        import_name = "PIL"
    elif package_name == "pyyaml":
        import_name = "yaml"
    
    try:
        result = subprocess.run(
            [venv_python, "-c", f"import {import_name}; print({import_name}.__version__)"],
            check=False,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except:
        return None

def check_and_install_dependencies():
    """检查并安装依赖"""
    print_step("步骤 4/6: 检查并安装依赖包")
    
    venv_python = get_venv_python()
    if not Path(venv_python).exists():
        print_error("虚拟环境 Python 不存在")
        return False
    
    packages = parse_requirements()
    if not packages:
        return False
    
    print("检查 requirements.txt 中的依赖...\n")
    
    installed_count = 0
    missing_packages = []
    
    for package in packages:
        package_name = package.split('>=')[0].split('==')[0].split('<')[0].split('!')[0]
        version = check_package_installed(venv_python, package_name)
        
        if version:
            print_success(f"{package_name} (v{version}) - 已安装")
            installed_count += 1
        else:
            print_warning(f"{package_name} - 需要安装")
            missing_packages.append(package)
    
    print(f"\n统计: 已安装 {installed_count} 个，缺失 {len(missing_packages)} 个\n")
    
    if not missing_packages:
        print_success("所有依赖已就绪!")
        return True
    
    print("正在安装缺失的依赖包...")
    print("这可能需要几分钟，请耐心等待...\n")
    
    try:
        result = subprocess.run(
            [venv_python, "-m", "pip", "install", "-r", "requirements.txt", "--no-cache-dir"],
            check=False,
            capture_output=False,
            timeout=600
        )
        
        if result.returncode == 0:
            print_success("所有依赖已安装完成!")
            return True
        else:
            print_error("依赖安装失败!")
            print_warning("可能的解决方案:")
            print("  1. 运行: pip install --upgrade pip")
            print("  2. 手动安装: pip install -r requirements.txt")
            print("  3. 使用国内镜像:")
            print("     pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple")
            return False
    except subprocess.TimeoutExpired:
        print_error("安装超时，请检查网络连接")
        return False
    except Exception as e:
        print_error(f"安装错误: {e}")
        return False

def create_config_file():
    """创建配置文件"""
    print_step("步骤 5/6: 检查配置文件")
    
    config_file = Path("config/config.yaml")
    example_file = Path("config/config.yaml.example")
    
    if config_file.exists():
        print_success("配置文件已存在")
        return True
    
    if not example_file.exists():
        print_error("未找到 config.yaml.example 文件!")
        return False
    
    print("正在创建配置文件...")
    try:
        import shutil
        shutil.copy(example_file, config_file)
        print_success("config.yaml 已创建")
        print_warning("重要: 请编辑 config/config.yaml 配置机器人信息:")
        print("  - 机器人 QQ 号 (bot.qq)")
        print("  - NapCat 连接地址 (onebot.http_url)")
        print("  - 管理员 QQ 号 (permission.admins)")
        return True
    except Exception as e:
        print_error(f"创建配置文件失败: {e}")
        return False

def create_directories():
    """创建必要的目录"""
    print_step("步骤 6/6: 创建目录结构")
    
    directories = ["logs", "cache", "save", "docs"]
    created = 0
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print_success(f"目录已创建: {dir_name}/")
            created += 1
        else:
            print_info(f"目录已存在: {dir_name}/")
    
    if created > 0:
        print_success(f"已创建 {created} 个目录")
    return True

def final_summary():
    """最终总结"""
    print_header("安装完成!")
    
    print("所有文件和依赖已准备就绪。\n")
    print("下一步:")
    print("  1. 编辑 config/config.yaml 配置机器人信息")
    print("  2. 运行启动脚本:")
    print("     Windows: start.bat")
    print("     Linux/Mac: bash start.sh")
    print()
    print("其他命令:")
    print("  - check_env.bat : 检查环境配置")
    print("  - python setup.py : 重新运行安装脚本")
    print()

def ask_to_start():
    """询问是否启动机器人"""
    try:
        choice = input("是否现在启动机器人？(y/N): ").strip().lower()
        return choice in ['y', 'yes']
    except:
        return False

def start_bot():
    """启动机器人"""
    print("\n启动机器人...\n")
    
    venv_python = get_venv_python()
    if not Path(venv_python).exists():
        print_error("虚拟环境不存在，无法启动机器人")
        print("请先运行: python setup.py")
        return
    
    try:
        subprocess.run([venv_python, "src/main.py"])
    except KeyboardInterrupt:
        print("\n\n机器人已停止")
    except Exception as e:
        print_error(f"启动失败: {e}")

def main():
    """主函数"""
    print_header("Starrain-BOT 安装脚本")
    
    print("本脚本将自动完成以下操作:")
    print("  1. 检查 Python 环境")
    print("  2. 创建虚拟环境")
    print("  3. 检查并安装依赖包")
    print("  4. 配置环境")
    print()
    
    if not check_python_version():
        pause()
        sys.exit(1)
    
    print()
    pause()
    
    if not create_virtual_environment():
        pause()
        sys.exit(1)
    
    print()
    pause()
    
    if not upgrade_pip():
        pass  # 不影响流程
    
    print()
    pause()
    
    if not check_and_install_dependencies():
        pause()
        sys.exit(1)
    
    print()
    
    if not create_config_file():
        print_warning("请手动创建 config/config.yaml 配置文件")
    
    if not create_directories():
        print_warning("某些目录创建失败，但不影响正常使用")
    
    print()
    final_summary()
    
    if ask_to_start():
        start_bot()
    
    pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户取消安装")
        sys.exit(0)
    except Exception as e:
        print(f"\n未能预期的错误: {e}")
        import traceback
        traceback.print_exc()
        pause()
        sys.exit(1)
