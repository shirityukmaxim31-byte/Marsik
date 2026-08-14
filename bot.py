import asyncio
import logging
import sqlite3
import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    CallbackQuery
)

# === НАЛАШТУВАННЯ ===
# Токен береться зі змінних середовища Render або вказується вручну
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
ADMIN_ID = 123456789  # ⚠️ Вкажіть ваш свій Telegram ID!

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === БАЗА ДАНИХ (SQLite) ===
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 10,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER,
            claimed_daily INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_user(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, balance, referrals, referred_by, claimed_daily FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def add_user(user_id, username, referred_by=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username, balance, referrals, referred_by, claimed_daily) VALUES (?, ?, 10, 0, ?, 0)",
        (user_id, username, referred_by)
    )
    conn.commit()
    conn.close()

def update_user(user_id, balance=None, referrals=None, claimed_daily=None, username=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    if balance is not None:
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (balance, user_id))
    if referrals is not None:
        cursor.execute("UPDATE users SET referrals = ? WHERE user_id = ?", (referrals, user_id))
    if claimed_daily is not None:
        cursor.execute("UPDATE users SET claimed_daily = ? WHERE user_id = ?", (claimed_daily, user_id))
    if username is not None:
        cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
    conn.close()


# === КЛАВІАТУРИ ===
def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="🎯 Завдання")],
            [KeyboardButton(text="👥 Реферали"), KeyboardButton(text="⭐ Вивести зірки")]
        ],
        resize_keyboard=True
    )

def task_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Отримати щоденний бонус (+5 балів)", callback_data="daily_bonus")]
        ]
    )


# === ОБРОБНИКИ ===

@dp.message(CommandStart())
async def start_handler(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Немає юзернейму"
    args = message.text.split()[1:] if len(message.text.split()) > 1 else []
    
    user = get_user(user_id)
    
    if not user:
        referrer_id = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user_id else None
        add_user(user_id, username, referrer_id)
        
        # Нараховуємо бонус за реферала
        if referrer_id:
            ref_user = get_user(referrer_id)
            if ref_user:
                new_balance = ref_user[2] + 15
                new_refs = ref_user[3] + 1
                update_user(referrer_id, balance=new_balance, referrals=new_refs)
                try:
                    await bot.send_message(referrer_id, "🎉 За вашим посиланням приєднався новий користувач! Вам нараховано +15 балів.")
                except Exception:
                    pass
    else:
        # Оновлюємо username, якщо змінився
        update_user(user_id, username=username)

    await message.answer(
        f"Вітаємо, {message.from_user.first_name}! 🌟\n\n"
        "Заробляйте бали за виконання завдань та запрошення друзів, а потім обмінюйте їх на **Telegram Stars**!",
        reply_markup=main_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(F.text == "💰 Баланс")
async def balance_handler(message: Message):
    user = get_user(message.from_user.id)
    balance = user[2] if user else 0
    referrals = user[3] if user else 0
    
    await message.answer(
        f"💳 **Ваш профіль:**\n\n"
        f"• Баланс: **{balance}** балів\n"
        f"• Запрошено друзів: **{referrals}**\n\n"
        f"*(Курс обміну: 100 балів = 5 Stars)*",
        parse_mode="Markdown"
    )

@dp.message(F.text == "🎯 Завдання")
async def tasks_handler(message: Message):
    await message.answer(
        "Виконуйте доступні завдання, щоб отримати бали:",
        reply_markup=task_keyboard()
    )

@dp.callback_query(F.data == "daily_bonus")
async def daily_bonus_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user:
        claimed_daily = user[5]
        if claimed_daily == 0:
            new_balance = user[2] + 5
            update_user(user_id, balance=new_balance, claimed_daily=1)
            await callback.answer("Вітаємо! Ви отримали +5 балів!", show_alert=True)
            await callback.message.edit_text("✅ Щоденний бонус виплачено! Повертайтеся завтра.")
        else:
            await callback.answer("Ви вже отримували бонус сьогодні!", show_alert=True)

@dp.message(F.text == "👥 Реферали")
async def ref_handler(message: Message):
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={message.from_user.id}"
    
    await message.answer(
        f"🔗 **Ваше реферальне посилання:**\n`{ref_link}`\n\n"
        f"Запрошуйте друзів та отримуйте **+15 балів** за кожного!",
        parse_mode="Markdown"
    )

@dp.message(F.text == "⭐ Вивести зірки")
async def withdraw_handler(message: Message):
    user_id = message.from_user.id
    user = get_user(user_id)
    
    if not user:
        return

    balance = user[2]
    MIN_BALANCE = 100
    
    if balance < MIN_BALANCE:
        await message.answer(
            f"❌ Недостатньо балів для виведення.\n"
            f"Мінімальна сума: **{MIN_BALANCE} балів**.\n"
            f"Ваш баланс: **{balance} балів**.",
            parse_mode="Markdown"
        )
    else:
        # Списуємо бали
        new_balance = balance - MIN_BALANCE
        update_user(user_id, balance=new_balance)
        
        await message.answer("✅ **Заявку на виведення прийнято!**\nАдміністратор перевірить виконання та надішле Stars у вигляді подарунка протягом 24 годин.")
        
        # Надсилаємо сповіщення адміну
        username_str = f"@{message.from_user.username}" if message.from_user.username else f"[{message.from_user.first_name}](tg://user?id={user_id})"
        
        await bot.send_message(
            ADMIN_ID,
            f"🔔 **НОВА ЗАЯВКА НА ВИВЕДЕННЯ!**\n\n"
            f"• Користувач: {username_str}\n"
            f"• Telegram ID: `{user_id}`\n"
            f"• Запрошено рефералів: {user[3]}\n"
            f"• Запитано: **5 Stars** (списано {MIN_BALANCE} балів).\n\n"
            f"👉 Натисніть на профіль користувача, щоб відправити йому подарунок/зірки.",
            parse_mode="Markdown"
        )

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
