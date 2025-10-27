from flask import Blueprint, request, jsonify, current_app
import os
import subprocess
import datetime

# 定义 Blueprint
video_generation_bp = Blueprint('video_generation', __name__)

@video_generation_bp.route('/generate_video', methods=['POST'])
def generate_video():
    try:
        # 获取前端发送的数据
        data = request.get_json()
        audio_file = data.get('audio_file')
        classification = data.get('classification')

        # 校验数据
        if not audio_file or classification is None:
            return jsonify({'status': 'error', 'message': 'Missing audio_file or classification.'}), 400

        # 确定模板路径 (使用绝对路径)
        template_folder = os.path.abspath(current_app.config['TEMPLATE_FOLDER'])
        template_filename = f"{classification}_sentence.mp4" if classification != "Unknown" else "1_sentence.mp4"
        template_path = os.path.join(template_folder, template_filename)

        if not os.path.exists(template_path):
            return jsonify({'status': 'error', 'message': f"Missing video template: {template_filename}"}), 400

        # 定义输出文件路径 (使用绝对路径)
        video_output_folder = os.path.abspath(current_app.config['VIDEO_OUTPUT_FOLDER'])
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        output_filename = f"{timestamp}_output.mp4"
        output_path = os.path.join(video_output_folder, output_filename)

        # 修正音频路径 (使用绝对路径)
        upload_folder = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
        audio_full_path = os.path.join(upload_folder, os.path.basename(audio_file))

        # 强制使用 new_wav2lip 目录作为工作目录
        wav2lip_dir = "./wav2lip"

        # 构建命令
        command = [
            "python",
            os.path.join(wav2lip_dir, "inference.py"),
            "--checkpoint_path", os.path.join(wav2lip_dir, "checkpoints/wav2lip_gan.pth"),
            # "--segmentation_path", os.path.join(wav2lip_dir, "checkpoints/face_segmentation.pth"),
            # "--enhance_face", "gfpgan",
            "--face", template_path,
            "--audio", audio_full_path,
            "--outfile", output_path,
        ]

        print(f"Running command: {' '.join(command)}")  # Debug 日志

        # 设置环境变量，强制使用 GPU
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "0"  # 选择 GPU 0

        # 执行命令
        process = subprocess.run(
            command,
            cwd=wav2lip_dir,  # 设置工作目录
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # 检查返回状态码
        if process.returncode == 0:
            # 成功生成视频
            video_url = f"/static/video_output/{output_filename}"
            print(f"Returning video URL: {video_url}")  # Debug 日志
            return jsonify({'status': 'success', 'video_url': video_url})
        else:
            # 视频生成失败
            error_message = f"Video generation failed. STDERR: {process.stderr.decode('utf-8')}"
            print(error_message)  # Debug 日志
            return jsonify({'status': 'error', 'message': 'Video processing failed.'}), 500

    except Exception as e:
        # 捕获异常并打印日志
        error_message = f"Error generating video: {e}"
        print(error_message)  # Debug 日志
        return jsonify({'status': 'error', 'message': str(e)}), 500
