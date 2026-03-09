# coding: utf-8
"""
Step 6: 使用 FFmpeg 合成最终视频（视频慢放适配 TTS 音频 + 烧录字幕）
"""
import os
import subprocess
import config


def compose_video(
    original_video: str,
    new_audio: str,
    output_path: str,
    video_intervals: list = None,
    subtitle_path: str = None,
) -> str:
    """
    合成最终视频：视频慢放适配音频 + 烧录字幕

    Args:
        original_video: 原始视频路径
        new_audio: 新音轨路径 (.wav)
        output_path: 输出视频路径
        video_intervals: [(orig_start, orig_end, speed_factor), ...]
        subtitle_path: SRT 字幕路径（烧录到视频中）
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if os.path.exists(output_path) and not config.FORCE_RERUN:
        print(f"  [跳过] 视频已存在: {output_path}")
        return output_path

    needs_slowdown = video_intervals and any(s < 0.999 for _, _, s in video_intervals)

    if needs_slowdown:
        return _compose_with_slowdown(
            original_video, new_audio, output_path, video_intervals, subtitle_path
        )
    else:
        return _compose_simple(original_video, new_audio, output_path, subtitle_path)


def _compose_simple(original_video, new_audio, output_path, subtitle_path=None):
    """简单替换音轨（+ 可选字幕烧录）"""
    if subtitle_path and os.path.exists(subtitle_path):
        srt_esc = subtitle_path.replace("\\", "/").replace(":", "\\:")
        sub_filter = (
            f"subtitles='{srt_esc}'"
            ":force_style='FontSize=16,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H80000000,Outline=2,BorderStyle=3,MarginV=30'"
        )
        cmd = [
            config.FFMPEG_PATH,
            "-i", original_video,
            "-i", new_audio,
            "-map", "0:v", "-map", "1:a",
            "-vf", sub_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-y", output_path,
        ]
    else:
        cmd = [
            config.FFMPEG_PATH,
            "-i", original_video,
            "-i", new_audio,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-y", output_path,
        ]

    print(f"  合成视频: {output_path}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 视频合成失败:\n{result.stderr}")

    _print_result(output_path)
    return output_path


def _compose_with_slowdown(original_video, new_audio, output_path,
                           video_intervals, subtitle_path=None):
    """带视频慢放的合成"""
    # 构建 filter_complex: 每个区间 trim + setpts, 然后 concat
    filter_parts = []
    concat_inputs = []

    for i, (start, end, speed) in enumerate(video_intervals):
        if abs(speed - 1.0) < 0.001:
            filter_parts.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}]"
            )
        else:
            pts_factor = 1.0 / speed
            filter_parts.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},"
                f"setpts=(PTS-STARTPTS)*{pts_factor:.4f}[v{i}]"
            )
        concat_inputs.append(f"[v{i}]")

    n = len(video_intervals)
    filter_str = ";".join(filter_parts)
    filter_str += f";{''.join(concat_inputs)}concat=n={n}:v=1:a=0[vcombined]"

    out_label = "[vcombined]"
    if subtitle_path and os.path.exists(subtitle_path):
        srt_esc = subtitle_path.replace("\\", "/").replace(":", "\\:")
        filter_str += (
            f";[vcombined]subtitles='{srt_esc}'"
            ":force_style='FontSize=24,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BackColour=&H80000000,Outline=2,BorderStyle=3,MarginV=30'[outv]"
        )
        out_label = "[outv]"

    # 写入滤镜脚本（避免命令行长度限制）
    script_path = os.path.join(os.path.dirname(output_path), "_filter_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(filter_str)

    cmd = [
        config.FFMPEG_PATH,
        "-i", original_video,
        "-i", new_audio,
        "-filter_complex_script", script_path,
        "-map", out_label,
        "-map", "1:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-y", output_path,
    ]

    slowdown_n = sum(1 for _, _, sp in video_intervals if sp < 0.999)
    print(f"  合成视频 (含 {slowdown_n} 个慢放区间)")
    if subtitle_path:
        print(f"  烧录字幕: {os.path.basename(subtitle_path)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    # 如果带字幕失败，尝试不烧录字幕
    if result.returncode != 0 and subtitle_path:
        print(f"  [警告] 带字幕合成失败，尝试不烧录字幕...")
        filter_str_nosub = ";".join(filter_parts)
        filter_str_nosub += f";{''.join(concat_inputs)}concat=n={n}:v=1:a=0[vcombined]"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(filter_str_nosub)
        cmd[-6] = "[vcombined]"  # map label
        result = subprocess.run(cmd, capture_output=True, text=True)

    # 清理脚本文件
    if os.path.exists(script_path):
        os.remove(script_path)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg 视频合成失败:\n{result.stderr}")

    _print_result(output_path)
    return output_path


def _print_result(output_path):
    file_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  ✓ 视频合成完成: {output_path} ({file_size:.1f} MB)")
