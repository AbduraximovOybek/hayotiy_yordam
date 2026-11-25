import asyncio
import ast
import operator
import os
from datetime import datetime

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
from deep_translator import GoogleTranslator
from openai import AsyncOpenAI

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not TOKEN:
    raise ValueError("BOT_TOKEN .env faylida mavjud emas!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
user_modes = {}

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧠 AI yordamchi"), KeyboardButton(text="🌐 Tarjimon")],
        [KeyboardButton(text="🧮 Kalkulyator"), KeyboardButton(text="💰 Xarajatlar")],
        [KeyboardButton(text="📊 Hisobot"), KeyboardButton(text="👤 Profilim")],
        [KeyboardButton(text="ℹ️ Yordam")],
    ],
    resize_keyboard=True,
)

async def init_db():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()

def calculate(expression: str):
    allowed = {
        ast.Add: operator.add, ast.Sub: operator.sub,
        ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in allowed:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Daraja juda katta")
            result = allowed[type(node.op)](left, right)
            if abs(result) > 10**15:
                raise ValueError("Natija juda katta")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
            return allowed[type(node.op)](evaluate(node.operand))
        raise ValueError("Noto'g'ri matematik ifoda")

    return evaluate(ast.parse(expression, mode="eval"))

@dp.message(CommandStart())
async def start(message: Message):
    user = message.from_user
    async with aiosqlite.connect("database.db") as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, full_name) VALUES (?, ?)",
            (user.id, user.full_name),
        )
        await db.commit()
    user_modes.pop(user.id, None)
    await message.answer(
        f"Assalomu alaykum, {user.first_name}! 👋\n\n"
        "🤖 HAYOTIY YORDAMCHI BOTga xush kelibsiz!\n"
        "Kerakli xizmatni menyudan tanlang:",
        reply_markup=main_menu,
    )

@dp.message(F.text == "🧠 AI yordamchi")
async def ai_mode(message: Message):
    user_modes[message.from_user.id] = "ai"
    if not ai_client:
        await message.answer(
            "🧠 AI xizmatini yoqish uchun .env fayliga OPENAI_API_KEY kiriting.\n"
            "AI kalitisiz qolgan xizmatlardan foydalanishingiz mumkin."
        )
        return
    await message.answer("Savolingizni yozing. Men javob beraman!")

@dp.message(F.text == "🌐 Tarjimon")
async def translate_mode(message: Message):
    user_modes[message.from_user.id] = "translate"
    await message.answer(
        "Tarjima uchun quyidagi formatda yuboring:\n"
        "uz-en: Salom, qalaysan?\n"
        "en-uz: Hello!\n"
        "uz-ru: Salom dunyo"
    )

@dp.message(F.text == "🧮 Kalkulyator")
async def calculator_mode(message: Message):
    user_modes[message.from_user.id] = "calculator"
    await message.answer("Misol yuboring. Masalan: 250 * 4 + 100")

@dp.message(F.text == "💰 Xarajatlar")
async def expense_mode(message: Message):
    user_modes[message.from_user.id] = "expense"
    await message.answer("Xarajatni quyidagicha yuboring:\n25000 ovqat")

@dp.message(F.text == "📊 Hisobot")
async def report(message: Message):
    async with aiosqlite.connect("database.db") as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE user_id = ?",
            (message.from_user.id,),
        )
        total, count = await cursor.fetchone()
    await message.answer(
        f"📊 HISOBOT\n\n💰 Jami xarajat: {total:,.0f} so'm\n"
        f"📝 Xarajatlar soni: {count}"
    )

@dp.message(F.text == "👤 Profilim")
async def profile(message: Message):
    user = message.from_user
    await message.answer(
        "👤 PROFILIM\n\n"
        f"Ism: {user.full_name}\n"
        f"Telegram ID: {user.id}\n"
        f"Username: @{user.username}" if user.username else
        f"👤 PROFILIM\n\nIsm: {user.full_name}\nTelegram ID: {user.id}\nUsername: mavjud emas"
    )

@dp.message(F.text == "ℹ️ Yordam")
async def help_message(message: Message):
    await message.answer(
        "ℹ️ BOT YORDAMI\n\n"
        "🧠 AI — savollarga javob (API kalit kerak)\n"
        "🌐 Tarjimon — uz-en, en-uz, uz-ru va boshqa tillar\n"
        "🧮 Kalkulyator — matematik hisob-kitob\n"
        "💰 Xarajatlar — xarajatlarni saqlash\n"
        "📊 Hisobot — jami xarajatlar\n"
        "👤 Profil — Telegram ma'lumotlaringiz",
        reply_markup=main_menu,
    )

@dp.message(F.text)
async def handle_text(message: Message):
    user_id = message.from_user.id
    text = message.text.strip()
    mode = user_modes.get(user_id)

    if mode == "calculator":
        try:
            await message.answer(f"🧮 Natija: {calculate(text)}")
        except Exception:
            await message.answer("Ifoda noto'g'ri. Masalan: 20 * 5 + 10")
        return

    if mode == "translate":
        try:
            parts = text.split(":", 1)
            if len(parts) != 2:
                raise ValueError
            languages = parts[0].strip().lower().split("-")
            if len(languages) != 2 or not parts[1].strip():
                raise ValueError
            result = await asyncio.to_thread(
                lambda: GoogleTranslator(
                    source=languages[0], target=languages[1]
                ).translate(parts[1].strip())
            )
            await message.answer(f"🌐 Tarjima:\n\n{result}")
        except Exception:
            await message.answer(
                "Tarjima amalga oshmadi. Formatni va til kodlarini tekshiring.\n"
                "Masalan: uz-en: Salom"
            )
        return

    if mode == "expense":
        try:
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                raise ValueError
            amount = float(parts[0].replace(",", "."))
            description = parts[1].strip()
            if amount <= 0 or amount > 1_000_000_000_000 or not description:
                raise ValueError
            async with aiosqlite.connect("database.db") as db:
                await db.execute(
                    "INSERT INTO expenses (user_id, amount, description, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, amount, description, datetime.now().strftime("%Y-%m-%d %H:%M")),
                )
                await db.commit()
            await message.answer(
                f"✅ Xarajat saqlandi!\n💰 {amount:,.0f} so'm\n📝 {description}"
            )
        except Exception:
            await message.answer("Format xato. Masalan: 25000 ovqat")
        return

    if mode == "ai":
        if not ai_client:
            await message.answer("AI API kaliti sozlanmagan. .env faylini tekshiring.")
            return
        try:
            response = await ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Sen foydali, muloyim va aniq javob beradigan o'zbek tilidagi yordamchisan."},
                    {"role": "user", "content": text},
                ],
            )
            await message.answer(response.choices[0].message.content or "Javob olinmadi.")
        except Exception:
            await message.answer("AI xizmatida xatolik. API kalit va hisobingizni tekshiring.")
        return

    await message.answer("Menyudan kerakli xizmatni tanlang 👇", reply_markup=main_menu)

async def main():
    await init_db()
    print("HAYOTIY YORDAMCHI BOT ISHGA TUSHDI!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot to'xtatildi.")
