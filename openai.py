import json
import requests
import os

from app import logger
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_KEY")

HEADERS = {
    "Authorization": f"Bearer {OPENAI_KEY}",
    "Content-Type": "application/json"
}

MODEL = "gpt-3.5-turbo"

def get_ai_response(content):
    data = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}]
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=HEADERS,
        data=json.dumps(data)
    )

    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        logger.info(f"Error: {response.status_code}")
        return False
