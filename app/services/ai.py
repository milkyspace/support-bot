import os
from typing import Optional
from openai import OpenAI

from app.services.rag_search import search_similar  # <-- наш FAISS поиск


async def generate_ai_reply(
    user_message: str,
    config,
    history: Optional[str] = None
) -> str:
    """
    Создаёт черновик ответа на основе RAG (FAISS) и сообщения клиента.
    """

    # ---------- 1. Поиск похожих фрагментов в базе знаний ----------
    try:
        kb_matches = search_similar(user_message, top_k=5)
        kb_text = "\n".join(f"- {m}" for m in kb_matches)
    except Exception as e:
        print("RAG error:", e)
        kb_text = ""  # fallback


    # ---------- 2. Формируем системный промпт ----------
    system_prompt = f"""
Ты — вежливый и профессиональный сотрудник службы поддержки VPN Ducks.

Всегда отвечай:
• кратко  
• по делу  
• дружелюбно  
• учитывая приоритет базы знаний ниже  

Если нужны уточнения — корректно попроси пользователя уточнить детали.

База знаний (релевантные фрагменты):
{kb_text}

Если вопрос сложный — предложи несколько вариантов ответа.
    """


    # ---------- 3. Формируем сообщения ----------
    messages = [{"role": "system", "content": system_prompt}]

    if history:
        messages.append({"role": "assistant", "content": history})

    messages.append({"role": "user", "content": user_message})


    # ---------- 4. OpenAI запрос ----------
    client = OpenAI(api_key=config.bot.OPENAI_API_KEY)

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,
    )

    return completion.choices[0].message.content.strip()