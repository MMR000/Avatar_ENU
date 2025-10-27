import os
from flask import Flask
from routes.home import home_bp
from routes.text_processing import text_processing_bp
from routes.video_generation import video_generation_bp
from utils.paths import PathManager
from celery_app import start_rabbitmq_listener


# 初始化 Flask 应用
app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)

# 配置文件夹路径
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'audio')  # 上传音频文件夹
app.config['VIDEO_OUTPUT_FOLDER'] = os.path.join(app.static_folder, 'video_output')  # 视频输出文件夹
app.config['TEMPLATE_FOLDER'] = os.path.join(app.static_folder, 'video_templates') # 视频模板文件夹

# 初始化路径管理器
path_manager = PathManager(app)
path_manager.ensure_directories()  # 确保必要目录存在

# 注册蓝图（Blueprint）
app.register_blueprint(home_bp)  # 主页蓝图
app.register_blueprint(text_processing_bp)  # 文本处理蓝图
app.register_blueprint(video_generation_bp)  # 视频生成蓝图

# 启动 Flask 服务器
if __name__ == '__main__':
    start_rabbitmq_listener()
    app.run(debug=True, host='0.0.0.0', port=5000)
