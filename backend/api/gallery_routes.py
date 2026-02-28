"""
Gallery API 路由
"""
from flask import Blueprint, render_template, jsonify, request, send_file, abort
from backend.services.gallery_service import GalleryService
from backend.services.auth_service import AuthService
from backend.utils.decorators import login_required
import os
import json
from datetime import datetime

gallery_bp = Blueprint('gallery', __name__)
gallery_service = GalleryService()
auth_service = AuthService()

@gallery_bp.route('/')
@login_required
def folder_list():
    """文件夹列表页面"""
    try:
        folders = gallery_service.get_folder_list()
        return render_template('folder_list.html', 
                             folders=folders, 
                             folder_count=len(folders))
    except Exception as e:
        return render_template('error.html', 
                             title='加载失败',
                             message=f'无法加载文件夹列表: {str(e)}'), 500


@gallery_bp.route('/api/folders')
@login_required
def api_folders():
    """API: 获取文件夹列表"""
    try:
        folders = gallery_service.get_folder_list()
        return jsonify({
            'success': True,
            'data': folders,
            'count': len(folders)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/folder/<path:folder_name>')
@login_required
def subfolder_list(folder_name):
    """子文件夹列表页面"""
    try:
        folder_info = gallery_service.get_folder_info(folder_name)
        if not folder_info:
            abort(404)
        
        subfolders = gallery_service.get_subfolder_list(folder_name)
        return render_template('subfolder_list.html',
                             folder_name=folder_name,
                             folder_info=folder_info,
                             subfolders=subfolders)
    except Exception as e:
        return render_template('error.html',
                             title='加载失败',
                             message=f'无法加载子文件夹: {str(e)}'), 500

@gallery_bp.route('/api/folder/<path:folder_name>/subfolders')
@login_required
def api_subfolders(folder_name):
    """API: 获取子文件夹列表"""
    try:
        subfolders = gallery_service.get_subfolder_list(folder_name)
        return jsonify({
            'success': True,
            'data': subfolders,
            'count': len(subfolders)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/images/<path:folder_name>')
@login_required
def gallery_page(folder_name):
    """图片画廊页面"""
    try:
        folder_info = gallery_service.get_folder_info(folder_name)
        if not folder_info:
            abort(404)
        
        # 获取排序参数，首次访问默认收益率排序
        sort_by = request.args.get('sort', 'neu_ret')
        # 首次加载只显示前20张图片，支持懒加载
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 检查是否是父文件夹（含有子文件夹）
        if folder_info.get('has_subfolders', False) and sort_by == 'neu_ret':
            # 如果是父文件夹且使用收益率排序，使用跨子文件夹收益率排序
            images = gallery_service.get_images_cross_folders_by_return(folder_name, page=page, per_page=per_page)
        else:
            # 否则使用原有的单文件夹排序
            images = gallery_service.get_image_list(folder_name, page=page, per_page=per_page, sort_by=sort_by)
        
        return render_template('gallery.html',
                             folder_name=folder_name,
                             folder_info=folder_info,
                             images=images)
    except Exception as e:
        return render_template('error.html',
                             title='加载失败',
                             message=f'无法加载图片画廊: {str(e)}'), 500

@gallery_bp.route('/api/folder/<path:folder_name>/images')
@login_required
def api_images(folder_name):
    """API: 获取图片列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        sort_by = request.args.get('sort', 'neu_ret')
        
        # 检查是否是父文件夹（含有子文件夹）
        folder_info = gallery_service.get_folder_info(folder_name)
        if folder_info and folder_info.get('has_subfolders', False) and sort_by == 'neu_ret':
            # 如果是父文件夹且使用收益率排序，使用跨子文件夹收益率排序
            images = gallery_service.get_images_cross_folders_by_return(folder_name, page, per_page)
        else:
            # 否则使用原有的单文件夹排序
            images = gallery_service.get_image_list(folder_name, page, per_page, sort_by)
        
        return jsonify({
            'success': True,
            'data': images,
            'page': page,
            'per_page': per_page
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/serve/<path:file_path>')
@login_required
def serve_file(file_path):
    """提供文件服务"""
    try:
        full_path = gallery_service.get_file_path(file_path)
        if not full_path or not os.path.exists(full_path):
            abort(404)
        
        return send_file(full_path)
    except Exception as e:
        abort(500)

@gallery_bp.route('/viewer/<path:file_path>')
@login_required
def file_viewer(file_path):
    """文件查看器页面"""
    try:
        full_path = gallery_service.get_file_path(file_path)
        if not full_path or not os.path.exists(full_path):
            abort(404)
        
        file_info = gallery_service.get_file_info(file_path)
        return render_template('viewer.html',
                             file_path=file_path,
                             file_info=file_info)
    except Exception as e:
        return render_template('error.html',
                             title='加载失败',
                             message=f'无法加载文件查看器: {str(e)}'), 500

@gallery_bp.route('/api/search')
@login_required
def api_search():
    """API: 搜索功能"""
    try:
        query = request.args.get('q', '').strip()
        folder = request.args.get('folder', '')
        file_type = request.args.get('type', 'all')
        
        if not query:
            return jsonify({
                'success': False,
                'message': '搜索关键词不能为空'
            }), 400
        
        results = gallery_service.search_files(query, folder, file_type)
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results),
            'query': query
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/search-in-folder/<path:folder_name>')
@login_required
def api_search_in_folder(folder_name):
    """API: 在指定文件夹中搜索图片（支持分页）"""
    try:
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        if not query:
            return jsonify({
                'success': False,
                'message': '搜索关键词不能为空'
            }), 400
        
        results = gallery_service.search_images_in_folder(folder_name, query, page, per_page)
        return jsonify({
            'success': True,
            'data': results,
            'query': query,
            'folder': folder_name
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/folder/<path:folder_name>/delete', methods=['POST'])
@login_required
def api_delete_files(folder_name):
    """API: 删除文件"""
    try:
        data = request.get_json()
        file_paths = data.get('files', [])
        
        if not file_paths:
            return jsonify({
                'success': False,
                'message': '没有选择要删除的文件'
            }), 400
        
        result = gallery_service.delete_files(folder_name, file_paths)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/backup/query')
@login_required
def api_backup_query():
    """API: 备份查询"""
    try:
        query = request.args.get('q', '').strip()
        results = gallery_service.query_backup_files(query)
        
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/description/<path:folder_name>/<filename>', methods=['GET'])
@login_required
def api_get_description(folder_name, filename):
    """API: 获取图片描述"""
    try:
        description = gallery_service.get_image_description(folder_name, filename)
        return jsonify({
            'success': True,
            'description': description
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/description/<path:folder_name>/<filename>', methods=['POST'])
@login_required
def api_set_description(folder_name, filename):
    """API: 设置图片描述"""
    try:
        data = request.get_json()
        description = data.get('description', '')
        success = gallery_service.set_image_description(folder_name, filename, description)
        if success:
            # 发送WebSocket通知，实时更新所有客户端
            emit_description_update(folder_name, filename, description)
            return jsonify({
                'success': True,
                'message': '描述已保存'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存失败'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/described-images/<path:folder_name>')
@login_required 
def api_described_images(folder_name):
    """API: 获取有描述的图片列表（包括子文件夹）"""
    try:
        # 获取当前文件夹的有描述图片
        images = gallery_service.get_described_images(folder_name)
        
        # 获取所有子文件夹的有描述图片
        subfolders = gallery_service.get_subfolder_list(folder_name)
        for subfolder in subfolders:
            subfolder_path = f"{folder_name}/{subfolder['name']}"
            subfolder_images = gallery_service.get_described_images(subfolder_path)
            
            # 为每个图片添加文件夹信息
            for img in subfolder_images:
                img['folder'] = subfolder['name']
                
            images.extend(subfolder_images)
        
        # 对所有图片按收益率进行全局排序
        images.sort(key=lambda x: x.get('neu_ret', 0), reverse=True)
        
        return jsonify({
            'success': True,
            'data': images
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/folder-description/<path:folder_name>', methods=['POST'])
@login_required
def api_set_folder_description(folder_name):
    """API: 设置文件夹描述"""
    try:
        data = request.get_json()
        description = data.get('description', '')
        success = gallery_service.set_folder_description(folder_name, description)
        if success:
            # 发送WebSocket通知，实时更新所有客户端
            emit_folder_description_update(folder_name, description)
            return jsonify({
                'success': True,
                'message': '文件夹描述已保存'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存失败'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/search-in-subfolders/<path:parent_folder>')
@login_required
def api_search_in_subfolders(parent_folder):
    """API: 在子文件夹中搜索图片（支持分页）"""
    try:
        query = request.args.get('q', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        if not query:
            return jsonify({
                'success': False,
                'message': '搜索关键词不能为空'
            }), 400
        
        results = gallery_service.search_images_in_subfolders(parent_folder, query, page, per_page)
        return jsonify({
            'success': True,
            'data': results,
            'query': query,
            'parent_folder': parent_folder
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/unique-image-names/<path:parent_folder>')
@login_required
def api_unique_image_names(parent_folder):
    """API: 获取父文件夹下所有子文件夹中的去重图片名称"""
    try:
        image_names = gallery_service.get_unique_image_names_in_subfolders(parent_folder)
        return jsonify({
            'success': True,
            'data': image_names,
            'count': len(image_names),
            'parent_folder': parent_folder
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/find-images-by-name/<path:parent_folder>')
@login_required
def api_find_images_by_name(parent_folder):
    """API: 根据图片名称在所有子文件夹中查找匹配的图片"""
    try:
        image_name = request.args.get('name', '').strip()
        
        if not image_name:
            return jsonify({
                'success': False,
                'message': '图片名称不能为空'
            }), 400
        
        results = gallery_service.find_images_by_name_in_subfolders(parent_folder, image_name)
        return jsonify({
            'success': True,
            'data': results,
            'count': len(results),
            'image_name': image_name,
            'parent_folder': parent_folder
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/images-cross-folders-by-return/<path:parent_folder>')
@login_required
def api_images_cross_folders_by_return(parent_folder):
    """API: 跨子文件夹按收益率排序获取图片列表"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)  # 跨文件夹查询默认更多图片
        
        result = gallery_service.get_images_cross_folders_by_return(parent_folder, page, per_page)
        return jsonify({
            'success': True,
            'data': result,
            'parent_folder': parent_folder
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@gallery_bp.route('/api/search-in-selected-subfolders/<path:parent_folder>')
@login_required
def api_search_in_selected_subfolders(parent_folder):
    """API: 在选中的子文件夹中搜索图片（支持分页）"""
    try:
        query = request.args.get('q', '').strip()
        subfolders_param = request.args.get('subfolders', '').strip()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        if not query:
            return jsonify({
                'success': False,
                'message': '搜索关键词不能为空'
            }), 400
        
        if not subfolders_param:
            return jsonify({
                'success': False,
                'message': '没有选择子文件夹'
            }), 400
        
        # 解析选中的子文件夹
        selected_subfolders = [name.strip() for name in subfolders_param.split(',') if name.strip()]
        
        if not selected_subfolders:
            return jsonify({
                'success': False,
                'message': '没有有效的子文件夹选择'
            }), 400
        
        results = gallery_service.search_images_in_selected_subfolders(parent_folder, query, selected_subfolders, page, per_page)
        return jsonify({
            'success': True,
            'data': results,
            'query': query,
            'parent_folder': parent_folder,
            'selected_subfolders': selected_subfolders
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@gallery_bp.route('/api/upload-pasted-image/<path:folder_name>', methods=['POST'])
@login_required
def api_upload_pasted_image(folder_name):
    """API: 上传粘贴的图片"""
    try:
        folder_path = gallery_service.images_root / folder_name
        if not folder_path.exists() or not folder_path.is_dir():
            return jsonify({
                'success': False,
                'message': '文件夹不存在'
            }), 404
        
        # 检查是否有文件数据
        if 'image' not in request.files:
            # 检查base64数据
            data = request.get_json()
            if data and 'image_data' in data:
                # 处理base64格式图片
                import base64
                import re
                image_data = data['image_data']
                
                # 解析base64数据
                match = re.match(r'^data:image/(\w+);base64,(.+)$', image_data)
                if not match:
                    return jsonify({
                        'success': False,
                        'message': '无效的图片格式'
                    }), 400
                
                ext = match.group(1)
                base64_content = match.group(2)
                
                # 确定文件名
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
                filename = f"pasted_image_{timestamp}.{ext}"
                
                # 保存图片
                image_path = folder_path / filename
                with open(image_path, 'wb') as f:
                    f.write(base64.b64decode(base64_content))
                
                return jsonify({
                    'success': True,
                    'filename': filename,
                    'url': f"/gallery/serve/{folder_name}/{filename}",
                    'markdown': f"![{filename}]({filename})"
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '没有收到图片数据'
                }), 400
        
        # 处理文件上传
        file = request.files['image']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '文件名为空'
            }), 400
        
        # 生成安全的文件名
        from werkzeug.utils import secure_filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        original_filename = secure_filename(file.filename)
        filename = f"pasted_{timestamp}_{original_filename}"
        
        # 保存图片
        image_path = folder_path / filename
        file.save(image_path)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'url': f"/gallery/serve/{folder_name}/{filename}",
            'markdown': f"![{filename}]({filename})"
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# WebSocket 通知函数
def emit_description_update(folder_name, filename, description):
    """发送描述更新通知到所有客户端"""
    from backend.app import socketio
    try:
        socketio.emit('description_updated', {
            'folder_name': folder_name,
            'filename': filename,
            'description': description
        }, broadcast=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'发送描述更新通知失败: {e}')


def emit_folder_description_update(folder_name, description):
    """发送文件夹描述更新通知到所有客户端"""
    from backend.app import socketio
    try:
        socketio.emit('folder_description_updated', {
            'folder_name': folder_name,
            'description': description
        }, broadcast=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'发送文件夹描述更新通知失败: {e}')


# ========== 因子相关性分析 API ==========

@gallery_bp.route('/api/correlation/calculate', methods=['POST'])
@login_required
def api_calculate_correlation():
    """API: 计算因子相关性矩阵"""
    from backend.utils.correlation_utils import calculate_correlation_matrix
    import uuid
    
    try:
        data = request.get_json()
        factor_names = data.get('factor_names', [])
        factor_version = data.get('factor_version', '')
        
        if not factor_names or len(factor_names) < 2:
            return jsonify({
                'success': False,
                'message': '至少需要选择2个因子'
            }), 400
        
        if not factor_version:
            return jsonify({
                'success': False,
                'message': '缺少因子版本参数'
            }), 400
        
        result = calculate_correlation_matrix(factor_version, factor_names)
        
        if result['success']:
            # 生成记录ID和时间戳
            from datetime import datetime
            result['id'] = str(uuid.uuid4())[:8]
            result['timestamp'] = datetime.now().isoformat()
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@gallery_bp.route('/api/correlation/history', methods=['GET'])
@login_required
def api_get_correlation_history():
    """API: 获取相关性分析历史记录"""
    from backend.utils.correlation_utils import get_correlation_history
    
    try:
        history = get_correlation_history()
        return jsonify({
            'success': True,
            'data': history
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@gallery_bp.route('/api/correlation/history/save', methods=['POST'])
@login_required
def api_save_correlation_history():
    """API: 保存相关性分析结果到历史"""
    from backend.utils.correlation_utils import save_correlation_history
    import uuid
    from datetime import datetime
    
    try:
        data = request.get_json()
        
        # 生成记录ID和时间戳
        record = {
            'id': data.get('id', str(uuid.uuid4())[:8]),
            'timestamp': datetime.now().isoformat(),
            'factor_version': data.get('factor_version'),
            'factor_names': data.get('factor_names', []),
            'correlation_matrix': data.get('correlation_matrix', [])
        }
        
        success = save_correlation_history(record)
        
        if success:
            return jsonify({
                'success': True,
                'message': '保存成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '保存失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@gallery_bp.route('/api/correlation/history/<record_id>', methods=['DELETE'])
@login_required
def api_delete_correlation_history(record_id):
    """API: 删除历史记录"""
    from backend.utils.correlation_utils import delete_correlation_history
    
    try:
        success = delete_correlation_history(record_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '记录不存在'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
