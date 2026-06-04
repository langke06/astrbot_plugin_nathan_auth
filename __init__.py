#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nathan-Auth 授权管理插件 - AstrBot 版本

提供域名授权管理、封禁解封、查询等功能
"""

from .main import NathanAuthPlugin
from .nathan_auth_client import NathanAuthClient

__all__ = ["NathanAuthPlugin", "NathanAuthClient"]
__version__ = "1.0.0"
__author__ = "langke06"
