import random
import string
import sqlite3
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio

BOT_TOKEN = "7010358417:AAFs-vZOE-FTruZS8PXhmXEi-327rHHfCN0"
BOT_NAME="kntr_bot"
CHANNEL_ID = "@bykounter"
PHOTO_PATH = "konkurs.jpg"
DATABASE = "users.db"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER UNIQUE,
                        username TEXT,
                        full_name TEXT
                    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY,
                        referrer_id INTEGER,
                        referred_id INTEGER
                    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS bonus_codes (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER,
                        code TEXT
                    )''')
    conn.commit()
    conn.close()

def add_user(user_id, username, full_name):
    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)',
                 (user_id, username, full_name))
    conn.commit()
    conn.close()

def add_referral(referrer_id, referred_id):
    conn = get_db_connection()
    existing_referral = conn.execute(
        'SELECT 1 FROM referrals WHERE referrer_id = ? AND referred_id = ?',
        (referrer_id, referred_id)
    ).fetchone()

    if not existing_referral:
        conn.execute('INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)',
                     (referrer_id, referred_id))
        conn.commit()

    conn.close()

def get_referral_count(referrer_id):
    conn = get_db_connection()
    count = conn.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id = ?', (referrer_id,)).fetchone()[0]
    conn.close()
    return count

def get_user_codes(user_id):
    conn = get_db_connection()
    codes = conn.execute('SELECT code FROM bonus_codes WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return [code['code'] for code in codes]

def add_bonus_code(user_id, code):
    conn = get_db_connection()
    conn.execute('INSERT INTO bonus_codes (user_id, code) VALUES (?, ?)', (user_id, code))
    conn.commit()
    conn.close()

def generate_code():
    digits = ''.join(random.choices(string.digits, k=6))
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    return digits + letters

def get_subscription_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎲 Бонусный код", callback_data="check_subscription"),
    )
    return builder.as_markup()

async def send_referral_link(user_id):
    referral_link = f"https://t.me/{BOT_NAME}?start={user_id}"
    await asyncio.sleep(180)
    await bot.send_message(
        chat_id=user_id,
        text=f"🗣 Пригласи 3 друзей и увеличь свои шансы на победу получив еще один бонус! Твоя реферальная ссылка:\n{referral_link}"
    )
@dp.message(Command("start"))
async def start_handler(message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        full_name = message.from_user.full_name
        referrer_id = None

        command_parts = message.text.split()
        if len(command_parts) > 1:
            args = command_parts[1]
            if args.isdigit():
                referrer_id = int(args)

        create_tables()

        conn = get_db_connection()
        existing_user = conn.execute('SELECT 1 FROM users WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()

        if not existing_user:
            add_user(user_id, username, full_name)

            if referrer_id and referrer_id != user_id:
                add_referral(referrer_id, user_id)
                await bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 У вас новый реферал: @{username or 'пользователь'}!"
                )

                referral_count = get_referral_count(referrer_id)
                if referral_count == 3:
                    second_code = generate_code()
                    add_bonus_code(referrer_id, second_code)
                    await bot.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 Поздравляем! Вы набрали 3 реферала. Ваш дополнительный бонусный код: *{second_code}*",
                        parse_mode="Markdown",

                    )
            await send_referral_link(user_id)

        photo = FSInputFile(PHOTO_PATH)
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption="Салют! Для участия в конкурсе нажми на кнопку 👇",
            reply_markup=get_subscription_keyboard()
        )

    except FileNotFoundError:
        await message.answer("Фотография не найдена. Проверьте путь к файлу.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

@dp.callback_query(lambda c: c.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ["member", "administrator", "creator"]:

            codes = get_user_codes(user_id)
            if not codes:
                code = generate_code()
                add_bonus_code(user_id, code)
                codes = [code]

            await bot.send_message(
                chat_id=callback.message.chat.id,
                text=f"*{codes[0]}*  - ваш бонусный код\n29 ноября среди всех бонусных кодов будет проводиться розыгрыш.",
                parse_mode='Markdown'
            )

            await send_referral_link(user_id)
        else:
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text=(
                    "Упс! Для того чтобы принять участие, нужно быть подписанным на "
                    "<a href='https://t.me/bykounter'>KOUNTER</a>."
                ),
                reply_markup=get_subscription_keyboard(),
                disable_web_page_preview=False,
                parse_mode='HTML'
            )
    except Exception as e:
        await callback.answer(
            f"Произошла ошибка при проверке подписки: {e}. Попробуйте позже.",
            show_alert=True
        )


async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
