"""
缓存工具
"""
import time
import functools
import hashlib
import json
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

class SimpleCache:
    """简单的内存缓存类"""
    
    def __init__(self, default_timeout: int = 300):
        self.cache = {}
        self.default_timeout = default_timeout
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key in self.cache:
            value, expires_at = self.cache[key]
            if time.time() < expires_at:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> None:
        """设置缓存值"""
        if timeout is None:
            timeout = self.default_timeout
        
        expires_at = time.time() + timeout
        self.cache[key] = (value, expires_at)
    
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
    
    def cleanup(self) -> int:
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expires_at) in self.cache.items()
            if current_time >= expires_at
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)

# 全局缓存实例
_cache = SimpleCache()

def get_cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    # 将参数转换为可序列化的字符串
    key_data = {
        'args': args,
        'kwargs': kwargs
    }
    
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()

def cached_result(timeout: int = 300, key_prefix: str = ''):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}{func.__name__}_{get_cache_key(*args, **kwargs)}"
            
            # 尝试从缓存获取
            cached_value = _cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"缓存命中: {cache_key}")
                return cached_value
            
            # 执行函数并缓存结果
            try:
                result = func(*args, **kwargs)
                _cache.set(cache_key, result, timeout)
                logger.debug(f"缓存设置: {cache_key}")
                return result
            except Exception as e:
                logger.error(f"函数执行失败，跳过缓存: {func.__name__} - {e}")
                raise
        
        # 添加缓存操作方法
        wrapper.cache_clear = lambda: _cache.clear()
        wrapper.cache_info = lambda: {'size': _cache.size()}
        
        return wrapper
    
    return decorator

def cache_get(key: str) -> Optional[Any]:
    """获取缓存值"""
    return _cache.get(key)

def cache_set(key: str, value: Any, timeout: int = 300) -> None:
    """设置缓存值"""
    _cache.set(key, value, timeout)

def cache_delete(key: str) -> bool:
    """删除缓存值"""
    return _cache.delete(key)

def cache_clear() -> None:
    """清空所有缓存"""
    _cache.clear()

def cache_cleanup() -> int:
    """清理过期缓存"""
    return _cache.cleanup()

def cache_info() -> Dict[str, Any]:
    """获取缓存信息"""
    return {
        'size': _cache.size(),
        'default_timeout': _cache.default_timeout
    }

class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self.caches = {}
    
    def get_cache(self, name: str, default_timeout: int = 300) -> SimpleCache:
        """获取指定名称的缓存实例"""
        if name not in self.caches:
            self.caches[name] = SimpleCache(default_timeout)
        return self.caches[name]
    
    def clear_all(self) -> None:
        """清空所有缓存"""
        for cache in self.caches.values():
            cache.clear()
    
    def cleanup_all(self) -> Dict[str, int]:
        """清理所有缓存"""
        result = {}
        for name, cache in self.caches.items():
            result[name] = cache.cleanup()
        return result
    
    def info(self) -> Dict[str, Dict[str, Any]]:
        """获取所有缓存信息"""
        return {
            name: {
                'size': cache.size(),
                'default_timeout': cache.default_timeout
            }
            for name, cache in self.caches.items()
        }

# 全局缓存管理器
cache_manager = CacheManager()

def get_named_cache(name: str, default_timeout: int = 300) -> SimpleCache:
    """获取命名缓存"""
    return cache_manager.get_cache(name, default_timeout)