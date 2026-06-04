#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nathan-Auth 授权管理插件 - AstrBot 版本
提供域名授权管理、封禁解封、查询等功能
"""

import asyncio
import re
from urllib.parse import urlparse
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from .nathan_auth_client import NathanAuthClient


@register(
    "astrbot_plugin_nathan_auth",
    "langke06",
    "Nathan-Auth 授权管理插件，支持域名授权管理、封禁解封、查询等功能",
    "1.3.0",
)
class NathanAuthPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.context = context
        self.config = config

        # 加载配置 - 兼容不同版本的 AstrBot
        if config is None:
            # 尝试从 context 获取配置
            config = getattr(context, 'config', None)

        # 加载配置项
        if config:
            self.base_url = getattr(config, "base_url", "")
            self.webkey = getattr(config, "webkey", "")
            self.admin_name = getattr(config, "admin_name", "")
            self.admin_password = getattr(config, "admin_password", "")
            self.default_appid = getattr(config, "default_appid", "1")
            self.default_authdate = getattr(config, "default_authdate", "0")
            self.default_ip = getattr(config, "default_ip", "127.0.0.1")
            self.admin_qqs = getattr(config, "admin_qqs", [])
            self.admin_groups = getattr(config, "admin_groups", [])
            self.blacklist_qqs = getattr(config, "blacklist_qqs", [])
        else:
            # 使用空默认值
            self.base_url = ""
            self.webkey = ""
            self.admin_name = ""
            self.admin_password = ""
            self.default_appid = "1"
            self.default_authdate = "0"
            self.default_ip = "127.0.0.1"
            self.admin_qqs = []
            self.admin_groups = []
            self.blacklist_qqs = []

        # 初始化客户端
        self.client = None
        self.site_name = "Nathan-Auth"  # 默认名称，异步获取后会更新

        if self.base_url and self.webkey:
            self.client = NathanAuthClient(
                base_url=self.base_url,
                webkey=self.webkey,
                admin_name=self.admin_name,
                admin_password=self.admin_password,
                default_appid=self.default_appid,
                default_authdate=self.default_authdate,
                default_ip=self.default_ip
            )
            # 异步获取网站标题
            asyncio.create_task(self._fetch_site_name())
            logger.info("授权插件加载完成")
        else:
            logger.warning("授权插件配置不完整，请在配置页面设置 base_url 和 webkey")

    async def _fetch_site_name(self):
        """异步获取网站标题"""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    html = await response.text()
                    # 解析 title 标签
                    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                    if match:
                        title = match.group(1).strip()
                        # 清理标题，移除常见的后缀
                        title = re.sub(r'[\|\-–—].*$', '', title).strip()
                        if title:
                            self.site_name = title
                            logger.info(f"获取到网站标题: {self.site_name}")
        except Exception as e:
            logger.debug(f"获取网站标题失败: {e}")
            # 使用域名作为备用
            self.site_name = self._extract_site_name_from_domain(self.base_url)

    def _extract_site_name_from_domain(self, base_url: str) -> str:
        """从域名提取网站名（备用方法）"""
        if not base_url:
            return "Nathan-Auth"
        try:
            parsed = urlparse(base_url)
            domain = parsed.netloc or parsed.path
            if domain:
                domain = domain.replace("www.", "").split(":")[0]
                parts = domain.split(".")
                if len(parts) >= 2:
                    return parts[-2]
                return domain
        except Exception:
            pass
        return "Nathan-Auth"

    def _is_blacklisted(self, event: AstrMessageEvent) -> bool:
        """检查用户是否在黑名单中"""
        sender_id = event.get_sender_id()
        return self.blacklist_qqs and sender_id in self.blacklist_qqs

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """检查用户是否是管理员"""
        sender_id = event.get_sender_id()

        # 检查QQ是否在管理员列表中
        if self.admin_qqs and sender_id in self.admin_qqs:
            return True

        return False

    def _check_permission(self, event: AstrMessageEvent, allow_guest: bool = False) -> bool:
        """
        检查用户是否有权限使用命令

        Args:
            event: 消息事件
            allow_guest: 是否允许普通用户使用（查询功能）

        Returns:
            是否有权限
        """
        sender_id = event.get_sender_id()

        # 检查是否在黑名单中
        if self._is_blacklisted(event):
            return False

        # 管理员始终有权限
        if self._is_admin(event):
            return True

        # 如果允许普通用户使用
        if allow_guest:
            return True

        # 如果没有配置管理员，允许所有人使用（不推荐）
        if not self.admin_qqs and not self.admin_groups:
            return True

        # 检查是否在允许的群组中
        message_obj = event.message_obj
        if message_obj.group_id and self.admin_groups:
            if message_obj.group_id in self.admin_groups:
                return True

        return False

    def _check_config(self) -> bool:
        """检查配置是否完整"""
        return self.client is not None and self.base_url and self.webkey

    @filter.command("授权")
    async def plan_command(self, event: AstrMessageEvent):
        '''Nathan-Auth 授权管理命令 - 用法：/授权 [操作] [参数...]'''

        # 检查配置
        if not self._check_config():
            yield event.plain_result("❌ 插件配置不完整，请联系管理员配置 base_url 和 webkey")
            return

        # 解析命令参数
        message = event.message_str.strip()
        parts = message.split()

        # 移除命令本身 (/授权)
        if len(parts) > 0 and parts[0] in ['/授权', '授权']:
            parts = parts[1:]

        action = parts[0] if len(parts) > 0 else ""
        args = parts[1:] if len(parts) > 1 else []

        # 显示菜单 + all 命令
        if not action or action == "all":
            async for result in self._show_all_menu(event):
                yield result
            return

        # 查询授权：智能识别域名或QQ（所有用户可用）
        if action == "查询授权":
            if not self._check_permission(event, allow_guest=True):
                yield event.plain_result("❌ 你已被禁止使用此功能")
                return
            async for result in self._handle_query_auth(event, args):
                yield result
            return

        # 更改域名（普通用户也可用，自动使用自己的QQ）
        if action == "更改域名" or action == "更改授权":
            if not self._check_permission(event, allow_guest=True):
                yield event.plain_result("❌ 你已被禁止使用此功能")
                return
            async for result in self._handle_replace(event, args):
                yield result
            return

        # 代理查询功能：所有用户可用
        if action == "代理查询":
            if not self._check_permission(event, allow_guest=True):
                yield event.plain_result("❌ 你已被禁止使用此功能")
                return
            async for result in self._handle_query_agent(event, args):
                yield result
            return

        # 其他功能需要管理员权限
        if not self._check_permission(event):
            yield event.plain_result("❌ 你没有权限使用此命令")
            return

        # 处理管理员功能
        try:
            if action == "添加授权":
                async for result in self._handle_add(event, args):
                    yield result
            elif action == "封禁":
                async for result in self._handle_freeze(event, args):
                    yield result
            elif action == "解封":
                async for result in self._handle_unseal(event, args):
                    yield result
            elif action == "删除授权":
                async for result in self._handle_delete(event, args):
                    yield result
            elif action == "应用列表":
                async for result in self._handle_applist(event):
                    yield result
            elif action == "生成卡密":
                async for result in self._handle_create_card(event, args):
                    yield result
            elif action == "授权码":
                async for result in self._handle_authcode(event, args):
                    yield result
            else:
                yield event.plain_result(f"❌ 未知操作：{action}\n请发送 /授权 查看帮助")
        except Exception as e:
            logger.error(f"Nathan-Auth 命令执行错误: {e}")
            yield event.plain_result(f"❌ 执行出错: {str(e)}")

    async def _show_all_menu(self, event: AstrMessageEvent):
        """显示完整帮助菜单（/授权 all）"""
        menu_text = f"""{self.site_name} 授权管理插件

