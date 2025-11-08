from flask import Blueprint, request, jsonify, current_app
import os
import subprocess
import datetime

# Define Blueprint
video_generation_bp = Blueprint('video_generation', __name__)

@video_generation_bp.route('/generate_video', methods=['POST'])
def generate_video():
    try:
        # Get data sent by the front end
        data = request.get_json()
        audio_file = data.get('audio_file')
        classification = data.get('classification')

        # Validate data
        if not audio_file or classification is None:
            return jsonify({'status': 'error', 'message': 'Missing audio_file or classification.'}), 400

        # Determine the template path (absolute path).
        template_folder = os.path.abspath(current_app.config['TEMPLATE_FOLDER'])
        template_filename = f"{classification}_sentence.mp4" if classification != "Unknown" else "1_sentence.mp4"
        template_path = os.path.join(template_folder, template_filename)

        if not os.path.exists(template_path):
            return jsonify({'status': 'error', 'message': f"Missing video template: {template_filename}"}), 400

        # Define the output file path (using an absolute path).
        video_output_folder = os.path.abspath(current_app.config['VIDEO_OUTPUT_FOLDER'])
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        output_filename = f"{timestamp}_output.mp4"
        output_path = os.path.join(video_output_folder, output_filename)

        # Correct the audio path (use absolute path).
        upload_folder = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
        audio_full_path = os.path.join(upload_folder, os.path.basename(audio_file))

        wav2lip_dir = "./wav2lip"

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

        print(f"Running command: {' '.join(command)}") 


        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = "0" 

        process = subprocess.run(
            command,
            cwd=wav2lip_dir, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # Check the return status code
        if process.returncode == 0:
            # Video successfully generated
            video_url = f"/static/video_output/{output_filename}"
            print(f"Returning video URL: {video_url}")  
            return jsonify({'status': 'success', 'video_url': video_url})
        else:
            # Video generation failed
            error_message = f"Video generation failed. STDERR: {process.stderr.decode('utf-8')}"
            print(error_message) 
            return jsonify({'status': 'error', 'message': 'Video processing failed.'}), 500

    except Exception as e:
        error_message = f"Error generating video: {e}"
        print(error_message) 
        return jsonify({'status': 'error', 'message': str(e)}), 500
