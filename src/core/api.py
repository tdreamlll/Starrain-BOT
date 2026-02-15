import os
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.utils.logger import get_logger

def _get_logger():
    return get_logger()


class NapCatAPI:
    """NapCat API封装"""
    
    def __init__(self, http_adapter):
        self.adapter = http_adapter
        self.logger = _get_logger()
    
    async def call(self, action: str, params: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        if params is None:
            params = {}
        return await self.adapter.call_api(action, params)


class AccountAPI(NapCatAPI):
    """账号相关API"""
    
    async def get_login_info(self) -> Optional[Dict[str, Any]]:
        return await self.call('get_login_info')
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        return await self.call('get_status')
    
    async def get_version_info(self) -> Optional[Dict[str, Any]]:
        return await self.call('get_version_info')
    
    async def bot_exit(self) -> bool:
        result = await self.call('bot_exit')
        return result is not None
    
    async def mark_all_as_read(self) -> bool:
        result = await self.call('_mark_all_as_read')
        return result is not None
    
    async def clean_cache(self) -> bool:
        result = await self.call('clean_cache')
        return result is not None
    
    async def set_self_longnick(self, long_nick: str) -> bool:
        result = await self.call('set_self_longnick', {'longNick': long_nick})
        return result is not None
    
    async def set_input_status(self, user_id: int, event_type: int) -> bool:
        result = await self.call('set_input_status', {'user_id': user_id, 'event_type': event_type})
        return result is not None
    
    async def set_qq_profile(self, nickname: str = None, company: str = None,
                           email: str = None, college: str = None,
                           personal_note: str = None) -> bool:
        params = {}
        if nickname is not None:
            params['nickname'] = nickname
        if company is not None:
            params['company'] = company
        if email is not None:
            params['email'] = email
        if college is not None:
            params['college'] = college
        if personal_note is not None:
            params['personal_note'] = personal_note
        result = await self.call('set_qq_profile', params)
        return result is not None
    
    async def get_clientkey(self) -> Optional[str]:
        result = await self.call('get_clientkey')
        return result.get('key') if result else None
    
    async def set_diy_online_status(self, face_id: int, face_type: int,
                                   wording: str = '') -> bool:
        params = {'face_id': str(face_id), 'face_type': str(face_type), 'wording': wording}
        result = await self.call('set_diy_online_status', params)
        return result is not None
    
    async def set_online_status(self, status: int) -> bool:
        result = await self.call('set_online_status', {'status': status})
        return result is not None
    
    async def set_qq_avatar(self, file: str, cache: int = 0) -> bool:
        result = await self.call('set_qq_avatar', {'file': file, 'cache': str(cache)})
        return result is not None
    
    async def can_send_image(self) -> bool:
        result = await self.call('can_send_image')
        return result.get('yes', False) if result else False
    
    async def can_send_record(self) -> bool:
        result = await self.call('can_send_record')
        return result.get('yes', False) if result else False


class FriendAPI(NapCatAPI):
    """好友相关API"""
    
    async def get_friend_list(self, no_cache: bool = False) -> Optional[List[Dict]]:
        return await self.call('get_friend_list', {'no_cache': str(no_cache).lower()})
    
    async def send_private_msg(self, user_id: int, message: str,
                             group_id: int = None) -> Optional[int]:
        params = {'user_id': user_id, 'message': message}
        if group_id is not None:
            params['group_id'] = group_id
        result = await self.call('send_private_msg', params)
        return result.get('message_id') if result else None
    
    async def delete_msg(self, message_id: int) -> bool:
        result = await self.call('delete_msg', {'message_id': message_id})
        return result is not None
    
    async def send_like(self, user_id: int, times: int = 1) -> bool:
        result = await self.call('send_like', {'user_id': user_id, 'times': times})
        return result is not None
    
    async def set_friend_remark(self, user_id: int, remark: str) -> bool:
        result = await self.call('set_friend_remark', {'user_id': user_id, 'remark': remark})
        return result is not None
    
    async def delete_friend(self, user_id: int) -> bool:
        result = await self.call('delete_friend', {'user_id': user_id})
        return result is not None
    
    async def mark_private_msg_as_read(self, user_id: int, time: int = None) -> bool:
        params = {'user_id': user_id}
        if time is not None:
            params['time'] = time
        result = await self.call('mark_private_msg_as_read', params)
        return result is not None
    
    async def get_friend_msg_history(self, user_id: int, count: int = 20) -> Optional[List[Dict]]:
        return await self.call('get_friend_msg_history', {
            'user_id': str(user_id),
            'message_type': 'private',
            'count': str(count)
        })
    
    async def get_unidirectional_friend_list(self) -> Optional[List[Dict]]:
        return await self.call('get_unidirectional_friend_list') or []
    
    async def get_doubt_friends_list(self) -> Optional[List[Dict]]:
        return await self.call('get_doubt_friends_add_request') or []
    
    async def set_doubt_friends_request(self, flag: str, approve: bool) -> bool:
        result = await self.call('set_doubt_friends_add_request', {
            'flag': flag,
            'approve': str(approve).lower()
        })
        return result is not None
    
    async def handle_friend_request(self, flag: str, approve: bool,
                                  remark: str = '') -> bool:
        result = await self.call('set_friend_add_request', {
            'flag': flag,
            'approve': str(approve).lower(),
            'remark': remark
        })
        return result is not None
    
    async def forward_friend_single_msg(self, user_id: int, message_id: str) -> Optional[int]:
        result = await self.call('forward_friend_single_msg', {
            'user_id': str(user_id),
            'message_id': message_id
        })
        return result.get('message_id') if result else None
    
    async def send_private_forward_msg(self, user_id: int, messages: List[Dict]) -> Optional[int]:
        result = await self.call('send_private_forward_msg', {
            'user_id': str(user_id),
            'messages': messages
        })
        return result.get('message_id') if result else None
    
    async def friend_poke(self, user_id: int) -> bool:
        result = await self.call('friend_poke', {'user_id': str(user_id)})
        return result is not None


class GroupAPI(NapCatAPI):
    """群相关API"""
    
    async def get_group_list(self, no_cache: bool = False) -> Optional[List[Dict]]:
        return await self.call('get_group_list', {'no_cache': str(no_cache).lower()})
    
    async def get_group_info(self, group_id: int, no_cache: bool = False) -> Optional[Dict]:
        return await self.call('get_group_info', {
            'group_id': group_id,
            'no_cache': str(no_cache).lower()
        })
    
    async def send_group_msg(self, group_id: int, message: str) -> Optional[int]:
        result = await self.call('send_group_msg', {'group_id': group_id, 'message': message})
        return result.get('message_id') if result else None
    
    async def set_group_kick(self, group_id: int, user_id: int,
                           reject_add_request: bool = False) -> bool:
        result = await self.call('set_group_kick', {
            'group_id': group_id,
            'user_id': user_id,
            'reject_add_request': str(reject_add_request).lower()
        })
        return result is not None
    
    async def set_group_ban(self, group_id: int, user_id: int, duration: int = 1800) -> bool:
        result = await self.call('set_group_ban', {
            'group_id': group_id,
            'user_id': user_id,
            'duration': duration
        })
        return result is not None
    
    async def set_group_whole_ban(self, group_id: int, enable: bool = True) -> bool:
        result = await self.call('set_group_whole_ban', {
            'group_id': group_id,
            'enable': str(enable).lower()
        })
        return result is not None
    
    async def set_group_admin(self, group_id: int, user_id: int, enable: bool = True) -> bool:
        result = await self.call('set_group_admin', {
            'group_id': group_id,
            'user_id': user_id,
            'enable': str(enable).lower()
        })
        return result is not None
    
    async def set_group_card(self, group_id: int, user_id: int, card: str) -> bool:
        result = await self.call('set_group_card', {
            'group_id': group_id,
            'user_id': user_id,
            'card': card
        })
        return result is not None
    
    async def set_group_name(self, group_id: int, group_name: str) -> bool:
        result = await self.call('set_group_name', {
            'group_id': group_id,
            'group_name': group_name
        })
        return result is not None
    
    async def set_group_leave(self, group_id: int, is_dismiss: bool = False) -> bool:
        result = await self.call('set_group_leave', {
            'group_id': group_id,
            'is_dismiss': str(is_dismiss).lower()
        })
        return result is not None
    
    async def get_group_member_info(self, group_id: int, user_id: int,
                                   no_cache: bool = False) -> Optional[Dict]:
        return await self.call('get_group_member_info', {
            'group_id': group_id,
            'user_id': user_id,
            'no_cache': str(no_cache).lower()
        })
    
    async def get_group_member_list(self, group_id: int,
                                    no_cache: bool = False) -> Optional[List[Dict]]:
        return await self.call('get_group_member_list', {
            'group_id': group_id,
            'no_cache': str(no_cache).lower()
        })
    
    async def get_group_honor_info(self, group_id: int, type: str = 'talkative') -> Optional[Dict]:
        return await self.call('get_group_honor_info', {'group_id': group_id, 'type': type})
    
    async def set_essence_msg(self, message_id: int) -> bool:
        result = await self.call('set_essence_msg', {'message_id': message_id})
        return result is not None
    
    async def delete_essence_msg(self, message_id: int) -> bool:
        result = await self.call('delete_essence_msg', {'message_id': message_id})
        return result is not None
    
    async def group_poke(self, group_id: int, user_id: int) -> bool:
        result = await self.call('group_poke', {'group_id': group_id, 'user_id': user_id})
        return result is not None
    
    async def get_group_msg_history(self, group_id: int, count: int = 20) -> Optional[List[Dict]]:
        return await self.call('get_group_msg_history', {
            'group_id': str(group_id),
            'message_type': 'group',
            'count': str(count)
        })
    
    async def mark_group_msg_as_read(self, group_id: int, time: int = None) -> bool:
        params = {'group_id': str(group_id)}
        if time is not None:
            params['time'] = str(time)
        result = await self.call('mark_group_msg_as_read', params)
        return result is not None
    
    async def forward_group_single_msg(self, group_id: int, message_id: str) -> Optional[int]:
        result = await self.call('forward_group_single_msg', {
            'group_id': str(group_id),
            'message_id': message_id
        })
        return result.get('message_id') if result else None
    
    async def send_group_forward_msg(self, group_id: int, messages: List[Dict]) -> Optional[int]:
        result = await self.call('send_group_forward_msg', {
            'group_id': str(group_id),
            'messages': messages
        })
        return result.get('message_id') if result else None
    
    async def send_poke(self, qq_type: str, user_id: int, group_id: int = None) -> bool:
        params = {'user_id': str(user_id)}
        if group_id:
            params['group_id'] = str(group_id)
        result = await self.call('send_poke', params)
        return result is not None
    
    async def set_msg_emoji_like(self, message_id: str, emoji_id: str) -> bool:
        result = await self.call('set_msg_emoji_like', {
            'message_id': message_id,
            'emoji_id': emoji_id
        })
        return result is not None
    
    async def fetch_emoji_like(self, message_id: str) -> Optional[List[Dict]]:
        return await self.call('fetch_emoji_like', {'message_id': message_id})
    
    async def handle_group_request(self, flag: str, approve: bool, reason: str = '') -> bool:
        result = await self.call('set_group_add_request', {
            'flag': flag,
            'approve': str(approve).lower(),
            'reason': reason
        })
        return result is not None
    
    async def get_group_system_msg(self, count: int = 50) -> Optional[Dict]:
        return await self.call('get_group_system_msg', {'count': str(count)})
    
    async def get_group_ignored_notifies(self) -> Optional[Dict]:
        return await self.call('get_group_ignored_notifies', {})
    
    async def get_group_ignore_add_request(self) -> Optional[List[Dict]]:
        return await self.call('get_group_ignore_add_request', {})


class MessageAPI(NapCatAPI):
    """消息相关API"""
    
    async def send_msg(self, message_type: str, user_id: int = None,
                      group_id: int = None, message: str = '') -> Optional[int]:
        params = {'message_type': message_type, 'message': message}
        if user_id is not None:
            params['user_id'] = user_id
        if group_id is not None:
            params['group_id'] = group_id
        result = await self.call('send_msg', params)
        return result.get('message_id') if result else None
    
    async def get_record(self, file: str, out_format: str = 'mp3') -> Optional[str]:
        result = await self.call('get_record', {'file': file, 'out_format': out_format})
        return result.get('file') if result else None
    
    async def get_image(self, file: str) -> Optional[str]:
        result = await self.call('get_image', {'file': file})
        return result.get('file') if result else None
    
    async def get_forward_msg(self, message_id: str) -> Optional[Dict]:
        return await self.call('get_forward_msg', {'message_id': message_id})
    
    async def send_forward_msg(self, messages: List[Dict]) -> Optional[int]:
        result = await self.call('send_forward_msg', {'messages': messages})
        return result.get('message_id') if result else None
    
    async def create_collection(self, collection_data: Dict) -> int:
        result = await self.call('create_collection', collection_data)
        return result or {}
    
    async def get_collection_list(self) -> Optional[List[Dict]]:
        return await self.call('get_collection_list') or []
    
    async def ocr_image(self, image: str) -> Optional[Dict]:
        result = await self.call('ocr_image', {'image': image})
        return result or {}
    
    async def ocr_image_enhanced(self, image: str) -> Optional[Dict]:
        result = await self.call('.ocr_image', {'image': image})
        return result or {}
    
    async def mark_msg_as_read(self, message_type: str, message_id: int, user_id: int = None) -> bool:
        params = {'message_type': message_type, 'message_id': message_id}
        if user_id:
            params['user_id'] = user_id
        result = await self.call('mark_msg_as_read', params)
        return result is not None
    
    async def get_recent_contact(self, count: int = 10) -> Optional[List[Dict]]:
        result = await self.call('get_recent_contact', {'count': str(count)})
        return result.get('data') if result else None


class GroupExtAPI(NapCatAPI):
    """群扩展相关API"""
    
    async def get_group_info_ex(self, group_id: int) -> Optional[Dict]:
        return await self.call('get_group_info_ex', {'group_id': str(group_id)})
    
    async def get_group_detail_info(self, group_id: int) -> Optional[Dict]:
        return await self.call('get_group_detail_info', {'group_id': str(group_id)})
    
    async def set_group_sign(self, group_id: int) -> bool:
        result = await self.call('set_group_sign', {'group_id': str(group_id)})
        return result is not None
    
    async def send_group_sign(self, group_id: int) -> bool:
        result = await self.call('send_group_sign', {'group_id': str(group_id)})
        return result is not None
    
    async def set_group_todo(self, group_id: int, message_id: str = None,
                            message_seq: str = None) -> bool:
        params = {'group_id': str(group_id)}
        if message_id:
            params['message_id'] = message_id
        if message_seq:
            params['message_seq'] = message_seq
        result = await self.call('set_group_todo', params)
        return result is not None
    
    async def set_group_add_option(self, group_id: int, add_type: int,
                                   question: str = None, answer: str = None) -> bool:
        params = {'group_id': str(group_id), 'add_type': add_type}
        if question:
            params['group_question'] = question
        if answer:
            params['group_answer'] = answer
        result = await self.call('set_group_add_option', params)
        return result is not None
    
    async def set_group_robot_add_option(self, group_id: int, add_type: int) -> bool:
        result = await self.call('set_group_robot_add_option', {
            'group_id': str(group_id),
            'add_type': add_type
        })
        return result is not None
    
    async def set_group_search(self, group_id: int, no_code_finger_open: int = None,
                               no_finger_open: int = None) -> bool:
        params = {'group_id': str(group_id)}
        if no_code_finger_open is not None:
            params['no_code_finger_open'] = no_code_finger_open
        if no_finger_open is not None:
            params['no_finger_open'] = no_finger_open
        result = await self.call('set_group_search', params)
        return result is not None
    
    async def set_group_remark(self, group_id: int, remark: str) -> bool:
        result = await self.call('set_group_remark', {
            'group_id': str(group_id),
            'remark': remark
        })
        return result is not None
    
    async def get_qun_album_list(self, group_id: int) -> Optional[List[Dict]]:
        return await self.call('get_qun_album_list', {'group_id': str(group_id)})
    
    async def get_group_album_media_list(self, group_id: int, album_id: str,
                                         attach_info: str = '') -> Optional[Dict]:
        return await self.call('get_group_album_media_list', {
            'group_id': str(group_id),
            'album_id': album_id,
            'attach_info': attach_info
        })
    
    async def upload_image_to_qun_album(self, group_id: int, album_id: str,
                                        album_name: str, file: str) -> bool:
        result = await self.call('upload_image_to_qun_album', {
            'group_id': str(group_id),
            'album_id': album_id,
            'album_name': album_name,
            'file': file
        })
        return result is not None
    
    async def del_group_album_media(self, group_id: int, album_id: str,
                                    media_id: str) -> bool:
        result = await self.call('del_group_album_media', {
            'group_id': str(group_id),
            'album_id': album_id,
            'media_id': media_id
        })
        return result is not None
    
    async def set_group_album_media_like(self, group_id: int, album_id: str,
                                         media_id: str, is_like: bool = True) -> bool:
        result = await self.call('set_group_album_media_like', {
            'group_id': str(group_id),
            'album_id': album_id,
            'media_id': media_id,
            'is_like': str(is_like).lower()
        })
        return result is not None
    
    async def do_group_album_comment(self, group_id: int, album_id: str,
                                     media_id: str, comment: str) -> bool:
        result = await self.call('do_group_album_comment', {
            'group_id': str(group_id),
            'album_id': album_id,
            'media_id': media_id,
            'comment': comment
        })
        return result is not None


class ArkAPI(NapCatAPI):
    """小程序卡片/Ark消息相关API"""
    
    async def get_mini_app_ark(self, type: str = None, title: str = None,
                               desc: str = None, pic_url: str = None,
                               jump_url: str = None, icon_url: str = None,
                               web_url: str = None, app_id: str = None,
                               scene: str = None, template_type: str = None,
                               business_type: str = None, ver_type: str = None,
                               share_type: str = None, version_id: str = None,
                               sdk_id: str = None, with_share_ticket: str = None,
                               raw_ark_data: bool = False, **kwargs) -> Optional[Dict]:
        params = {}
        if type:
            params['type'] = type
        if title:
            params['title'] = title
        if desc:
            params['desc'] = desc
        if pic_url:
            params['picUrl'] = pic_url
        if jump_url:
            params['jumpUrl'] = jump_url
        if icon_url:
            params['iconUrl'] = icon_url
        if web_url:
            params['webUrl'] = web_url
        if app_id:
            params['appId'] = app_id
        if scene:
            params['scene'] = scene
        if template_type:
            params['templateType'] = template_type
        if business_type:
            params['businessType'] = business_type
        if ver_type:
            params['verType'] = ver_type
        if share_type:
            params['shareType'] = share_type
        if version_id:
            params['versionId'] = version_id
        if sdk_id:
            params['sdkId'] = sdk_id
        if with_share_ticket:
            params['withShareTicket'] = with_share_ticket
        if raw_ark_data:
            params['rawArkData'] = str(raw_ark_data).lower()
        params.update(kwargs)
        return await self.call('get_mini_app_ark', params)
    
    async def get_mini_app_ark_bili(self, title: str, desc: str, pic_url: str,
                                    jump_url: str, web_url: str = None) -> Optional[Dict]:
        return await self.get_mini_app_ark(
            type='bili', title=title, desc=desc,
            pic_url=pic_url, jump_url=jump_url, web_url=web_url
        )
    
    async def get_mini_app_ark_weibo(self, title: str, desc: str, pic_url: str,
                                     jump_url: str, web_url: str = None) -> Optional[Dict]:
        return await self.get_mini_app_ark(
            type='weibo', title=title, desc=desc,
            pic_url=pic_url, jump_url=jump_url, web_url=web_url
        )
    
    async def ark_share_group(self, group_id: int) -> Optional[str]:
        result = await self.call('ArkShareGroup', {'group_id': str(group_id)})
        return result
    
    async def ark_share_peer(self, user_id: int = None, group_id: int = None,
                             phone_number: str = '') -> Optional[Dict]:
        params = {'phone_number': phone_number}
        if user_id:
            params['user_id'] = str(user_id)
        if group_id:
            params['group_id'] = str(group_id)
        return await self.call('ArkSharePeer', params)
    
    async def send_group_ark_share(self, group_id: int) -> Optional[str]:
        result = await self.call('send_group_ark_share', {'group_id': str(group_id)})
        return result
    
    async def send_ark_share(self, user_id: int = None, group_id: int = None,
                             phone_number: str = '') -> Optional[Dict]:
        params = {'phone_number': phone_number}
        if user_id:
            params['user_id'] = str(user_id)
        if group_id:
            params['group_id'] = str(group_id)
        return await self.call('send_ark_share', params)
    
    async def click_inline_keyboard_button(self, group_id: int, message_id: str,
                                           button_id: str, callback_data: str = None) -> bool:
        params = {
            'group_id': str(group_id),
            'message_id': message_id,
            'button_id': button_id
        }
        if callback_data:
            params['callback_data'] = callback_data
        result = await self.call('click_inline_keyboard_button', params)
        return result is not None


class FileAPI(NapCatAPI):
    """文件相关API"""
    
    async def upload_group_file(self, group_id: int, file: str, name: str,
                               folder: str = '') -> bool:
        params = {'group_id': group_id, 'file': file, 'name': name}
        if folder:
            params['folder'] = folder
        result = await self.call('upload_group_file', params)
        return result is not None
    
    async def delete_group_file(self, group_id: int, file_id: str, busid: int) -> bool:
        result = await self.call('delete_group_file', {
            'group_id': group_id,
            'file_id': file_id,
            'busid': busid
        })
        return result is not None
    
    async def get_group_file_url(self, group_id: int, file_id: str, busid: int) -> Optional[str]:
        result = await self.call('get_group_file_url', {
            'group_id': group_id,
            'file_id': file_id,
            'busid': busid
        })
        return result.get('url') if result else None
    
    async def delete_group_folder(self, group_id: int, folder_id: str) -> bool:
        result = await self.call('delete_group_folder', {
            'group_id': group_id,
            'folder_id': folder_id
        })
        return result is not None
    
    async def create_group_file_folder(self, group_id: int, parent_id: str,
                                     folder_name: str) -> bool:
        result = await self.call('create_group_file_folder', {
            'group_id': group_id,
            'parent_id': parent_id,
            'name': folder_name
        })
        return result is not None
    
    async def rename_group_file(self, group_id: int, file_id: str, busid: int,
                               new_name: str, parent_folder: str = '/') -> bool:
        result = await self.call('rename_group_file', {
            'group_id': group_id,
            'file_id': file_id,
            'busid': busid,
            'current_parent_directory': parent_folder,
            'new_name': new_name
        })
        return result is not None
    
    async def move_group_file(self, group_id: int, file_id: str, busid: int,
                             target_dir: str) -> bool:
        result = await self.call('move_group_file', {
            'group_id': group_id,
            'file_id': file_id,
            'busid': busid,
            'target_dir': target_dir
        })
        return result is not None
    
    async def upload_private_file(self, user_id: int, file: str, name: str) -> bool:
        result = await self.call('upload_private_file', {
            'user_id': user_id,
            'file': file,
            'name': name
        })
        return result is not None
    
    async def get_private_file_url(self, user_id: int, file_id: str, busid: int) -> Optional[str]:
        result = await self.call('get_private_file_url', {
            'user_id': user_id,
            'file_id': file_id,
            'busid': busid
        })
        return result.get('url') if result else None


class NapCatClient:
    """NapCat 客户端主类"""
    
    def __init__(self, http_adapter):
        self.account = AccountAPI(http_adapter)
        self.friend = FriendAPI(http_adapter)
        self.group = GroupAPI(http_adapter)
        self.group_ext = GroupExtAPI(http_adapter)
        self.ark = ArkAPI(http_adapter)
        self.message = MessageAPI(http_adapter)
        self.file = FileAPI(http_adapter)
    
    @property
    def api(self):
        return self.account
