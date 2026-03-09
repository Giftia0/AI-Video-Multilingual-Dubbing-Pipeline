# coding: utf-8
"""
Step 7: 生成 SRT 字幕文件（原文 / 译文 / 双语）
"""
import os
import config


def _format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(segments: list[dict], output_path: str) -> str:
    """
    生成标准 SRT 字幕文件

    Args:
        segments: 句段列表 [{"id", "start", "end", "text"}, ...]
        output_path: 输出 .srt 文件路径

    Returns:
        输出文件路径
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    lines = []
    for i, seg in enumerate(segments, 1):
        text = seg.get("text", "").strip()
        if not text:
            continue
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")  # 空行分隔

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  ✓ 字幕已生成: {output_path} ({len(segments)} 条)")
    return output_path


def generate_bilingual_srt(
    source_segments: list[dict],
    translated_segments: list[dict],
    output_path: str,
) -> str:
    """
    生成双语字幕文件（上方译文，下方原文）

    Args:
        source_segments: 源语言句段
        translated_segments: 翻译后句段（含 original_text 字段）
        output_path: 输出 .srt 文件路径

    Returns:
        输出文件路径
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    lines = []
    for i, (src, tgt) in enumerate(zip(source_segments, translated_segments), 1):
        src_text = src.get("text", "").strip()
        tgt_text = tgt.get("text", "").strip()
        if not src_text and not tgt_text:
            continue

        start = _format_srt_time(tgt["start"])
        end = _format_srt_time(tgt["end"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        # 译文在上，原文在下
        if tgt_text:
            lines.append(tgt_text)
        if src_text:
            lines.append(src_text)
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  ✓ 双语字幕已生成: {output_path}")
    return output_path


def generate_all_subtitles(
    source_segments: list[dict],
    translated_segments: list[dict],
    target_lang: str,
    output_dir: str,
    video_name: str,
) -> dict:
    """
    生成所有类型的字幕文件

    Returns:
        字幕文件路径字典
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    # 中文字幕
    cn_path = os.path.join(output_dir, f"{video_name}_zh.srt")
    paths["zh"] = generate_srt(source_segments, cn_path)

    # 目标语言字幕
    tgt_path = os.path.join(output_dir, f"{video_name}_{target_lang}.srt")
    paths[target_lang] = generate_srt(translated_segments, tgt_path)

    # 双语字幕
    bi_path = os.path.join(output_dir, f"{video_name}_zh-{target_lang}.srt")
    paths[f"zh-{target_lang}"] = generate_bilingual_srt(
        source_segments, translated_segments, bi_path
    )

    return paths


if __name__ == "__main__":
    # 测试
    test_src = [
        {"id": 1, "start": 0.0, "end": 3.0, "text": "大家好"},
        {"id": 2, "start": 3.5, "end": 7.0, "text": "今天学习 GitHub"},
    ]
    test_tgt = [
        {"id": 1, "start": 0.0, "end": 3.0, "text": "Hello everyone"},
        {"id": 2, "start": 3.5, "end": 7.0, "text": "Today we learn GitHub"},
    ]
    out = os.path.join(config.OUTPUT_DIR, "_test")
    paths = generate_all_subtitles(test_src, test_tgt, "en", out, "test")
    print(f"生成的字幕: {paths}")
