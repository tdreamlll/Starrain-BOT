# -*- coding: utf-8 -*-
import os
import sys
import asyncio
from pathlib import Path

try:
    import yaml
except ImportError:
    from src.utils.logger import get_logger
    logger = get_logger({'level': 'INFO', 'console': True, 'color': True, 'file': 'logs/bot.log'})
    logger.error("PyYAML 未安装!")
    logger.info("请运行: pip install pyyaml")
    sys.exit(1)

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.core import Bot
    from src.core.permission import PermissionLevel
    from src.utils.currency import get_currency_store
except ImportError as e:
    from src.utils.logger import get_logger
    logger = get_logger({'level': 'INFO', 'console': True, 'color': True, 'file': 'logs/bot.log'})
    logger.error(f"导入模块失败: {e}")
    logger.info("请确保所有依赖已安装")
    logger.info("运行: pip install -r requirements.txt")
    sys.exit(1)

from src.utils.logger import get_logger
from src.web import init_web, run_web_server

get_logger({'level': 'INFO', 'console': True, 'color': True, 'file': 'logs/bot.log'})

def load_config(config_path: str = 'config/config.yaml') -> dict:
    logger = get_logger()
    path = Path(config_path)
    if not path.is_absolute():
        path = project_root / path
    if not path.exists():
        logger.error(f"配置文件未找到: {config_path}")
        sys.exit(1)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if not config:
                logger.error("配置文件为空")
                sys.exit(1)
            if 'bot' not in config or 'qq' not in config['bot']:
                logger.error("配置无效 - 缺少 bot.qq")
                sys.exit(1)
            if 'onebot' not in config:
                logger.error("配置无效 - 缺少 onebot 部分")
                sys.exit(1)
            return config
    except yaml.YAMLError as e:
        logger.error(f"解析配置文件失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"加载配置失败: {e}")
        sys.exit(1)

def _format_uptime(seconds: float) -> str:
    if seconds <= 0:
        return "未启动"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    if d > 0:
        return f"{d}天{h}时{m}分"
    if h > 0:
        return f"{h}时{m}分{s}秒"
    if m > 0:
        return f"{m}分{s}秒"
    return f"{s}秒"


def _build_debug_message(bot, section: str):
    pm = bot.permission_manager
    uptime = _format_uptime(bot.uptime_seconds)

    if section == "":
        adapters = []
        for a in bot.adapters:
            name = a.__class__.__name__
            ok = getattr(a, "connected", False) or (getattr(a, "is_connected", lambda: False)())
            adapters.append(f"{name}:{'✓' if ok else '✗'}")
        return (
            "【Debug 总览】\n"
            f"运行: {uptime} | QQ: {bot.qq}\n"
            f"适配器: {', '.join(adapters)}\n"
            f"3级: {len(pm.list_admins())} | 4级: {len(pm.list_owners())} | 5级: {len(pm.list_developers())}\n"
            f"黑名单群: {len(pm.list_blacklisted_groups())} | 插件: {len(bot.plugin_manager.plugins)}\n"
            f"货币缓存: {get_currency_store().get_debug_info()['cache_size']} 条"
        )

    if section == "system":
        import platform
        try:
            import psutil
            mem = psutil.virtual_memory()
            mem_info = f"内存: 已用 {mem.percent}% | 可用 {mem.available // (1024*1024)}MB"
        except ImportError:
            mem_info = "内存: (安装 psutil 可显示)"
        return (
            "【Debug · System】\n"
            f"Python: {sys.version.split()[0]} | {platform.system()} {platform.release()}\n"
            f"CPU 核心: {os.cpu_count() or '?'}\n"
            f"{mem_info}\n"
            f"运行: {uptime}"
        )

    if section == "permission":
        L3, L4, L5 = pm.list_admins(), pm.list_owners(), pm.list_developers()
        black = pm.list_blacklisted_groups()
        def _fmt(lst, cap=10):
            if len(lst) <= cap:
                return ",".join(map(str, lst)) or "无"
            return ",".join(map(str, lst[:cap])) + f"…+{len(lst)-cap}"
        return (
            "【Debug · Permission】\n"
            f"3级({len(L3)}): {_fmt(L3)}\n"
            f"4级({len(L4)}): {_fmt(L4)}\n"
            f"5级({len(L5)}): {_fmt(L5)}\n"
            f"黑名单群({len(black)}): {_fmt(black)}"
        )

    if section == "plugins":
        lines = ["【Debug · Plugins】"]
        for name, plugin in sorted(bot.plugin_manager.plugins.items()):
            enabled = name in bot.plugin_manager.enabled_plugins
            ctx_ok = bot.plugin_manager.is_plugin_enabled_for_context(name, None)
            ver = plugin.metadata.get("version", "?") if isinstance(plugin.metadata, dict) else getattr(plugin.metadata, "version", "?")
            lines.append(f"  {'✓' if enabled else '✗'} {name} v{ver} (全局:{'开' if ctx_ok else '关'})")
        return "\n".join(lines) if lines else "【Debug · Plugins】\n  无插件"

    if section == "currency":
        store = get_currency_store()
        info = store.get_debug_info()
        return (
            "【Debug · Currency】\n"
            f"内存缓存条数: {info['cache_size']}\n"
            "数据目录: data/ | 分片: currency_0~31.json"
        )

    if section == "full":
        return [
            _build_debug_message(bot, ""),
            _build_debug_message(bot, "system"),
            _build_debug_message(bot, "permission"),
            _build_debug_message(bot, "plugins"),
            _build_debug_message(bot, "currency"),
        ]

    return ""


def _help_text(level: PermissionLevel) -> str:
    parts = [
        "【1级】/help /version /plugins /currency_help",
        "【1级】/balance /daily /pay — 货币（签到、转账）",
    ]
    if level >= PermissionLevel.GROUP_STAFF:
        parts.append("【2级】/enable_grp <插件> /disable_grp <插件> — 本群插件开关")
        parts.append("【2级】/mute <@某人|QQ> [分钟] — 禁言（默认1分钟，0=解除）")
    if level >= PermissionLevel.BOT_ADMIN:
        parts.append("【3级】/enable /disable /reload — 全局插件")
        parts.append("【3级】/blacklist_add <群号> /blacklist_remove <群号>")
        parts.append("【3级】/add_admin /remove_admin <QQ>")
        parts.append("【3级】/set_currency <QQ> <金额> /add_currency <QQ> <增减> — 改他人数据（不能改同级或更高级）")
    if level >= PermissionLevel.OWNER:
        parts.append("【4级】/add_owner /remove_owner <QQ>；/restart /shutdown")
    if level >= PermissionLevel.DEVELOPER:
        parts.append("【5级】/add_developer /remove_developer <QQ>")
        parts.append("【5级】/debug [system|permission|plugins|currency|full]")
    return "\n".join(parts)


async def register_commands(bot: Bot):
    @bot.on_group_message
    async def dispatch_commands(event, permission_level):
        message = (event.raw_message or "").strip()
        args = message.split()
        if not args:
            return
        command = args[0]
        group_id = getattr(event, "group_id", 0)

        if command == '/help':
            await bot.send_group_message(group_id, _help_text(permission_level))
            return
        if command == '/version':
            await bot.send_group_message(group_id, "Starrain-BOT v1.0.0 - 基于OneBot v11")
            return
        if command == '/plugins':
            lines = ["已加载插件:"]
            for name, plugin in bot.plugin_manager.plugins.items():
                enabled = bot.plugin_manager.is_plugin_enabled_for_context(name, group_id)
                status = "✓" if enabled else "✗"
                ver = plugin.metadata.get("version", "?") if isinstance(plugin.metadata, dict) else getattr(plugin.metadata, "version", "?")
                lines.append(f"  {status} {name} v{ver}")
            await bot.send_group_message(group_id, "\n".join(lines))
            return
        if command in ('/currency_help', '/balance', '/daily') or message.startswith('/pay ') or message.startswith('/转账 '):
            return

        if permission_level < PermissionLevel.GROUP_STAFF:
            return
        if command == '/enable_grp' and len(args) >= 2:
            bot.plugin_manager.set_group_plugin_enabled(group_id, args[1], True)
            await bot.send_group_message(group_id, f"✓ 本群已启用插件: {args[1]}")
            return
        if command == '/disable_grp' and len(args) >= 2:
            bot.plugin_manager.set_group_plugin_enabled(group_id, args[1], False)
            await bot.send_group_message(group_id, f"✓ 本群已禁用插件: {args[1]}")
            return
        if command == '/mute' and len(args) >= 2:
            try:
                uid_str = args[1].strip()
                if uid_str.startswith("[CQ:at,qq="):
                    import re
                    m = re.search(r"qq=(\d+)", uid_str)
                    uid_str = m.group(1) if m else uid_str
                user_id = int(uid_str)
                duration = int(args[2]) if len(args) > 2 else 1
                duration = max(0, min(43200, duration))
                ok = await bot.set_group_ban(group_id, user_id, duration * 60)
                if ok:
                    await bot.send_group_message(group_id, f"✓ 已禁言 {duration} 分钟" if duration else "✓ 已解除禁言")
                else:
                    await bot.send_group_message(group_id, "✗ 禁言失败（无权限或接口不可用）")
            except (ValueError, IndexError):
                await bot.send_group_message(group_id, "✗ 用法: /mute <@某人|QQ> [分钟]，0=解除")
            return
        if command in ('/set_group_cfg', '/get_group_cfg', '/list_group_cfg'):
            if command == '/set_group_cfg' and len(args) >= 3:
                bot.db.set_group_config(group_id, args[1], " ".join(args[2:]))
                await bot.send_group_message(group_id, f"✓ 已设置 {args[1]} = {' '.join(args[2:])}")
            elif command == '/get_group_cfg' and len(args) >= 2:
                v = bot.db.get_group_config(group_id, args[1])
                await bot.send_group_message(group_id, f"{args[1]} = {v}" if v else f"本群未设置 {args[1]}")
            elif command == '/list_group_cfg':
                cfg = bot.db.list_group_configs(group_id)
                await bot.send_group_message(group_id, "本群配置:\n" + "\n".join(f"{k}={v}" for k, v in cfg.items()) if cfg else "本群暂无配置")
            return

        if permission_level < PermissionLevel.BOT_ADMIN:
            return
        if command == '/enable' and len(args) >= 2:
            ok = bot.plugin_manager.enable_plugin(args[1])
            await bot.send_group_message(group_id, f"✓ 已全局启用: {args[1]}" if ok else f"✗ 失败: {args[1]}")
            return
        if command == '/disable' and len(args) >= 2:
            ok = bot.plugin_manager.disable_plugin(args[1])
            await bot.send_group_message(group_id, f"✓ 已全局禁用: {args[1]}" if ok else f"✗ 失败: {args[1]}")
            return
        if command == '/reload' and len(args) >= 2:
            ok = bot.plugin_manager.reload_plugin(args[1])
            await bot.send_group_message(group_id, f"✓ 已重载: {args[1]}" if ok else f"✗ 失败: {args[1]}")
            return
        if command == '/blacklist_add' and len(args) >= 2:
            try:
                gid = int(args[1])
                bot.permission_manager.add_group_blacklist(gid)
                await bot.send_group_message(group_id, f"✓ 已拉黑群 {gid}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效群号")
            return
        if command == '/blacklist_remove' and len(args) >= 2:
            try:
                gid = int(args[1])
                bot.permission_manager.remove_group_blacklist(gid)
                await bot.send_group_message(group_id, f"✓ 已移除黑名单群 {gid}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效群号")
            return
        if command == '/add_admin' and len(args) >= 2:
            try:
                qq = int(args[1])
                bot.permission_manager.add_admin(qq)
                await bot.send_group_message(group_id, f"✓ 已添加 3 级管理员: {qq}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效 QQ")
            return
        if command == '/remove_admin' and len(args) >= 2:
            try:
                qq = int(args[1])
                bot.permission_manager.remove_admin(qq)
                await bot.send_group_message(group_id, f"✓ 已移除 3 级管理员: {qq}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效 QQ")
            return
        if command == '/add_owner' and len(args) >= 2 and permission_level >= PermissionLevel.OWNER:
            try:
                qq = int(args[1])
                bot.permission_manager.add_owner(qq)
                await bot.send_group_message(group_id, f"✓ 已添加 4 级所有者: {qq}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效 QQ")
            return
        if command == '/remove_owner' and len(args) >= 2 and permission_level >= PermissionLevel.OWNER:
            try:
                qq = int(args[1])
                bot.permission_manager.remove_owner(qq)
                await bot.send_group_message(group_id, f"✓ 已移除 4 级所有者: {qq}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效 QQ")
            return
        if command == '/add_developer' and len(args) >= 2 and permission_level >= PermissionLevel.DEVELOPER:
            try:
                qq = int(args[1])
                bot.permission_manager.add_developer(qq)
                await bot.send_group_message(group_id, f"✓ 已添加 5 级开发者: {qq}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效 QQ")
            return
        if command == '/remove_developer' and len(args) >= 2 and permission_level >= PermissionLevel.DEVELOPER:
            try:
                qq = int(args[1])
                bot.permission_manager.remove_developer(qq)
                await bot.send_group_message(group_id, f"✓ 已移除 5 级开发者: {qq}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 请输入有效 QQ")
            return
        if command == '/set_currency' and len(args) >= 3:
            try:
                target_qq = int(args[1])
                amount = int(args[2])
                if not bot.can_modify_user(event.user_id, target_qq, group_id, getattr(event, "sender_role", None)):
                    await bot.send_group_message(group_id, "✗ 无权修改该用户数据（对方等级不低于你）")
                    return
                store = get_currency_store()
                store.set_currency(target_qq, max(0, amount))
                await bot.send_group_message(group_id, f"✓ 已将 {target_qq} 的余额设为 {store.get_currency(target_qq)}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 用法: /set_currency <QQ> <金额>")
            return
        if command == '/add_currency' and len(args) >= 3:
            try:
                target_qq = int(args[1])
                delta = int(args[2])
                if not bot.can_modify_user(event.user_id, target_qq, group_id, getattr(event, "sender_role", None)):
                    await bot.send_group_message(group_id, "✗ 无权修改该用户数据（对方等级不低于你）")
                    return
                store = get_currency_store()
                new_balance = store.add_currency(target_qq, delta)
                await bot.send_group_message(group_id, f"✓ 已为 {target_qq} 增减 {delta}，当前余额: {new_balance}")
            except ValueError:
                await bot.send_group_message(group_id, "✗ 用法: /add_currency <QQ> <增减值>")
            return

        if permission_level < PermissionLevel.OWNER:
            return
        if command == '/restart':
            bot._restart_requested = True
            await bot.send_group_message(group_id, "✓ 正在重启机器人…")
            await bot.stop()
            return
        if command == '/shutdown':
            bot._shutdown_requested = True
            await bot.send_group_message(group_id, "✓ 正在关闭机器人…")
            await bot.stop()
            return

        if permission_level < PermissionLevel.DEVELOPER:
            return
        if command == '/debug':
            section = (args[1].lower() if len(args) >= 2 else "").strip()
            msg = _build_debug_message(bot, section)
            if not msg:
                await bot.send_group_message(
                    group_id,
                    "【Debug】用法: /debug [system|permission|plugins|currency|full]\n"
                    "无参数=总览 | system=系统 | permission=权限列表 | plugins=插件 | currency=货币缓存 | full=全部"
                )
                return
            if isinstance(msg, list):
                for m in msg:
                    await bot.send_group_message(group_id, m)
            else:
                await bot.send_group_message(group_id, msg)
            return


async def main():
    logger = get_logger()
    try:
        if sys.version_info < (3, 8):
            logger.error("需要 Python 3.8+")
            sys.exit(1)
        logger.info("正在加载配置...")
        config = load_config()
        logger.success("配置已加载")
        logger.info("正在初始化机器人...")
        bot = Bot(config)
        bot._restart_requested = False
        bot._shutdown_requested = False
        logger.success(f"机器人已初始化 QQ: {config['bot']['qq']}")

        if bot.permission_manager.self_check_and_ensure_developer_fallback():
            logger.warning("已将兜底开发者写入 5 级列表，正在重启…")
            os.execv(sys.executable, [sys.executable] + sys.argv)

        logger.info("正在注册命令...")
        await register_commands(bot)
        logger.success("命令已注册")
        
        web_cfg = config.get('web', {})
        if web_cfg.get('enabled', True):
            logger.info("正在初始化Web管理后台...")
            init_web(bot, config)
            asyncio.create_task(run_web_server())
        
        logger.info("正在启动机器人... 按 Ctrl+C 停止")

        try:
            await bot.run()
        except KeyboardInterrupt:
            logger.info("收到停止信号，正在关闭...")
            await bot.stop()
        except Exception as e:
            logger.error(f"运行异常: {e}")
            import traceback
            traceback.print_exc()
            try:
                await bot.stop()
            except Exception:
                pass

        if getattr(bot, "_restart_requested", False):
            logger.info("执行重启…")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger = get_logger()
        logger.info("程序已停止")
    except Exception as e:
        logger = get_logger()
        logger.error(f"严重错误: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")
