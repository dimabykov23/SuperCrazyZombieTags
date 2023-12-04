import os
import random

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram import Dispatcher, executor
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from aiogram.dispatcher.filters.state import State, StatesGroup
import aiofiles

load_dotenv()
ROOM_SERIES = 1
bot: Bot = Bot(token=os.getenv("TELEGRAM_API_TOKEN"))
memory_storage: MemoryStorage = MemoryStorage()
dispatcher: Dispatcher = Dispatcher(bot, storage=memory_storage)

button_start_new_game = KeyboardButton("Создать новую игру")
button_join_game = KeyboardButton("Присоединиться к игре")
button_help = KeyboardButton("Правила")
menu_keyboard = (
    ReplyKeyboardMarkup(one_time_keyboard=True)
    .row(button_start_new_game, button_join_game)
    .add(button_help)
)

cancel_keyboard = InlineKeyboardMarkup().add(
    InlineKeyboardButton(text="Отменить ввод", callback_data="cancel")
)


class CollectRoomNumber(StatesGroup):
    number = State()


@dispatcher.message_handler(commands=["start"])
async def start_command(message: Message):
    await message.answer(
        reply_markup=menu_keyboard, text="Добро пожаловать в безумные зомби прятки"
    )


@dispatcher.message_handler(lambda message: message.text == button_start_new_game.text)
async def create_new_room(message: Message):
    global ROOM_SERIES
    await message.answer("Создаю новую игру")
    async with aiofiles.open(f"rooms/{ROOM_SERIES}.txt", "w") as file:
        await file.write(str(message.from_user.id) + "\n")
    room_keyboard = (
        InlineKeyboardMarkup()
        .row(
            InlineKeyboardButton(
                "Выбрать воду", callback_data=f"choose_tagger {ROOM_SERIES}"
            )
        )
        .row(
            InlineKeyboardButton(
                "Начать игру", callback_data=f"start_game {ROOM_SERIES}"
            )
        )
    )
    await message.answer(f"Номер комнаты: {ROOM_SERIES}", reply_markup=room_keyboard)
    ROOM_SERIES += 1


@dispatcher.message_handler(text=button_join_game.text)
async def join_room(message: Message):
    await message.answer(
        "Чтобы присоединиться к уже существующей игре, введите номер комнаты:"
    )
    await CollectRoomNumber.number.set()


@dispatcher.message_handler(state=CollectRoomNumber.number)
async def process_room_number(message: Message, state: FSMContext):
    room_number = message.text.strip()
    if os.path.exists(f"rooms/{room_number}.txt"):
        async with aiofiles.open(f"rooms/{room_number}.txt", "r+") as file:
            users = (await file.read()).strip().split("\n")
            tguser = message.from_user
            if str(tguser.id) not in users:
                tguser_name = (
                        dict(tguser).get("first_name", "")
                        + " "
                        + dict(tguser).get("last_name", "")
                )
                for user in users:
                    if not user.startswith("tagger"):
                        await bot.send_message(
                            int(user),
                            f"Новый игрок <a href='tg://user?id={tguser.id}'>{tguser_name}</a> в комнате номер "
                            + room_number,
                            parse_mode="HTML",
                        )
                await file.write(str(message.from_user.id) + "\n")
                await message.answer(
                    "Вы успешно присоединились к комнате номер " + room_number
                )
            else:
                await message.answer("Вы уже находитесь в этой комнате")
        await state.finish()
    else:
        await message.answer(
            "Вы ввели неправильный номер комнаты", reply_markup=cancel_keyboard
        )


@dispatcher.callback_query_handler(
    lambda call: call.data and call.data.startswith("choose_tagger")
)
async def choose_tagger(call: CallbackQuery):
    room_number = call.data.split()[1]
    async with aiofiles.open(f"rooms/{room_number}.txt", "r+") as file:
        users = (await file.read()).strip().split("\n")
        if len(users) > 1:
            tagger = random.choice(users)
            tagger_user = dict(await bot.get_chat(int(tagger)))
            tagger_name = (
                    tagger_user.get("first_name", "")
                    + " "
                    + tagger_user.get("last_name", "")
            )
            users.remove(tagger)
            users.append(tagger + " tagger")
            await file.write("\n".join(users))
            for user in users:
                user = user.split()[0]
                await bot.send_message(
                    int(user),
                    f"Вода выбран: <a href='tg://user?id={tagger}'>{tagger_name}</a>",
                    parse_mode="HTML",
                )
        else:
            await call.message.answer("Пока в комнате только один человек")


@dispatcher.callback_query_handler(
    lambda call: call.data and call.data.startswith("start_game")
)
async def start_game(call: CallbackQuery):
    room_number = call.data.split()[1]
    async with aiofiles.open(f"rooms/{room_number}.txt", "r") as file:
        users = (await file.read()).strip().split("\n")
        tagger = list(filter(lambda x: x.endswith("tagger"), users))
        if len(tagger) == 1:
            tagger = tagger[0]
            tagger_user = dict(await bot.get_chat(int(tagger.split()[0])))
            tagger_name = (
                    tagger_user.get("first_name", "")
                    + " "
                    + tagger_user.get("last_name", "")
            )
            for user in users:
                user = user.split()[0]
                await bot.send_message(
                    int(user),
                    f"Игра началась, вода: <a href='tg://user?id={tagger}'>{tagger_name}</a>",
                    parse_mode="HTML",
                )


@dispatcher.callback_query_handler(
    lambda call: call.data and call.data.startswith("cancel"), state="*"
)
async def cancel_input(call: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.finish()
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)
    await start_command(call.message)


@dispatcher.message_handler(
    lambda message: message.text == button_help.text or message.text == "/help"
)
async def help_command(message: Message):
    await message.answer("Привет, добро подаловать в безумные зомби прятки, если ты тут, то тебе явно нечего терять, так что или создавать комнату, или присоединяйтся к уже существующий, спросив ее номер у хоста! Удачных зомби пряток!\n/start - перезапускает игру\n/help - поясняет правила!")


if __name__ == "__main__":
    executor.start_polling(dispatcher=dispatcher)
