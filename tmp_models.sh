#!/bin/bash
source /opt/belegpilot/.env
curl -s https://openrouter.ai/api/v1/models \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
models = data.get('data', [])
# Find vision-capable models
for m in models:
    mid = m['id']
    arch = m.get('architecture', {})
    modality = arch.get('modality', '')
    if 'image' in str(modality).lower() or 'vision' in str(modality).lower() or 'multimodal' in str(modality).lower():
        if 'qwen' in mid.lower() or 'gpt-4o' in mid.lower():
            ctx = m.get('context_length', 0)
            pricing = m.get('pricing', {})
            prompt_price = pricing.get('prompt', 'N/A')
            print(f'{mid}  ctx={ctx}  prompt=\${prompt_price}')
"
