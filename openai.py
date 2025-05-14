import json
import requests
import os

from dotenv import load_dotenv
from script import instructions

load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_KEY")

HEADERS = {
    "Authorization": f"Bearer {OPENAI_KEY}",
    "Content-Type": "application/json"
}

MODEL = "gpt-3.5-turbo"

def get_ai_response(content):
    messages = [{"role": "system", "content": instructions}]

    messages.append({"role": "user", "content": content})

    data = { "model": MODEL, "messages": messages }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=HEADERS,
        data=json.dumps(data)
    )

    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        print(f"Error: {response.status_code}")
        return False
