import asyncio
from pathlib import Path
from typing import Any

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from bot.config import load_config
from bot.storage import load_storage, save_storage, add_account, set_groups
from bot.telethon_manager import (
    PendingLogin,
    start_login,
    finish_login,
    fetch_groups,
    send_broadcast,
)


class AddAccountStates(StatesGroup):
    label = State()
    phone = State()
    code = State()
    password = State()


class BroadcastStates(StatesGroup):
    account = State()
    text = State()
    image = State()
    delay = State()
    mention = State()


router = Router()

pending_logins: dict[int, PendingLogin] = {}


def is_admin(config: Any, user_id: int | None) -> bool:
    return bool(user_id and user_id in config.admin_ids)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/accounts"), KeyboardButton(text="/add_account")],
            [KeyboardButton(text="/collect_groups"), KeyboardButton(text="/broadcast")],
        ],
        resize_keyboard=True,
    )
    await message.answer(
        "Команды:\n"
        "/accounts — список аккаунтов\n"
        "/add_account — добавить аккаунт\n"
        "/collect_groups <label> — собрать группы\n"
        "/broadcast — начать рассылку\n",
        reply_markup=keyboard,
    )


@router.message(Command("accounts"))
async def cmd_accounts(message: Message) -> None:
    config = message.bot["config"]
    storage = load_storage(config.storage_path)
    if not storage["accounts"]:
        await message.answer("Аккаунты не добавлены.")
        return
    lines = [f"{index + 1}. {acc['label']} ({acc['phone']})" for index, acc in enumerate(storage["accounts"])]
    await message.answer("\n".join(lines))


@router.message(Command("add_account"))
async def cmd_add_account(message: Message, state: FSMContext) -> None:
    config = message.bot["config"]
    if not is_admin(config, message.from_user.id if message.from_user else None):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(AddAccountStates.label)
    await message.answer("Введите название аккаунта (label).")


@router.message(AddAccountStates.label)
async def add_account_label(message: Message, state: FSMContext) -> None:
    await state.update_data(label=message.text.strip())
    await state.set_state(AddAccountStates.phone)
    await message.answer("Введите номер телефона в формате +79991234567.", reply_markup=ReplyKeyboardRemove())


@router.message(AddAccountStates.phone)
async def add_account_phone(message: Message, state: FSMContext) -> None:
    config = message.bot["config"]
    phone = message.text.strip()
    pending = await start_login(config.api_id, config.api_hash, phone)
    pending_logins[message.from_user.id] = pending
    await state.update_data(phone=phone)
    await state.set_state(AddAccountStates.code)
    await message.answer("Код отправлен. Введите код из Telegram.")


@router.message(AddAccountStates.code)
async def add_account_code(message: Message, state: FSMContext) -> None:
    config = message.bot["config"]
    data = await state.get_data()
    pending = pending_logins.get(message.from_user.id)
    if not pending:
        await message.answer("Сессия добавления не найдена. Начните заново /add_account.")
        await state.clear()
        return
    await state.update_data(code=message.text.strip())
    try:
        session = await finish_login(pending, message.text.strip())
    except Exception:
        await state.set_state(AddAccountStates.password)
        await message.answer("Нужен пароль 2FA. Введите пароль.")
        return
    storage = load_storage(config.storage_path)
    add_account(storage, data["label"], data["phone"], session)
    save_storage(config.storage_path, storage)
    pending_logins.pop(message.from_user.id, None)
    await state.clear()
    await message.answer("Аккаунт добавлен.")


@router.message(AddAccountStates.password)
async def add_account_password(message: Message, state: FSMContext) -> None:
    config = message.bot["config"]
    data = await state.get_data()
    pending = pending_logins.get(message.from_user.id)
    if not pending:
        await message.answer("Сессия добавления не найдена. Начните заново /add_account.")
        await state.clear()
        return
    session = await finish_login(pending, data.get("code", ""), message.text.strip())
    storage = load_storage(config.storage_path)
    add_account(storage, data["label"], data["phone"], session)
    save_storage(config.storage_path, storage)
    pending_logins.pop(message.from_user.id, None)
    await state.clear()
    await message.answer("Аккаунт добавлен.")


