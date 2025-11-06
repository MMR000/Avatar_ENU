import os
from flask import Flask
from routes.home import home_bp
from routes.text_processing import text_processing_bp
from routes.video_generation import video_generation_bp
from utils.paths import PathManager
from celery_app import start_rabbitmq_listener


# Initialize the Flask application
app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)

# Configuration folder path
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'audio')  
app.config['VIDEO_OUTPUT_FOLDER'] = os.path.join(app.static_folder, 'video_output')  
app.config['TEMPLATE_FOLDER'] = os.path.join(app.static_folder, 'video_templates') 

# Initialize the path manager
path_manager = PathManager(app)
path_manager.ensure_directories()

# Register a Blueprint
app.register_blueprint(home_bp)
app.register_blueprint(text_processing_bp)
app.register_blueprint(video_generation_bp)

if __name__ == '__main__':
    start_rabbitmq_listener()
    app.run(debug=True, host='0.0.0.0', port=5000)
