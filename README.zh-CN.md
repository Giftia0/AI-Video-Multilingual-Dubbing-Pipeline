[English](README.md) | **中文**

# 🎬 AI 视频多语言配音流水线

端到端流水线，自动将中文教学视频转换为英语/法语配音版本，支持声音克隆、说话人分离和字幕烧录。

## 📋 目录

- [功能特性](#功能特性)
- [架构](#架构)
- [前置条件](#前置条件)
- [安装](#安装)
- [使用方法](#使用方法)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [技术细节](#技术细节)
- [常见问题](#常见问题)

## ✨ 功能特性

- **语音识别 (ASR)** — Whisper large-v3（本地模型，GPU 加速），精准转录中文语音
- **AI 翻译** — Ollama 驱动的大模型翻译（中文 → 英语 / 法语）
- **说话人分离** — pyannote.audio 3.1 识别不同说话人，支持指定人数
- **声音克隆** — OpenVoice V2 音色转换，保留原说话人声音特征
- **性别感知 TTS** — 男声（Andrew）和女声（Ava）神经网络语音，edge-tts 生成，MeloTTS 备选
- **视频减速适配** — 视频自动减速以匹配 TTS 时长，而非加速音频（保证自然度）
- **字幕烧录** — SRT 字幕直接渲染到视频画面，半透明背景
- **多格式字幕** — 同时生成中文、目标语言、双语三种 SRT 文件
- **容错机制** — edge-tts 自动重试 + MeloTTS 备选，单句失败不影响全局
- **缓存复用** — 每步中间结果自动缓存，支持 `--force` 强制重跑

## 🏗️ 架构

```
输入：中文教学视频 (.mp4)
    │
    ├─ Step 1: FFmpeg ─────────────── 提取音频 (.wav)
    ├─ Step 2: faster-whisper ─────── 语音识别 → 带时间戳的中文句段
    ├─ Step 3: Ollama LLM ─────────── 翻译 → 英文/法文句段
    ├─ Step 4.1: pyannote.audio ───── 说话人分离（谁在什么时候说话）
    ├─ Step 4.2: pydub ────────────── 提取每位说话人的参考音频
    ├─ Step 4.3: edge-tts + OpenVoice V2 ── 语音合成 + 声音克隆
    ├─ Step 5: pydub ──────────────── 音频拼接 + 视频减速区间计算
    ├─ Step 6: FFmpeg ─────────────── 视频合成（减速 + 字幕烧录）
    └─ Step 7: SRT 生成器 ─────────── 中文 / 目标语言 / 双语字幕
    │
输出：配音视频 (.mp4) + 字幕文件 (.srt)
```

## 📦 前置条件

| 依赖 | 版本 | 用途 |
|:---|:---|:---|
| **Python** | 3.10+ | 运行环境 |
| **FFmpeg** | 6.0+ | 音频提取、视频合成、字幕烧录 |
| **Ollama** | 最新版 | LLM 翻译后端 |
| **CUDA** | 11.8+（可选） | GPU 加速 Whisper、pyannote、OpenVoice |

## 🚀 安装

> **说明：** 模型文件（`checkpoints_v2/`、`whisper/`）和第三方源码（`OpenVoice/`、`MeloTTS/`）仅在本地使用，不包含在此仓库中。

### 1. 克隆仓库

```bash
git clone https://github.com/Giftia0/AI-Video-Multilingual-Dubbing-Pipeline.git
cd AI-Video-Multilingual-Dubbing-Pipeline
```

### 2. 安装 PyTorch（推荐 GPU 版本）

根据你的 CUDA 版本，从 https://pytorch.org/get-started/locally/ 选择对应命令。

```bash
# 示例 — CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

包含：`faster-whisper`、`edge-tts`、`pydub`、`requests`、`soundfile`、`pyannote.audio`、`huggingface_hub`、`openai-whisper`。

### 4. 克隆并安装 OpenVoice V2（声音克隆）

```bash
git clone https://github.com/myshell-ai/OpenVoice.git
pip install -e OpenVoice --no-deps
pip install wavmark
```

### 5. 克隆并安装 MeloTTS（备选 TTS）

```bash
git clone https://github.com/myshell-ai/MeloTTS.git
pip install -e MeloTTS
```

### 6. 设置环境变量

pyannote 说话人分离需要 HuggingFace Token。
从 https://huggingface.co/settings/tokens 获取（需先接受 pyannote 模型的使用协议）。

Linux / macOS：

```bash
export HF_TOKEN="hf_your_token_here"
```

Windows PowerShell：

```powershell
$env:HF_TOKEN="hf_your_token_here"
```

### 7. 安装并启动 Ollama（翻译后端）

从 https://ollama.com 下载安装，然后：

```bash
ollama pull gpt-oss:120b-cloud
ollama serve   # 在另一个终端保持运行
```

### 8. 放置源视频

将中文 `.mp4` 视频放到 `../project-video-audio-CN-EN-FR/` 目录下。

### 9. 首次运行 — 自动下载模型

`checkpoints_v2/`（OpenVoice V2）和 `whisper/`（faster-whisper large-v3）会在首次运行时自动下载。
这些目录已在 `.gitignore` 中，仅保留在本地。

## 🎯 使用方法

### 基本用法（所有视频、所有语言）

```bash
python main.py
```

### 选择指定视频和语言

```bash
# 单个视频、单种语言
python main.py --videos a --langs en

# 多个视频、单种语言
python main.py --videos a b --langs fr

# 单个视频、所有语言
python main.py --videos c --langs en fr
```

### 强制重新生成（忽略缓存）

```bash
python main.py --force --videos a --langs en
```

### 命令行选项

| 参数 | 可选值 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `--videos` | `a` `b` `c` | 全部 | 要处理的视频 |
| `--langs` | `en` `fr` | 全部 | 目标语言 |
| `--force` | （标志位） | 关闭 | 跳过所有缓存，强制重新生成 |

## ⚙️ 配置说明

所有配置集中在 [`config.py`](config.py)：

### ASR（语音识别）

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `WHISPER_MODEL_SIZE` | `./whisper` | 本地模型目录（large-v3） |
| `WHISPER_DEVICE` | `cuda` | `cuda` 或 `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | `float16` / `int8_float16` / `int8` |
| `WHISPER_BEAM_SIZE` | `5` | Beam search 宽度 |

### 翻译（Ollama）

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `OLLAMA_MODEL` | `gpt-oss:120b-cloud` | 模型名称 |
| `OLLAMA_TIMEOUT` | `120` | 请求超时（秒） |
| `OLLAMA_TEMPERATURE` | `0.3` | 越低越确定性 |

### TTS 与声音克隆

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `TTS_VOICES` | Andrew (en), Henri (fr) | 男声 edge-tts 语音 |
| `TTS_VOICES_FEMALE` | Ava (en), Denise (fr) | 女声 edge-tts 语音 |
| `TTS_RATE` | `+0%` | 语速调整 |
| `SPEAKER_GENDER` | 按说话人配置 | 性别映射，用于选择 TTS 语音 |
| `VIDEO_NUM_SPEAKERS` | 按视频配置 | 约束 pyannote 输出的说话人数量 |

### 声音克隆（OpenVoice V2）

`voice_cloner.py` 中的 `tau` 参数控制音色转换强度：
- `tau=0.3` — 更强的声音克隆（更像原说话人，可能有瑕疵）
- `tau=0.5` — 均衡模式（当前默认值）
- `tau=0.7` — 更自然的 TTS 基础音质，较低的说话人相似度

## 📁 项目结构

```
project1-pipeline/
├── main.py                  # 流水线编排器 & CLI
├── config.py                # 集中配置
├── audio_extractor.py       # Step 1: FFmpeg 音频提取
├── transcriber.py           # Step 2: faster-whisper 语音识别
├── translator.py            # Step 3: Ollama LLM 翻译
├── speaker_diarizer.py      # Step 4.1: pyannote 说话人分离
├── reference_extractor.py   # Step 4.2: 提取说话人参考音频
├── voice_cloner.py          # Step 4.3: edge-tts + OpenVoice V2 声音克隆
├── tts_synthesizer.py       # 旧版 TTS 模块（仅 edge-tts）
├── audio_assembler.py       # Step 5: 音频拼接 + 减速区间计算
├── video_composer.py        # Step 6: FFmpeg 视频合成 + 字幕烧录
├── subtitle_generator.py    # Step 7: SRT 字幕生成
├── requirements.txt         # Python 依赖
├── whisper/                 # 本地 Whisper large-v3 模型
├── checkpoints_v2/          # OpenVoice V2 模型检查点
├── OpenVoice/               # OpenVoice 源码（git clone，不提交）
├── MeloTTS/                 # MeloTTS 源码（git clone，不提交）
└── output/                  # 生成结果（已 gitignore）
    └── github-workflow-a/
        ├── _audio/          # 提取的 WAV + 说话人分离缓存
        ├── _transcription/  # Whisper ASR 结果
        ├── _references/     # 说话人参考音频片段
        ├── en/              # 英文输出
        │   ├── cloned_en/   # 每句克隆音频
        │   ├── github-workflow-a_en.mp4    # 最终配音视频
        │   ├── github-workflow-a_en.srt    # 英文字幕
        │   ├── github-workflow-a_zh.srt    # 中文字幕
        │   └── github-workflow-a_zh-en.srt # 双语字幕
        └── fr/              # 法文输出（结构相同）
```

## 🔧 技术细节

### 视频减速适配

流水线不会加速 TTS 音频（听起来不自然），而是在 TTS 句段时长超过原始语音的位置**自动减速视频**：

1. 音频拼接器计算每个句段的 `speed_factor = 原始时长 / TTS时长`
2. 视频合成器使用 FFmpeg `trim` + `setpts` 滤镜对对应区间进行减速
3. 字幕时间戳重新映射到新的（减速后的）时间线

### 声音克隆流程

1. **基础 TTS**：edge-tts 生成高质量神经网络语音（根据性别选择声音）
2. **源 SE 提取**：OpenVoice 从 TTS 输出中提取说话人嵌入向量
3. **目标 SE 提取**：OpenVoice 从参考音频中提取说话人嵌入向量（已缓存）
4. **音色转换**：OpenVoice 将基础音频转换为匹配参考说话人的音色（tau=0.5）

### 容错机制

- **edge-tts**：3 次重试（间隔 2 秒），失败后回退到 MeloTTS
- **声音克隆**：单句段错误隔离 — 一句失败不影响整条流水线
- **字幕烧录**：如果烧录失败，仍会输出不含字幕的视频

## 🐛 常见问题

| 问题 | 解决方案 |
|:---|:---|
| `No module named 'openvoice'` | `pip install -e OpenVoice --no-deps` |
| `No module named 'wavmark'` | `pip install wavmark` |
| Whisper 维度不匹配（80 vs 128） | 确保 `whisper/preprocessor_config.json` 包含 `"feature_size": 128` |
| OpenVoice 检查点未找到 | 首次运行会自动从 HuggingFace 下载 |
| edge-tts 连接错误 | 检查网络；流水线会自动重试 3 次后回退到 MeloTTS |
| pyannote 识别的说话人数量不对 | 在 `config.py` 中设置 `VIDEO_NUM_SPEAKERS` |
| Ollama 连接被拒绝 | 启动 Ollama：`ollama serve` |

## 📄 许可

本项目用于数据工程课程教学目的。
