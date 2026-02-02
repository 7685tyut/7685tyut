from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from bot.utils import build_invisible_mentions


@dataclass
class PendingLogin:
    phone: str
    client: TelegramClient


async def start_login(api_id: int, api_hash: str, phone: str) -> PendingLogin:
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    await client.send_code_request(phone)
    return PendingLogin(phone=phone, client=client)


async def finish_login(pending: PendingLogin, code: str, password: str | None = None) -> str:
    try:
        await pending.client.sign_in(pending.phone, code)
    except SessionPasswordNeededError:
        if not password:
            raise
        await pending.client.sign_in(password=password)
    session_string = pending.client.session.save()
    await pending.client.disconnect()
    return session_string


async def fetch_groups(api_id: int, api_hash: str, session: str) -> list[dict[str, str | int]]:
    client = TelegramClient(StringSession(session), api_id, api_hash)
    await client.connect()
    groups: list[dict[str, str | int]] = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if getattr(entity, "megagroup", False) or dialog.is_group:
            groups.append({"id": dialog.id, "title": dialog.title})
    await client.disconnect()
    return groups


async def send_broadcast(
    api_id: int,
    api_hash: str,
    session: str,
    group_ids: Iterable[int],
    text: str,
    media_path: str | None = None,
    delay_seconds: float = 0,
    include_invisible_mentions: bool = False,
    mention_limit: int = 50,
) -> None:
    client = TelegramClient(StringSession(session), api_id, api_hash)
    await client.connect()
    for group_id in group_ids:
        message_text = text
        if include_invisible_mentions:
            participant_ids = [
                participant.id
                async for participant in client.iter_participants(group_id, limit=mention_limit)
            ]
            if participant_ids:
                mentions = build_invisible_mentions(participant_ids)
                message_text = f"{text}\n{mentions}"
        if media_path:
            await client.send_file(group_id, media_path, caption=message_text, parse_mode="md")
        else:
            await client.send_message(group_id, message_text, parse_mode="md")
        if delay_seconds:
            await client.sleep(delay_seconds)
    await client.disconnect()
