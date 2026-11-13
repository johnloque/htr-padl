#!/usr/bin/env bash
# Lance une stratégie sur plusieurs modèles, un seul chargé à la fois, puis l'évaluation.
#   scripts/run_benchmark.sh N0 qwen3-vl-8b gemma3-12b churro-3b
set -u
cd "$(dirname "$0")/.."
strategy=$1; shift
for model in "$@"; do
  id=$(uv run python -c "import yaml,sys;print(yaml.safe_load(open('configs/$strategy/$model.yaml'))['model']['id'])")
  # attend la fin d'un éventuel téléchargement (max 2 h)
  for _ in $(seq 1 240); do ollama show "$id" >/dev/null 2>&1 && break; sleep 30; done
  echo "=== $strategy / $model ($id) — $(date '+%H:%M:%S')"
  uv run python -m htr.run --strategy "$strategy" --model "$model" || echo "!!! échec $model"
done
uv run python -m eval.evaluate