使用示例：
• /授权 查询授权 example.com
• /授权 查询授权 [QQ]
• /授权 代理查询 [QQ]
• /授权 添加授权 example.com 123456789
• /授权 添加授权 example.com 123456789 365
• /授权 封禁 example.com 违规使用
• /授权 解封 example.com
• /授权 删除授权 example.com
• /授权 生成卡密 2 10 365
• /授权 更改域名 old.com new.com 123456789
• /授权 授权码 example.com

说明：
• 天数为0表示永久授权
• 卡密类型：1=余额卡密，2=授权卡密
• [QQ]为可选参数，不填则查询/使用你自己的QQ
• 普通用户：/授权 更改域名 old.com new.com（自动用你的QQ）
"""
        yield event.plain_result(menu_text)

    async def _show_menu(self, event: AstrMessageEvent):
        """显示帮助菜单"""
        is_admin = self._is_admin(event)

        if is_admin:
            menu_text = f"""{self.site_name} 授权管理插件

使用示例：
• /授权 查询授权 example.com
• /授权 查询授权 [QQ]
• /授权 代理查询 [QQ]
• /授权 添加授权 example.com 123456789
• /授权 添加授权 example.com 123456789 365
• /授权 封禁 example.com 违规使用
• /授权 解封 example.com
• /授权 删除授权 example.com
• /授权 生成卡密 2 10 365
• /授权 更改域名 old.com new.com 123456789
• /授权 授权码 example.com

