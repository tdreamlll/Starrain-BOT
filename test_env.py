# -*- coding: utf-8 -*-
"""
Starrain-BOT 环境检测脚本
用于检查环境是否正常
"""

import sys
import os
from pathlib import Path

def print_header(text):
    """打印标题"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def print_success(text):
    """打印成功信息"""
    print(f"[OK] {text}")

def print_error(text):
    """打印错误信息"""
    print(f"[错误] {text}")

def print_warning(text):
    """打印警告信息"""
    print(f"[警告] {text}")

def print_info(text):
    """打印信息"""
    print(f"[信息] {text}")

def check_python_version():
    """检查Python版本"""
    print_header("Python版本检查")
    version = sys.version_info
    print(f"Python版本: {sys.version.split()[0]}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print_error("需要 Python 3.8 或更高版本!")
        print(f"当前版本: {version.major}.{version.minor}.{version.micro}")
        return False
    else:
        print_success(f"Python {version.major}.{version.minor}.{version.micro} 兼容")
        return True

def check_module(module_name, import_name=None):
    """检查模块是否已安装"""
    if import_name is None:
        import_name = module_name
    
    try:
        __import__(import_name)
        print_success(f"{module_name}: 已安装")
        return True
    except ImportError:
        print_error(f"{module_name}: 未安装")
        return False

def check_modules():
    """检查所有必需模块"""
    print_header("模块依赖检查")
    
    required_modules = [
        ("websockets", "websockets"),
        ("aiohttp", "aiohttp"),
        ("watchdog", "watchdog"),
        ("Pillow", "PIL"),
        ("colorama", "colorama"),
        ("yaml", "yaml"),
        ("rich", "rich"),
        ("aiofiles", "aiofiles"),
        ("pymysql", "pymysql"),
        ("asyncio", "asyncio"),
    ]
    
    optional_modules = [
        ("pyppeteer", "pyppeteer"),
    ]
    
    all_ok = True
    missing_modules = []
    
    print("必需模块:")
    for module_name, import_name in required_modules:
        import_name = import_name or module_name
        ok = check_module(module_name, import_name)
        if not ok:
            all_ok = False
            missing_modules.append(module_name)
    
    if not all_ok:
        print_warning(f"缺少 {len(missing_modules)} 个必需模块")
        print_error("请运行以下命令安装:")
        print("  pip install -r requirements.txt")
    
    print("\n可选模块 (图片渲染功能):")
    for module_name, import_name in optional_modules:
        import_name = import_name or module_name
        ok = check_module(module_name, import_name)
        if not ok:
            print_warning(f"图片渲染将不可用")
            print_info("  如需使用图片渲染，请安装:")
            print_info("    pip install pyppeteer")
    
    return all_ok

def check_project_structure():
    """检查项目结构"""
    print_header("项目结构检查")
    
    required_paths = [
        ("config/config.yaml", "配置文件"),
        ("config/config.yaml.example", "配置模板"),
        ("src/main.py", "主程序"),
        ("src/core/bot.py", "机器人核心"),
        ("src/core/permission.py", "权限管理器"),
        ("src/core/plugin_manager.py", "插件管理器"),
        ("plugins/", "插件目录"),
        ("logs/", "日志目录"),
        ("cache/", "缓存目录"),
    ]
    
    all_ok = True
    for path, description in required_paths:
        path_obj = Path(path)
        if path_obj.exists():
            print_success(f"{description}: {path}")
        else:
            print_error(f"{description}: {path} - 未找到")
            all_ok = False
    
    return all_ok

def check_virtual_env():
    """检查虚拟环境"""
    print_header("虚拟环境检查")
    
    in_venv = (
        hasattr(sys, 'real_prefix') or 
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )
    
    if in_venv:
        print_success("当前在虚拟环境中")
        print(f"  虚拟环境路径: {sys.prefix}")
        return True
    else:
        print_warning("当前不在虚拟环境中")
        print("  建议使用虚拟环境")
        print("  运行以下命令创建:")
        print("    python -m venv venv")
        if os.name == 'nt':
            print("    venv\\Scripts\\activate")
        else:
            print("    source venv/bin/activate")
        return False

def main():
    """主函数"""
    print("\n")
    print("="*60)
    print("  Starrain-BOT 环境检测")
    print("="*60)
    
    results = []
    
    # 检查Python版本
    results.append(("Python版本", check_python_version()))
    
    # 检查虚拟环境
    results.append(("虚拟环境", check_virtual_env()))
    
    # 检查项目结构
    results.append(("项目结构", check_project_structure()))
    
    # 检查模块
    results.append(("模块", check_modules()))
    
    # 总结
    print_header("检测总结")
    
    all_ok = True
    for name, ok in results:
        status = "[通过]" if ok else "[失败]"
        print(f"{name}: {status}")
        if not ok:
            all_ok = False
    
    print()
    if all_ok:
        print_success("所有检查通过！现在可以启动机器人了。")
        print("\n推荐启动命令:")
        if os.name == 'nt':
            print("  Windows: start.bat")
        else:
            print("  Linux/Mac: bash start.sh")
    else:
        print_error("部分检查未通过，请修复上述问题。")
        print("\n获取更多帮助:")
        print("  - 阅读 项目文档")
        print("  - 使用 start_debug.bat 进行诊断")
        print("  - 查看 README.md 安装指南")
    
    print()
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())
