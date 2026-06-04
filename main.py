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
    "1.0.0",
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
                    import re
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

    def _check_permission(self, event: AstrMessageEvent) -> bool:
        """检查用户是否有权限使用命令"""
        # 如果没有配置管理员，允许所有人使用（不推荐）
        if not self.admin_qqs and not self.admin_groups:
            return True

        # 检查QQ是否在管理员列表中
        sender_id = event.get_sender_id()
        if self.admin_qqs and sender_id in self.admin_qqs:
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
        '''Nathan-Auth 授权管理命令 - 用法：/授权 [操作] [参数...]

        可用操作：
        /授权 - 显示帮助菜单
        /授权 查询 <域名> - 查询域名授权状态
        /授权 添加 <域名> <QQ> [天数] - 添加域名授权
        /授权 封禁 <域名> <原因> - 封禁域名授权
        /授权 解封 <域名> - 解封域名授权
        /授权 删除 <域名> - 删除域名授权
        /授权 应用列表 - 获取应用列表
        /授权 生成卡密 <类型> <数量> [天数] - 生成卡密（类型：1=余额卡密，2=授权卡密）
        /授权 更换 <旧域名> <新域名> <QQ> - 更换授权域名
        /授权 授权码 <域名> - 获取域名授权码
        '''
        # 检查权限
        if not self._check_permission(event):
            yield event.plain_result("❌ 叼毛，让你用了吗。你就用！！！！")
            return

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

        # 显示菜单
        if not action:
            async for result in self._show_menu(event):
                yield result
            return

        # 处理各种操作
        try:
            if action == "查询":
                async for result in self._handle_query(event, args):
                    yield result
            elif action == "添加":
                async for result in self._handle_add(event, args):
                    yield result
            elif action == "封禁":
                async for result in self._handle_freeze(event, args):
                    yield result
            elif action == "解封":
                async for result in self._handle_unseal(event, args):
                    yield result
            elif action == "删除":
                async for result in self._handle_delete(event, args):
                    yield result
            elif action == "应用列表":
                async for result in self._handle_applist(event):
                    yield result
            elif action == "生成卡密":
                async for result in self._handle_create_card(event, args):
                    yield result
            elif action == "更换":
                async for result in self._handle_replace(event, args):
                    yield result
            elif action == "授权码":
                async for result in self._handle_authcode(event, args):
                    yield result
            else:
                yield event.plain_result(f"❌ 未知操作：{action}\n请发送 /授权 查看帮助")
        except Exception as e:
            logger.error(f"Nathan-Auth 命令执行错误: {e}")
            yield event.plain_result(f"❌ 执行出错: {str(e)}")

    async def _show_menu(self, event: AstrMessageEvent):
        """显示帮助菜单"""
        menu_text = f"""{self.site_name} 授权管理插件

命令列表：
━━━━━━━━━━━━━━━━
/授权 - 显示此菜单
/授权 查询 <域名> - 查询域名授权状态
/授权 添加 <域名> <QQ> [天数] - 添加域名授权
/授权 封禁 <域名> <原因> - 封禁域名授权
/授权 解封 <域名> - 解封域名授权
/授权 删除 <域名> - 删除域名授权
/授权 应用列表 - 获取应用列表
/授权 生成卡密 <类型> <数量> [天数] - 生成卡密
/授权 更换 <旧域名> <新域名> <QQ> - 更换授权域名
/授权 授权码 <域名> - 获取域名授权码
━━━━━━━━━━━━━━━━

使用示例：
• /授权 查询 example.com
• /授权 添加 example.com 123456789
• /授权 添加 example.com 123456789 365
• /授权 封禁 example.com 违规使用
• /授权 解封 example.com
• /授权 删除 example.com
• /授权 生成卡密 2 10 365
• /授权 更换 old.com new.com 123456789
• /授权 授权码 example.com

说明：
• 天数为0表示永久授权
• 卡密类型：1=余额卡密，2=授权卡密
"""
        yield event.plain_result(menu_text)

    async def _handle_query(self, event: AstrMessageEvent, args):
        """处理查询授权"""
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/授权 查询 <域名>\n示例：/授权 查询 example.com")
            return

        domain = args[0]
        result = await self.client.query_auth(self.default_appid, domain)

        if result.get("code") == "1":
            data = result.get("data", {})
            status_text = "✅ 正常" if data.get("status") == "1" else "❌ 封禁"
            reply = f"""📋 授权查询结果

🌐 域名：{domain}
📊 状态：{status_text}
👤 QQ：{data.get('qq', '未知')}
📧 邮箱：{data.get('email', '未知')}
📅 到期时间：{data.get('authdate', '未知')}
📝 授权码：{data.get('authcode', '未知')}"""
        else:
            reply = f"❌ 查询失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_add(self, event: AstrMessageEvent, args):
        """处理添加授权"""
        if len(args) < 2:
            yield event.plain_result("❌ 用法：/授权 添加 <域名> <QQ> [天数]\n示例：/授权 添加 example.com 123456789")
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

        if result.get("code") == "1":
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

        if result.get("code") == "1":
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

        if result.get("code") == "1":
            reply = f"""✅ 授权解封成功

🌐 域名：{domain}
📊 状态：已恢复正常"""
        else:
            reply = f"❌ 解封失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_delete(self, event: AstrMessageEvent, args):
        """处理删除授权"""
        if len(args) < 1:
            yield event.plain_result("❌ 用法：/授权 删除 <域名>\n示例：/授权 删除 example.com")
            return

        domain = args[0]

        result = await self.client.del_auth(self.default_appid, domain)

        if result.get("code") == "1":
            reply = f"""✅ 授权删除成功

🌐 域名：{domain}
📝 该域名的授权已被永久删除"""
        else:
            reply = f"❌ 删除失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def _handle_applist(self, event: AstrMessageEvent):
        """处理获取应用列表"""
        result = await self.client.get_applist()

        if result.get("code") == "1":
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

        if result.get("code") == "1":
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
        if len(args) < 3:
            yield event.plain_result("❌ 用法：/授权 更换 <旧域名> <新域名> <QQ>\n示例：/授权 更换 old.com new.com 123456789")
            return

        old_domain = args[0]
        new_domain = args[1]
        qq = args[2]

        yield event.plain_result(f"📝 正在更换授权域名，请稍候...")

        result = await self.client.replace_auth(
            qq=qq,
            url=old_domain,
            new_url=new_domain
        )

        if result.get("code") == "1":
            reply = f"""✅ 授权更换成功

🌐 旧域名：{old_domain}
🌐 新域名：{new_domain}
👤 QQ：{qq}"""
        else:
            reply = f"❌ 更换失败：{result.get('msg', '未知错误')}"

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

        if result.get("code") == "1":
            data = result.get("data", {})
            reply = f"""✅ 授权码获取成功

🌐 域名：{data.get('url', domain)}
👤 QQ：{data.get('qq', '未知')}
🔑 授权码：{data.get('authcode', '未知')}"""
        else:
            reply = f"❌ 获取失败：{result.get('msg', '未知错误')}"

        yield event.plain_result(reply)

    async def terminate(self):
        '''插件卸载时调用'''
        logger.info("Nathan-Auth 插件已卸载")
