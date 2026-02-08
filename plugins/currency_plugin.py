# -*- coding: utf-8 -*-
"""
货币插件：使用 JSON 文件存储货币，替代 MySQL 的 user_currency。
命令：/balance /余额 /daily /签到 /pay /转账 /currency_help
"""
import re
from datetime import date

from src.utils.currency import get_currency_store
from src.utils.logger import get_logger

logger = get_logger()

__plugin_metadata__ = {
    "name": "currency",
    "version": "1.0.0",
    "author": "Starrain",
    "description": "货币系统（JSON 存储），查询余额、每日签到、转账",
}

# 每日签到奖励
DAILY_REWARD = 100
async def on_load():
    logger.info(f"插件加载: {__plugin_metadata__['name']} v{__plugin_metadata__['version']}（JSON 货币，无需 MySQL）")


def on_group_message(event, permission_level):
    """处理群消息：余额、签到、转账、帮助。"""
    raw = event.raw_message.strip()
    bot = getattr(event, "bot", None)
    if not bot:
        return

    store = get_currency_store()
    group_id = getattr(event, "group_id", 0)
    user_id = event.user_id

    async def reply(msg):
        if group_id:
            await bot.send_group_message(group_id, msg)

    # 帮助
    if raw in ("/currency_help", "/货币帮助", "/help_currency"):
        help_text = """【货币插件】使用 JSON 存储，无需 MySQL
/balance 或 /余额 — 查询自己的余额
/daily 或 /签到 — 每日签到领奖励（每日一次）
/pay <对方QQ> <金额> 或 /转账 <对方QQ> <金额> — 转账给他人
/currency_help — 本帮助"""
        import asyncio
        asyncio.create_task(reply(help_text))
        return

    # 查询余额
    if raw in ("/balance", "/余额"):
        balance = store.get_currency(user_id)
        import asyncio
        asyncio.create_task(reply(f"你的当前余额：{balance} 金币"))
        return

    # 每日签到
    if raw in ("/daily", "/签到"):
        today = date.today().isoformat()
        last = store.get_last_daily_date(user_id)
        if last == today:
            import asyncio
            asyncio.create_task(reply("今天已经签到过了，明天再来吧~"))
            return
        store.set_last_daily_date(user_id, today)
        new_balance = store.add_currency(user_id, DAILY_REWARD)
        import asyncio
        asyncio.create_task(reply(f"签到成功！获得 {DAILY_REWARD} 金币，当前余额：{new_balance} 金币"))
        return

    # 转账：/pay <qq> <金额> 或 /转账 <qq> <金额>；也支持 /pay [CQ:at,qq=123] 100
    pay_match = re.match(r"^(/pay|/转账)\s+(?:\[CQ:at,qq=(\d+)\]|(\d+))\s+(\d+)\s*$", raw)
    if pay_match:
        target_qq_str = pay_match.group(2) or pay_match.group(3)
        target_qq = int(target_qq_str)
        amount = int(pay_match.group(4))
        if amount <= 0:
            import asyncio
            asyncio.create_task(reply("转账金额必须大于 0"))
            return
        if target_qq == user_id:
            import asyncio
            asyncio.create_task(reply("不能给自己转账"))
            return
        my_balance = store.get_currency(user_id)
        if my_balance < amount:
            import asyncio
            asyncio.create_task(reply(f"余额不足，当前余额：{my_balance} 金币"))
            return
        store.add_currency(user_id, -amount)
        store.add_currency(target_qq, amount)
        import asyncio
        asyncio.create_task(reply(f"已向 {target_qq} 转账 {amount} 金币，当前余额：{store.get_currency(user_id)} 金币"))
        return
