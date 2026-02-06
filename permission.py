from typing import Set, Optional
from enum import Enum

from src.utils.db import Database


class PermissionLevel(Enum):
    """权限级别"""
    BOT_ADMIN = 0
    GROUP_OWNER = 1
    GROUP_ADMIN = 2
    MEMBER = 3


class PermissionManager:
    """权限管理器"""
    
    def __init__(self, config: dict, db: Optional[Database] = None):
        self.config = config
        self.db = db or Database()
        # 优先从数据库读取管理员列表，如果数据库为空则退回配置文件中的 admins
        db_admins = set(self.db.list_admins())
        config_admins = set(config.get('admins', []))
        self.admin_qqs: Set[int] = db_admins or config_admins

        # 如果数据库中还没有管理员，但配置文件里有，则写入一次
        if not db_admins and config_admins:
            for qq in config_admins:
                self.db.add_admin(qq)

        self.enable_group_permission = config.get('enable_group_permission', True)
        self.group_admin_permissions = config.get('group_admin_permissions', [])
    
    def check_permission(self, qq: int, group_id: Optional[int] = None, group_role: Optional[str] = None) -> PermissionLevel:
        """检查权限"""
        if qq in self.admin_qqs:
            return PermissionLevel.BOT_ADMIN
        
        if group_id and group_role:
            if group_role == 'owner':
                return PermissionLevel.GROUP_OWNER
            elif group_role == 'admin':
                return PermissionLevel.GROUP_ADMIN
        
        return PermissionLevel.MEMBER
    
    def is_admin(self, qq: int) -> bool:
        """是否是BOT管理员"""
        return qq in self.admin_qqs
    
    def is_group_admin(self, group_role: Optional[str] = None) -> bool:
        """是否是群管理员（包括群主）"""
        if not self.enable_group_permission or not group_role:
            return False
        return group_role in ['owner', 'admin']
    
    def is_group_owner(self, group_role: Optional[str] = None) -> bool:
        """是否是群主"""
        if not group_role:
            return False
        return group_role == 'owner'
    
    def add_admin(self, qq: int):
        """添加BOT管理员"""
        self.admin_qqs.add(qq)
        if self.db:
            self.db.add_admin(qq)
    
    def remove_admin(self, qq: int):
        """移除BOT管理员"""
        self.admin_qqs.discard(qq)
        if self.db:
            self.db.remove_admin(qq)
    
    def has_permission(self, qq: int, permission: str, group_id: Optional[int] = None, group_role: Optional[str] = None) -> bool:
        """检查是否具有特定权限"""
        level = self.check_permission(qq, group_id, group_role)
        
        if level == PermissionLevel.BOT_ADMIN:
            return True
        
        if level in [PermissionLevel.GROUP_OWNER, PermissionLevel.GROUP_ADMIN]:
            return permission in self.group_admin_permissions
        
        return False
