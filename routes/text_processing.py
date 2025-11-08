from flask import Blueprint, request, jsonify, current_app
from utils.nlp import parse_text
from utils.classify import classify_sentence_structure
from utils.tts import synthesize_speech
from utils.paths import PathManager
import datetime
import os

# define Blueprint
text_processing_bp = Blueprint('text_processing', __name__)

@text_processing_bp.route('/process_text', methods=['POST'])
def process_text():
    try:
        # get input
        data = request.get_json()
        text = data.get('text', '').strip()

        # check input null
        if not text:
            return jsonify({'status': 'error', 'message': 'Text input cannot be empty.'}), 400

        # Parse the text into sentences
        sentences, stanza_outputs = parse_text(text)

        # Initialize the path manager
        path_manager = PathManager(current_app)
        audio_files = []

        # Iterate through each sentence to generate an audio file.
        for index, sentence in enumerate(sentences):
            # Define file path
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{index}.wav"
            filepath = path_manager.get_audio_path(filename)

            # Synthetic speech
            synthesize_speech(sentence, filepath)

            # Check if the file was generated successfully.
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Audio file {filepath} was not created.")

            # Path to save audio files
            audio_files.append(f"/static/audio/{filename}")

        # Returns a JSON response
        return jsonify({
            'status': 'success',
            'stanza_outputs': stanza_outputs,
            'audio_files': audio_files
        })

    except Exception as e:
        # Capture and return error information
        print(f"Error processing text: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
