"""
进度监控 API 路由
"""
from flask import Blueprint, render_template, jsonify, request
from flask_socketio import emit, disconnect
from backend.services.progress_service import ProgressService
from backend.utils.decorators import login_required
import logging

progress_bp = Blueprint('progress', __name__)
progress_service = ProgressService()
logger = logging.getLogger(__name__)

@progress_bp.route('/')
@login_required
def progress_monitor():
    """进度监控页面"""
    try:
        active_tasks = progress_service.get_active_tasks()
        return render_template('progress.html',
                             active_tasks=active_tasks)
    except Exception as e:
        return render_template('error.html',
                             title='加载失败',
                             message=f'无法加载进度监控: {str(e)}'), 500

@progress_bp.route('/api/tasks')
@login_required
def api_tasks():
    """API: 获取任务列表"""
    try:
        tasks = progress_service.get_all_tasks()
        return jsonify({
            'success': True,
            'data': tasks,
            'count': len(tasks)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@progress_bp.route('/api/tasks/<task_id>')
@login_required
def api_task_detail(task_id):
    """API: 获取任务详情"""
    try:
        task = progress_service.get_task(task_id)
        if not task:
            return jsonify({
                'success': False,
                'message': '任务不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': task
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@progress_bp.route('/api/tasks/<task_id>/cancel', methods=['POST'])
@login_required
def api_cancel_task(task_id):
    """API: 取消任务"""
    try:
        result = progress_service.cancel_task(task_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@progress_bp.route('/api/tasks/clear', methods=['POST'])
@login_required
def api_clear_tasks():
    """API: 清除已完成的任务"""
    try:
        result = progress_service.clear_completed_tasks()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# WebSocket 事件处理
def init_socketio_events(socketio):
    """初始化 SocketIO 事件"""
    
    @socketio.on('connect')
    def handle_connect():
        """客户端连接"""
        logger.info('客户端连接到进度监控')
        emit('connected', {'message': '连接成功'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """客户端断开连接"""
        logger.info('客户端断开连接')
    
    @socketio.on('subscribe_task')
    def handle_subscribe_task(data):
        """订阅任务进度"""
        task_id = data.get('task_id')
        if task_id:
            progress_service.subscribe_task(task_id, request.sid)
            emit('subscribed', {'task_id': task_id})
    
    @socketio.on('unsubscribe_task')
    def handle_unsubscribe_task(data):
        """取消订阅任务进度"""
        task_id = data.get('task_id')
        if task_id:
            progress_service.unsubscribe_task(task_id, request.sid)
            emit('unsubscribed', {'task_id': task_id})
    
    @socketio.on('get_task_status')
    def handle_get_task_status(data):
        """获取任务状态"""
        task_id = data.get('task_id')
        if task_id:
            task = progress_service.get_task(task_id)
            emit('task_status', {
                'task_id': task_id,
                'task': task
            })

def emit_task_progress(task_id, progress_data):
    """发送任务进度更新"""
    from app import socketio
    socketio.emit('task_progress', {
        'task_id': task_id,
        'progress': progress_data
    }, room=f'task_{task_id}')

def emit_task_completed(task_id, result):
    """发送任务完成通知"""
    from app import socketio
    socketio.emit('task_completed', {
        'task_id': task_id,
        'result': result
    }, room=f'task_{task_id}')

def emit_task_failed(task_id, error):
    """发送任务失败通知"""
    from app import socketio
    socketio.emit('task_failed', {
        'task_id': task_id,
        'error': error
    }, room=f'task_{task_id}')