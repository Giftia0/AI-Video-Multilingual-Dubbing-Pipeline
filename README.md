**English** | [中文](README.zh-CN.md)

# 🎬 AI Video Multilingual Dubbing Pipeline

An end-to-end pipeline that automatically converts Chinese tutorial videos into English/French dubbed versions with voice cloning, speaker diarization, and burned-in subtitles.

## 📋 Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Demo](#demo)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Pipeline Details](#pipeline-details)
- [Troubleshooting](#troubleshooting)

## ✨ Features

- **Automatic Speech Recognition** — Whisper large-v3 (local, GPU-accelerated) for accurate Chinese transcription
- **AI Translation** — Ollama-powered LLM translation (Chinese → English / French)
- **Speaker Diarization** — pyannote.audio 3.1 identifies individual speakers with configurable speaker count
- **Voice Cloning** — OpenVoice V2 tone color conversion preserves original speaker timbre
- **Gender-Aware TTS** — Male (Andrew) and female (Ava) neural voices via edge-tts, with MeloTTS fallback
- **Video Speed Adaptation** — Video slows down to match TTS duration instead of speeding up audio
- **Subtitle Burn-in** — SRT subtitles rendered directly onto the video with semi-transparent background
- **Multi-format Subtitles** — Chinese, target language, and bilingual SRT files generated
- **Fault Tolerance** — edge-tts retry with MeloTTS fallback, per-segment error isolation
- **Caching** — Intermediate results cached per step; use `--force` to regenerate

## 🏗️ Architecture

```
Input: Chinese tutorial video (.mp4)
    │
    ├─ Step 1: FFmpeg ─────────────── Extract audio (.wav)
    ├─ Step 2: faster-whisper ─────── ASR → timestamped Chinese segments
    ├─ Step 3: Ollama LLM ─────────── Translation → English/French segments
    ├─ Step 4.1: pyannote.audio ───── Speaker diarization (who speaks when)
    ├─ Step 4.2: pydub ────────────── Extract reference audio per speaker
    ├─ Step 4.3: edge-tts + OpenVoice V2 ── Voice cloning per segment
    ├─ Step 5: pydub ──────────────── Audio assembly + video slowdown calculation
    ├─ Step 6: FFmpeg ─────────────── Video composition (slowdown + subtitle burn-in)
    └─ Step 7: SRT generator ──────── Chinese / target / bilingual subtitles
    │
Output: Dubbed video (.mp4) + subtitle files (.srt)
```

## 📦 Prerequisites

| Dependency | Version | Purpose |
|:---|:---|:---|
| **Python** | 3.10+ | Runtime |
| **FFmpeg** | 6.0+ | Audio extraction, video composition, subtitle burn-in |
| **Ollama** | Latest | LLM translation backend |
| **CUDA** | 11.8+ (optional) | GPU acceleration for Whisper, pyannote, OpenVoice |

## 🚀 Installation

> **Note:** Model files (`checkpoints_v2/`, `whisper/`) and third-party source repos (`OpenVoice/`, `MeloTTS/`) are local-only and intentionally excluded from this repository.

### 1. Clone the repository

```bash
git clone https://github.com/Giftia0/AI-Video-Multilingual-Dubbing-Pipeline.git
cd AI-Video-Multilingual-Dubbing-Pipeline
```

### 2. Install PyTorch (GPU recommended)

Choose the command matching your CUDA version from https://pytorch.org/get-started/locally/.

```bash
# Example — CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs: `faster-whisper`, `edge-tts`, `pydub`, `requests`, `soundfile`, `pyannote.audio`, `huggingface_hub`, `openai-whisper`.

### 4. Clone & install OpenVoice V2 (voice cloning)

```bash
git clone https://github.com/myshell-ai/OpenVoice.git
pip install -e OpenVoice --no-deps
pip install wavmark
```

### 5. Clone & install MeloTTS (fallback TTS)

```bash
git clone https://github.com/myshell-ai/MeloTTS.git
pip install -e MeloTTS
```

### 6. Set up environment variables

A HuggingFace token is required for pyannote speaker diarization.
Get one at https://huggingface.co/settings/tokens (accept the pyannote model license first).

Linux / macOS:

```bash
export HF_TOKEN="hf_your_token_here"
```

Windows PowerShell:

```powershell
$env:HF_TOKEN="hf_your_token_here"
```

### 7. Install & start Ollama (translation backend)

Download from https://ollama.com, then:

```bash
ollama pull gpt-oss:120b-cloud
ollama serve   # keep running in a separate terminal
```

### 8. Place source videos

Put your Chinese `.mp4` videos in the `../project-video-audio-CN-EN-FR/` directory.

### 9. First run — auto-download model checkpoints

`checkpoints_v2/` (OpenVoice V2) and `whisper/` (faster-whisper large-v3) will be downloaded automatically on the first run.
These directories are gitignored and should stay local-only.

## 🎯 Usage

### Basic (all videos, all languages)

```bash
python main.py
```

### Select specific videos and languages

```bash
# Single video, single language
python main.py --videos a --langs en

# Multiple videos, single language
python main.py --videos a b --langs fr

# Single video, all languages
python main.py --videos c --langs en fr
```

### Force regeneration (ignore cache)

```bash
python main.py --force --videos a --langs en
```

### CLI Options

| Flag | Values | Default | Description |
|:---|:---|:---|:---|
| `--videos` | `a` `b` `c` | all | Videos to process |
| `--langs` | `en` `fr` | all | Target languages |
| `--force` | (flag) | off | Skip all cache, regenerate everything |

## ⚙️ Configuration

All settings are in [`config.py`](config.py):

### ASR (Speech Recognition)

| Parameter | Default | Description |
|:---|:---|:---|
| `WHISPER_MODEL_SIZE` | `./whisper` | Local model directory (large-v3) |
| `WHISPER_DEVICE` | `cuda` | `cuda` or `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | `float16` / `int8_float16` / `int8` |
| `WHISPER_BEAM_SIZE` | `5` | Beam search width |

### Translation (Ollama)

| Parameter | Default | Description |
|:---|:---|:---|
| `OLLAMA_MODEL` | `gpt-oss:120b-cloud` | Model name |
| `OLLAMA_TIMEOUT` | `120` | Request timeout (seconds) |
| `OLLAMA_TEMPERATURE` | `0.3` | Low = more deterministic |

### TTS & Voice Cloning

| Parameter | Default | Description |
|:---|:---|:---|
| `TTS_VOICES` | Andrew (en), Henri (fr) | Male edge-tts voices |
| `TTS_VOICES_FEMALE` | Ava (en), Denise (fr) | Female edge-tts voices |
| `TTS_RATE` | `+0%` | Speed adjustment |
| `SPEAKER_GENDER` | per-speaker | Gender map for TTS voice selection |
| `VIDEO_NUM_SPEAKERS` | per-video | Constrain pyannote output |

### Voice Cloning (OpenVoice V2)

The `tau` parameter in `voice_cloner.py` controls tone color conversion strength:
- `tau=0.3` — Stronger voice cloning (more like reference speaker, may have artifacts)
- `tau=0.5` — Balanced (current default)
- `tau=0.7` — More natural base TTS quality, less speaker similarity

## 📁 Project Structure

```
project1-pipeline/
├── main.py                  # Pipeline orchestrator & CLI
├── config.py                # Centralized configuration
├── audio_extractor.py       # Step 1: FFmpeg audio extraction
├── transcriber.py           # Step 2: faster-whisper ASR
├── translator.py            # Step 3: Ollama LLM translation
├── speaker_diarizer.py      # Step 4.1: pyannote speaker diarization
├── reference_extractor.py   # Step 4.2: Extract reference audio per speaker
├── voice_cloner.py          # Step 4.3: edge-tts + OpenVoice V2 voice cloning
├── tts_synthesizer.py       # Legacy TTS module (edge-tts only)
├── audio_assembler.py       # Step 5: Audio assembly + slowdown calculation
├── video_composer.py        # Step 6: FFmpeg video composition + subtitles
├── subtitle_generator.py    # Step 7: SRT subtitle generation
├── requirements.txt         # Python dependencies
├── whisper/                 # Local Whisper large-v3 model
├── checkpoints_v2/          # OpenVoice V2 model checkpoints
├── OpenVoice/               # OpenVoice source (git clone, not committed)
├── MeloTTS/                 # MeloTTS source (git clone, not committed)
└── output/                  # Generated results (gitignored)
    └── github-workflow-a/
        ├── _audio/          # Extracted WAV + diarization cache
        ├── _transcription/  # Whisper ASR results
        ├── _references/     # Speaker reference audio clips
        ├── en/              # English output
        │   ├── cloned_en/   # Per-segment cloned audio
        │   ├── github-workflow-a_en.mp4    # Final dubbed video
        │   ├── github-workflow-a_en.srt    # English subtitles
        │   ├── github-workflow-a_zh.srt    # Chinese subtitles
        │   └── github-workflow-a_zh-en.srt # Bilingual subtitles
        └── fr/              # French output (same structure)
```

## 🔧 Pipeline Details

### Video Speed Adaptation

Instead of speeding up TTS audio (which sounds unnatural), the pipeline **slows down the video** where TTS segments are longer than the original speech:

1. Audio assembler calculates `speed_factor = original_duration / tts_duration` per segment
2. Video composer uses FFmpeg `trim` + `setpts` filters to slow down those intervals
3. Subtitle timestamps are remapped to the new (slower) timeline

### Voice Cloning Flow

1. **Base TTS**: edge-tts generates high-quality neural speech (gender-aware voice selection)
2. **Source SE extraction**: OpenVoice extracts speaker embedding from base TTS output
3. **Target SE extraction**: OpenVoice extracts speaker embedding from reference audio (cached)
4. **Tone color conversion**: OpenVoice converts base audio to match reference speaker's timbre (tau=0.5)

### Fault Tolerance

- **edge-tts**: 3 retries with 2s delay, falls back to MeloTTS on failure
- **Voice cloning**: Per-segment error isolation — one failure doesn't stop the pipeline
- **Subtitles**: If burn-in fails, video is still produced without embedded subtitles

## 🐛 Troubleshooting

| Issue | Solution |
|:---|:---|
| `No module named 'openvoice'` | `pip install -e OpenVoice --no-deps` |
| `No module named 'wavmark'` | `pip install wavmark` |
| Whisper shape mismatch (80 vs 128) | Ensure `whisper/preprocessor_config.json` has `"feature_size": 128` |
| OpenVoice checkpoint not found | Run once — auto-downloads from HuggingFace |
| edge-tts connection errors | Check network; pipeline will auto-retry 3x then fallback to MeloTTS |
| pyannote identifies wrong speaker count | Set `VIDEO_NUM_SPEAKERS` in `config.py` |
| Ollama connection refused | Start Ollama: `ollama serve` |

## 📄 License

This project is for educational purposes as part of a data engineering course.
