import os
from aiogram import F
from typing import Optional

from openai import OpenAI

client = OpenAI(api_key=F.config.bot.OPENAI_API_KEY)

# Загружаем базу знаний из файла (можно заменить на БД)
with open("knowledge_base.txt", "r", encoding="utf8") as f:
    KNOWLEDGE = f.read()


async def generate_ai_reply(user_message: str, history: Optional[str] = None) -> str:
    """
    Создает черновик ответа на основе базы знаний и сообщения клиента.
    """

    system_prompt = f"""
Ты — профессиональный сотрудник службы поддержки VPN Ducks.
Отвечаешь кратко, по делу, дружелюбно.
Всегда учитывай базу знаний ниже, она имеет высший приоритет.

База знаний:
{KNOWLEDGE}

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
