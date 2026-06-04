"""
Nathan-Auth 授权管理系统 API 客户端 (异步版本)
提供域名授权管理、封禁解封、查询等功能
"""

import json
import aiohttp
from typing import Optional, Dict, Any
from urllib.parse import urljoin


class NathanAuthClient:
    """Nathan-Auth 授权管理系统 API 客户端"""

    def __init__(
        self,
        base_url: str,
        webkey: str,
        admin_name: str = "",
        admin_password: str = "",
        default_appid: str = "1",
        default_authdate: str = "0",
        default_ip: str = "127.0.0.1"
    ):
        """
        初始化客户端

        Args:
            base_url: 授权系统域名
            webkey: 网站安全密钥
            admin_name: 管理员用户名（添加授权时需要）
            admin_password: 管理员密码（添加授权时需要）
            default_appid: 默认应用ID
            default_authdate: 默认授权天数（0为永久）
            default_ip: 默认服务器IP
        """
        self.base_url = base_url.rstrip('/')
        self.webkey = webkey
        self.admin_name = admin_name
        self.admin_password = admin_password
        self.default_appid = default_appid
        self.default_authdate = default_authdate
        self.default_ip = default_ip
        self.api_prefix = "/api/Index"

    async def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送API请求

        Args:
            endpoint: API端点
            params: 请求参数

        Returns:
            API响应数据
        """
        url = urljoin(self.base_url, f"{self.api_prefix}/{endpoint}")
        params['webkey'] = self.webkey

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()
                    # 先获取文本，再尝试解析JSON
                    text = await response.text()
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        # 如果返回的不是JSON，可能是错误页面
                        return {"code": "0", "msg": f"API返回非JSON数据: {text[:200]}"}
        except aiohttp.ClientError as e:
            return {"code": "0", "msg": f"请求失败: {str(e)}"}
        except Exception as e:
            return {"code": "0", "msg": f"请求异常: {str(e)}"}

    async def query_auth(self, appid: str, url: str) -> Dict[str, Any]:
        """
        查询授权状态

        Args:
            appid: 应用ID
            url: 目标站域名

        Returns:
            授权查询结果
        """
        params = {
            "appid": appid,
            "url": url
        }
        return await self._make_request("query_auth", params)

    async def check_auth(self, appid: str, url: str, ip: str, authcode: str) -> Dict[str, Any]:
        """
        检测授权

        Args:
            appid: 应用ID
            url: 目标站域名
            ip: 目标站服务器IP
            authcode: 授权码

        Returns:
            授权检测结果
        """
        params = {
            "appid": appid,
            "url": url,
            "ip": ip,
            "authcode": authcode
        }
        return await self._make_request("check_auth", params)

    async def admin_add_auth(
        self,
        url: str,
        qq: str,
        appid: Optional[str] = None,
        ip: Optional[str] = None,
        adminname: Optional[str] = None,
        password: Optional[str] = None,
        authdate: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        管理员添加授权

        Args:
            url: 授权的网站域名
            qq: 授权的网站站长QQ
            appid: 应用ID，默认使用配置中的 default_appid
            ip: 授权的服务器IP，默认使用配置中的 default_ip
            adminname: 管理员用户名，默认使用配置中的 admin_name
            password: 管理员密码，默认使用配置中的 admin_password
            authdate: 授权天数（0为永久，1为1天），默认使用配置中的 default_authdate
            email: 授权邮箱（可选，默认自动拼接为 QQ@qq.com）
            phone: 授权手机号（可选）

        Returns:
            添加结果
        """
        # 使用默认值
        appid = appid or self.default_appid
        ip = ip or self.default_ip
        adminname = adminname or self.admin_name
        password = password or self.admin_password
        authdate = authdate or self.default_authdate

        # 如果没有提供邮箱，自动拼接 QQ@qq.com
        if email is None and qq:
            email = f"{qq}@qq.com"

        params = {
            "appid": appid,
            "url": url,
            "qq": qq,
            "ip": ip,
            "adminname": adminname,
            "password": password,
            "authdate": authdate
        }
        if email:
            params["email"] = email
        if phone:
            params["phone"] = phone

        return await self._make_request("admin_add_auth", params)

    async def user_add_auth(
        self,
        appid: str,
        url: str,
        qq: str,
        ip: str,
        key: str,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        用户添加授权

        Args:
            appid: 应用ID
            url: 授权的网站域名
            qq: 授权的网站站长QQ
            ip: 授权的服务器IP
            key: 用户密钥
            email: 授权邮箱（可选，默认自动拼接为 QQ@qq.com）
            phone: 授权手机号（可选）

        Returns:
            添加结果
        """
        # 如果没有提供邮箱，自动拼接 QQ@qq.com
        if email is None and qq:
            email = f"{qq}@qq.com"

        params = {
            "appid": appid,
            "url": url,
            "qq": qq,
            "ip": ip,
            "key": key
        }
        if email:
            params["email"] = email
        if phone:
            params["phone"] = phone

        return await self._make_request("user_add_auth", params)

    async def freeze_auth(self, appid: str, url: str, reason: str) -> Dict[str, Any]:
        """
        禁封授权

        Args:
            appid: 应用ID
            url: 授权域名
            reason: 禁封原因

        Returns:
            禁封结果
        """
        params = {
            "appid": appid,
            "url": url,
            "reason": reason
        }
        return await self._make_request("freeze_auth", params)

    async def unseal_auth(self, appid: str, url: str) -> Dict[str, Any]:
        """
        解封授权

        Args:
            appid: 应用ID
            url: 授权域名

        Returns:
            解封结果
        """
        params = {
            "appid": appid,
            "url": url
        }
        return await self._make_request("unseal_auth", params)

    async def del_auth(self, appid: str, url: str) -> Dict[str, Any]:
        """
        删除授权

        Args:
            appid: 应用ID
            url: 授权域名

        Returns:
            删除结果
        """
        params = {
            "appid": appid,
            "url": url
        }
        return await self._make_request("del_auth", params)

    async def query_auth_up_info(self, appid: str, url: str) -> Dict[str, Any]:
        """
        查询授权所属用户信息

        Args:
            appid: 应用ID
            url: 授权域名

        Returns:
            用户信息
        """
        params = {
            "appid": appid,
            "url": url
        }
        return await self._make_request("QueryAuthUpInfo", params)

    async def query_auth_up_status(self, appid: str, url: str) -> Dict[str, Any]:
        """
        检测授权所属用户状态

        Args:
            appid: 应用ID
            url: 授权域名

        Returns:
            用户状态
        """
        params = {
            "appid": appid,
            "url": url
        }
        return await self._make_request("QueryAuthUpStatus", params)

    async def get_applist(self) -> Dict[str, Any]:
        """
        获取应用列表

        Returns:
            应用列表
        """
        params = {}
        return await self._make_request("applist", params)

    async def user_add(
        self,
        username: str,
        password: str,
        qq: str,
        apistate: str,
        money: str,
        admin_name: Optional[str] = None,
        admin_password: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建用户

        Args:
            username: 用户名
            password: 用户密码
            qq: 用户QQ
            apistate: API状态 1开启 2关闭
            money: 账户余额
            admin_name: 管理员账号，默认使用配置中的 admin_name
            admin_password: 管理员密码，默认使用配置中的 admin_password
            email: 用户邮箱（可选，默认自动拼接为 QQ@qq.com）
            phone: 用户手机号（可选）

        Returns:
            创建结果
        """
        # 使用默认值
        admin_name = admin_name or self.admin_name
        admin_password = admin_password or self.admin_password

        # 如果没有提供邮箱，自动拼接 QQ@qq.com
        if email is None and qq:
            email = f"{qq}@qq.com"

        params = {
            "username": username,
            "password": password,
            "qq": qq,
            "apistate": apistate,
            "money": money,
            "admin_name": admin_name,
            "admin_password": admin_password
        }
        if email:
            params["email"] = email
        if phone:
            params["phone"] = phone

        return await self._make_request("user_add", params)

    async def create_card(
        self,
        card_act: str,
        count: str,
        appid: Optional[str] = None,
        authdate: Optional[str] = None,
        money: str = "0",
        prefix: str = ""
    ) -> Dict[str, Any]:
        """
        生成卡密

        Args:
            card_act: 卡密类型 1余额卡密 2授权卡密
            count: 生成数量
            appid: 应用ID，默认使用配置中的 default_appid
            authdate: 授权天数（卡密类型为2时必填，0为永久），默认使用配置中的 default_authdate
            money: 卡密余额（卡密类型为1时必填）
            prefix: 卡密前缀（可选，如 APP 则生成 APP_xxxxx）

        Returns:
            生成结果，成功时返回卡密列表
        """
        appid = appid or self.default_appid
        authdate = authdate or self.default_authdate

        params = {
            "CardAct": card_act,
            "count": count,
            "appid": appid,
            "authdate": authdate,
            "money": money
        }
        if prefix:
            params["prefix"] = prefix

        return await self._make_request("createCard", params)

    async def replace_auth(
        self,
        qq: str,
        url: str,
        new_url: str,
        appid: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更换授权（更改域名）

        Args:
            qq: 授权QQ
            url: 旧授权域名
            new_url: 新授权域名
            appid: 应用ID，默认使用配置中的 default_appid
            phone: 授权手机号（可选）
            email: 授权邮箱（可选，默认自动拼接为 QQ@qq.com）
            ip: 授权IP（可选）

        Returns:
            更换结果
        """
        appid = appid or self.default_appid

        # 如果没有提供邮箱，自动拼接 QQ@qq.com
        if email is None and qq:
            email = f"{qq}@qq.com"

        params = {
            "appid": appid,
            "qq": qq,
            "url": url,
            "new_url": new_url
        }
        if phone:
            params["phone"] = phone
        if email:
            params["email"] = email
        if ip:
            params["ip"] = ip

        return await self._make_request("replace_auth", params)

    async def card_auth(
        self,
        appid: str,
        url: str,
        qq: str,
        key: str,
        ip: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        卡密授权（使用卡密自助授权）

        Args:
            appid: 应用ID
            url: 授权的网站域名
            qq: 授权的网站站长QQ
            key: 授权卡密
            ip: 授权的服务器IP，默认使用配置中的 default_ip
            email: 授权邮箱（可选，默认自动拼接为 QQ@qq.com）
            phone: 授权手机号（可选）

        Returns:
            授权结果
        """
        ip = ip or self.default_ip

        # 如果没有提供邮箱，自动拼接 QQ@qq.com
        if email is None and qq:
            email = f"{qq}@qq.com"

        params = {
            "appid": appid,
            "url": url,
            "qq": qq,
            "ip": ip,
            "key": key
        }
        if email:
            params["email"] = email
        if phone:
            params["phone"] = phone

        return await self._make_request("create_auth", params)

    async def get_url_authcode(self, appid: str, url: str) -> Dict[str, Any]:
        """
        获取域名授权码

        Args:
            appid: 应用ID
            url: 授权域名

        Returns:
            授权码信息，包含 url、qq、authcode
        """
        params = {
            "appid": appid,
            "url": url
        }
        return await self._make_request("UrlAuthCode", params)
