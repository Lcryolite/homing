from __future__ import annotations

import asyncio
import base64
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    aiohttp = None
    AIOHTTP_AVAILABLE = False

from openemail.models.account import Account


class SyncFolderType(Enum):
    """ActiveSync同步文件夹类型"""

    EMAIL = "Email"
    CALENDAR = "Calendar"
    CONTACTS = "Contacts"
    TASKS = "Tasks"


class SyncCommandType(Enum):
    """ActiveSync命令类型"""

    SYNC = "Sync"
    FOLDER_SYNC = "FolderSync"
    GET_ITEM_ESTIMATE = "GetItemEstimate"
    MOVE_ITEMS = "MoveItems"
    SEND_MAIL = "SendMail"
    SMART_REPLY = "SmartReply"
    SMART_FORWARD = "SmartForward"
    GET_ATTACHMENT = "GetAttachment"
    FETCH = "Fetch"
    MEETING_RESPONSE = "MeetingResponse"
    SEARCH = "Search"
    SETTINGS = "Settings"
    PING = "Ping"
    ITEM_OPERATIONS = "ItemOperations"


class ActiveSyncClient:
    """Exchange ActiveSync客户端"""

    def __init__(self, account: Account):
        self.account = account
        self.session: Optional[aiohttp.ClientSession] = None
        self.device_id: str = ""
        self.policy_key: str = ""
        self._init_device_id()

    def _init_device_id(self):
        """初始化设备ID"""
        if self.account.eas_device_id:
            self.device_id = self.account.eas_device_id
        else:
            # 生成唯一设备ID
            self.device_id = f"OPENEMAIL-{uuid.uuid4().hex[:16].upper()}"

    async def connect(self) -> bool:
        """连接到ActiveSync服务器"""
        try:
            if not self.account.eas_host:
                print(f"ActiveSync主机未配置: {self.account.email}")
                return False

            # 构建URL
            url = f"https://{self.account.eas_host}{self.account.eas_path}"

            # 创建会话
            self.session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "OpenEmail/1.0",
                    "MS-ASProtocolVersion": "14.1",
                }
            )

            # 测试连接
            return await self._test_connection(url)

        except Exception as e:
            print(f"ActiveSync连接失败 {self.account.email}: {e}")
            return False

    async def _test_connection(self, url: str) -> bool:
        """测试连接"""
        try:
            # 尝试FolderSync命令测试连接
            response = await self._send_command(
                url,
                SyncCommandType.FOLDER_SYNC,
                {},
                sync_key="0",  # 初始同步键
            )
            return response is not None
        except Exception as e:
            print(f"ActiveSync测试连接失败: {e}")
            return False

    async def _send_command(
        self,
        url: str,
        command: SyncCommandType,
        data: Dict[str, Any],
        sync_key: str = "",
    ) -> Optional[ET.Element]:
        """发送ActiveSync命令"""
        if not self.session:
            return None

        try:
            # 构建XML请求
            xml_request = self._build_xml_request(command, data, sync_key)

            headers = {
                "Content-Type": "application/vnd.ms-sync.wbxml",
                "Authorization": self._get_auth_header(),
            }

            async with self.session.post(
                url,
                data=xml_request,
                headers=headers,
            ) as response:
                if response.status == 200:
                    # 解析响应
                    content = await response.read()
                    return self._parse_xml_response(content)
                else:
                    print(f"ActiveSync命令失败: {response.status}")
                    return None

        except Exception as e:
            print(f"发送ActiveSync命令失败: {e}")
            return None

    def _build_xml_request(
        self, command: SyncCommandType, data: Dict[str, Any], sync_key: str
    ) -> bytes:
        """构建XML请求（简化版）"""
        # 在实际实现中，这里需要构建正确的WBXML格式
        # 这里返回一个占位符
        return b""

    def _parse_xml_response(self, content: bytes) -> Optional[ET.Element]:
        """解析XML响应（简化版）"""
        # 在实际实现中，这里需要解析WBXML响应
        # 这里返回一个占位符
        return None

    def _get_auth_header(self) -> str:
        """获取认证头"""
        if self.account.auth_type == "oauth2" and self.account.oauth_token:
            return f"Bearer {self.account.oauth_token}"
        else:
            # 基本认证
            auth_str = f"{self.account.email}:{self.account.password}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            return f"Basic {encoded}"

    async def folder_sync(self) -> List[Dict[str, Any]]:
        """同步文件夹列表"""
        try:
            url = f"https://{self.account.eas_host}{self.account.eas_path}"
            response = await self._send_command(
                url, SyncCommandType.FOLDER_SYNC, {}, sync_key="0"
            )

            if response:
                return self._parse_folders(response)
            return []
        except Exception as e:
            print(f"文件夹同步失败: {e}")
            return []

    def _parse_folders(self, xml_response: ET.Element) -> List[Dict[str, Any]]:
        """解析文件夹响应"""
        folders = []
        # 简化实现 - 实际需要解析XML
        default_folders = [
            {"name": "收件箱", "type": "inbox"},
            {"name": "已发送邮件", "type": "sent"},
            {"name": "草稿", "type": "drafts"},
            {"name": "已删除邮件", "type": "trash"},
        ]
        return default_folders

    async def email_sync(
        self, folder_id: str, sync_key: str = "", limit: int = 100
    ) -> Dict[str, Any]:
        """同步邮件"""
        try:
            url = f"https://{self.account.eas_host}{self.account.eas_path}"
            data = {
                "folder_id": folder_id,
                "collection_id": folder_id,
                "get_changes": "1" if sync_key else "0",
                "window_size": str(limit),
            }

            response = await self._send_command(
                url, SyncCommandType.SYNC, data, sync_key=sync_key or "0"
            )

            if response:
                return self._parse_email_sync(response)
            return {"sync_key": "", "emails": []}
        except Exception as e:
            print(f"邮件同步失败: {e}")
            return {"sync_key": "", "emails": []}

    def _parse_email_sync(self, xml_response: ET.Element) -> Dict[str, Any]:
        """解析邮件同步响应"""
        # 简化实现
        return {"sync_key": "1", "emails": []}

    async def sync_calendar(self) -> List[Dict[str, Any]]:
        """同步日历"""
        # 暂不实现
        return []

    async def sync_contacts(self) -> List[Dict[str, Any]]:
        """同步联系人"""
        # 暂不实现
        return []

    async def disconnect(self):
        """断开连接"""
        if self.session:
            await self.session.close()
            self.session = None

    def __del__(self):
        """析构函数确保会话关闭 - 不再在GC时创建异步任务"""
        # asyncio.create_task 在 __del__ 中不安全（可能没有运行中的事件循环）
        # 调用方应显式调用 disconnect()，这里只做同步关闭尝试
        if self.session and not self.session.closed:
            try:
                import warnings
                warnings.warn(
                    f"ActiveSyncClient for {self.account.email} was not properly disconnected. "
                    "Call disconnect() explicitly.",
                    ResourceWarning,
                    stacklevel=2,
                )
            except Exception:
                pass


