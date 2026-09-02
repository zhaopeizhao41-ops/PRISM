"""
PRISM Backend - Flask应用工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request, send_from_directory
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('prism')

    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process

    if should_log_startup:
        logger.info("=" * 50)
        logger.info("PRISM Backend 启动中...")
        logger.info("=" * 50)

    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 请求日志中间件
    @app.before_request
    def log_request():
        logger = get_logger('prism.request')
        logger.debug(f"请求: {request.method} {request.path}")
        if request.content_type and 'json' in request.content_type:
            logger.debug(f"请求体: {request.get_json(silent=True)}")
    
    @app.after_request
    def log_response(response):
        logger = get_logger('prism.request')
        logger.debug(f"响应: {response.status_code}")
        return response

    # 注册蓝图
    from .api import (
        graph_bp, profile_bp, branch_bp,
        evolution_bp, relationship_bp, roundtable_bp,
    )
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(profile_bp, url_prefix='/api/profile')
    app.register_blueprint(branch_bp, url_prefix='/api/branch')
    app.register_blueprint(evolution_bp, url_prefix='/api/evolution')
    app.register_blueprint(relationship_bp, url_prefix='/api/relationship')
    app.register_blueprint(roundtable_bp, url_prefix='/api/roundtable')
    
    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'PRISM Backend'}

    # 生产模式：托管前端构建产物（SPA fallback）
    # 开发模式下 frontend/dist 不存在，此块不生效，仍由 Vite dev server 提供前端
    dist_dir = os.path.abspath(os.environ.get(
        'PRISM_FRONTEND_DIST',
        os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'dist'),
    ))
    if os.path.isdir(dist_dir):
        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def spa(path):
            # API 与健康检查路由优先匹配；未命中时才走静态托管
            if path.startswith(('api/', 'health')):
                return {'error': 'not found'}, 404
            if path and os.path.isfile(os.path.join(dist_dir, path)):
                return send_from_directory(dist_dir, path)
            # SPA 路由（如 /workbench/p1）统一回退到 index.html
            return send_from_directory(dist_dir, 'index.html')

        logger.info(f"生产模式：托管前端构建产物 {dist_dir}")

    if should_log_startup:
        logger.info("PRISM Backend 启动完成")
    
    return app

