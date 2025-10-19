import json
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

# === Настройки ===
TOKEN = os.environ.get("TOKEN")# <-- вставь сюда токен
ADMIN_IDS = [419323427, 984378370]  # <-- сюда ID админов (через запятую)
DB_NAME = "database.db"
QUESTIONS_FILE = "questions.json"

# === Инициализация ===
bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Работа с БД ===
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS answers (
        user_id INTEGER,
        question_number INTEGER,
        answer TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    """)
    conn.commit()
    conn.close()

def save_answer(user_id: int, q_num: int, answer: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO answers (user_id, question_number, answer) VALUES (?, ?, ?)",
                (user_id, q_num, answer))
    conn.commit()
    conn.close()

def get_user_answers_count(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM answers WHERE user_id = ?", (user_id,))
    count = cur.fetchone()[0]
    conn.close()
    return count

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM answers")
    users_count = cur.fetchone()[0]
    cur.execute("SELECT question_number, answer, COUNT(*) FROM answers GROUP BY question_number, answer")
    stats = cur.fetchall()
    conn.close()
    return users_count, stats

# === Загрузка вопросов ===
with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)["questions"]

# === Помощь с клавиатурой ===
def get_answer_keyboard(q_num: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for letter in ["А", "Б", "В", "Г"]:
        kb.button(text=letter, callback_data=f"answer:{q_num}:{letter}")
    kb.adjust(2)
    return kb.as_markup()

# === Хэндлеры ===
@dp.message(CommandStart())
async def start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

    await message.answer(
        "Привет! 👋 Это опрос по информированности.\n\n"
        "Я буду поочередно задавать тебе вопросы. Ответ выбирай кнопками ниже.\n\n"
        "Опрос полностью анонимен."
    )

    await send_question(message.chat.id, 1)

async def send_question(chat_id: int, q_num: int):
    if q_num > len(QUESTIONS):
        await bot.send_message(chat_id, "✅ Спасибо! Ты ответил на все вопросы.")
        return

    question = QUESTIONS[q_num - 1]
    options_text = "\n".join(question["options"])

    text = (
        f"**Вопрос {q_num}/{len(QUESTIONS)}**\n\n"
        f"{question['question']}\n\n"
        f"{options_text}"
    )

    await bot.send_message(
        chat_id,
        text,
        reply_markup=get_answer_keyboard(q_num),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("answer:"))
async def handle_answer(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    _, q_num, answer = callback.data.split(":")
    q_num = int(q_num)

    save_answer(user_id, q_num, answer)
    await callback.answer(f"Ответ {answer} сохранен ✅")

    next_q = q_num + 1
    await send_question(callback.message.chat.id, next_q)

# === Команды для админов ===
@dp.message(Command("stats"))
async def admin_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("⛔ У вас нет прав для этой команды.")

    users_count, stats = get_stats()
    text = f"📊 Статистика опроса:\n\nВсего участников: {users_count}\n\n"
    for q_num, ans, count in stats:
        text += f"Вопрос {q_num} — {ans}: {count} ответов\n"
    await message.answer(text)

@dp.message(Command("reset"))
async def admin_reset(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.reply("⛔ У вас нет прав для этой команды.")

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM answers")
    conn.commit()
    conn.close()
    await message.answer("🧹 Все ответы удалены.")

# === Запуск ===
async def main():
    init_db()
    print("Бот запущен 🚀")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
