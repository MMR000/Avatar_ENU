import os
import pandas as pd
from transformers import VitsModel, AutoTokenizer
import torch
import numpy as np
import scipy.io.wavfile

# 加载 TTS 模型
model_path = "facebook/mms-tts-kaz"
speech_model = VitsModel.from_pretrained(model_path, ignore_mismatched_sizes=True).cuda()
tokenizer = AutoTokenizer.from_pretrained(model_path)

# 输入和输出路径
input_txt_dir = "/home/mmr/Videos/ISSAI_KazakhTTS/M1_Iseke/Transcripts"  # 输入文件夹路径
output_dir = "/home/mmr/Desktop/VoiceClass/org/Synthesized"  # 输出文件夹路径
os.makedirs(output_dir, exist_ok=True)


# 合成语音并保存为文件
def synthesize_speech(text, output_path):
    inputs = tokenizer(text, return_tensors="pt").to("cuda")
    with torch.no_grad():
        output = speech_model(**inputs).waveform.squeeze()
    output_int16 = (output.cpu().numpy() * 32767).astype(np.int16)
    scipy.io.wavfile.write(output_path, rate=speech_model.config.sampling_rate, data=output_int16)


# 遍历 txt 文件
print("开始读取并合成语音...")

for filename in os.listdir(input_txt_dir):
    if filename.endswith('.txt'):  # 只处理 .txt 文件
        file_path = os.path.join(input_txt_dir, filename)

        # 使用 UTF-8 编码读取 txt 文件中的文本内容
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read().strip()
        except UnicodeDecodeError as e:
            print(f"无法读取文件 {file_path}: {e}")
            continue

        # 设置输出文件路径，使用 txt 文件名作为 wav 文件名
        output_path = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.wav")

        # 合成语音
        synthesize_speech(text, output_path)
        print(f"生成完成：{output_path}")

print("所有语音生成完成！")
