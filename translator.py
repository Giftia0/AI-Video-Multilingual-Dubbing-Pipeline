# coding: utf-8
"""
Step 3: 使用 Ollama 将中文句段翻译为目标语言（英文/法文）
"""
import json
import os
import requests
import config


def _build_prompt(text: str, target_lang: str) -> str:
    """构建翻译 prompt"""
    lang_name = config.LANGUAGE_NAMES.get(target_lang, target_lang)

    return (
        f"You are a professional translator. Translate the following Chinese text into {lang_name}.\n"
        f"This text is from an instructional video about GitHub workflows.\n"
        f"Rules:\n"
        f"- Translate accurately, preserving technical terms (e.g., pull request, merge, branch, commit).\n"
        f"- Keep the translation natural and fluent.\n"
        f"- Output ONLY the translated text, no explanations.\n"
        f"- If the text contains code or commands, keep them as-is.\n\n"
        f"Chinese: {text}\n"
        f"{lang_name}:"
    )


def translate_segment(text: str, target_lang: str) -> str:
    """
    翻译单个句段

    Args:
        text: 中文文本
        target_lang: 目标语言代码 ("en" / "fr")

    Returns:
        翻译后的文本
    """
    if not text.strip():
        return ""

    prompt = _build_prompt(text, target_lang)

    try:
        resp = requests.post(
            config.OLLAMA_URL,
            json={
                "model": config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": config.OLLAMA_TEMPERATURE},
            },
            timeout=config.OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        translated = resp.json().get("response", "").strip()

        # 简单校验：翻译结果不应为空或过长
        if translated and len(translated) < len(text) * 5:
            return translated
        else:
            print(f"    [警告] 翻译结果异常，保留原文: {text}")
            return text
    except Exception as e:
        print(f"    [错误] 翻译失败: {e}，保留原文")
        return text


def translate_segments(
    segments: list[dict], target_lang: str, output_dir: str
) -> list[dict]:
    """
    批量翻译句段列表

    Args:
        segments: 源语言句段列表 [{"id", "start", "end", "text"}, ...]
        target_lang: 目标语言代码
        output_dir: 输出目录

    Returns:
        翻译后的句段列表（保留时间戳，替换 text）
    """
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"translated_{target_lang}.json")

    # 如果已有结果，直接加载
    if os.path.exists(json_path) and not config.FORCE_RERUN:
        print(f"  [跳过] 翻译结果已存在: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    lang_name = config.LANGUAGE_NAMES.get(target_lang, target_lang)
    print(f"  开始翻译: 中文 → {lang_name} ({len(segments)} 个句段)")

    translated_segments = []
    for i, seg in enumerate(segments):
        translated_text = translate_segment(seg["text"], target_lang)
        translated_segments.append({
            "id": seg["id"],
            "start": seg["start"],
            "end": seg["end"],
            "text": translated_text,
            "original_text": seg["text"],
        })
        print(f"    [{i + 1}/{len(segments)}] {seg['text']} → {translated_text}")

    # 保存结果
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(translated_segments, f, indent=2, ensure_ascii=False)

    print(f"  ✓ 翻译完成 → {json_path}")
    return translated_segments


if __name__ == "__main__":
    # 测试
    test_segments = [
        {"id": 1, "start": 0.0, "end": 3.0, "text": "大家好，今天我们来学习 GitHub 的 Pull Request"},
        {"id": 2, "start": 3.5, "end": 7.0, "text": "首先我们需要创建一个新的分支"},
    ]
    for lang in config.TARGET_LANGUAGES:
        result = translate_segments(
            test_segments, lang, os.path.join(config.OUTPUT_DIR, "_test")
        )
        print(f"\n{lang}: {json.dumps(result, indent=2, ensure_ascii=False)}")