说明：
• 天数为0表示永久授权
• 卡密类型：1=余额卡密，2=授权卡密
• [QQ]为可选参数，不填则查询/使用你自己的QQ
"""
        else:
            menu_text = f"""{self.site_name} 授权管理插件

使用示例：
• /授权 查询授权 example.com
• /授权 查询授权
• /授权 代理查询
• /授权 更改域名 old.com new.com

说明：
• 查询功能对所有用户开放
• 查询授权/代理查询默认使用你的QQ
• 更改域名会自动使用你的QQ
"""
        yield event.plain_result(menu_text)

    async def _handle_query_auth(self, event: AstrMessageEvent, args):
        """处理查询授权 - 智能识别域名或QQ"""
        sender_qq = event.get_sender_id()

        if len(args) >= 1:
            arg = args[0]
            # 包含 '.' 的视为域名查询，否则视为QQ查询
            if "." in arg:
                # 域名查询
                domain = arg
                # 请求前先获取 cookie
                await self.client._ensure_cookie()
                result = await self.client.query_auth(self.default_appid, domain)
                if str(result.get("code")) == "1":
                    data = result.get("data", {})
                    status_text = "正常" if data.get("status") == "1" else "封禁"
                    reply = f"查询结果\n域名：{domain}\n状态：{status_text}\nQQ：{data.get('qq', '未知')}\n邮箱：{data.get('email', '未知')}\n到期：{data.get('authdate', '未知')}\n授权码：{data.get('authcode', '未知')}"
                else:
                    reply = f"查询失败：{result.get('msg', '未知错误')}"
            else:
                # QQ查询
                qq = arg
                yield event.plain_result(f"正在查询QQ {qq} 的授权，请稍候...")
                result = await self.client.query_auth_by_qq(appid=self.default_appid, qq=qq)
                code = result.get("code")
                if code == 1 or str(code) == "1":
                    msg = self.client._strip_html(result.get("msg", ""))
                    reply = f"查询结果（QQ: {qq}）：\n{msg}" if msg else f"查询成功（QQ: {qq}）"
                else:
                    msg = self.client._strip_html(result.get("msg", "未找到相关授权信息"))
                    reply = f"{msg}"
        else:
            # 无参数：查询发送者自己的QQ
            qq = sender_qq
            yield event.plain_result(f"正在查询你的授权，请稍候...")
            result = await self.client.query_auth_by_qq(appid=self.default_appid, qq=qq)
            code = result.get("code")
            if code == 1 or str(code) == "1":
                msg = self.client._strip_html(result.get("msg", ""))
                reply = f"查询结果（QQ: {qq}）：\n{msg}" if msg else f"查询成功（QQ: {qq}）"
            else:
                msg = self.client._strip_html(result.get("msg", "未找到相关授权信息"))
                reply = f"{msg}"

        yield event.plain_result(reply)

    async def _handle_add(self, event: AstrMessageEvent, args):
        """处理添加授权"""
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/授权 添加授权 <域名> <QQ> [天数]\n示例：/授权 添加授权 example.com 123456789")
            return

        domain = args[0]
        qq = args[1]
        authdate = args[2] if len(args) > 2 else self.default_authdate

        yield event.plain_result(f"📝 正在添加授权，请稍候...")

        result = await self.client.admin_add_auth(
            url=domain,
            qq=qq,
            authdate=authdate
        )

        if str(result.get("code")) == "1":
            date_text = "永久" if authdate == "0" else f"{authdate}天"
            reply = f"""✅ 授权添加成功

