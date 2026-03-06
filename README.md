# Murmure wyoming protocol

[Murmure](https://github.com/Kieirra/murmure) is a privacy-first, open-source speech-to-text application that runs entirely on your machine, powered by a neural network via NVIDIA’s [Parakeet TDT 0.6B v3 model](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) for fast, local transcription. Murmure turns your voice into text with no internet connection and zero data collection, and supports 25 European languages.

Learn more on the [official website](https://murmure.al1x-ai.com/).

This repository is a bridge for the Wyoming protocol allowing murmure to be used directly in HomeAssistant

<img width="577" height="548" alt="Capture d’écran 2026-03-07 à 00 51 29" src="https://github.com/user-attachments/assets/1646c49f-538a-4545-9077-968d4b11347e" />

## Quickstart

1. Download and install murmure
2. Activate the API (default port 4800)
3. Clone this repository
4. Launch following command

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python bridge.py \
  --host 0.0.0.0 \
  --port 10300 \
  --murmure-url http://127.0.0.1:4800/api/transcribe \
  --model-name murmure \
  --language fr \
  --log-level DEBUG
```
