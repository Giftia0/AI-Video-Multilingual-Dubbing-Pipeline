# coding: utf-8
"""
集中配置：路径、模型参数、目标语言等
"""
import os

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

# 输入视频目录
VIDEO_DIR = os.path.join(PROJECT_ROOT, "project-video-audio-CN-EN-FR")

# 视频文件列表
VIDEOS = [
    "github-workflow-a.mp4",
    "github-workflow-b.mp4",
    "github-workflow-c.mp4",
]

# 输出根目录
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# ==================== ASR 配置 (faster-whisper) ====================
WHISPER_MODEL_SIZE = os.path.join(BASE_DIR, "whisper")   # 指向本地下载的模型目录
WHISPER_DEVICE = "cuda"           # "cuda" 或 "cpu"
WHISPER_COMPUTE_TYPE = "float16"  # cuda: float16/int8_float16; cpu: int8/float32
WHISPER_LANGUAGE = "zh"           # 源语言
WHISPER_BEAM_SIZE = 5

# ==================== Speaker Diarization (pyannote) ====================
HF_TOKEN = os.environ.get("HF_TOKEN", "")
# pyannote 会自动下载模型到 ~/.cache/huggingface

# ==================== Ollama 翻译配置 ====================
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gpt-oss:120b-cloud"
OLLAMA_TIMEOUT = 120              # 单次请求超时（秒）
OLLAMA_TEMPERATURE = 0.3          # 翻译用低温度保证准确性

# ==================== TTS 配置 (edge-tts) ====================
# edge-tts 语音选择: https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4
TTS_VOICES = {
    "en": "en-US-AndrewMultilingualNeural",   # 英文男声（多语言）
    "fr": "fr-FR-HenriNeural",                # 法文男声
}
TTS_VOICES_FEMALE = {
    "en": "en-US-AvaMultilingualNeural",       # 英文女声（多语言）
    "fr": "fr-FR-DeniseNeural",               # 法文女声
}
TTS_RATE = "+0%"  # 语速调整，如 "+10%", "-5%"

# 每个视频的实际说话人数（传给 pyannote 约束输出）
# key = 视频文件名（不含扩展名），value = 说话人数
VIDEO_NUM_SPEAKERS = {
    "github-workflow-a": 2,
    "github-workflow-b": 2,
    "github-workflow-c": 2,
}

# 说话人性别映射（用于语音克隆时选择男/女声基础 TTS）
SPEAKER_GENDER = {
    "SPEAKER_00": "male",    # 主讲人（男）
    "SPEAKER_01": "female",  # 孙蝴蝶同学（女）
}

# ==================== 目标语言 ====================
TARGET_LANGUAGES = ["en", "fr"]

LANGUAGE_NAMES = {
    "zh": "中文",
    "en": "English",
    "fr": "Français",
}

# ==================== FFmpeg ====================
FFMPEG_PATH = "ffmpeg"  # 如果不在 PATH 中，改为完整路径

# ==================== 运行控制 ====================
FORCE_RERUN = False  # 由 main.py --force 设置，跳过所有缓存
