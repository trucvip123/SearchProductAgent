#!/usr/bin/env python3
import requests

resp = requests.get('http://localhost:11434/api/tags')
if resp.status_code == 200:
    models = resp.json().get('models', [])
    print('Available Ollama models:')
    for m in models:
        print(f"  • {m['name']}")
else:
    print(f"Error: {resp.status_code}")
