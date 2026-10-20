#!/usr/bin/env bash
# Richtet die Stil-KI für wallist ein (CLIP-Bildmodell, läuft komplett lokal).
# Eigene Python-Umgebung nur für die App, das System bleibt unberührt.
# Ohne diese Einrichtung läuft wallist trotzdem, bewertet den Stil dann aber nur grob über Farben.
set -euo pipefail
dir=~/.local/share/wallist
model=$dir/models/clip-vit-b32-vision-q.onnx

if [[ ! -x $dir/venv/bin/python ]]; then
    python3 -m venv --system-site-packages "$dir/venv"   # nutzt GTK, Pillow und numpy vom System
fi
"$dir/venv/bin/pip" install --quiet --disable-pip-version-check onnxruntime

if [[ ! -s $model ]]; then
    mkdir -p "$dir/models"
    curl -fL --progress-bar -o "$model.part" \
        "https://huggingface.co/Xenova/clip-vit-base-patch32/resolve/main/onnx/vision_model_quantized.onnx"
    mv "$model.part" "$model"
fi
echo "Stil-KI bereit."