🌐 域名：{domain}
👤 QQ：{qq}
📅 授权时长：{date_text}
📧 邮箱：{qq}@qq.com"""
        else:
            reply = f"❌ 添加失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_freeze(self, event: AstrMessageEvent, args):
        """处理封禁授权"""
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/授权 封禁 <域名> <原因>\n示例：/授权 封禁 example.com 违规使用")
            return

        domain = args[0]
        reason = " ".join(args[1:])

        result = await self.client.freeze_auth(self.default_appid, domain, reason)

        if str(result.get("code")) == "1":
            reply = f"""✅ 授权封禁成功

🌐 域名：{domain}
📝 封禁原因：{reason}"""
        else:
            reply = f"❌ 封禁失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_unseal(self, event: AstrMessageEvent, args):
        """处理解封授权"""
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/授权 解封 <域名>\n示例：/授权 解封 example.com")
            return

        domain = args[0]

        result = await self.client.unseal_auth(self.default_appid, domain)

        if str(result.get("code")) == "1":
            reply = f"""✅ 授权解封成功

🌐 域名：{domain}
📊 状态：已恢复正常"""
        else:
            reply = f"❌ 解封失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_delete(self, event: AstrMessageEvent, args):
        """处理删除授权"""
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/授权 删除授权 <域名>\n示例：/授权 删除授权 example.com")
            return

        domain = args[0]

        result = await self.client.del_auth(self.default_appid, domain)

        if str(result.get("code")) == "1":
            reply = f"""✅ 授权删除成功

🌐 域名：{domain}
📝 该域名的授权已被永久删除"""
        else:
            reply = f"❌ 删除失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_applist(self, event: AstrMessageEvent):
        """处理获取应用列表"""
        result = await self.client.get_applist()

        if str(result.get("code")) == "1":
            apps = result.get("data", [])
            if not apps:
                reply = "📭 暂无应用数据"
            else:
                reply = "📱 应用列表：\n\n"
                for app in apps:
                    reply += f"🔹 ID: {app.get('id', '未知')} - {app.get('name', '未知')}\n"
        else:
            reply = f"❌ 获取失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_create_card(self, event: AstrMessageEvent, args):
        """处理生成卡密"""
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/授权 生成卡密 <类型> <数量> [天数]\n类型：1=余额卡密，2=授权卡密\n示例：/授权 生成卡密 2 10 365")
            return

        card_type = args[0]
        count = args[1]
        authdate = args[2] if len(args) > 2 else self.default_authdate

        # 验证类型
        if card_type not in ["1", "2"]:
            yield event.plain_result("❌ 卡密类型错误：1=余额卡密，2=授权卡密")
            return

        yield event.plain_result(f"📝 正在生成卡密，请稍候...")

        # 根据类型设置参数
        money = "0"
        if card_type == "1":
            # 余额卡密不需要authdate
            authdate = "0"
            money = "100"  # 默认余额

        result = await self.client.create_card(
            card_act=card_type,
            count=count,
            authdate=authdate,
            money=money
        )

        if str(result.get("code")) == "1":
            cards = result.get("data", [])
            type_text = "余额卡密" if card_type == "1" else "授权卡密"
            reply = f"""✅ 卡密生成成功

