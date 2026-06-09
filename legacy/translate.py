import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "")

def translate_file(filepath):
    print(f"Reading {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"Translating {filepath}... This might take a minute.")
    prompt = f"""
You are an expert Python developer and translator. 
I have a Python file containing Chinese strings, comments, and docstrings.
Please translate ALL Chinese text into Portuguese.
Preserve ALL Python syntax, formatting, whitespace, quotes, and variable names exactly as they are.
ONLY translate the Chinese text to Portuguese. Do NOT add any explanations.
Return the entire translated file content inside a python code block.

File content:
```python
{content}
```
"""
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0}
    }
    
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            text = result['candidates'][0]['content']['parts'][0]['text']
            
            if text.startswith("```python\n"):
                text = text[10:]
            elif text.startswith("```python"):
                text = text[9:]
            
            if text.endswith("```"):
                text = text[:-3]
            elif text.endswith("```\n"):
                text = text[:-4]
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Successfully translated and saved {filepath}")
    except Exception as e:
        print(f"Error translating {filepath}: {e}")

if __name__ == "__main__":
    translate_file("src/analyzer.py")
    translate_file("src/notification.py")
