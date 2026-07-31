import os
import subprocess

try:
    output = subprocess.check_output(["git", "show", "3f8900327:backend/llm/prompts.py"], text=True)
    print("--- OLD PROMPTS.PY ---")
    print(output)
except Exception as e:
    print(e)
