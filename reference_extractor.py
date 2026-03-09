# coding: utf-8
"""
提取参考音频模块 (Reference Audio Extractor)
基于 Diarization 的结果，为每个说话人自动提取一段清晰的参考音频（用于语音克隆提取音色）。
策略：找出该说话人最长的一段连续发言，截取中间的 3~10 秒。
"""
import os
from pydub import AudioSegment
import config

def get_reference_audio(merged_segments: list[dict], audio_path: str, output_dir: str):
    """
    自动为每个说话人获取参考音频
    
    Args:
        merged_segments: 从 speaker_diarizer 生成的带有 speaker 字段的句段列表
        audio_path: 原始长音频路径
        output_dir: 参考音频的保存目录
        
    Returns:
        dict: { "SPEAKER_00": "path/to/ref_00.wav", ... }
    """
    os.makedirs(output_dir, exist_ok=True)
    
    reference_files = {}
    speakers_segments = {}
    
    # 按照说话人给句段分组
    for seg in merged_segments:
        speaker = seg.get("speaker", "SPEAKER_UNKNOWN")
        if speaker not in speakers_segments:
            speakers_segments[speaker] = []
        speakers_segments[speaker].append(seg)
        
    # 如果音频还没加载，准备加载
    audio = None
    
    for speaker, segs in speakers_segments.items():
        if speaker == "SPEAKER_UNKNOWN":
            continue
            
        ref_path = os.path.join(output_dir, f"ref_{speaker}.wav")
        # 如果已经存在该人的参考音频，跳过
        if os.path.exists(ref_path) and not config.FORCE_RERUN:
            print(f"  [跳过] 参考音频已存在: {ref_path}")
            reference_files[speaker] = ref_path
            continue
            
        # 找出该人说话最长的一段
        longest_seg = max(segs, key=lambda s: s["end"] - s["start"])
        start_ms = int(longest_seg["start"] * 1000)
        end_ms = int(longest_seg["end"] * 1000)
        duration_ms = end_ms - start_ms
        
        # 截取策略：为了避免头尾由于对齐不准或者吸气声/噪音，尽量取句段中间的内容
        # 如果句段长于 5 秒，取中间的 5 秒；如果短于 5 秒但长于 2 秒，取中间这段；如果太短，就全取。
        if duration_ms > 7000:
            crop_start = start_ms + (duration_ms - 5000) // 2
            crop_end = crop_start + 5000
        elif duration_ms > 3000:
            crop_start = start_ms + 500
            crop_end = end_ms - 500
        else:
            crop_start = start_ms
            crop_end = end_ms
            
        if audio is None:
            # 延迟加载长音频以节省内存
            print(f"  加载原始音频以提取参考片段: {audio_path}")
            audio = AudioSegment.from_file(audio_path)
            
        print(f"  提取 {speaker} 参考音频 (取 {crop_start/1000:.1f}s - {crop_end/1000:.1f}s)")
        ref_audio = audio[crop_start:crop_end]
        ref_audio.export(ref_path, format="wav")
        reference_files[speaker] = ref_path
        
    print(f"  ✓ 提取完成，共 {len(reference_files)} 个参考音频")
    return reference_files

if __name__ == "__main__":
    print("请通过 main.py 运行完整流水线")
