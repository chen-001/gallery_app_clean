"""
装饰器工具
"""
from functools import wraps
from flask import session, request, redirect, url_for, jsonify
import logging

logger = logging.getLogger(__name__)

def login_required(f):
    """登录验证装饰器（已禁用 - 直接通过）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 跳过所有认证检查，直接执行函数
        return f(*args, **kwargs)
    
    return decorated_function

def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        from backend.services.auth_service import AuthService
        
        auth_service = AuthService()
        current_user = auth_service.get_current_user()
        
        # 这里可以添加管理员权限检查逻辑
        # 目前简化处理，所有登录用户都有权限
        
        return f(*args, **kwargs)
    
    return decorated_function

def rate_limit(max_requests=100, window=3600):
    """简单的速率限制装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 这里可以实现速率限制逻辑
            # 目前只是占位符
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def json_required(f):
    """JSON请求验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({
                'success': False,
                'message': '请求必须是JSON格式'
            }), 400
        return f(*args, **kwargs)
    return decorated_function