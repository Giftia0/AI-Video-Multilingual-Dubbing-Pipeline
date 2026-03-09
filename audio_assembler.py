# coding: utf-8
"""
Step 5: 将 TTS 合成的音频片段拼接为完整音轨
新方案：不加速音频，保持自然语速。如果 TTS 比原始时间长，记录需要慢放的视频区间。
"""
import json
import os
import config


def assemble_audio(
    segments: list[dict],
    total_duration_ms: int,
    output_dir: str,
    target_lang: str,
) -> tuple[str, list]:
    """
    将 TTS 音频片段拼接为完整音轨（保持自然语速），并计算视频慢放区间。

    策略：
    - 如果 TTS 片段短于原始时段，放在原始位置（自然留白）
    - 如果 TTS 片段长于原始时段，保持原速，记录该区间需要慢放视频

    Returns:
        (audio_path, video_intervals)
        video_intervals: [(orig_start_s, orig_end_s, speed_factor), ...]
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"full_audio_{target_lang}.wav")
    intervals_path = os.path.join(output_dir, f"video_intervals_{target_lang}.json")

    if os.path.exists(output_path) and os.path.exists(intervals_path) and not config.FORCE_RERUN:
        print(f"  [跳过] 完整音轨已存在: {output_path}")
        with open(intervals_path, "r") as f:
            video_intervals = [tuple(x) for x in json.load(f)]
        return output_path, video_intervals

    from pydub import AudioSegment

    # 过滤出有效音频段并按时间排序
    valid_segs = [
        s for s in segments
        if s.get("audio_path") and os.path.exists(s["audio_path"])
    ]
    valid_segs.sort(key=lambda s: s["start"])

    total_duration_s = total_duration_ms / 1000.0

    video_intervals = []  # (orig_start, orig_end, speed_factor)
    placements = []       # (new_start_ms, tts_audio)
    current_pos = 0.0
    time_offset = 0.0

    print(f"  拼接音频: {len(valid_segs)} 个有效片段, 原始总时长 {total_duration_s:.1f}s")

    for seg in valid_segs:
        orig_start = seg["start"]
        orig_end = seg["end"]
        orig_duration = orig_end - orig_start

        if orig_duration <= 0:
            continue

        # 该段前面的间隙（保持原速）
        if orig_start > current_pos + 0.01:
            video_intervals.append((current_pos, orig_start, 1.0))

        # 加载 TTS 音频
        try:
            tts_audio = AudioSegment.from_file(seg["audio_path"])
        except Exception as e:
            print(f"    [警告] 无法加载 {seg['audio_path']}: {e}")
            video_intervals.append((orig_start, orig_end, 1.0))
            current_pos = orig_end
            continue

        tts_duration_s = len(tts_audio) / 1000.0
        new_duration = max(orig_duration, tts_duration_s)
        speed_factor = orig_duration / new_duration  # < 1.0 需要慢放

        video_intervals.append((orig_start, orig_end, speed_factor))

        # 在新时间线上的放置位置
        new_start_ms = int((orig_start + time_offset) * 1000)
        placements.append((new_start_ms, tts_audio))

        time_offset += (new_duration - orig_duration)
        current_pos = orig_end

    # 最后一段间隙
    if current_pos < total_duration_s:
        video_intervals.append((current_pos, total_duration_s, 1.0))

    # 合并连续的相同速度区间
    video_intervals = _merge_intervals(video_intervals)

    # 创建新时间线上的静音底轨并放置音频
    new_total_ms = int((total_duration_s + time_offset) * 1000)
    final_audio = AudioSegment.silent(duration=new_total_ms)

    placed_count = 0
    for start_ms, tts_audio in placements:
        final_audio = final_audio.overlay(tts_audio, position=start_ms)
        placed_count += 1

    # 导出音频
    final_audio.export(output_path, format="wav")
    file_size = os.path.getsize(output_path) / (1024 * 1024)

    # 保存 intervals 以便缓存
    with open(intervals_path, "w") as f:
        json.dump(video_intervals, f)

    slowdown_count = sum(1 for _, _, s in video_intervals if s < 0.999)
    print(f"  ✓ 音轨拼接完成: {placed_count}/{len(valid_segs)} 片段")
    print(f"    新总时长: {new_total_ms/1000:.1f}s (原 {total_duration_s:.1f}s, 增加 {time_offset:.1f}s)")
    print(f"    需要慢放的视频区间: {slowdown_count} 个")
    print(f"    输出: {output_path} ({file_size:.1f} MB)")

    return output_path, video_intervals


def _merge_intervals(intervals):
    """合并连续的相同速度区间"""
    if not intervals:
        return []
    merged = [list(intervals[0])]
    for start, end, speed in intervals[1:]:
        prev = merged[-1]
        if abs(prev[2] - speed) < 0.001 and abs(start - prev[1]) < 0.01:
            prev[1] = end
        else:
            merged.append([start, end, speed])
    return [tuple(m) for m in merged]


def remap_timestamp(t: float, video_intervals: list) -> float:
    """将原始时间戳映射到新的（慢放后的）时间线"""
    offset = 0.0
    for orig_start, orig_end, speed in video_intervals:
        orig_dur = orig_end - orig_start
        new_dur = orig_dur / speed if speed > 0 else orig_dur

        if t <= orig_start:
            break
        elif t >= orig_end:
            offset += new_dur - orig_dur
        else:
            within = t - orig_start
            new_within = within / speed if speed > 0 else within
            offset += new_within - within
            break

    return t + offset
def get_audio_duration_ms(audio_path: str) -> int:
    """获取音频文件时长（毫秒）"""
    from pydub import AudioSegment
    audio = AudioSegment.from_file(audio_path)
    return len(audio)


if __name__ == "__main__":
    print("请通过 main.py 运行完整流水线")
