"""
进度监控服务层
处理任务进度监控相关的业务逻辑
"""
import uuid
import time
import threading
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ProgressService:
    """进度监控服务类"""
    
    def __init__(self):
        self.tasks = {}  # 存储所有任务
        self.subscribers = {}  # 订阅者映射
        self.lock = threading.RLock()  # 线程锁
        
        # 启动清理线程
        self._start_cleanup_thread()
    
    def create_task(self, name: str, description: str = '', total_steps: int = 100) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())
        
        with self.lock:
            self.tasks[task_id] = {
                'id': task_id,
                'name': name,
                'description': description,
                'status': TaskStatus.PENDING.value,
                'progress': 0,
                'total_steps': total_steps,
                'current_step': 0,
                'message': '',
                'error': None,
                'result': None,
                'created_at': datetime.now().isoformat(),
                'started_at': None,
                'completed_at': None,
                'updated_at': datetime.now().isoformat()
            }
        
        logger.info(f"创建任务: {task_id} - {name}")
        return task_id
    
    def start_task(self, task_id: str):
        """开始任务"""
        with self.lock:
            if task_id not in self.tasks:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            task['status'] = TaskStatus.RUNNING.value
            task['started_at'] = datetime.now().isoformat()
            task['updated_at'] = datetime.now().isoformat()
        
        self._notify_subscribers(task_id)
        logger.info(f"开始任务: {task_id}")
        return True
    
    def update_task_progress(self, task_id: str, current_step: int = None, 
                           progress: int = None, message: str = ''):
        """更新任务进度"""
        with self.lock:
            if task_id not in self.tasks:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            
            if task['status'] not in [TaskStatus.RUNNING.value, TaskStatus.PENDING.value]:
                logger.warning(f"任务状态不允许更新: {task_id} - {task['status']}")
                return False
            
            if current_step is not None:
                task['current_step'] = current_step
                # 根据步骤计算进度
                if task['total_steps'] > 0:
                    task['progress'] = min(100, int((current_step / task['total_steps']) * 100))
            
            if progress is not None:
                task['progress'] = min(100, max(0, progress))
            
            if message:
                task['message'] = message
            
            task['updated_at'] = datetime.now().isoformat()
        
        self._notify_subscribers(task_id)
        return True
    
    def complete_task(self, task_id: str, result: Any = None, message: str = '完成'):
        """完成任务"""
        with self.lock:
            if task_id not in self.tasks:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            task['status'] = TaskStatus.COMPLETED.value
            task['progress'] = 100
            task['message'] = message
            task['result'] = result
            task['completed_at'] = datetime.now().isoformat()
            task['updated_at'] = datetime.now().isoformat()
        
        self._notify_subscribers(task_id)
        logger.info(f"任务完成: {task_id}")
        return True
    
    def fail_task(self, task_id: str, error: str, message: str = '失败'):
        """任务失败"""
        with self.lock:
            if task_id not in self.tasks:
                logger.error(f"任务不存在: {task_id}")
                return False
            
            task = self.tasks[task_id]
            task['status'] = TaskStatus.FAILED.value
            task['message'] = message
            task['error'] = error
            task['completed_at'] = datetime.now().isoformat()
            task['updated_at'] = datetime.now().isoformat()
        
        self._notify_subscribers(task_id)
        logger.error(f"任务失败: {task_id} - {error}")
        return True
    
    def cancel_task(self, task_id: str) -> Dict:
        """取消任务"""
        try:
            with self.lock:
                if task_id not in self.tasks:
                    return {'success': False, 'message': '任务不存在'}
                
                task = self.tasks[task_id]
                
                if task['status'] in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]:
                    return {'success': False, 'message': '任务已结束，无法取消'}
                
                task['status'] = TaskStatus.CANCELLED.value
                task['message'] = '已取消'
                task['completed_at'] = datetime.now().isoformat()
                task['updated_at'] = datetime.now().isoformat()
            
            self._notify_subscribers(task_id)
            logger.info(f"任务已取消: {task_id}")
            return {'success': True, 'message': '任务已取消'}
            
        except Exception as e:
            logger.error(f"取消任务失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        with self.lock:
            return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        with self.lock:
            return list(self.tasks.values())
    
    def get_active_tasks(self) -> List[Dict]:
        """获取活跃任务"""
        with self.lock:
            return [
                task for task in self.tasks.values() 
                if task['status'] in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]
            ]
    
    def clear_completed_tasks(self) -> Dict:
        """清除已完成的任务"""
        try:
            cleared_count = 0
            
            with self.lock:
                completed_tasks = [
                    task_id for task_id, task in self.tasks.items()
                    if task['status'] in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value]
                ]
                
                for task_id in completed_tasks:
                    del self.tasks[task_id]
                    # 清除订阅
                    if task_id in self.subscribers:
                        del self.subscribers[task_id]
                    cleared_count += 1
            
            logger.info(f"清除了 {cleared_count} 个已完成的任务")
            return {'success': True, 'cleared_count': cleared_count}
            
        except Exception as e:
            logger.error(f"清除任务失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def subscribe_task(self, task_id: str, client_id: str):
        """订阅任务进度"""
        with self.lock:
            if task_id not in self.subscribers:
                self.subscribers[task_id] = set()
            self.subscribers[task_id].add(client_id)
        
        logger.debug(f"客户端 {client_id} 订阅任务 {task_id}")
    
    def unsubscribe_task(self, task_id: str, client_id: str):
        """取消订阅任务进度"""
        with self.lock:
            if task_id in self.subscribers:
                self.subscribers[task_id].discard(client_id)
                if not self.subscribers[task_id]:
                    del self.subscribers[task_id]
        
        logger.debug(f"客户端 {client_id} 取消订阅任务 {task_id}")
    
    def _notify_subscribers(self, task_id: str):
        """通知订阅者"""
        try:
            # 这里应该通过WebSocket发送更新
            # 由于需要访问SocketIO实例，这里只记录日志
            with self.lock:
                if task_id in self.subscribers and self.subscribers[task_id]:
                    logger.debug(f"通知任务更新: {task_id} - {len(self.subscribers[task_id])} 个订阅者")
                    
                    # 实际的WebSocket通知应该在API层处理
                    # 这里可以触发一个事件或调用回调
                    
        except Exception as e:
            logger.error(f"通知订阅者失败: {e}")
    
    def _start_cleanup_thread(self):
        """启动清理线程"""
        def cleanup_worker():
            while True:
                try:
                    # 每小时清理一次过期任务
                    time.sleep(3600)
                    self._cleanup_old_tasks()
                except Exception as e:
                    logger.error(f"清理线程异常: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("启动任务清理线程")
    
    def _cleanup_old_tasks(self):
        """清理旧任务"""
        try:
            current_time = time.time()
            cleanup_threshold = 24 * 3600  # 24小时
            
            with self.lock:
                old_tasks = []
                for task_id, task in self.tasks.items():
                    try:
                        task_time = datetime.fromisoformat(task['updated_at']).timestamp()
                        if current_time - task_time > cleanup_threshold:
                            old_tasks.append(task_id)
                    except Exception as e:
                        logger.warning(f"解析任务时间失败 {task_id}: {e}")
                
                for task_id in old_tasks:
                    del self.tasks[task_id]
                    if task_id in self.subscribers:
                        del self.subscribers[task_id]
            
            if old_tasks:
                logger.info(f"清理了 {len(old_tasks)} 个过期任务")
                
        except Exception as e:
            logger.error(f"清理旧任务失败: {e}")

# 全局进度服务实例
progress_service = ProgressService()