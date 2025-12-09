import os
from openai import OpenAI
from typing import Optional

from app.config import Config

client = OpenAI(api_key=Config.bot.OPENAI_API_KEY)

# Загружаем базу знаний из файла (можно заменить на БД)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(BASE_DIR, "..", "data", "knowledge_base.txt")

with open(KB_PATH, "r", encoding="utf8") as f:
    KNOWLEDGE_TEXT = f.read()


async def generate_ai_reply(user_message: str, history: Optional[str] = None) -> str:
    """
    Создает черновик ответа на основе базы знаний и сообщения клиента.
    """

    system_prompt = f"""
Ты — профессиональный сотрудник службы поддержки VPN Ducks.
Отвечаешь кратко, по делу, дружелюбно.
Всегда учитывай базу знаний ниже, она имеет высший приоритет.

База знаний:
{KNOWLEDGE_TEXT}

Если вопрос сложный — предложи несколько вариантов ответа.
    """

    messages = [
        {"role": "system", "content": system_prompt},
    ]

    if history:
        messages.append({"role": "assistant", "content": history})

    messages.append({"role": "user", "content": user_message})

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
    )

    return completion.choices[0].message.content.strip()
