# Local Model Setup Guide

This guide explains how to run Content Autopilot with local models instead of cloud APIs. This is useful for:

- **Cost reduction**: Local inference is free after initial hardware investment
- **Privacy**: Data never leaves your machine
- **Offline operation**: No internet required after model download
- **Development**: Faster iteration without API rate limits

## Hardware Requirements

**Recommended**: NVIDIA RTX 3060 (12GB VRAM) or better

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU VRAM | 8GB | 12GB+ |
| RAM | 16GB | 32GB |
| Storage | 50GB free | 100GB+ SSD |
| GPU | NVIDIA (CUDA) | RTX 3060+ |

## Quick Start

1. Install local providers (Ollama, ComfyUI, etc.)
2. Update `.env` with provider selection
3. Run `python scripts/test_local_setup.py` to verify
4. Start the server with `python main.py`

## Provider Selection

Edit your `.env` file to select providers:

```bash
# Use local LLM via Ollama
LLM_PROVIDER=ollama

# Use local image generation via ComfyUI
IMAGE_PROVIDER=comfyui

# Keep HeyGen for video (best quality)
VIDEO_PROVIDER=heygen
```

## LLM Providers

### Option 1: Ollama (Recommended)

Ollama is the easiest way to run local LLMs.

**Installation:**

```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows: Download from https://ollama.com/download
```

**Setup:**

```bash
# Start Ollama server
ollama serve

# Pull a model (in another terminal)
ollama pull qwen2.5:14b    # Best quality for 12GB (8GB used)
# OR
ollama pull mistral:7b-v0.3  # Faster, uses less VRAM (5GB)
# OR
ollama pull llama3.2:8b      # Balanced option (6GB)
```

**Configure `.env`:**

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

### Option 2: vLLM (Production)

vLLM offers better performance for production workloads.

**Installation:**

```bash
pip install vllm
```

**Run server:**

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-14B-Instruct \
    --quantization awq \
    --gpu-memory-utilization 0.9
```

**Configure `.env`:**

```bash
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=http://localhost:8000/v1
OPENAI_COMPAT_MODEL=Qwen/Qwen2.5-14B-Instruct
```

### Option 3: LM Studio (GUI)

LM Studio provides a user-friendly interface.

1. Download from https://lmstudio.ai/
2. Download a model (search for "Qwen 2.5 14B")
3. Start the local server in LM Studio
4. Configure `.env`:

```bash
LLM_PROVIDER=openai_compat
OPENAI_COMPAT_BASE_URL=http://localhost:1234/v1
OPENAI_COMPAT_MODEL=qwen2.5-14b-instruct
```

### Model Recommendations for 12GB VRAM

| Model | VRAM | Quality | Speed | Use Case |
|-------|------|---------|-------|----------|
| Qwen 2.5 14B (Q4) | ~8GB | ★★★★☆ | ★★★☆☆ | Best overall |
| Mistral 7B v0.3 | ~5GB | ★★★☆☆ | ★★★★★ | Fast tasks |
| Llama 3.2 8B | ~6GB | ★★★☆☆ | ★★★★☆ | Balanced |
| Qwen 2.5 7B | ~5GB | ★★★☆☆ | ★★★★☆ | Good balance |

## Image Providers

### Option 1: ComfyUI (Recommended)

ComfyUI provides flexible, node-based image generation.

**Installation:**

```bash
# Clone ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI

# Install dependencies
pip install -r requirements.txt

# Download SDXL Turbo (fast, good quality)
# Place in ComfyUI/models/checkpoints/
# Get from: https://huggingface.co/stabilityai/sdxl-turbo
```

**Run:**

```bash
python main.py --listen 0.0.0.0
```

**Configure `.env`:**

```bash
IMAGE_PROVIDER=comfyui
COMFYUI_BASE_URL=http://localhost:8188
```

### Option 2: Stable Diffusion WebUI

The classic AUTOMATIC1111 interface.

**Installation:**

```bash
git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui
cd stable-diffusion-webui

