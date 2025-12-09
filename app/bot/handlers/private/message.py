import asyncio
from typing import Optional

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.types import Message

from app.bot.manager import Manager
from app.bot.types.album import Album
from app.bot.utils.create_forum_topic import (
    create_forum_topic,
    get_or_create_forum_topic,
)
from app.bot.utils.redis import RedisStorage
from app.bot.utils.redis.models import UserData

router = Router()
router.message.filter(F.chat.type == "private", StateFilter(None))


@router.edited_message()
async def handle_edited_message(message: Message, manager: Manager) -> None:
    text = manager.text_message.get("message_edited")
    msg = await message.reply(text)
    await asyncio.sleep(5)
    await msg.delete()


@router.message(F.media_group_id)
@router.message(F.media_group_id.is_(None))
async def handle_incoming_message(
    message: Message,
    manager: Manager,
    redis: RedisStorage,
    user_data: UserData,
    album: Optional[Album] = None,
) -> None:

    if user_data.is_banned:
        return

    async def send_ai_suggestion(message_thread_id: int, client_message: str):
        """
        Запуск AI-ответа в фоне (не блокирует обработку).
        """
        import html
        from app.services.rag_ai import generate_ai_reply_rag

        try:
            ai_text = await asyncio.wait_for(
                generate_ai_reply_rag(client_message, manager.config),
                timeout=6
            )
        except Exception as e:
            print("AI ERROR:", e)
            return

        if not ai_text:
            return

        try:
            escaped = html.escape(ai_text)
            preview = (
                "🤖 <b>AI предлагает ответ:</b>\n\n"
                f"<blockquote>{escaped}</blockquote>"
            )

            # режем длинные
            if len(preview) > 3800:
                chunks = [preview[i:i + 3500] for i in range(0, len(preview), 3500)]
                for ch in chunks:
                    await message.bot.send_message(
                        chat_id=manager.config.bot.GROUP_ID,
                        text=ch,
                        message_thread_id=message_thread_id,
                        parse_mode="HTML",
                    )
            else:
                await message.bot.send_message(
                    chat_id=manager.config.bot.GROUP_ID,
                    text=preview,
                    message_thread_id=message_thread_id,
                    parse_mode="HTML",
                )

        except Exception as e:
            print("Failed to send AI preview:", e)

    async def copy_message_to_topic():
        message_thread_id = await get_or_create_forum_topic(
            message.bot, redis, manager.config, user_data
        )

        # --- копируем сообщение ---
        if not album:
            await message.forward(
                chat_id=manager.config.bot.GROUP_ID,
                message_thread_id=message_thread_id,
            )
        else:
            await album.copy_to(
                chat_id=manager.config.bot.GROUP_ID,
                message_thread_id=message_thread_id,
            )

        # --- Отправляем ответ клиенту сразу ---
        text = manager.text_message.get("message_sent")
        msg = await message.reply(text)
        asyncio.create_task(_delete_later(msg))

        # --- Запускаем AI асинхронно ---
        client_message = message.text or message.caption or ""
        if client_message.strip():
            asyncio.create_task(send_ai_suggestion(message_thread_id, client_message))

    async def _delete_later(msg):
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass

    # --- обработка ошибок с топиками ---
    try:
        await copy_message_to_topic()
    except TelegramBadRequest as ex:
        if "message thread not found" in ex.message:
            user_data.message_thread_id = await create_forum_topic(
                message.bot, manager.config, user_data.full_name
            )
            await redis.update_user(user_data.id, user_data)
            await copy_message_to_topic()
        else:
            raise