class MockActiveSyncClient(ActiveSyncClient):
    """用于测试的Mock ActiveSync客户端"""

    async def connect(self) -> bool:
        """模拟连接成功"""
        print(f"Mock ActiveSync连接: {self.account.email}")
        self.session = None  # 模拟会话
        return True

    async def folder_sync(self) -> List[Dict[str, Any]]:
        """模拟文件夹同步"""
        return [
            {"id": "inbox", "name": "收件箱", "type": "inbox"},
            {"id": "sent", "name": "已发送邮件", "type": "sent"},
            {"id": "drafts", "name": "草稿", "type": "drafts"},
            {"id": "trash", "name": "已删除邮件", "type": "trash"},
        ]

    async def email_sync(
        self, folder_id: str, sync_key: str = "", limit: int = 100
    ) -> Dict[str, Any]:
        """模拟邮件同步"""
        from datetime import datetime, timedelta

        # 生成模拟邮件
        emails = []
        for i in range(min(10, limit)):
            email = {
                "id": f"email_{i}",
                "subject": f"测试邮件 {i + 1}",
                "from": f"sender{i}@example.com",
                "to": [self.account.email],
                "date": (datetime.now() - timedelta(hours=i)).isoformat(),
                "read": i % 2 == 0,
                "flagged": i % 3 == 0,
                "has_attachment": i % 4 == 0,
            }
            emails.append(email)

        return {
            "sync_key": "mock_sync_key",
            "emails": emails,
        }
