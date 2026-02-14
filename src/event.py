from pathlib import Path


class Event:
    """事件基类"""
    
    def __init__(self, event_type: str, data: dict):
        self.event_type = event_type
        self.message_type = ''
        self.data = data
    
    @property
    def user_id(self) -> int:
        """发送者QQ号"""
        return self.data.get('user_id', 0)
    
    @property
    def group_id(self) -> int:
        """群号"""
        return self.data.get('group_id', 0)
    
    @property
    def message(self) -> str:
        """消息内容"""
        return self.data.get('message', '')
    
    @property
    def raw_message(self) -> str:
        """原始消息"""
        return self.data.get('raw_message', '')
    
    @property
    def message_id(self) -> int:
        """消息ID"""
        return self.data.get('message_id', 0)
    
    @property
    def sender(self) -> dict:
        """发送者信息"""
        return self.data.get('sender', {})
    
    @property
    def sender_role(self) -> str:
        """发送者群身份"""
        return self.sender.get('role', 'member')


class MessageEvent(Event):
    """消息事件"""
    
    def __init__(self, data: dict):
        super().__init__('message', data)
        self.message_type = data.get('message_type', '')
    
    @property
    def is_private(self) -> bool:
        """是否是私聊消息"""
        return self.message_type == 'private'
    
    @property
    def is_group(self) -> bool:
        """是否是群消息"""
        return self.message_type == 'group'


class GroupMessageEvent(MessageEvent):
    """群消息事件"""
    
    def __init__(self, data: dict):
        super().__init__(data)
        self.message_type = 'group'


class PrivateMessageEvent(MessageEvent):
    """私聊消息事件"""
    
    def __init__(self, data: dict):
        super().__init__(data)
        self.message_type = 'private'


class NoticeEvent(Event):
    """通知事件"""
    
    def __init__(self, data: dict):
        super().__init__('notice', data)
        self.notice_type = data.get('notice_type', '')


class RequestEvent(Event):
    """请求事件"""
    
    def __init__(self, data: dict):
        super().__init__('request', data)
        self.request_type = data.get('request_type', '')


class MetaEvent(Event):
    """元事件"""
    
    def __init__(self, data: dict):
        super().__init__('meta_event', data)
        self.meta_event_type = data.get('meta_event_type', '')


def parse_event(data: dict) -> Event:
    post_type = data.get('post_type', '')
    
    if post_type == 'message':
        message_type = data.get('message_type', '')
        if message_type == 'group':
            return GroupMessageEvent(data)
        elif message_type == 'private':
            return PrivateMessageEvent(data)
        else:
            return MessageEvent(data)
    elif post_type == 'message_sent':
        message_type = data.get('message_type', '')
        if message_type == 'group':
            return GroupMessageEvent(data)
        elif message_type == 'private':
            return PrivateMessageEvent(data)
        else:
            return MessageEvent(data)
    elif post_type == 'notice':
        return NoticeEvent(data)
    elif post_type == 'request':
        return RequestEvent(data)
    elif post_type == 'meta_event':
        return MetaEvent(data)
    else:
        return Event('unknown', data)