@router.message(Command("collect_groups"))
async def cmd_collect_groups(message: Message, command: CommandObject) -> None:
    config = message.bot["config"]
    if not is_admin(config, message.from_user.id if message.from_user else None):
        await message.answer("Доступ запрещен.")
        return
    if not command.args:
        await message.answer("Укажите label аккаунта: /collect_groups mylabel")
        return
    storage = load_storage(config.storage_path)
    account = next((acc for acc in storage["accounts"] if acc["label"] == command.args), None)
    if not account:
        await message.answer("Аккаунт не найден.")
        return
    groups = await fetch_groups(config.api_id, config.api_hash, account["session"])
    set_groups(storage, account["label"], groups)
    save_storage(config.storage_path, storage)
    await message.answer(f"Группы собраны: {len(groups)}.")


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext) -> None:
    config = message.bot["config"]
    if not is_admin(config, message.from_user.id if message.from_user else None):
        await message.answer("Доступ запрещен.")
        return
    await state.set_state(BroadcastStates.account)
    await message.answer("Введите label аккаунта для рассылки.", reply_markup=ReplyKeyboardRemove())


@router.message(BroadcastStates.account)
async def broadcast_account(message: Message, state: FSMContext) -> None:
    await state.update_data(account_label=message.text.strip())
    await state.set_state(BroadcastStates.text)
    await message.answer("Введите текст для рассылки.")


@router.message(BroadcastStates.text)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    await state.update_data(text=message.text)
    await state.set_state(BroadcastStates.image)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="skip")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer("Отправьте изображение или напишите skip.", reply_markup=keyboard)


@router.message(BroadcastStates.image, F.photo)
async def broadcast_image(message: Message, state: FSMContext) -> None:
    config = message.bot["config"]
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    media_dir = Path(config.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    target = media_dir / f"{photo.file_id}.jpg"
    await message.bot.download_file(file.file_path, target)
    await state.update_data(media_path=str(target))
    await state.set_state(BroadcastStates.delay)
    await message.answer("Введите задержку между сообщениями (секунды).", reply_markup=ReplyKeyboardRemove())


@router.message(BroadcastStates.image)
async def broadcast_image_skip(message: Message, state: FSMContext) -> None:
    if message.text and message.text.lower() == "skip":
        await state.update_data(media_path=None)
        await state.set_state(BroadcastStates.delay)
        await message.answer("Введите задержку между сообщениями (секунды).", reply_markup=ReplyKeyboardRemove())
        return
    await message.answer("Отправьте изображение или напишите skip.")


@router.message(BroadcastStates.delay)
async def broadcast_delay(message: Message, state: FSMContext) -> None:
    try:
        delay = float(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите число, например 1.5.")
        return
    await state.update_data(delay=delay)
    await state.set_state(BroadcastStates.mention)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="yes"), KeyboardButton(text="no")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer("Невидимое упоминание включить? (yes/no)", reply_markup=keyboard)


@router.message(BroadcastStates.mention)
async def broadcast_mention(message: Message, state: FSMContext) -> None:
    config = message.bot["config"]
    storage = load_storage(config.storage_path)
    data = await state.get_data()
    include_mentions = message.text.lower() == "yes"
    account_label = data["account_label"]
    account = next((acc for acc in storage["accounts"] if acc["label"] == account_label), None)
    if not account:
        await message.answer("Аккаунт не найден.")
        await state.clear()
        return
    groups = storage.get("groups", {}).get(account_label, [])
    if not groups:
        await message.answer("Нет сохраненных групп. Используйте /collect_groups.")
        await state.clear()
        return
    text = data["text"].strip()
    await send_broadcast(
        config.api_id,
        config.api_hash,
        account["session"],
        [group["id"] for group in groups],
        text,
        data.get("media_path"),
        data.get("delay", 0),
        include_invisible_mentions=include_mentions,
    )
    await message.answer("Рассылка завершена.", reply_markup=ReplyKeyboardRemove())
    await state.clear()


def create_bot() -> Dispatcher:
    config = load_config()
    bot = Bot(token=config.bot_token)
    dp = Dispatcher()
    dp["config"] = config
    dp.include_router(router)
    return dp


async def main() -> None:
    dispatcher = create_bot()
    await dispatcher.start_polling(dispatcher.bot)


if __name__ == "__main__":
    asyncio.run(main())
