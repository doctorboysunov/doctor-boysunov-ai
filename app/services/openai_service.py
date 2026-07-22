from openai import OpenAI
from app.config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

def ask_ai(message: str):
    response = client.responses.create(
        model="gpt-5.5",
        input=message
    )
    return response.output_text