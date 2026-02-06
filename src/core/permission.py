from typing import Set, Optional
from enum import Enum


class PermissionLevel(Enum):
    """权限级别"""
    BOT_ADMIN = 0
    GROUP_OWNER = 1
    GROUP_ADMIN = 2
    MEMBER = 3


class PermissionManager:
    """权限管理器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.admin_qqs: Set[int] = set(config.get('admins', []))
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
    
    def remove_admin(self, qq: int):
        """移除BOT管理员"""
        self.admin_qqs.discard(qq)
    
    def has_permission(self, qq: int, permission: str, group_id: Optional[int] = None, group_role: Optional[str] = None) -> bool:
        """检查是否具有特定权限"""
        level = self.check_permission(qq, group_id, group_role)
        
        if level == PermissionLevel.BOT_ADMIN:
            return True
        
        if level in [PermissionLevel.GROUP_OWNER, PermissionLevel.GROUP_ADMIN]:
            return permission in self.group_admin_permissions
        
        return False
