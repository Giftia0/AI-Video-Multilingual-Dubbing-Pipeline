# coding: utf-8
"""
AI 视频多语言转换流水线 — 主入口

流程:
  1. FFmpeg 提取音频
  2. faster-whisper 语音识别
  3. Ollama 翻译
  4. edge-tts 语音合成
  5. pydub 音频拼接与时间对齐
  6. FFmpeg 替换音轨生成最终视频
  7. 生成 SRT 字幕文件
"""
import argparse
import json
import os
import sys
import time

# 强制标准输出使用 utf-8 编码，防止 Windows 控制台因打印 emoji 报错
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import config
from audio_extractor import extract_audio
from transcriber import transcribe
from translator import translate_segments
from tts_synthesizer import synthesize_segments
from audio_assembler import assemble_audio, get_audio_duration_ms, remap_timestamp
from video_composer import compose_video
from subtitle_generator import generate_all_subtitles


def process_video(video_filename: str, target_lang: str):
    """
    处理单个视频的完整流水线

    Args:
        video_filename: 视频文件名（如 "github-workflow-a.mp4"）
        target_lang: 目标语言代码（"en" / "fr"）
    """
    video_name = os.path.splitext(video_filename)[0]
    video_path = os.path.join(config.VIDEO_DIR, video_filename)
    lang_name = config.LANGUAGE_NAMES.get(target_lang, target_lang)

    # 输出目录
    video_output_dir = os.path.join(config.OUTPUT_DIR, video_name, target_lang)
    os.makedirs(video_output_dir, exist_ok=True)

    print(f"\n{'=' * 60}")
    print(f"  处理视频: {video_filename}")
    print(f"  目标语言: {lang_name} ({target_lang})")
    print(f"  输出目录: {video_output_dir}")
    print(f"{'=' * 60}")

    if not os.path.exists(video_path):
        print(f"  [错误] 视频文件不存在: {video_path}")
        return False

    start_time = time.time()

    # ===== Step 1: 提取音频 =====
    print(f"\n--- Step 1: 提取音频 ---")
    audio_dir = os.path.join(config.OUTPUT_DIR, video_name, "_audio")
    audio_path = extract_audio(video_path, audio_dir)

    # ===== Step 2: 语音识别 =====
    print(f"\n--- Step 2: 语音识别 (faster-whisper) ---")
    transcription_dir = os.path.join(config.OUTPUT_DIR, video_name, "_transcription")
    source_segments = transcribe(audio_path, transcription_dir)
    print(f"  共识别 {len(source_segments)} 个句段")

    # ===== Step 3: 翻译 =====
    print(f"\n--- Step 3: 翻译 (Ollama → {lang_name}) ---")
    translated_segments = translate_segments(
        source_segments, target_lang, video_output_dir
    )

    # ===== Step 4.1: 说话人识别 (Diarization) =====
    print(f"\n--- Step 4.1: 说话人识别 (pyannote) ---")
    from speaker_diarizer import diarize_audio, merge_transcription_and_diarization
    
    # diarization 只跟源音频有关，不跟目标语言有关，缓存在共享目录
    diarization_dir = os.path.join(config.OUTPUT_DIR, video_name, "_audio")
    num_spk = config.VIDEO_NUM_SPEAKERS.get(video_name)
    diarization_segments = diarize_audio(audio_path, diarization_dir, num_speakers=num_spk)
    # 将说话人标签合并到翻译后的句段中
    merged_segments = merge_transcription_and_diarization(
        translated_segments, diarization_segments, video_output_dir, f"{video_name}_{target_lang}"
    )

    # ===== Step 4.2: 提取参考声音 =====
    print(f"\n--- Step 4.2: 提取参考声音 (Reference Audio) ---")
    from reference_extractor import get_reference_audio
    ref_audio_dir = os.path.join(config.OUTPUT_DIR, video_name, "_references")
    reference_files = get_reference_audio(merged_segments, audio_path, ref_audio_dir)

    # ===== Step 4.3: 跨语言语音克隆 =====
    print(f"\n--- Step 4.3: 语音克隆 (OpenVoice V2) ---")
    from voice_cloner import synthesize_cloned_voice
    
    tts_output_dir = os.path.join(video_output_dir, f"cloned_{target_lang}")
    os.makedirs(tts_output_dir, exist_ok=True)
    
    cloned_segments = []
    for i, seg in enumerate(merged_segments):
        speaker = seg.get("speaker", "SPEAKER_UNKNOWN")
        text = seg["text"]
        
        # 默认声音回调（如果没有找到参考音频）
        ref_audio_path = reference_files.get(speaker)
        if not ref_audio_path:
            # 如果没有，尝试随便用一个
            if reference_files:
                ref_audio_path = list(reference_files.values())[0]
            else:
                # 极端情况，直接跳过或者使用一个默认的
                print(f"  [跳过] 找不到说话人参考声音: {text[:20]}...")
                continue
                
        out_filename = f"seg_{i:04d}_{speaker}.wav"
        out_path = os.path.join(tts_output_dir, out_filename)
        
        if not os.path.exists(out_path) or config.FORCE_RERUN:
            print(f"  [{i+1}/{len(merged_segments)}] 克隆 {speaker} 的声音 -> {out_filename}")
            try:
                synthesize_cloned_voice(text, target_lang, speaker, ref_audio_path, out_path)
            except (KeyboardInterrupt, SystemExit):
                print(f"    [错误] 克隆被中断: {text[:30]}...")
                continue
            except Exception as e:
                print(f"    [错误] 克隆失败: {e}")
                continue
                
        seg_copy = dict(seg)
        seg_copy["audio_path"] = out_path
        cloned_segments.append(seg_copy)

    # ===== Step 5: 音频拼接与时间计算 =====
    print(f"\n--- Step 5: 音频拼接与时间计算 ---")
    total_duration_ms = get_audio_duration_ms(audio_path)
    full_audio_path, video_intervals = assemble_audio(
        cloned_segments, total_duration_ms, video_output_dir, target_lang
    )

    # ===== Step 6: 生成字幕 =====
    print(f"\n--- Step 6: 生成字幕文件 ---")
    # 将原始时间戳映射到新时间线（视频慢放后的时间轴）
    adjusted_source = []
    for seg in source_segments:
        new_seg = dict(seg)
        new_seg["start"] = remap_timestamp(seg["start"], video_intervals)
        new_seg["end"] = remap_timestamp(seg["end"], video_intervals)
        adjusted_source.append(new_seg)

    adjusted_translated = []
    for seg in merged_segments:
        new_seg = dict(seg)
        new_seg["start"] = remap_timestamp(seg["start"], video_intervals)
        new_seg["end"] = remap_timestamp(seg["end"], video_intervals)
        adjusted_translated.append(new_seg)

    subtitle_paths = generate_all_subtitles(
        adjusted_source, adjusted_translated,
        target_lang, video_output_dir, video_name
    )

    # ===== Step 7: 合成最终视频（慢放 + 字幕烧录）=====
    print(f"\n--- Step 7: 合成最终视频 ---")
    burn_in_srt = subtitle_paths.get(target_lang)
    final_video_path = os.path.join(
        video_output_dir, f"{video_name}_{target_lang}.mp4"
    )
    compose_video(video_path, full_audio_path, final_video_path,
                  video_intervals, burn_in_srt)

    # ===== 完成 =====
    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"  ✅ 处理完成: {video_filename} → {lang_name}")
    print(f"  耗时: {elapsed:.1f} 秒")
    print(f"  输出文件:")
    print(f"    视频: {final_video_path}")
    for label, path in subtitle_paths.items():
        print(f"    字幕 ({label}): {path}")
    print(f"{'=' * 60}")

    # 保存处理记录
    log_path = os.path.join(video_output_dir, "processing_log.json")
    log_data = {
        "video": video_filename,
        "target_lang": target_lang,
        "elapsed_seconds": round(elapsed, 1),
        "segment_count": len(source_segments),
        "output_video": final_video_path,
        "subtitles": subtitle_paths,
    }
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    return True