# Install and run with API enabled
./webui.sh --api
```

**Configure `.env`:**

```bash
IMAGE_PROVIDER=sdwebui
SDWEBUI_BASE_URL=http://localhost:7860
```

### Model Recommendations for Image Generation

| Model | VRAM | Quality | Speed | Notes |
|-------|------|---------|-------|-------|
| SDXL Turbo | ~8GB | ★★★★☆ | ★★★★★ | 4 steps, fast |
| SDXL Base | ~8GB | ★★★★★ | ★★★☆☆ | 20-30 steps |
| SD 1.5 | ~4GB | ★★★☆☆ | ★★★★★ | Lower quality |

## Video Providers

### HeyGen (Recommended)

For avatar-style videos, HeyGen provides the best quality. Keep using the cloud API:

```bash
VIDEO_PROVIDER=heygen
HEYGEN_API_KEY=your_api_key
```

### CogVideoX (Experimental)

Local video generation is experimental and lower quality than HeyGen.

**Note:** CogVideoX-2B fits in 12GB VRAM but produces lower quality results. Recommended only for testing or when cloud APIs aren't available.

**Installation:**

See https://github.com/THUDM/CogVideo for setup instructions.

```bash
VIDEO_PROVIDER=cogvideo
COGVIDEO_BASE_URL=http://localhost:8000
```

## Testing Your Setup

Run the test script to verify all providers are working:

```bash
python scripts/test_local_setup.py
```

Expected output:

```
==================================================
LOCAL PROVIDER SETUP TEST
==================================================

LLM Provider: ollama
Image Provider: comfyui
Video Provider: heygen

==================================================
LLM PROVIDER CHECK
==================================================
Configured provider: ollama
  Base URL: http://localhost:11434
  Model: qwen2.5:14b

  Provider instance: OllamaProvider
  Running health check... ✓ HEALTHY
  Testing completion... ✓ WORKS
    Response: Hello, World!
    Tokens: 15 in, 4 out
    Cost: $0.000000
    Latency: 1234ms

...

==================================================
SUMMARY
==================================================
  LLM: ✓ PASS
  IMAGE: ✓ PASS
  VIDEO: ✓ PASS

✓ All providers configured correctly!
```

## Running the Server

Start the server with local providers:

```bash
# Ensure local services are running
ollama serve &
cd /path/to/ComfyUI && python main.py &

# Start Content Autopilot
python main.py
```

## Cost Comparison

| Setup | Monthly Cost (est.) |
|-------|---------------------|
| All Cloud (Bedrock + fal.ai + HeyGen) | $100-500 |
| Local LLM + Cloud Image/Video | $50-200 |
| Local LLM + Local Image + Cloud Video | $20-50 |
| All Local (experimental) | $5-10 (electricity) |

## Troubleshooting

### Ollama Issues

**"Cannot connect to Ollama"**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags
# If not running:
ollama serve
```

**"Model not found"**
```bash
# Pull the model
ollama pull qwen2.5:14b
```

**Slow first response**
- First inference loads the model into GPU memory
- Subsequent calls are faster
- Consider keeping Ollama running

### ComfyUI Issues

**"Cannot connect to ComfyUI"**
```bash
# Check if ComfyUI is running
curl http://localhost:8188/system_stats
# If not:
cd /path/to/ComfyUI && python main.py --listen
```

**"Model not found"**
- Ensure model files are in `ComfyUI/models/checkpoints/`
- Check model filename matches workflow expectations

### Out of Memory Errors

1. Close other GPU-using applications
2. Use a smaller model (Mistral 7B instead of Qwen 14B)
3. Reduce image generation resolution
4. Enable model offloading if available

### Slow Performance

1. Ensure CUDA is properly installed: `nvidia-smi`
2. Check GPU utilization during inference
3. Consider quantized models (Q4, Q5)
4. Close browser tabs and other applications

## Hybrid Configurations

You can mix cloud and local providers for the best balance:

**Cost-Optimized:**
```bash
LLM_PROVIDER=ollama         # Free
IMAGE_PROVIDER=fal          # ~$0.02/image
VIDEO_PROVIDER=heygen       # Best quality
```

**Quality-Optimized:**
```bash
LLM_PROVIDER=bedrock        # Best LLM quality
IMAGE_PROVIDER=comfyui      # Good quality, free
VIDEO_PROVIDER=heygen       # Best video quality
```

**Fully Local (Development):**
```bash
LLM_PROVIDER=ollama
IMAGE_PROVIDER=comfyui
VIDEO_PROVIDER=cogvideo     # Experimental
```