📋 类型：{type_text}
📊 数量：{len(cards)} 张

🔑 卡密列表：
"""
            for i, card in enumerate(cards, 1):
                reply += f"{i}. {card}\n"
        else:
            reply = f"❌ 生成失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_replace(self, event: AstrMessageEvent, args):
        """处理更换授权域名"""
        is_admin = self._is_admin(event)
        sender_qq = event.get_sender_id()

        if is_admin:
            # 管理员：需要旧域名、新域名、QQ
            if len(args) < 3:
                yield event.plain_result("❌ 用法：/授权 更改域名 <旧域名> <新域名> <QQ>\n示例：/授权 更改域名 old.com new.com 123456789")
                return
            old_domain = args[0]
            new_domain = args[1]
            qq = args[2]
        else:
            # 普通用户：只需要旧域名和新域名，自动使用发送者的QQ
            if len(args) < 2:
                yield event.plain_result("❌ 用法：/授权 更改域名 <旧域名> <新域名>\n示例：/授权 更改域名 old.com new.com")
                return
            old_domain = args[0]
            new_domain = args[1]
            qq = sender_qq

        yield event.plain_result(f"📝 正在更改域名，请稍候...")

        result = await self.client.replace_auth(
            qq=qq,
            url=old_domain,
            new_url=new_domain
        )

        if str(result.get("code")) == "1":
            reply = f"""✅ 域名更改成功

🌐 旧域名：{old_domain}
🌐 新域名：{new_domain}
👤 QQ：{qq}"""
        else:
            error_msg = result.get('msg', '未知错误')
            if not is_admin:
                # 普通用户更换失败，提示使用绑定的QQ
                reply = f"❌ 更改失败：{error_msg}\n\n💡 提示：请使用绑定该授权的QQ号来发送此指令"
            else:
                reply = f"❌ 更改失败：{error_msg}"

        yield event.plain_result(reply)

    async def _handle_authcode(self, event: AstrMessageEvent, args):
        """处理获取域名授权码"""
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/授权 授权码 <域名>\n示例：/授权 授权码 example.com")
            return

        domain = args[0]

        yield event.plain_result(f"📝 正在获取授权码，请稍候...")

        result = await self.client.get_url_authcode(
            appid=self.default_appid,
            url=domain
        )

        if str(result.get("code")) == "1":
            data = result.get("data", {})
            reply = f"""✅ 授权码获取成功

🌐 域名：{data.get('url', domain)}
👤 QQ：{data.get('qq', '未知')}
🔑 授权码：{data.get('authcode', '未知')}"""
        else:
            reply = f"❌ 获取失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_query_agent(self, event: AstrMessageEvent, args):
        """处理代理查询"""
        sender_qq = event.get_sender_id()

        # 如果用户传了QQ号，使用用户传的，否则使用发送者的QQ
        if len(args) >= 1:
            qq = args[0]
        else:
            qq = sender_qq

        yield event.plain_result(f"📝 正在查询QQ {qq} 的代理信息，请稍候...")

        result = await self.client.query_agent(
            appid=self.default_appid,
            qq=qq
        )

        code = result.get("code")
        if code == 1 or str(code) == "1":
            msg = self.client._strip_html(result.get("msg", ""))
            if msg:
                reply = f"✅ 代理查询结果（QQ: {qq}）：\n\n{msg}"
            else:
                reply = f"✅ 查询成功（QQ: {qq}）"
        else:
            msg = self.client._strip_html(result.get("msg", "该用户不是授权商"))
            reply = f"❌ {msg}"

        yield event.plain_result(reply)

    async def terminate(self):
        '''插件卸载时调用'''
        logger.info("Nathan-Auth 插件已卸载")
