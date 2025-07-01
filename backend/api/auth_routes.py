"""
认证 API 路由
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from backend.services.auth_service import AuthService
import logging

auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()
logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面和处理"""
    if request.method == 'GET':
        # 检查是否已经登录
        if auth_service.is_logged_in():
            next_url = request.args.get('next', '/gallery')
            return redirect(next_url)
        
        # 获取认证配置
        auth_config = auth_service.get_auth_config()
        
        # 检查自动认证
        auto_auth_result = auth_service.check_auto_auth(request)
        if auto_auth_result['success']:
            next_url = request.args.get('next', '/gallery')
            return redirect(next_url)
        
        # 显示登录页面
        return render_template('login.html',
                             title='用户登录',
                             next_url=request.args.get('next', '/gallery'),
                             is_manual_logout=session.get('manual_logout', False),
                             manual_logout_user=session.get('manual_logout_user', ''),
                             show_allowed_users=auth_config.get('show_allowed_users', False),
                             allowed_users=list(auth_config.get('users', {}).keys()))
    
    elif request.method == 'POST':
        # 处理登录请求
        try:
            username = request.form.get('username', '').strip()
            next_url = request.form.get('next', '/gallery')
            
            if not username:
                return jsonify({
                    'success': False,
                    'message': '用户名不能为空'
                }), 400
            
            # 验证用户
            auth_result = auth_service.authenticate_user(username, request)
            
            if auth_result['success']:
                # 清除手动登出状态
                session.pop('manual_logout', None)
                session.pop('manual_logout_user', None)
                
                return jsonify({
                    'success': True,
                    'message': '登录成功',
                    'redirect_url': next_url
                })
            else:
                return jsonify({
                    'success': False,
                    'message': auth_result.get('message', '登录失败')
                }), 401
                
        except Exception as e:
            logger.error(f"登录处理异常: {e}")
            return jsonify({
                'success': False,
                'message': '登录过程中发生错误'
            }), 500

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """登出"""
    try:
        current_user = session.get('username', '')
        
        # 执行登出
        auth_service.logout_user()
        
        # 设置手动登出标记
        session['manual_logout'] = True
        session['manual_logout_user'] = current_user
        
        if request.method == 'POST':
            return jsonify({
                'success': True,
                'message': '已成功登出'
            })
        else:
            return redirect(url_for('auth.login'))
            
    except Exception as e:
        logger.error(f"登出处理异常: {e}")
        return jsonify({
            'success': False,
            'message': '登出过程中发生错误'
        }), 500

@auth_bp.route('/clear_logout_status', methods=['POST'])
def clear_logout_status():
    """清除登出状态"""
    try:
        session.pop('manual_logout', None)
        session.pop('manual_logout_user', None)
        
        return jsonify({
            'success': True,
            'message': '登出状态已清除'
        })
    except Exception as e:
        logger.error(f"清除登出状态异常: {e}")
        return jsonify({
            'success': False,
            'message': '清除状态时发生错误'
        }), 500

@auth_bp.route('/status')
def auth_status():
    """获取认证状态"""
    try:
        is_logged_in = auth_service.is_logged_in()
        current_user = session.get('username', '') if is_logged_in else None
        
        return jsonify({
            'success': True,
            'is_logged_in': is_logged_in,
            'username': current_user,
            'is_manual_logout': session.get('manual_logout', False)
        })
    except Exception as e:
        logger.error(f"获取认证状态异常: {e}")
        return jsonify({
            'success': False,
            'message': '获取认证状态失败'
        }), 500

@auth_bp.route('/config')
def auth_config():
    """获取认证配置信息（公开信息）"""
    try:
        config = auth_service.get_auth_config()
        
        # 只返回公开信息
        public_config = {
            'auth_methods': config.get('auth_methods', []),
            'show_allowed_users': config.get('show_allowed_users', False),
            'allowed_users': list(config.get('users', {}).keys()) if config.get('show_allowed_users') else []
        }
        
        return jsonify({
            'success': True,
            'data': public_config
        })
    except Exception as e:
        logger.error(f"获取认证配置异常: {e}")
        return jsonify({
            'success': False,
            'message': '获取配置失败'
        }), 500