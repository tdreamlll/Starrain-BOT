# -*- coding: utf-8 -*-
import sys
import asyncio
from pathlib import Path

try:
    import yaml
except ImportError:
    print("错误: PyYAML 未安装!")
    print("请运行: pip install pyyaml")
    sys.exit(1)

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.core import Bot
    from src.core.permission import PermissionLevel
except ImportError as e:
    print(f"错误: 导入模块失败: {e}")
    print("请确保所有依赖已安装")
    print("运行: pip install -r requirements.txt")
    sys.exit(1)


def load_config(config_path: str = 'config/config.yaml') -> dict:
    """加载配置文件"""
    path = Path(config_path)
    if not path.exists():
        print(f"错误: 配置文件未找到: {config_path}")
        print("请在config目录创建配置文件")
        sys.exit(1)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if not config:
                print("错误: 配置文件为空")
                sys.exit(1)
            
            # Validate config
            if 'bot' not in config or 'qq' not in config['bot']:
                print("错误: 配置无效 - 缺少 bot.qq")
                sys.exit(1)
            
            if 'onebot' not in config:
                print("错误: 配置无效 - 缺少 onebot 部分")
                sys.exit(1)
            
            return config
    except yaml.YAMLError as e:
        print(f"错误: 解析配置文件失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 加载配置失败: {e}")
        sys.exit(1)


def print_banner():
    """打印启动横幅"""
    print("""
    ╔══════════════════════════════════════════╗
    ║      Starrain-BOT v1.0.0               ║
    ║         基于OneBot v11                  ║
    ╚══════════════════════════════════════════╝
    """)


async def register_commands(bot: Bot):
    """注册命令处理器"""
    
    @bot.on_group_message
    async def handle_message(event, permission_level):
        """处理群消息"""
        # 只处理普通成员
        if permission_level != PermissionLevel.MEMBER:
            return
        
        message = event.raw_message
        
        # 示例命令
        if message.startswith('/help'):
            help_text = """
Starrain-BOT 命令列表:
/help - 查看帮助
/version - 查看版本
/plugins - 查看插件列表
            
管理员命令:
/enable <插件名> - 启用插件
/disable <插件名> - 禁用插件
/reload <插件名> - 重载插件
            """
            await bot.send_group_message(event.group_id, help_text)
        
        elif message.startswith('/version'):
            await bot.send_group_message(
                event.group_id,
                "Starrain-BOT v1.0.0 - 基于OneBot v11的Python机器人框架"
            )
        
        elif message.startswith('/plugins'):
            plugin_list = "已加载插件:\n"
            for name, plugin in bot.plugin_manager.plugins.items():
                status = "✓" if plugin.enabled else "✗"
                version = plugin.metadata.version if plugin.metadata else "1.0.0"
                plugin_list += f"{status} {name} v{version}\n"
            await bot.send_group_message(event.group_id, plugin_list)
    
    @bot.on_group_message
    async def handle_admin_commands(event, permission_level):
        """处理管理员命令"""
        if permission_level != PermissionLevel.BOT_ADMIN:
            return
        
        message = event.raw_message
        args = message.split()
        
        if len(args) < 2:
            return
        
        command = args[0]

        # 管理员管理命令（持久化到数据库）
        if command == '/add_admin':
            try:
                qq = int(args[1])
            except (ValueError, IndexError):
                await bot.send_group_message(event.group_id, "✗ 请输入有效的 QQ 号，例如：/add_admin 123456789")
                return

            bot.permission_manager.add_admin(qq)
            await bot.send_group_message(event.group_id, f"✓ 已将 {qq} 添加为 BOT 管理员（已写入数据库）")
            return

        if command == '/remove_admin':
            try:
                qq = int(args[1])
            except (ValueError, IndexError):
                await bot.send_group_message(event.group_id, "✗ 请输入有效的 QQ 号，例如：/remove_admin 123456789")
                return

            bot.permission_manager.remove_admin(qq)
            await bot.send_group_message(event.group_id, f"✓ 已将 {qq} 从 BOT 管理员中移除（已更新数据库）")
            return

        # 群配置相关命令（持久化到数据库的 group_configs 表）
        if command == '/set_group_cfg':
            if len(args) < 3:
                await bot.send_group_message(
                    event.group_id,
                    "✗ 用法：/set_group_cfg <key> <value>"
                )
                return

            key = args[1]
            value = " ".join(args[2:])
            bot.db.set_group_config(event.group_id, key, value)
            await bot.send_group_message(
                event.group_id,
                f"✓ 已为本群设置配置项：{key} = {value}"
            )
            return

        if command == '/get_group_cfg':
            key = args[1]
            value = bot.db.get_group_config(event.group_id, key)
            if value is None:
                await bot.send_group_message(
                    event.group_id,
                    f"ℹ 本群尚未设置配置项：{key}"
                )
            else:
                await bot.send_group_message(
                    event.group_id,
                    f"本群配置 {key} = {value}"
                )
            return

        if command == '/list_group_cfg':
            configs = bot.db.list_group_configs(event.group_id)
            if not configs:
                await bot.send_group_message(event.group_id, "ℹ 本群暂无配置项")
                return

            lines = ["本群配置列表："]
            for k, v in configs.items():
                lines.append(f"{k} = {v}")
            await bot.send_group_message(event.group_id, "\n".join(lines))
            return

        plugin_name = args[1] if len(args) > 1 else None
        
        if command == '/enable' and plugin_name:
            success = bot.plugin_manager.enable_plugin(plugin_name)
            if success:
                await bot.send_group_message(event.group_id, f"✓ 插件已启用: {plugin_name}")
            else:
                await bot.send_group_message(event.group_id, f"✗ 插件启用失败: {plugin_name}")
        
        elif command == '/disable' and plugin_name:
            success = bot.plugin_manager.disable_plugin(plugin_name)
            if success:
                await bot.send_group_message(event.group_id, f"✓ 插件已禁用: {plugin_name}")
            else:
                await bot.send_group_message(event.group_id, f"✗ 插件禁用失败: {plugin_name}")
        
        elif command == '/reload' and plugin_name:
            success = bot.plugin_manager.reload_plugin(plugin_name)
            if success:
                await bot.send_group_message(event.group_id, f"✓ 插件已重载: {plugin_name}")
            else:
                await bot.send_group_message(event.group_id, f"✗ 插件重载失败: {plugin_name}")


async def main():
    """主函数"""
    try:
        print_banner()
        
        # 检查Python版本
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            print(f"错误: 需要 Python 3.8+，当前版本: {sys.version.split()[0]}")
            print("请升级 Python 到 3.8 或更高版本")
            sys.exit(1)
        
        # 加载配置
        print("正在加载配置...")
        config = load_config()
        print("[完成] 配置已加载")
        
        # 创建机器人实例
        print("正在初始化机器人...")
        bot = Bot(config)
        print(f"[完成] 机器人已初始化 QQ: {config['bot']['qq']}")
        
        # 注册命令
        print("正在注册命令...")
        await register_commands(bot)
        print("[完成] 命令已注册")
        
        # 启动机器人
        print("\n" + "=" * 50)
        print("正在启动机器人... 按 Ctrl+C 停止")
        print("=" * 50 + "\n")
        
        try:
            await bot.run()
        except KeyboardInterrupt:
            print("\n\n收到停止信号，正在关闭...")
            await bot.stop()
        except Exception as e:
            print(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
            try:
                await bot.stop()
            except:
                pass
    
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"\n严重错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")

