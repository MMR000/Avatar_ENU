from flask import Blueprint, request, jsonify, current_app
from utils.nlp import parse_text
from utils.classify import classify_sentence_structure
from utils.tts import synthesize_speech
from utils.paths import PathManager
import datetime
import os

# 定义 Blueprint
text_processing_bp = Blueprint('text_processing', __name__)

@text_processing_bp.route('/process_text', methods=['POST'])
def process_text():
    try:
        # 获取输入数据
        data = request.get_json()
        text = data.get('text', '').strip()

        # 检查输入是否为空
        if not text:
            return jsonify({'status': 'error', 'message': 'Text input cannot be empty.'}), 400

        # 解析文本为句子
        sentences, stanza_outputs = parse_text(text)

        # 初始化路径管理器
        path_manager = PathManager(current_app)
        audio_files = []

        # 遍历每个句子，生成语音文件
        for index, sentence in enumerate(sentences):
            # 定义文件路径
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{timestamp}_{index}.wav"
            filepath = path_manager.get_audio_path(filename)

            # 合成语音
            synthesize_speech(sentence, filepath)

            # 检查文件是否生成成功
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Audio file {filepath} was not created.")

            # 保存音频文件路径
            audio_files.append(f"/static/audio/{filename}")

        # 返回 JSON 响应
        return jsonify({
            'status': 'success',
            'stanza_outputs': stanza_outputs,
            'audio_files': audio_files
        })

    except Exception as e:
        # 捕获并返回错误信息
        print(f"Error processing text: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
