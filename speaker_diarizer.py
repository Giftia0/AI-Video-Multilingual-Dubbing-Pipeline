# coding: utf-8
"""
说话人识别模块 (Speaker Diarization)
使用 pyannote.audio 识别不同说话人的语音片段，并与 Whisper 识别结果对齐
"""
import json
import os
import torch
from pyannote.audio import Pipeline
import config


def get_diarization_pipeline():
    """初始化并返回 pyannote diarization pipeline"""
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=config.HF_TOKEN
    )
    
    # 使用 GPU 加速
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))
        
    return pipeline


def diarize_audio(audio_path: str, output_dir: str, num_speakers: int = None) -> list[dict]:
    """
    对音频进行说话人识别

    Args:
        audio_path: 音频文件路径
        output_dir: 结果输出目录

    Returns:
        包含说话人片段的列表
        [{"start": 0.0, "end": 2.5, "speaker": "SPEAKER_00"}, ...]
    """
    os.makedirs(output_dir, exist_ok=True)
    audio_name = os.path.splitext(os.path.basename(audio_path))[0]
    json_path = os.path.join(output_dir, f"{audio_name}_diarization.json")

    # 如果已有结果，直接加载
    if os.path.exists(json_path) and not config.FORCE_RERUN:
        print(f"  [跳过] Diarization 结果已存在: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"  开始说话人识别 (pyannote): {audio_path}")
    pipeline = get_diarization_pipeline()
    
    # 为了避免 Windows 下 torchcodec 的 BUG，使用 soundfile 读取音频到内存
    import soundfile as sf
    
    waveform_np, sample_rate = sf.read(audio_path, dtype="float32")
    if waveform_np.ndim == 1:
        waveform_np = waveform_np.reshape(1, -1)
    else:
        waveform_np = waveform_np.T
    
    waveform = torch.from_numpy(waveform_np)
    audio_in_memory = {"waveform": waveform, "sample_rate": sample_rate}
    
    # 运行 diarization
    diarize_kwargs = {}
    if num_speakers is not None:
        diarize_kwargs["num_speakers"] = num_speakers
    result = pipeline(audio_in_memory, **diarize_kwargs)
    
    # pyannote >= 3.1 返回 DiarizeOutput 对象, 其中 .speaker_diarization 才是 Annotation
    # 旧版本直接返回 Annotation
    if hasattr(result, "speaker_diarization"):
        annotation = result.speaker_diarization
    else:
        annotation = result
    
    segments = []
    unique_speakers = set()
    
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        segments.append({
            "start": round(turn.start, 3),
            "end": round(turn.end, 3),
            "speaker": speaker
        })
        unique_speakers.add(speaker)
        
    print(f"  ✓ 识别出 {len(unique_speakers)} 个不同说话人: {', '.join(sorted(list(unique_speakers)))}")
    
    # 保存结果
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)
        
    return segments


def merge_transcription_and_diarization(
    transcription_segments: list[dict],
    diarization_segments: list[dict],
    output_dir: str,
    audio_name: str
) -> list[dict]:
    """
    将 Whisper 的文字段落与 pyannote 的说话人标签对齐
    为每个 Whisper segment 增加 "speaker" 字段
    """
    json_path = os.path.join(output_dir, f"{audio_name}_merged.json")
    
    if os.path.exists(json_path) and not config.FORCE_RERUN:
        print(f"  [跳过] 合并后的分轨结果已存在: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print("  开始合并语音识别与说话人标签...")
    merged_segments = []
    
    for t_seg in transcription_segments:
        t_start = t_seg["start"]
        t_end = t_seg["end"]
        t_mid = (t_start + t_end) / 2
        
        # 寻找在时间上与当前字幕段重合度最高/包含中点的说话人
        assigned_speaker = "SPEAKER_UNKNOWN"
        max_overlap = 0
        
        for d_seg in diarization_segments:
            d_start = d_seg["start"]
            d_end = d_seg["end"]
            
            # 计算重叠时间
            overlap_start = max(t_start, d_start)
            overlap_end = min(t_end, d_end)
            overlap = max(0, overlap_end - overlap_start)
            
            # 如果重叠时间最长，或者该段包含了这句话的中点
            if overlap > max_overlap or (d_start <= t_mid <= d_end and max_overlap == 0):
                max_overlap = max(overlap, 0.1) # 至少有点重合
                assigned_speaker = d_seg["speaker"]
                
        # 记录
        merged_seg = dict(t_seg)
        merged_seg["speaker"] = assigned_speaker
        merged_segments.append(merged_seg)
        
    # 保存结果
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(merged_segments, f, indent=2, ensure_ascii=False)
        
    print(f"  ✓ 合并完成: 供后续按说话人使用")
    return merged_segments


if __name__ == "__main__":
    print("请通过 main.py 运行完整流水线")
