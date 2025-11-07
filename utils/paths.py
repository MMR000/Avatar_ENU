import os

class PathManager:
    """path manager"""
    def __init__(self, app):
        self.audio_folder = app.config.get('UPLOAD_FOLDER', './static/audio')
        self.video_output_folder = app.config.get('VIDEO_OUTPUT_FOLDER', './static/video_output')
        self.template_folder = app.config.get('TEMPLATE_FOLDER', './templates')

    def ensure_directories(self):
        """make sure path exist"""
        os.makedirs(self.audio_folder, exist_ok=True)
        os.makedirs(self.video_output_folder, exist_ok=True)

    def get_audio_path(self, filename):
        """get audio path"""
        return os.path.join(self.audio_folder, filename)

    def get_video_output_path(self, filename):
        """get video path"""
        return os.path.join(self.video_output_folder, filename)

    def get_template_path(self, template_filename):
        """get template path"""
        return os.path.join(self.template_folder, template_filename)
