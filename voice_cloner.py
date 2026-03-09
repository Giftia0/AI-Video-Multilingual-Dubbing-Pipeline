# coding: utf-8
"""
语音克隆模块 (Voice Cloner)
使用 OpenVoice V2 替换原有 edge-tts
流程：文本 -> MeloTTS 基础声音 -> OpenVoice 提取参考音色转换 -> 目标声音
"""
import os
import torch
import config

_tone_color_converter = None
_load_failed = False
_melo_models = {}

def load_voice_models():
    """按需加载 OpenVoice 和 MeloTTS 模型"""
    global _tone_color_converter, _load_failed
    
    if _tone_color_converter is not None:
        return
    if _load_failed:
        raise RuntimeError("OpenVoice 模型加载曾失败，跳过重试")
        
    print("  加载 OpenVoice V2 模型...")
    # 延迟导入
    try:
        from openvoice import se_extractor
        from openvoice.api import ToneColorConverter
        import whisper # OpenVoice 依赖的 whisper
        
        # 初始化 OpenVoice
        ckpt_converter = os.path.join(config.BASE_DIR, 'checkpoints_v2', 'converter')
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 确保模型被下载
        if not os.path.exists(ckpt_converter):
            print("  正在下载 OpenVoice V2 预处理模型...")
            from huggingface_hub import snapshot_download
            snapshot_download(
                repo_id='myshell-ai/OpenVoiceV2',
                local_dir=os.path.join(config.BASE_DIR, 'checkpoints_v2'),
            )
            
        _tone_color_converter = ToneColorConverter(f'{ckpt_converter}/config.json', device=device)
        _tone_color_converter.load_ckpt(f'{ckpt_converter}/checkpoint.pth')
    except Exception as e:
        _load_failed = True
        raise RuntimeError(f"OpenVoice 模型加载失败: {e}") from e
    
    print("  ✓ OpenVoice V2 初始化完成")

def get_melo_model(language_code):
    """根据语言获取对应的 MeloTTS 基础说话人模型"""
    global _melo_models
    
    # 映射语言代码到 MeloTTS 支持的代码
    melo_lang_map = {
        "en": "EN",
        "en-US": "EN",
        "fr": "FR",
        "zh": "ZH",
        "zh-CN": "ZH",
    }
    melo_lang = melo_lang_map.get(language_code.split('-')[0].lower(), "EN")
    
    if melo_lang not in _melo_models:
        from melo.api import TTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  加载 MeloTTS 基础语言模型: {melo_lang}...")
        _melo_models[melo_lang] = TTS(language=melo_lang, device=device)
        
    return _melo_models[melo_lang], melo_lang

def _edge_tts_generate(text: str, voice: str, output_path: str):
    """使用 edge-tts 生成基础音频，含重试机制"""
    import asyncio
    import edge_tts
    import time
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=config.TTS_RATE)
            asyncio.run(communicate.save(output_path))
            return True
        except (KeyboardInterrupt, asyncio.CancelledError):
            if attempt < 2:
                print(f"    [重试] edge-tts 连接中断，第 {attempt+2} 次尝试...")
                time.sleep(2)
        except Exception as e:
            if attempt < 2:
                print(f"    [重试] edge-tts 失败 ({e})，第 {attempt+2} 次尝试...")
                time.sleep(2)
    return False


def synthesize_cloned_voice(text: str, target_lang: str, speaker_id: str, ref_audio_path: str, output_path: str):
    """
    合成包含原说话人音色的目标语言语音
    """
    load_voice_models()
    
    temp_base_audio = output_path.replace(".wav", "_base.wav")
    gender = config.SPEAKER_GENDER.get(speaker_id, "male")
    
    # 根据性别选择对应的 edge-tts 声音
    if gender == "female":
        voice = config.TTS_VOICES_FEMALE.get(target_lang, "en-US-AvaMultilingualNeural")
    else:
        voice = config.TTS_VOICES.get(target_lang, "en-US-AndrewMultilingualNeural")
    
    # 优先使用 edge-tts（音质更好），失败时回退到 MeloTTS
    if not _edge_tts_generate(text, voice, temp_base_audio):
        print(f"    [回退] edge-tts 失败，使用 MeloTTS 替代")
        melo, melo_lang = get_melo_model(target_lang)
        speaker_key = list(melo.hps.data.spk2id.keys())[0]
        speaker_id_melo = melo.hps.data.spk2id[speaker_key]
        melo.tts_to_file(text, speaker_id_melo, temp_base_audio, speed=1.05)
    
    # 2. 获取基础声音的音色
    from openvoice import se_extractor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # MeloTTS V2 的 base speaker 的 se 可以预先加载，但为了灵活性动态提取
    # 注意：实际上 OpenVoice V2 建议使用官方提供的 base_speaker_se，这里为了简单，直接提取刚生成音频的 SE
    source_se, source_name = se_extractor.get_se(temp_base_audio, _tone_color_converter, target_dir='processed', vad=True)
    
    # 3. 提取目标参考声音的音色
    # 缓存 reference 的 SE 以加速
    ref_se_path = ref_audio_path.replace(".wav", "_se.pth")
    if os.path.exists(ref_se_path):
        target_se = torch.load(ref_se_path, map_location=device)
    else:
        target_se, audio_name = se_extractor.get_se(ref_audio_path, _tone_color_converter, target_dir='processed', vad=True)
        torch.save(target_se, ref_se_path)
        
    # 4. 音色转换（tau 越高保留越多原始音质，越低越像参考人但可能失真）
    _tone_color_converter.convert(
        audio_src_path=temp_base_audio, 
        src_se=source_se, 
        tgt_se=target_se, 
        output_path=output_path,
        tau=0.5,
        message="@MyShell"
    )
    
    # 清理临时基础音频
    if os.path.exists(temp_base_audio):
        os.remove(temp_base_audio)
        
    return output_path

if __name__ == "__main__":
    print("此模块由主函数调用")
