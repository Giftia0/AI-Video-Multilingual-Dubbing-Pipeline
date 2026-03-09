# coding: utf-8
"""
Step 4: 使用 edge-tts 将翻译后的文本合成为语音
"""
import asyncio
import os
import config


async def _synthesize_one(text: str, voice: str, output_path: str, rate: str = "+0%"):
    """合成单个句段的语音"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_path)


def synthesize_segment(
    text: str, target_lang: str, output_path: str
) -> str:
    """
    合成单个句段语音

    Args:
        text: 要合成的文本
        target_lang: 目标语言代码 ("en" / "fr")
        output_path: 输出 mp3 文件路径

    Returns:
        输出文件路径
    """
    if os.path.exists(output_path) and not config.FORCE_RERUN:
        return output_path

    voice = config.TTS_VOICES.get(target_lang, config.TTS_VOICES["en"])
    asyncio.run(_synthesize_one(text, voice, output_path, config.TTS_RATE))
    return output_path


def synthesize_segments(
    segments: list[dict], target_lang: str, output_dir: str
) -> list[dict]:
    """
    批量合成所有句段语音

    Args:
        segments: 翻译后的句段列表 [{"id", "start", "end", "text"}, ...]
        target_lang: 目标语言代码
        output_dir: TTS 输出目录

    Returns:
        增加了 "audio_path" 字段的句段列表
    """
    tts_dir = os.path.join(output_dir, f"tts_{target_lang}")
    os.makedirs(tts_dir, exist_ok=True)

    lang_name = config.LANGUAGE_NAMES.get(target_lang, target_lang)
    voice = config.TTS_VOICES.get(target_lang, config.TTS_VOICES["en"])
    print(f"  开始语音合成: {lang_name} (voice={voice}, {len(segments)} 个句段)")

    result_segments = []
    for i, seg in enumerate(segments):
        text = seg["text"]
        if not text.strip():
            result_segments.append({**seg, "audio_path": None})
            continue

        audio_path = os.path.join(tts_dir, f"seg_{seg['id']:04d}.mp3")

        if not os.path.exists(audio_path) or config.FORCE_RERUN:
            try:
                synthesize_segment(text, target_lang, audio_path)
                print(f"    [{i + 1}/{len(segments)}] ✓ {text[:40]}...")
            except Exception as e:
                print(f"    [{i + 1}/{len(segments)}] ✗ TTS 失败: {e}")
                result_segments.append({**seg, "audio_path": None})
                continue
        else:
            print(f"    [{i + 1}/{len(segments)}] [跳过] 已存在")

        result_segments.append({**seg, "audio_path": audio_path})

    success_count = sum(1 for s in result_segments if s.get("audio_path"))
    print(f"  ✓ 语音合成完成: {success_count}/{len(segments)} 成功")
    return result_segments


if __name__ == "__main__":
    # 测试
    test_segments = [
        {"id": 1, "start": 0.0, "end": 3.0, "text": "Hello everyone, today we will learn about GitHub Pull Requests"},
        {"id": 2, "start": 3.5, "end": 7.0, "text": "First, we need to create a new branch"},
    ]
    out = os.path.join(config.OUTPUT_DIR, "_test")
    result = synthesize_segments(test_segments, "en", out)
    for seg in result:
        print(f"  {seg['id']}: {seg.get('audio_path')}")
