"""
认证服务层
处理用户认证相关的业务逻辑
"""
import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List
from flask import session, request

# 临时设置配置文件路径
import os
from pathlib import Path
AUTH_CONFIG_FILE = Path(__file__).parent.parent.parent / "config" / "gallery_config.json"

logger = logging.getLogger(__name__)

class AuthService:
    """认证服务类"""
    
    def __init__(self):
        self.config_file = Path(AUTH_CONFIG_FILE)
        self._config_cache = None
        self._config_mtime = 0
    
    def get_auth_config(self) -> Dict:
        """获取认证配置"""
        try:
            # 检查配置文件是否有更新
            if self.config_file.exists():
                current_mtime = self.config_file.stat().st_mtime
                if current_mtime > self._config_mtime:
                    self._load_config()
                    self._config_mtime = current_mtime
            else:
                # 如果配置文件不存在，使用默认配置
                self._config_cache = self._get_default_config()
            
            return self._config_cache or {}
            
        except Exception as e:
            logger.error(f"获取认证配置失败: {e}")
            return self._get_default_config()
    
    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
        except Exception as e:
            logger.error(f"加载认证配置文件失败: {e}")
            self._config_cache = self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            "auth_methods": ["manual"],
            "manual_auth": {
                "enabled": True,
                "auto_login": False
            },
            "header_auth": {
                "enabled": True,
                "headers": ["X-Remote-User", "X-Forwarded-User"]
            },
            "ip_auth": {
                "enabled": False,
                "ip_users": {}
            },
            "users": {
                "admin": "admin123",
                "user": "user123"
            },
            "show_allowed_users": False,
            "session_timeout": 3600
        }
    
    def is_logged_in(self) -> bool:
        """检查用户是否已登录"""
        return session.get('authenticated', False) and session.get('username') is not None
    
    def get_current_user(self) -> Optional[str]:
        """获取当前登录用户"""
        if self.is_logged_in():
            return session.get('username')
        return None
    
    def check_auto_auth(self, request_obj) -> Dict:
        """检查自动认证"""
        try:
            config = self.get_auth_config()
            
            # 检查是否有手动登出标记
            if session.get('manual_logout', False):
                return {'success': False, 'message': '用户已手动登出'}
            
            # 检查header认证
            if config.get('header_auth', {}).get('enabled', False):
                header_result = self._check_header_auth(request_obj, config)
                if header_result['success']:
                    return header_result
            
            # 检查IP认证
            if config.get('ip_auth', {}).get('enabled', False):
                ip_result = self._check_ip_auth(request_obj, config)
                if ip_result['success']:
                    return ip_result
            
            # 检查是否启用了自动登录
            if config.get('manual_auth', {}).get('auto_login', False):
                # 如果只有一个用户，自动登录
                users = config.get('users', {})
                if len(users) == 1:
                    username = list(users.keys())[0]
                    self._set_user_session(username)
                    return {'success': True, 'username': username, 'method': 'auto'}
            
            return {'success': False, 'message': '无自动认证方式'}
            
        except Exception as e:
            logger.error(f"自动认证检查失败: {e}")
            return {'success': False, 'message': '认证检查失败'}
    
    def _check_header_auth(self, request_obj, config: Dict) -> Dict:
        """检查header认证"""
        try:
            headers = config.get('header_auth', {}).get('headers', [])
            users = config.get('users', {})
            
            for header_name in headers:
                header_value = request_obj.headers.get(header_name)
                if header_value and header_value in users:
                    self._set_user_session(header_value)
                    return {
                        'success': True, 
                        'username': header_value, 
                        'method': 'header',
                        'header': header_name
                    }
            
            return {'success': False, 'message': '无有效的header认证'}
            
        except Exception as e:
            logger.error(f"Header认证失败: {e}")
            return {'success': False, 'message': 'Header认证失败'}
    
    def _check_ip_auth(self, request_obj, config: Dict) -> Dict:
        """检查IP认证"""
        try:
            client_ip = self._get_client_ip(request_obj)
            ip_users = config.get('ip_auth', {}).get('ip_users', {})
            
            if client_ip in ip_users:
                username = ip_users[client_ip]
                self._set_user_session(username)
                return {
                    'success': True, 
                    'username': username, 
                    'method': 'ip',
                    'ip': client_ip
                }
            
            return {'success': False, 'message': 'IP未授权'}
            
        except Exception as e:
            logger.error(f"IP认证失败: {e}")
            return {'success': False, 'message': 'IP认证失败'}
    
    def _get_client_ip(self, request_obj) -> str:
        """获取客户端IP"""
        # 检查代理头
        if request_obj.headers.get('X-Forwarded-For'):
            return request_obj.headers.get('X-Forwarded-For').split(',')[0].strip()
        elif request_obj.headers.get('X-Real-IP'):
            return request_obj.headers.get('X-Real-IP')
        else:
            return request_obj.remote_addr
    
    def authenticate_user(self, username: str, request_obj) -> Dict:
        """认证用户"""
        try:
            config = self.get_auth_config()
            users = config.get('users', {})
            
            if username not in users:
                return {'success': False, 'message': '用户不存在'}
            
            # 对于手动认证，这里可以添加密码验证逻辑
            # 目前简化处理，直接验证用户名存在即可
            
            self._set_user_session(username)
            
            logger.info(f"用户登录成功: {username}")
            return {
                'success': True, 
                'username': username, 
                'method': 'manual'
            }
            
        except Exception as e:
            logger.error(f"用户认证失败: {e}")
            return {'success': False, 'message': '认证过程中发生错误'}
    
    def _set_user_session(self, username: str):
        """设置用户会话"""
        session['authenticated'] = True
        session['username'] = username
        session['login_time'] = int(time.time())
        session.permanent = True
        
        # 清除登出标记
        session.pop('manual_logout', None)
        session.pop('manual_logout_user', None)
    
    def logout_user(self):
        """用户登出"""
        try:
            username = session.get('username', '')
            
            # 清除会话
            session.clear()
            
            logger.info(f"用户登出: {username}")
            
        except Exception as e:
            logger.error(f"用户登出失败: {e}")
    
    def check_session_timeout(self) -> bool:
        """检查会话超时"""
        try:
            if not self.is_logged_in():
                return True
            
            config = self.get_auth_config()
            timeout = config.get('session_timeout', 3600)
            
            login_time = session.get('login_time', 0)
            if login_time and (time.time() - login_time) > timeout:
                self.logout_user()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"会话超时检查失败: {e}")
            return True
    
    def get_user_list(self) -> List[str]:
        """获取用户列表"""
        try:
            config = self.get_auth_config()
            return list(config.get('users', {}).keys())
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return []
    
    def is_user_authorized(self, username: str) -> bool:
        """检查用户是否有权限"""
        try:
            config = self.get_auth_config()
            users = config.get('users', {})
            return username in users
        except Exception as e:
            logger.error(f"检查用户权限失败: {e}")
            return False

# 导入time模块
import time