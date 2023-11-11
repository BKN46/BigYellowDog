from curses.ascii import isdigit
import math
import time
import re
from typing import Any, Tuple

import nonebot
from nonebot.adapters import Message
from nonebot.matcher import Matcher
from nonebot.params import RegexGroup, EventMessage
from nonebot.plugin import on_message, on_regex
from nonebot.rule import to_me
from nonebot.message import event_postprocessor

from nonebot.adapters.mirai2.event.message import MessageEvent
from nonebot.adapters.mirai2 import MessageChain

from toogle.configs import config
from toogle.index import export_plugins, active_plugins
from toogle.message_handler import MESSAGE_HISTORY
from toogle.nonebot2_adapter import PluginWrapper, bot_send_message

# ping trigger

echo = on_regex("^22222$")

async def handle_echo(foo: Tuple[Any, ...] = RegexGroup()):
    await echo.send("22222")


echo.append_handler(handle_echo)

# main part

from toogle.index import export_plugins, linear_handler

if config.get("CONCURRENCY") == 'true':
    for plugin in export_plugins:
        try:
            matcher = on_regex(plugin.plugin.trigger)
            matcher.append_handler(plugin.ret)
            if plugin.plugin.to_me_trigger:
                to_me_matcher = on_message(rule=to_me())
                to_me_matcher.append_handler(plugin.ret)
                nonebot.logger.success(f"[{plugin.plugin.name}] Also loaded as to_me trigger")  # type: ignore
        except Exception as e:
            nonebot.logger.error(f"[{plugin.plugin.name}] failed to add matcher/handler: {repr(e)}") # type: ignore

else:
    matcher = on_message()
    matcher.append_handler(linear_handler.ret)


# /help

get_help_regex = f"^(#help#|\.help|/help|@{config['MIRAI_QQ'][0]})(.*)" # type: ignore
get_help = on_regex(get_help_regex)

async def handle_help(
    matcher: Matcher,
    event: MessageEvent,
    message: MessageChain = EventMessage(),
):
    def get_help_page(page, page_size=5):
        res = []
        total_page = math.ceil(len(export_plugins)/page_size)
        if page >= total_page:
            page = total_page - 1
        elif page < 0:
            page = 0
        p1, p2 = page * page_size, min((page + 1) * page_size, len(export_plugins))
        for mod in export_plugins[p1:p2]:
            res.append(
                f"{mod.plugin.name}\n【说明】 {mod.plugin.readme}"
            )
        return f"\n{'#'*15}\n".join(res) + f"\n\nPage {page + 1}/{total_page} (指令后加上序号翻页，也可具体查询功能名称)"

    def fuzz_search(content):
        res = []
        for mod in export_plugins:
            if content in mod.plugin.name or content in mod.plugin.trigger or content in mod.plugin.readme:
                res.append(
                    f"{mod.plugin.name}\n【触发正则】 {mod.plugin.trigger}\n【说明】 {mod.plugin.readme}"
                )
        return f"\n{'#'*15}\n".join(res)

    message_pack = PluginWrapper.get_message_pack(event, message)
    search_content = re.search(get_help_regex, message_pack.message.asDisplay()).groups()[1].strip() # type: ignore
    if not search_content:
        res = get_help_page(0)
    elif str.isdigit(search_content):
        res = get_help_page(int(search_content) - 1)
    else:
        res = fuzz_search(search_content)
    await get_help.send(res)

get_help.append_handler(handle_help)


# message history
@event_postprocessor
async def message_post_process(event: MessageEvent, message: MessageChain = EventMessage()):
    # record history
    message_pack = PluginWrapper.get_message_pack(event, message)
    MESSAGE_HISTORY.add(message_pack.group.id, message_pack) # type: ignore

    # do active plugins
    for plugin in active_plugins:
        if str(message_pack.group.id) in config['CHAT_GROUP_LIST'] and plugin.is_trigger_random(message=message_pack):
            message_ret = await plugin.ret_wrapper(message_pack)
            if message_ret:
                await bot_send_message(message_pack, message_ret)