def main():
    parser = argparse.ArgumentParser(
        description="AI 视频多语言转换流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                           # 处理所有视频，翻译为英文和法文
  python main.py --videos a                # 只处理视频 a
  python main.py --videos a b --langs en   # 视频 a 和 b，只翻译为英文
  python main.py --langs fr                # 所有视频，只翻译为法文
        """,
    )
    parser.add_argument(
        "--videos",
        nargs="+",
        choices=["a", "b", "c"],
        default=["a", "b", "c"],
        help="要处理的视频 (默认: 全部)",
    )
    parser.add_argument(
        "--langs",
        nargs="+",
        choices=["en", "fr"],
        default=["en", "fr"],
        help="目标语言 (默认: en fr)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重新生成所有结果，忽略缓存",
    )
    args = parser.parse_args()

    if args.force:
        config.FORCE_RERUN = True

    # 映射简写到文件名
    video_map = {
        "a": "github-workflow-a.mp4",
        "b": "github-workflow-b.mp4",
        "c": "github-workflow-c.mp4",
    }
    selected_videos = [video_map[v] for v in args.videos]
    selected_langs = args.langs

    total = len(selected_videos) * len(selected_langs)
    print(f"\n🎬 AI 视频多语言转换流水线")
    print(f"   视频: {', '.join(selected_videos)}")
    print(f"   语言: {', '.join(selected_langs)}")
    print(f"   共 {total} 个任务")

    overall_start = time.time()
    success_count = 0
    fail_count = 0

    for video in selected_videos:
        for lang in selected_langs:
            try:
                ok = process_video(video, lang)
                if ok:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"\n  ❌ 处理失败: {video} → {lang}")
                print(f"     错误: {e}")
                fail_count += 1

    overall_elapsed = time.time() - overall_start
    print(f"\n{'=' * 60}")
    print(f"  🏁 全部任务完成!")
    print(f"     成功: {success_count}/{total}")
    print(f"     失败: {fail_count}/{total}")
    print(f"     总耗时: {overall_elapsed:.1f} 秒")
    print(f"     输出目录: {config.OUTPUT_DIR}")
    print(f"{'=' * 60}")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
