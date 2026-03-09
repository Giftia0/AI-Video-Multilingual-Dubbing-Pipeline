# coding: utf-8
"""
Step 2: 使用 faster-whisper 进行中文语音识别（ASR）
输出带时间戳的句段列表
"""
import json
import os
import config


def transcribe(audio_path: str, output_dir: str) -> list[dict]:
    """
    对音频进行语音识别，返回带时间戳的句段列表

    Args:
        audio_path: 输入音频路径 (.wav)
        output_dir: 输出目录（保存 JSON）

    Returns:
        句段列表，每个元素:
        {
            "id": int,
            "start": float,   # 开始时间（秒）
            "end": float,     # 结束时间（秒）
            "text": str       # 识别文本
        }
    """
    os.makedirs(output_dir, exist_ok=True)
    audio_name = os.path.splitext(os.path.basename(audio_path))[0]
    json_path = os.path.join(output_dir, f"{audio_name}_transcription.json")

    # 如果已有结果，直接加载
    if os.path.exists(json_path) and not config.FORCE_RERUN:
        print(f"  [跳过] 转写结果已存在: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    from faster_whisper import WhisperModel

    print(f"  加载 Whisper 模型: {config.WHISPER_MODEL_SIZE} ({config.WHISPER_DEVICE})")
    model = WhisperModel(
        config.WHISPER_MODEL_SIZE,
        device=config.WHISPER_DEVICE,
        compute_type=config.WHISPER_COMPUTE_TYPE,
    )

    print(f"  开始转写: {audio_path}")
    segments_gen, info = model.transcribe(
        audio_path,
        language=config.WHISPER_LANGUAGE,
        beam_size=config.WHISPER_BEAM_SIZE,
        vad_filter=True,          # VAD 过滤静音
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    print(f"  检测语言: {info.language} (概率: {info.language_probability:.2f})")
    print(f"  音频时长: {info.duration:.1f}s")

    segments = []
    for seg in segments_gen:
        segments.append({
            "id": seg.id,
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        })
        print(f"    [{seg.start:.1f}s - {seg.end:.1f}s] {seg.text.strip()}")

    # 保存结果
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)

    print(f"  ✓ 转写完成: {len(segments)} 个句段 → {json_path}")
    return segments


if __name__ == "__main__":
    # 测试
    test_audio = os.path.join(config.OUTPUT_DIR, "_test",
                              os.path.splitext(config.VIDEOS[0])[0] + ".wav")
    if os.path.exists(test_audio):
        result = transcribe(test_audio, os.path.join(config.OUTPUT_DIR, "_test"))
        print(f"\n共 {len(result)} 个句段")
    else:
        print(f"测试音频不存在: {test_audio}")
        print("请先运行 audio_extractor.py")
