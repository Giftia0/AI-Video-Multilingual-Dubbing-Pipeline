# coding: utf-8
"""
Step 1: 使用 FFmpeg 从视频中提取音频
"""
import os
import subprocess
import config


def extract_audio(video_path: str, output_dir: str) -> str:
    """
    从视频中提取音频为 WAV 格式（16kHz 单声道，适合 Whisper）

    Args:
        video_path: 输入视频路径
        output_dir: 输出目录

    Returns:
        提取的音频文件路径
    """
    os.makedirs(output_dir, exist_ok=True)

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_dir, f"{video_name}.wav")

    if os.path.exists(audio_path) and not config.FORCE_RERUN:
        print(f"  [跳过] 音频已存在: {audio_path}")
        return audio_path

    cmd = [
        config.FFMPEG_PATH,
        "-i", video_path,
        "-vn",                   # 不要视频
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "16000",          # 16kHz 采样率
        "-ac", "1",              # 单声道
        "-y",                    # 覆盖输出
        audio_path,
    ]

    print(f"  提取音频: {video_path}")
    print(f"  命令: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 音频提取失败:\n{result.stderr}")

    file_size = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"  ✓ 音频已提取: {audio_path} ({file_size:.1f} MB)")
    return audio_path


if __name__ == "__main__":
    # 测试：提取第一个视频的音频
    video = os.path.join(config.VIDEO_DIR, config.VIDEOS[0])
    out = os.path.join(config.OUTPUT_DIR, "_test")
    result = extract_audio(video, out)
    print(f"结果: {result}")
