import asyncio
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import MagicData
from aiogram.types import Message
from aiogram.utils.markdown import hlink

from app.bot.manager import Manager
from app.bot.types.album import Album
from app.bot.utils.redis import RedisStorage

router = Router()
router.message.filter(
    MagicData(F.event_chat.id == F.config.bot.GROUP_ID),  # type: ignore
    F.chat.type.in_(["group", "supergroup"]),
    F.message_thread_id.is_not(None),
)


@router.message(F.forum_topic_created)
async def handler(message: Message, manager: Manager, redis: RedisStorage) -> None:
    await asyncio.sleep(3)
    user_data = await redis.get_by_message_thread_id(message.message_thread_id)
    if not user_data: return None  # noqa

    # Generate a URL for the user's profile
    url = f"https://t.me/{user_data.username[1:]}" if user_data.username != "-" else f"tg://user?id={user_data.id}"

    # Get the appropriate text based on the user's state
    text = manager.text_message.get("user_started_bot")

    message = await message.bot.send_message(
        chat_id=manager.config.bot.GROUP_ID,
        text=text.format(name=hlink(user_data.full_name, url)),
        message_thread_id=user_data.message_thread_id
    )

    # Pin the message
    await message.pin()


@router.message(F.pinned_message | F.forum_topic_edited | F.forum_topic_closed | F.forum_topic_reopened)
async def handler(message: Message) -> None:
    """
    Delete service messages such as pinned, edited, closed, or reopened forum topics.

    :param message: Message object.
    :return: None
    """
    await message.delete()


from app.services.ai import generate_ai_reply

@router.message(F.media_group_id, F.from_user[F.is_bot.is_(False)])
@router.message(F.media_group_id.is_(None), F.from_user[F.is_bot.is_(False)])
async def handler(message: Message, manager: Manager, redis: RedisStorage, album: Optional[Album] = None) -> None:
    print(f'message')
    user_data = await redis.get_by_message_thread_id(message.message_thread_id)
    if not user_data:
        return

    if user_data.message_silent_mode:
        return

    # ------ AI DRAFT BLOCK ------
    print(f'AI DRAFT BLOCK')
    try:
        # вытаскиваем текст клиентского сообщения
        client_message = message.text or message.caption or ""

        if client_message.strip():
            ai_text = await generate_ai_reply(client_message)
            print(f'{ai_text}')

            await message.bot.send_message(
                chat_id=manager.config.bot.GROUP_ID,
                text=f"🤖 *AI предлагает ответ:*\n\n<code>{ai_text}</code>",
                message_thread_id=message.message_thread_id,
                parse_mode="Markdown",
            )
    except Exception as e:
        print("AI error:", e)
    # ------ END AI BLOCK ------

    # далее — оригинальная логика отправки оператор → клиент
    text = manager.text_message.get("message_sent_to_user")

    try:
        if not album:
            await message.copy_to(chat_id=user_data.id)
        else:
            await album.copy_to(chat_id=user_data.id)

    except TelegramAPIError as ex:
        if "blocked" in ex.message:
            text = manager.text_message.get("blocked_by_user")

    except Exception:
        text = manager.text_message.get("message_not_sent")

    msg = await message.reply(text)
    await asyncio.sleep(5)
    await msg.delete()