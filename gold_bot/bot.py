#!/usr/bin/env python3
""" 
GOLD BOT - ИСПРАВЛЕННАЯ ВЕРСИЯ
ПРАВИЛЬНАЯ ЛОГИКА: Подтверждение чека → Ожидание покупки → Завершение заказа
"""

import asyncio
import logging
import json
import os
import random
import re
import time
import sys
import threading
from datetime import datetime
from uuid import uuid4

# ===================== ПРОВЕРКА И УСТАНОВКА ЗАВИСИМОСТЕЙ =====================
try:
    import aiohttp
    from aiogram import Bot, Dispatcher, types, F
    from aiogram.filters import Command
    from aiogram.types import (
        InlineKeyboardMarkup, InlineKeyboardButton,
        ReplyKeyboardMarkup, KeyboardButton
    )
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
    from flask import Flask
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
    print("📦 Устанавливаю зависимости...")
    os.system("pip install aiogram==3.0.0 aiohttp flask")
    print("✅ Зависимости установлены. Перезапустите бота!")
    sys.exit(0)

# ===================== FLASK ДЛЯ RENDER =====================
flask_app = Flask(__name__)

@flask_app.route('/')
def flask_home():
    return "✅ Gold Bot is ALIVE! Ping me every 5-10 minutes.", 200

@flask_app.route('/health')
def flask_health():
    return "OK", 200

def run_flask():
    """Запуск Flask в отдельном потоке"""
    try:
        port = int(os.environ.get('PORT', 5000))
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Ошибка Flask: {e}")

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8546640668:AAEVHTdr4Qw2-CVyQlnFFKsVyvuods5Pibo"
ADMIN_ID = 6086536190
ADMIN_USERNAME = "@Bahich_1"
HUMO_CARD = "9860 6067 4427 9617"
CARD_HOLDER = "R.M"

# Курсы
EXCHANGE_RATE = 150  # 150 сум = 1 голда
RUB_UZS_RATE = 170   # 1 RUB = 170 UZS
TON_FEE = 0.55
MIN_WITHDRAWAL = 100

# TON адрес
TON_WALLET = "UQCgVleFGU6aQUSyJ-8XNh52Igy9SBhq5jhEMK3PwDFvc0n8"

# ===================== TELEGRAM PREMIUM ПАКЕТЫ =====================
PREMIUM_WITH_LOGIN = {
    "⭐ 1 месяц - 50,000 сум": {"price": 50000, "period": "1 месяц"},
    "⭐ 12 месяцев - 375,990 сум": {"price": 375990, "period": "12 месяцев"}
}

PREMIUM_GIFT = {
    "🎁 3 месяца - 170,000 сум": {"price": 170000, "period": "3 месяца"},
    "🎁 6 месяцев - 230,000 сум": {"price": 230000, "period": "6 месяцев"},
    "🎁 12 месяцев - 400,000 сум": {"price": 400000, "period": "12 месяцев"}
}

# ===================== ФАЙЛЫ =====================
USERS_FILE = "users.json"
ORDERS_GOLD_FILE = "orders_gold.json"
ORDERS_BP_FILE = "orders_bp.json"
ORDERS_STARS_FILE = "orders_stars.json"
ORDERS_SUBS_FILE = "orders_subs.json"
WITHDRAWALS_FILE = "withdrawals.json"
REVIEWS_FILE = "reviews.json"

# ===================== АКТИВНЫЕ ЧАТЫ =====================
active_chats = {}  # {user_id: {"order_id": "...", "active": True}}

# ===================== НАСТРОЙКА ЛОГГЕРА =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ===================== СОСТОЯНИЯ =====================
class UserStates(StatesGroup):
    # Голда
    waiting_gold_amount = State()
    waiting_gold_receipt = State()
    
    # BP
    waiting_bp_choice = State()
    waiting_bp_id = State()
    waiting_bp_receipt = State()
    
    # Stars
    waiting_stars_choice = State()
    waiting_stars_username = State()
    waiting_stars_receipt = State()
    
    # Telegram Premium
    waiting_sub_type = State()
    waiting_sub_choice = State()
    waiting_sub_phone = State()
    waiting_sub_phone_confirm = State()
    waiting_sub_cloud_password = State()
    waiting_sub_cloud_password_input = State()
    waiting_sub_cloud_password_confirm = State()
    waiting_sub_username = State()
    waiting_sub_username_confirm = State()
    waiting_sub_receipt = State()
    
    # Вывод голды
    waiting_withdraw_amount = State()
    
    # Отзывы
    waiting_review_photo = State()
    waiting_review_text = State()
    
    # Чат
    chatting = State()
    waiting_chat_end_confirm = State()
    waiting_reject_reason = State()
    waiting_skin_photo = State()

# ===================== ИНИЦИАЛИЗАЦИЯ =====================
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===================== УТИЛИТЫ =====================
def load_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки {filename}: {e}")
            return {}
    return {}

def save_data(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")

async def get_ton_rate():
    try:
        url = "https://api.coinbase.com/v2/prices/TON-RUB/spot"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data['data']['amount'])
                else:
                    return 114.79
    except Exception as e:
        logger.error(f"Ошибка получения курса TON: {e}")
        return 114.79

async def calculate_ton_price(amount_sums):
    try:
        rub_amount = amount_sums / RUB_UZS_RATE
        ton_rate = await get_ton_rate()
        ton_amount = rub_amount / ton_rate
        total_ton = ton_amount + TON_FEE
        return round(total_ton, 3), round(ton_rate, 2)
    except Exception as e:
        logger.error(f"Ошибка расчета TON: {e}")
        total_ton = (amount_sums / RUB_UZS_RATE / 114.79) + TON_FEE
        return round(total_ton, 3), 114.79

def get_random_bonus():
    chances = {1: 50, 2: 23, 3: 12, 4: 10, 5: 5}
    rand = random.randint(1, 100)
    cumulative = 0
    for amount, chance in chances.items():
        cumulative += chance
        if rand <= cumulative:
            return amount
    return 1

# ===================== ЗАГРУЗКА ДАННЫХ =====================
users = load_data(USERS_FILE)
orders_gold = load_data(ORDERS_GOLD_FILE)
orders_bp = load_data(ORDERS_BP_FILE)
orders_stars = load_data(ORDERS_STARS_FILE)
orders_subs = load_data(ORDERS_SUBS_FILE)
withdrawals = load_data(WITHDRAWALS_FILE)
reviews = load_data(REVIEWS_FILE)

# ===================== КЛАВИАТУРЫ =====================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟡 Купить голду")],
            [KeyboardButton(text="🎫 Купить BP")],
            [KeyboardButton(text="⭐️ Telegram Stars")],
            [KeyboardButton(text="📅 Telegram Premium")],
            [KeyboardButton(text="💰 Мой баланс"), KeyboardButton(text="💸 Вывести голду")],
            [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="🆘 Поддержка")]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_payment_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 HUMO", callback_data="pay_humo")],
        [InlineKeyboardButton(text="💎 TON", callback_data="pay_ton")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
    ])

def get_bp_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💎 GOLD PASS - 128,490 сум")],
            [KeyboardButton(text="💎 GOLD PASS + - 212,490 сум")],
            [KeyboardButton(text="💎 1 LVL - 20,490 сум")],
            [KeyboardButton(text="💎 10 LVL - 144,490 сум")],
            [KeyboardButton(text="💎 20 LVL - 254,490 сум")],
            [KeyboardButton(text="💎 45 LVL - 442,490 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_stars_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⭐️ 50 stars - 13,000 сум")],
            [KeyboardButton(text="⭐️ 100 stars - 25,000 сум")],
            [KeyboardButton(text="⭐️ 150 stars - 37,000 сум")],
            [KeyboardButton(text="⭐️ 350 stars - 86,000 сум")],
            [KeyboardButton(text="⭐️ 500 stars - 125,000 сум")],
            [KeyboardButton(text="⭐️ 750 stars - 180,000 сум")],
            [KeyboardButton(text="⭐️ 1000 stars - 240,000 сум")],
            [KeyboardButton(text="⭐️ 1500 stars - 360,000 сум")],
            [KeyboardButton(text="⭐️ 2500 stars - 600,000 сум")],
            [KeyboardButton(text="⭐️ 5000 stars - 1,200,000 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_subs_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Со входом в аккаунт")],
            [KeyboardButton(text="🎁 Без входа (подарочная)")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_sub_period_keyboard(sub_type):
    if sub_type == "with_login":
        keyboard = [
            [KeyboardButton(text="⭐ 1 месяц - 50,000 сум")],
            [KeyboardButton(text="⭐ 12 месяцев - 375,990 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ]
    else:
        keyboard = [
            [KeyboardButton(text="🎁 3 месяца - 170,000 сум")],
            [KeyboardButton(text="🎁 6 месяцев - 230,000 сум")],
            [KeyboardButton(text="🎁 12 месяцев - 400,000 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_phone_confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, это мой номер")],
            [KeyboardButton(text="❌ Нет, изменить номер")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_cloud_password_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Есть облачный пароль")],
            [KeyboardButton(text="🚫 Нет облачного пароля")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_cloud_password_confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, это правильный пароль")],
            [KeyboardButton(text="❌ Нет, изменить пароль")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_username_confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, верно")],
            [KeyboardButton(text="❌ Изменить получателя")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_chat_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Главное меню")]],
        resize_keyboard=True
    )

def get_chat_end_confirm_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да, завершить чат")],
            [KeyboardButton(text="❌ Нет, продолжить общение")]
        ],
        resize_keyboard=True
    )

def get_admin_withdrawal_keyboard(withdrawal_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🛒 Купить скин", callback_data=f"buy_skin_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_w_{withdrawal_id}")
        ]
    ])

def get_admin_ready_for_photo_keyboard(withdrawal_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📸 Отправить фото скина", callback_data=f"send_skin_{withdrawal_id}")]
    ])

def get_admin_skin_purchased_keyboard(withdrawal_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Я купил скин у покупателя", callback_data=f"skin_purchased_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Проблема", callback_data=f"skin_problem_{withdrawal_id}")
        ]
    ])

def get_leave_review_keyboard(order_id, order_type="withdrawal"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Оставить отзыв", callback_data=f"leave_review_{order_type}_{order_id}")]
    ])

def get_admin_order_keyboard(order_id, order_type="gold"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"approve_{order_type}_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_type}_{order_id}")
        ]
    ])

def get_admin_complete_keyboard(order_id, order_type="gold"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить заказ (купить скин)", callback_data=f"complete_{order_type}_{order_id}")]
    ])

def get_admin_start_chat_keyboard(order_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Начать чат с покупателем", callback_data=f"start_chat_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_sub_{order_id}")
        ]
    ])

# ===================== СТАРТ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "💬 **Вы находитесь в активном чате с администратором!**\n\n"
            "Вы можете только отправлять сообщения. Для завершения чата обратитесь к администратору.",
            parse_mode="Markdown",
            reply_markup=get_chat_keyboard()
        )
        return
    
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "orders_count": 0,
            "reviews_count": 0,
            "total_bonus": 0
        }
        save_data(users, USERS_FILE)
    
    welcome_text = f"""
🎮 Добро пожаловать в Gold Bot!

💰 Ваш баланс: {users[user_id]['balance']} голды

🟡 Купить голду - пополнить баланс
🎫 Купить BP - Battle Pass для игры
⭐️ Telegram Stars - звёзды для Telegram
📅 Telegram Premium - премиум подписка
💸 Вывести голду - обменять на скин

💎 Курс: {EXCHANGE_RATE} сум = 1 голда
💸 Минимальный вывод: {MIN_WITHDRAWAL} голды
"""
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

# ===================== БАЛАНС =====================
@dp.message(F.text == "💰 Мой баланс")
async def show_balance(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    balance = users.get(user_id, {}).get('balance', 0)
    await message.answer(f"💰 Ваш баланс: {balance} голды")

# ===================== ВЫВОД ГОЛДЫ =====================
@dp.message(F.text == "💸 Вывести голду")
async def withdraw_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    balance = users.get(user_id, {}).get('balance', 0)
    
    if balance < MIN_WITHDRAWAL:
        await message.answer(
            f"❌ Недостаточно голды!\n"
            f"Минимум: {MIN_WITHDRAWAL} голды\n"
            f"Ваш баланс: {balance} голды"
        )
        return
    
    await message.answer(
        f"💸 Вывод голды\n\n"
        f"💰 Ваш баланс: {balance} голды\n"
        f"📊 Минимум: {MIN_WITHDRAWAL} голды\n\n"
        f"Введите сумму для вывода:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_withdraw_amount)

@dp.message(UserStates.waiting_withdraw_amount, F.text)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    user_id = str(message.from_user.id)
    
    try:
        amount = int(message.text.strip())
        balance = users.get(user_id, {}).get('balance', 0)
        
        if amount < MIN_WITHDRAWAL:
            await message.answer(f"❌ Минимальная сумма вывода: {MIN_WITHDRAWAL} голды")
            return
        
        if amount > balance:
            await message.answer(f"❌ Недостаточно голды! Ваш баланс: {balance}")
            return
        
        withdrawal_id = f"w_{int(time.time())}_{user_id[-4:]}"
        
        withdrawals[withdrawal_id] = {
            "user_id": user_id,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_name": message.from_user.full_name,
            "username": message.from_user.username
        }
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        # Отправляем админу
        await bot.send_message(
            ADMIN_ID,
            f"💰 **НОВЫЙ ЗАЯВКА НА ВЫВОД**\n\n"
            f"👤 {message.from_user.full_name}\n"
            f"📱 @{message.from_user.username}\n"
            f"🆔 `{user_id}`\n"
            f"💸 Сумма: {amount} голды\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📋 ID: `{withdrawal_id}`",
            parse_mode="Markdown",
            reply_markup=get_admin_withdrawal_keyboard(withdrawal_id)
        )
        
        await message.answer(
            f"✅ Заявка на вывод {amount} голды создана!\n"
            f"Ожидайте подтверждения администратора.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число!")

# ===================== ПОДДЕРЖКА =====================
@dp.message(F.text == "🆘 Поддержка")
async def support_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    support_text = f"""
🆘 **ПОДДЕРЖКА**

📍 **Администратор:** {ADMIN_USERNAME}
🤖 **Бот:** @Gold_stars_prem_donatuzbbot

📞 **По вопросам:**
• Не пришла голда / товар
• Проблемы с оплатой
• Ошибки в боте
• Другие вопросы

💎 **Курс:** {EXCHANGE_RATE} сум = 1 голда
💸 **Мин. вывод:** {MIN_WITHDRAWAL} голды

💳 **Реквизиты HUMO:**
`{HUMO_CARD}`
👤 {CARD_HOLDER}

💎 **Реквизиты TON:**
`{TON_WALLET}`
"""
    await message.answer(support_text, parse_mode="Markdown")

# ===================== МОИ ЗАКАЗЫ =====================
@dp.message(F.text == "📋 Мои заказы")
async def my_orders_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    orders_text = "📋 **Ваши заказы:**\n\n"
    has_orders = False
    
    # Вывод голды
    for withdrawal_id, withdrawal in withdrawals.items():
        if withdrawal['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "admin_buying": "🛒",
                "skin_sent_to_buyer": "📸",
                "awaiting_admin_purchase": "📋",
                "completed": "✅",
                "rejected": "❌"
            }.get(withdrawal['status'], "❓")
            
            orders_text += f"{status_emoji} **Вывод голды**\n"
            orders_text += f"💰 {withdrawal['amount']} голды\n"
            orders_text += f"📅 {withdrawal['created_at']}\n"
            orders_text += f"📋 ID: `{withdrawal_id}`\n\n"
    
    # Покупка голды
    for order_id, order in orders_gold.items():
        if order['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "awaiting_purchase": "🛒",
                "completed": "✅",
                "rejected": "❌"
            }.get(order['status'], "❓")
            orders_text += f"{status_emoji} **Покупка голды**\n"
            orders_text += f"💰 {order['gold_amount']} голды\n"
            orders_text += f"📅 {order['created_at']}\n"
            orders_text += f"📋 ID: `{order_id}`\n\n"
    
    # Покупка BP
    for order_id, order in orders_bp.items():
        if order['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "awaiting_purchase": "🛒",
                "completed": "✅",
                "rejected": "❌"
            }.get(order['status'], "❓")
            orders_text += f"{status_emoji} **Покупка BP**\n"
            orders_text += f"🎮 {order['bp_package']}\n"
            orders_text += f"📅 {order['created_at']}\n"
            orders_text += f"📋 ID: `{order_id}`\n\n"
    
    # Покупка Stars
    for order_id, order in orders_stars.items():
        if order['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "awaiting_purchase": "🛒",
                "completed": "✅",
                "rejected": "❌"
            }.get(order['status'], "❓")
            orders_text += f"{status_emoji} **Покупка Stars**\n"
            orders_text += f"⭐️ {order['stars_package']}\n"
            orders_text += f"📅 {order['created_at']}\n"
            orders_text += f"📋 ID: `{order_id}`\n\n"
    
    # Покупка Premium
    for order_id, order in orders_subs.items():
        if order['user_id'] == user_id:
            has_orders = True
            status_emoji = {
                "pending": "⏳",
                "awaiting_purchase": "🛒",
                "completed": "✅",
                "rejected": "❌"
            }.get(order['status'], "❓")
            sub_type_ru = "Со входом" if order['sub_type'] == "with_login" else "Подарочная"
            orders_text += f"{status_emoji} **Telegram Premium**\n"
            orders_text += f"📅 {sub_type_ru}, {order['sub_period']}\n"
            orders_text += f"📅 {order['created_at']}\n"
            orders_text += f"📋 ID: `{order_id}`\n\n"
    
    if not has_orders:
        orders_text = "📭 **У вас нет заказов**"
    
    await message.answer(orders_text, parse_mode="Markdown")

# ===================== ПОКУПКА ГОЛДЫ =====================
@dp.message(F.text == "🟡 Купить голду")
async def buy_gold_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    await message.answer(
        "💵 Введите сумму в сумах:\n\nПример: 30000",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_gold_amount)

@dp.message(UserStates.waiting_gold_amount, F.text)
async def process_gold_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        amount_sums = int(message.text.strip().replace(" ", ""))
        if amount_sums < EXCHANGE_RATE:
            await message.answer(f"❌ Минимальная сумма: {EXCHANGE_RATE} сум")
            return
        
        gold_amount = amount_sums // EXCHANGE_RATE
        ton_total, ton_rate = await calculate_ton_price(amount_sums)
        
        await state.update_data(
            amount_sums=amount_sums,
            gold_amount=gold_amount,
            ton_total=ton_total,
            ton_rate=ton_rate,
            order_type="gold"
        )
        
        await message.answer(
            f"💎 Расчёт:\n"
            f"{amount_sums:,} сум = {gold_amount} голды\n\n"
            f"Вы получите: {gold_amount} голды\n\n"
            f"Выберите способ оплаты:",
            reply_markup=get_payment_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ Введите число!\nПример: 30000")

# ===================== ПОКУПКА BP =====================
@dp.message(F.text == "🎫 Купить BP")
async def buy_bp_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    await message.answer(
        "🎫 Выберите пакет BP:",
        reply_markup=get_bp_keyboard()
    )
    await state.set_state(UserStates.waiting_bp_choice)

@dp.message(UserStates.waiting_bp_choice, F.text)
async def process_bp_choice(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    bp_prices = {
        "💎 GOLD PASS - 128,490 сум": 128490,
        "💎 GOLD PASS + - 212,490 сум": 212490,
        "💎 1 LVL - 20,490 сум": 20490,
        "💎 10 LVL - 144,490 сум": 144490,
        "💎 20 LVL - 254,490 сум": 254490,
        "💎 45 LVL - 442,490 сум": 442490
    }
    
    if message.text not in bp_prices:
        await message.answer("❌ Выберите пакет из списка")
        return
    
    price = bp_prices[message.text]
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        bp_package=message.text,
        bp_price=price,
        ton_total=ton_total,
        ton_rate=ton_rate,
        order_type="bp"
    )
    
    await message.answer(
        "🎮 Введите ваш ID в игре (только цифры):\n\n"
        "Это нужно для активации BP",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_bp_id)

@dp.message(UserStates.waiting_bp_id, F.text)
async def process_bp_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if not message.text.isdigit():
        await message.answer("❌ ID должен содержать только цифры!\nПример: 123456789")
        return
    
    await state.update_data(game_id=message.text)
    data = await state.get_data()
    
    await message.answer(
        f"🎫 Пакет: {data['bp_package']}\n"
        f"💰 Цена: {data['bp_price']:,} сум\n"
        f"🆔 ID в игре: {data['game_id']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== TELEGRAM STARS =====================
@dp.message(F.text == "⭐️ Telegram Stars")
async def buy_stars_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    await message.answer(
        "⭐️ Выберите пакет Stars:",
        reply_markup=get_stars_keyboard()
    )
    await state.set_state(UserStates.waiting_stars_choice)

@dp.message(UserStates.waiting_stars_choice, F.text)
async def process_stars_choice(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    stars_prices = {
        "⭐️ 50 stars - 13,000 сум": {"name": "50 stars", "price": 13000},
        "⭐️ 100 stars - 25,000 сум": {"name": "100 stars", "price": 25000},
        "⭐️ 150 stars - 37,000 сум": {"name": "150 stars", "price": 37000},
        "⭐️ 350 stars - 86,000 сум": {"name": "350 stars", "price": 86000},
        "⭐️ 500 stars - 125,000 сум": {"name": "500 stars", "price": 125000},
        "⭐️ 750 stars - 180,000 сум": {"name": "750 stars", "price": 180000},
        "⭐️ 1000 stars - 240,000 сум": {"name": "1000 stars", "price": 240000},
        "⭐️ 1500 stars - 360,000 сум": {"name": "1500 stars", "price": 360000},
        "⭐️ 2500 stars - 600,000 сум": {"name": "2500 stars", "price": 600000},
        "⭐️ 5000 stars - 1,200,000 сум": {"name": "5000 stars", "price": 1200000}
    }
    
    if message.text not in stars_prices:
        await message.answer("❌ Выберите пакет из списка")
        return
    
    package_info = stars_prices[message.text]
    ton_total, ton_rate = await calculate_ton_price(package_info["price"])
    
    await state.update_data(
        stars_package=package_info["name"],
        stars_price=package_info["price"],
        ton_total=ton_total,
        ton_rate=ton_rate,
        order_type="stars"
    )
    
    await message.answer(
        "📱 Введите юзернейм получателя (например @username):\n\n"
        "Stars будут отправлены этому пользователю",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_stars_username)

@dp.message(UserStates.waiting_stars_username, F.text)
async def process_stars_username(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    username = message.text.strip()
    if not username.startswith("@"):
        username = f"@{username}"
    
    await state.update_data(stars_recipient=username)
    data = await state.get_data()
    
    await message.answer(
        f"⭐️ Пакет: {data['stars_package']}\n"
        f"💰 Цена: {data['stars_price']:,} сум\n"
        f"👤 Получатель: {data['stars_recipient']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== TELEGRAM PREMIUM =====================
@dp.message(F.text == "📅 Telegram Premium")
async def buy_premium_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    await message.answer(
        "📅 **Telegram Premium**\n\n"
        "Выберите тип подписки:\n\n"
        "📱 **Со входом в аккаунт** — доступ через ваш аккаунт\n"
        "🎁 **Без входа (подарочная)** — отправка подарка другу\n\n"
        "👇 Сделайте выбор:",
        parse_mode="Markdown",
        reply_markup=get_subs_keyboard()
    )
    await state.set_state(UserStates.waiting_sub_type)

@dp.message(UserStates.waiting_sub_type, F.text)
async def process_premium_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text == "📱 Со входом в аккаунт":
        await state.update_data(sub_type="with_login")
        await message.answer(
            "📅 **Telegram Premium (Со входом)**\n\n"
            "Выберите срок подписки:",
            parse_mode="Markdown",
            reply_markup=get_sub_period_keyboard("with_login")
        )
        await state.set_state(UserStates.waiting_sub_choice)
        
    elif message.text == "🎁 Без входа (подарочная)":
        await state.update_data(sub_type="gift")
        await message.answer(
            "📅 **Telegram Premium (Подарочная)**\n\n"
            "Выберите срок подписки:",
            parse_mode="Markdown",
            reply_markup=get_sub_period_keyboard("gift")
        )
        await state.set_state(UserStates.waiting_sub_choice)
    else:
        await message.answer("❌ Пожалуйста, выберите тип подписки из списка")

@dp.message(UserStates.waiting_sub_choice, F.text)
async def process_premium_choice(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    sub_type = data.get('sub_type')
    
    # Определяем цену
    price = None
    period = None
    
    if sub_type == "with_login":
        if message.text in PREMIUM_WITH_LOGIN:
            price = PREMIUM_WITH_LOGIN[message.text]["price"]
            period = PREMIUM_WITH_LOGIN[message.text]["period"]
    else:
        if message.text in PREMIUM_GIFT:
            price = PREMIUM_GIFT[message.text]["price"]
            period = PREMIUM_GIFT[message.text]["period"]
    
    if not price:
        await message.answer("❌ Выберите пакет из списка")
        return
    
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        sub_period=message.text,
        sub_price=price,
        sub_period_text=period,
        ton_total=ton_total,
        ton_rate=ton_rate,
        order_type="sub"
    )
    
    if sub_type == "with_login":
        await message.answer(
            "📱 Введите номер телефона аккаунта Telegram\n\n"
            "Формат: +998901234567",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_phone)
    else:
        await message.answer(
            "👤 Введите username получателя (например @username):\n\n"
            "Premium будет отправлен как подарок",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_username)

@dp.message(UserStates.waiting_sub_phone, F.text)
async def process_premium_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    phone = message.text.strip()
    if not re.match(r'^\+?[0-9]{10,15}$', phone):
        await message.answer("❌ Неверный формат номера!\nПример: +998901234567")
        return
    
    await state.update_data(sub_phone=phone)
    
    await message.answer(
        f"✅ Номер телефона: {phone}\n\n"
        f"Всё верно?",
        reply_markup=get_phone_confirm_keyboard()
    )
    await state.set_state(UserStates.waiting_sub_phone_confirm)

@dp.message(UserStates.waiting_sub_phone_confirm, F.text)
async def process_phone_confirm(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text == "✅ Да, это мой номер":
        await message.answer(
            "🔐 Есть ли у вас облачный пароль в Telegram?",
            reply_markup=get_cloud_password_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_cloud_password)
    elif message.text == "❌ Нет, изменить номер":
        await message.answer(
            "📱 Введите номер телефона заново:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_phone)
    else:
        await message.answer("❌ Пожалуйста, выберите действие из меню")

@dp.message(UserStates.waiting_sub_cloud_password, F.text)
async def process_cloud_password(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text == "🔐 Есть облачный пароль":
        await message.answer(
            "🔐 Введите ваш облачный пароль:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_cloud_password_input)
    elif message.text == "🚫 Нет облачного пароля":
        await state.update_data(sub_cloud_password=None)
        await show_premium_payment(message, state)
    else:
        await message.answer("❌ Пожалуйста, выберите действие из меню")

@dp.message(UserStates.waiting_sub_cloud_password_input, F.text)
async def process_cloud_password_input(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(sub_cloud_password=message.text)
    
    await message.answer(
        "✅ Пароль сохранен. Всё верно?",
        reply_markup=get_cloud_password_confirm_keyboard()
    )
    await state.set_state(UserStates.waiting_sub_cloud_password_confirm)

@dp.message(UserStates.waiting_sub_cloud_password_confirm, F.text)
async def process_cloud_password_confirm(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text == "✅ Да, это правильный пароль":
        await show_premium_payment(message, state)
    elif message.text == "❌ Нет, изменить пароль":
        await message.answer(
            "🔐 Введите облачный пароль заново:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_cloud_password_input)
    else:
        await message.answer("❌ Пожалуйста, выберите действие из меню")

@dp.message(UserStates.waiting_sub_username, F.text)
async def process_premium_username(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    username = message.text.strip()
    if not username.startswith("@"):
        username = f"@{username}"
    
    await state.update_data(sub_recipient=username)
    
    await message.answer(
        f"✅ Получатель: {username}\n\n"
        f"Всё верно?",
        reply_markup=get_username_confirm_keyboard()
    )
    await state.set_state(UserStates.waiting_sub_username_confirm)

@dp.message(UserStates.waiting_sub_username_confirm, F.text)
async def process_username_confirm(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text == "✅ Да, верно":
        await show_premium_payment(message, state)
    elif message.text == "❌ Изменить получателя":
        await message.answer(
            "👤 Введите username получателя заново:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_username)
    else:
        await message.answer("❌ Пожалуйста, выберите действие из меню")

async def show_premium_payment(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    details = f"Тип: {'Со входом' if data['sub_type'] == 'with_login' else 'Подарочная'}\n"
    details += f"Период: {data['sub_period']}\n"
    
    if data['sub_type'] == 'with_login':
        details += f"Телефон: {data.get('sub_phone', 'Не указан')}\n"
        if data.get('sub_cloud_password'):
            details += f"🔐 Облачный пароль: {data['sub_cloud_password']}\n"
    else:
        details += f"Получатель: {data.get('sub_recipient', 'Не указан')}\n"
    
    await message.answer(
        f"📅 **Детали заказа:**\n\n"
        f"{details}\n"
        f"💰 Цена: {data['sub_price']:,} сум\n\n"
        f"Выберите способ оплаты:",
        parse_mode="Markdown",
        reply_markup=get_payment_keyboard()
    )

# ===================== ОПЛАТА =====================
@dp.callback_query(lambda c: c.data == "pay_humo")
async def show_humo_details(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        order_type = data.get('order_type')
        
        if not data:
            await callback.answer("❌ Данные не найдены!")
            return
        
        if order_type == "gold":
            amount_sums = data['amount_sums']
            details = f"Получите: {data['gold_amount']} голды"
        elif order_type == "bp":
            amount_sums = data['bp_price']
            details = f"Пакет: {data['bp_package']}\nID игры: {data.get('game_id', 'не указан')}"
        elif order_type == "stars":
            amount_sums = data['stars_price']
            details = f"Пакет: {data['stars_package']}\nПолучатель: {data.get('stars_recipient', 'не указан')}"
        elif order_type == "sub":
            amount_sums = data['sub_price']
            
            if data['sub_type'] == 'with_login':
                details = f"Тип: Со входом\nПериод: {data['sub_period']}\nТелефон: {data.get('sub_phone', 'Не указан')}"
                if data.get('sub_cloud_password'):
                    details += f"\n🔐 Пароль: {data['sub_cloud_password']}"
            else:
                details = f"Тип: Подарочная\nПериод: {data['sub_period']}\nПолучатель: {data.get('sub_recipient', 'Не указан')}"
        else:
            await callback.answer("❌ Ошибка данных")
            return
        
        payment_text = f"""
💳 **ОПЛАТА HUMO**

🏦 **Номер карты:** `{HUMO_CARD}`
👤 **Владелец:** {CARD_HOLDER}
💰 **Сумма:** {amount_sums:,} сум

📋 **Детали заказа:**
{details}

📋 **Инструкция:**
1️⃣ Переведите {amount_sums:,} сум на карту выше
2️⃣ Сделайте скриншот чека об оплате
3️⃣ Отправьте скриншот в этот чат

⚠️ После отправки чека ожидайте подтверждения администратора
"""
        
        await callback.message.edit_text(payment_text, parse_mode="Markdown")
        await state.set_state(UserStates.waiting_gold_receipt)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в pay_humo: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(lambda c: c.data == "pay_ton")
async def show_ton_details(callback: types.CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        order_type = data.get('order_type')
        
        if not data:
            await callback.answer("❌ Данные не найдены!")
            return
        
        if order_type == "gold":
            amount_sums = data['amount_sums']
            details = f"Получите: {data['gold_amount']} голды"
            ton_total = data['ton_total']
        elif order_type == "bp":
            amount_sums = data['bp_price']
            details = f"Пакет: {data['bp_package']}\nID игры: {data.get('game_id', 'не указан')}"
            ton_total = data['ton_total']
        elif order_type == "stars":
            amount_sums = data['stars_price']
            details = f"Пакет: {data['stars_package']}\nПолучатель: {data.get('stars_recipient', 'не указан')}"
            ton_total = data['ton_total']
        elif order_type == "sub":
            amount_sums = data['sub_price']
            ton_total = data['ton_total']
            
            if data['sub_type'] == 'with_login':
                details = f"Тип: Со входом\nПериод: {data['sub_period']}\nТелефон: {data.get('sub_phone', 'Не указан')}"
                if data.get('sub_cloud_password'):
                    details += f"\n🔐 Пароль: {data['sub_cloud_password']}"
            else:
                details = f"Тип: Подарочная\nПериод: {data['sub_period']}\nПолучатель: {data.get('sub_recipient', 'Не указан')}"
        else:
            await callback.answer("❌ Ошибка данных")
            return
        
        payment_text = f"""
💎 **ОПЛАТА TON**

💰 **Сумма:** {amount_sums:,} сум

📋 **Детали заказа:**
{details}

💎 **ИТОГ к оплате:** `{ton_total} TON`

🏦 **Адрес TON:** `{TON_WALLET}`

📋 **Инструкция:**
1️⃣ Переведите {ton_total} TON на адрес выше
2️⃣ Сделайте скриншот транзакции
3️⃣ Отправьте скриншот в этот чат

⚠️ После отправки чека ожидайте подтверждения администратора
"""
        
        await callback.message.edit_text(payment_text, parse_mode="Markdown")
        await state.set_state(UserStates.waiting_gold_receipt)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в pay_ton: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(lambda c: c.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Оплата отменена")
    await callback.message.answer("❌ Отменено", reply_markup=get_main_keyboard())
    await callback.answer()

# ===================== ПРИЕМ ЧЕКОВ =====================
@dp.message(UserStates.waiting_gold_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    try:
        data = await state.get_data()
        order_type = data.get('order_type')
        
        user_id = str(message.from_user.id)
        order_id = f"{order_type}_{int(time.time())}_{user_id[-4:]}"
        
        if order_type == "gold":
            orders_data = orders_gold
            orders_file = ORDERS_GOLD_FILE
            amount = data['gold_amount']
            details = f"Сумма: {data['amount_sums']:,} сум\nГолда: {amount}"
        elif order_type == "bp":
            orders_data = orders_bp
            orders_file = ORDERS_BP_FILE
            amount = data['bp_price']
            details = f"Пакет: {data['bp_package']}\nID игры: {data.get('game_id', 'не указан')}"
        elif order_type == "stars":
            orders_data = orders_stars
            orders_file = ORDERS_STARS_FILE
            amount = data['stars_price']
            details = f"Пакет: {data['stars_package']}\nПолучатель: {data.get('stars_recipient', 'не указан')}"
        elif order_type == "sub":
            orders_data = orders_subs
            orders_file = ORDERS_SUBS_FILE
            
            if data['sub_type'] == 'with_login':
                details = f"Тип: Со входом\nПериод: {data['sub_period']}\nТелефон: {data.get('sub_phone', 'Не указан')}"
                if data.get('sub_cloud_password'):
                    details += f"\n🔐 Пароль: {data['sub_cloud_password']}"
            else:
                details = f"Тип: Подарочная\nПериод: {data['sub_period']}\nПолучатель: {data.get('sub_recipient', 'Не указан')}"
            amount = data['sub_price']
        else:
            await message.answer("❌ Ошибка данных")
            await state.clear()
            return
        
        # Сохраняем заказ со статусом "pending" (ожидание подтверждения оплаты)
        orders_data[order_id] = {
            "user_id": user_id,
            "user_name": message.from_user.full_name,
            "username": message.from_user.username,
            "order_type": order_type,
            "amount": amount,
            "details": details,
            "data": data,
            "status": "pending",  # Ожидает подтверждения оплаты
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "receipt_file_id": message.photo[-1].file_id
        }
        save_data(orders_data, orders_file)
        
        # Отправляем админу
        caption = f"""
📦 **НОВЫЙ ЗАКАЗ #{order_type.upper()}**

👤 {message.from_user.full_name}
📱 @{message.from_user.username}
🆔 `{user_id}`

📋 **Детали:**
{details}

💰 Сумма: {amount:,} сум
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📋 ID: `{order_id}`

✅ Подтвердите оплату или отклоните заказ:
"""
        
        await bot.send_photo(
            ADMIN_ID,
            photo=message.photo[-1].file_id,
            caption=caption,
            parse_mode="Markdown",
            reply_markup=get_admin_order_keyboard(order_id, order_type)
        )
        
        await message.answer(
            "✅ Чек получен! Ожидайте подтверждения администратора.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_receipt: {e}")
        await message.answer("❌ Произошла ошибка")
        await state.clear()

# ===================== АДМИН: ПОДТВЕРЖДЕНИЕ ОПЛАТЫ =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('approve_'))
async def admin_approve_order(callback: types.CallbackQuery):
    """Подтверждение оплаты заказа администратором"""
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        # Формат: approve_{order_type}_{order_id}
        parts = callback.data.split("_")
        order_type = parts[1]
        order_id = "_".join(parts[2:])
        
        logger.info(f"Подтверждение оплаты заказа: type={order_type}, id={order_id}")
        
        # Определяем файл и данные заказа
        if order_type == "gold":
            orders_file = ORDERS_GOLD_FILE
            orders_data = orders_gold
        elif order_type == "bp":
            orders_file = ORDERS_BP_FILE
            orders_data = orders_bp
        elif order_type == "stars":
            orders_file = ORDERS_STARS_FILE
            orders_data = orders_stars
        elif order_type == "sub":
            orders_file = ORDERS_SUBS_FILE
            orders_data = orders_subs
        else:
            await callback.answer("❌ Неизвестный тип заказа!")
            return
        
        order = orders_data.get(order_id)
        if not order:
            await callback.answer("❌ Заказ не найден!")
            return
        
        # Обновляем статус на "awaiting_purchase" (ожидание покупки)
        order['status'] = "awaiting_purchase"
        order['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order['approved_by'] = str(ADMIN_ID)
        save_data(orders_data, orders_file)
        
        # Уведомляем пользователя - оплата подтверждена, ждем покупку
        user_id = order['user_id']
        try:
            if order_type == "gold":
                await bot.send_message(
                    user_id,
                    f"✅ **Оплата подтверждена!**\n\n"
                    f"💰 Ваш заказ на {order['data']['gold_amount']} голды принят в обработку\n"
                    f"📋 ID заказа: `{order_id}`\n\n"
                    f"⏳ Ожидайте, администратор скоро купит скин и отправит вам.\n"
                    f"Как только скин будет куплен, вы получите уведомление!",
                    parse_mode="Markdown"
                )
                
            elif order_type == "bp":
                await bot.send_message(
                    user_id,
                    f"✅ **Оплата подтверждена!**\n\n"
                    f"🎮 Заказ BP принят в обработку\n"
                    f"📋 ID заказа: `{order_id}`\n\n"
                    f"⏳ Ожидайте, администратор активирует BP и пришлет подтверждение.",
                    parse_mode="Markdown"
                )
                
            elif order_type == "stars":
                await bot.send_message(
                    user_id,
                    f"✅ **Оплата подтверждена!**\n\n"
                    f"⭐️ Заказ Stars принят в обработку\n"
                    f"📋 ID заказа: `{order_id}`\n\n"
                    f"⏳ Ожидайте, администратор отправит Stars получателю.",
                    parse_mode="Markdown"
                )
                
            elif order_type == "sub":
                sub_type_ru = "Со входом" if order['data']['sub_type'] == 'with_login' else "Подарочная"
                await bot.send_message(
                    user_id,
                    f"✅ **Оплата подтверждена!**\n\n"
                    f"📅 Заказ Telegram Premium принят в обработку\n"
                    f"Тип: {sub_type_ru}\n"
                    f"📋 ID заказа: `{order_id}`\n\n"
                    f"⏳ Ожидайте, администратор активирует подписку и пришлет подтверждение.",
                    parse_mode="Markdown"
                )
            
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")
        
        # Отправляем админу уведомление с кнопкой для завершения заказа
        await callback.message.answer(
            f"✅ **ОПЛАТА ПОДТВЕРЖДЕНА**\n\n"
            f"📋 ID заказа: `{order_id}`\n"
            f"📦 Тип: {order_type}\n"
            f"👤 Пользователь: {order['user_name']}\n\n"
            f"🛒 **Теперь нужно купить скин/товар и отправить пользователю!**\n\n"
            f"Нажмите кнопку ниже, когда купите товар:",
            parse_mode="Markdown",
            reply_markup=get_admin_complete_keyboard(order_id, order_type)
        )
        
        # Редактируем исходное сообщение
        try:
            # Пытаемся отредактировать сообщение с чеком
            if callback.message.photo:
                # Если это фото с подписью
                await callback.message.edit_caption(
                    caption=f"{callback.message.caption}\n\n✅ **ОПЛАТА ПОДТВЕРЖДЕНА**\n⏰ {datetime.now().strftime('%H:%M:%S')}\n\n➡️ **Ожидание покупки товара**",
                    reply_markup=None
                )
            elif callback.message.text:
                # Если это текстовое сообщение
                await callback.message.edit_text(
                    text=f"{callback.message.text}\n\n✅ **ОПЛАТА ПОДТВЕРЖДЕНА**\n⏰ {datetime.now().strftime('%H:%M:%S')}\n\n➡️ **Ожидание покупки товара**",
                    reply_markup=None
                )
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения: {e}")
        
        await callback.answer("✅ Оплата подтверждена!")
        
    except Exception as e:
        logger.error(f"Ошибка в admin_approve_order: {e}")
        await callback.answer("❌ Произошла ошибка")

# ===================== АДМИН: ОТКЛОНЕНИЕ ЗАКАЗА =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('reject_') and not c.data.startswith('reject_w_') and not c.data.startswith('reject_sub_'))
async def admin_reject_order(callback: types.CallbackQuery, state: FSMContext):
    """Отклонение заказа администратором"""
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        # Формат: reject_{order_type}_{order_id}
        parts = callback.data.split("_")
        order_type = parts[1]
        order_id = "_".join(parts[2:])
        
        # Сохраняем данные для ввода причины
        await state.update_data(
            reject_order_id=order_id,
            reject_order_type=order_type
        )
        
        await callback.message.answer(
            f"❓ **Укажите причину отклонения заказа**\n\n"
            f"📋 ID заказа: `{order_id}`\n\n"
            f"Отправьте сообщение с причиной или нажмите ❌ Отмена",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(UserStates.waiting_reject_reason)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_reject_order: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_reject_reason, F.text)
async def process_reject_reason(message: types.Message, state: FSMContext):
    """Обработка причины отклонения заказа"""
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Нет доступа!")
        await state.clear()
        return
    
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    order_id = data.get('reject_order_id')
    order_type = data.get('reject_order_type')
    reason = message.text
    
    # Определяем файл и данные заказа
    if order_type == "gold":
        orders_file = ORDERS_GOLD_FILE
        orders_data = orders_gold
    elif order_type == "bp":
        orders_file = ORDERS_BP_FILE
        orders_data = orders_bp
    elif order_type == "stars":
        orders_file = ORDERS_STARS_FILE
        orders_data = orders_stars
    elif order_type == "sub":
        orders_file = ORDERS_SUBS_FILE
        orders_data = orders_subs
    else:
        await message.answer("❌ Неизвестный тип заказа!")
        await state.clear()
        return
    
    order = orders_data.get(order_id)
    if not order:
        await message.answer("❌ Заказ не найден!")
        await state.clear()
        return
    
    # Обновляем статус
    order['status'] = "rejected"
    order['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    order['rejected_by'] = str(ADMIN_ID)
    order['reject_reason'] = reason
    save_data(orders_data, orders_file)
    
    # Уведомляем пользователя
    user_id = order['user_id']
    try:
        await bot.send_message(
            user_id,
            f"❌ **Заказ отклонен**\n\n"
            f"📋 ID заказа: `{order_id}`\n"
            f"📝 Причина: {reason}\n\n"
            f"📞 По вопросам обращайтесь к администратору {ADMIN_USERNAME}",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователя: {e}")
    
    await message.answer(
        f"✅ **Заказ отклонен!**\n\n"
        f"📋 ID: `{order_id}`\n"
        f"📝 Причина: {reason}\n"
        f"👤 Пользователь уведомлен.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

# ===================== АДМИН: ЗАВЕРШЕНИЕ ЗАКАЗА (ПОКУПКА ТОВАРА) =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('complete_'))
async def admin_complete_order(callback: types.CallbackQuery, state: FSMContext):
    """Завершение заказа - админ купил товар и отправляет подтверждение"""
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        # Формат: complete_{order_type}_{order_id}
        parts = callback.data.split("_")
        order_type = parts[1]
        order_id = "_".join(parts[2:])
        
        logger.info(f"Завершение заказа: type={order_type}, id={order_id}")
        
        # Определяем файл и данные заказа
        if order_type == "gold":
            orders_file = ORDERS_GOLD_FILE
            orders_data = orders_gold
        elif order_type == "bp":
            orders_file = ORDERS_BP_FILE
            orders_data = orders_bp
        elif order_type == "stars":
            orders_file = ORDERS_STARS_FILE
            orders_data = orders_stars
        elif order_type == "sub":
            orders_file = ORDERS_SUBS_FILE
            orders_data = orders_subs
        else:
            await callback.answer("❌ Неизвестный тип заказа!")
            return
        
        order = orders_data.get(order_id)
        if not order:
            await callback.answer("❌ Заказ не найден!")
            return
        
        # Сохраняем данные в state
        await state.update_data(
            complete_order_id=order_id,
            complete_order_type=order_type,
            complete_order_data=order
        )
        
        # Удаляем сообщение с кнопкой
        await callback.message.delete()
        
        # Отправляем запрос на фото
        await callback.message.answer(
            f"📸 **Отправьте фото подтверждения**\n\n"
            f"📋 Заказ: `{order_id}`\n"
            f"📦 Тип: {order_type}\n\n"
            f"Отправьте фото/скриншот, подтверждающий покупку/активацию товара.\n"
            f"Это фото будет отправлено пользователю.",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(UserStates.waiting_skin_photo)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в admin_complete_order: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_skin_photo, F.photo)
async def process_complete_photo(message: types.Message, state: FSMContext):
    """Обработка фото подтверждения от админа и завершение заказа"""
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Нет доступа!")
        await state.clear()
        return
    
    data = await state.get_data()
    order_id = data.get('complete_order_id')
    order_type = data.get('complete_order_type')
    order = data.get('complete_order_data')
    
    if not order:
        await message.answer("❌ Данные заказа не найдены!")
        await state.clear()
        return
    
    user_id = order['user_id']
    
    try:
        # Определяем файл для сохранения
        if order_type == "gold":
            orders_file = ORDERS_GOLD_FILE
            orders_data = orders_gold
            
            # Начисляем голду пользователю
            gold_amount = order['data']['gold_amount']
            if user_id in users:
                users[user_id]['balance'] = users[user_id].get('balance', 0) + gold_amount
                users[user_id]['orders_count'] = users[user_id].get('orders_count', 0) + 1
                save_data(users, USERS_FILE)
            
            # Отправляем фото пользователю
            await bot.send_photo(
                user_id,
                photo=message.photo[-1].file_id,
                caption=f"✅ **Заказ выполнен!**\n\n"
                        f"💰 Вам начислено {gold_amount} голды\n"
                        f"📋 ID заказа: `{order_id}`\n\n"
                        f"Спасибо за покупку! 🙏",
                parse_mode="Markdown"
            )
            
        elif order_type == "bp":
            orders_file = ORDERS_BP_FILE
            orders_data = orders_bp
            
            await bot.send_photo(
                user_id,
                photo=message.photo[-1].file_id,
                caption=f"✅ **Заказ BP выполнен!**\n\n"
                        f"🎮 {order['data']['bp_package']}\n"
                        f"🆔 ID в игре: {order['data'].get('game_id', 'Не указан')}\n"
                        f"📋 ID заказа: `{order_id}`\n\n"
                        f"Спасибо за покупку! 🙏",
                parse_mode="Markdown"
            )
            
        elif order_type == "stars":
            orders_file = ORDERS_STARS_FILE
            orders_data = orders_stars
            
            await bot.send_photo(
                user_id,
                photo=message.photo[-1].file_id,
                caption=f"✅ **Заказ Stars выполнен!**\n\n"
                        f"⭐️ {order['data']['stars_package']}\n"
                        f"👤 Получатель: {order['data'].get('stars_recipient', 'Не указан')}\n"
                        f"📋 ID заказа: `{order_id}`\n\n"
                        f"Спасибо за покупку! 🙏",
                parse_mode="Markdown"
            )
            
        elif order_type == "sub":
            orders_file = ORDERS_SUBS_FILE
            orders_data = orders_subs
            sub_type_ru = "Со входом" if order['data']['sub_type'] == 'with_login' else "Подарочная"
            
            await bot.send_photo(
                user_id,
                photo=message.photo[-1].file_id,
                caption=f"✅ **Заказ Telegram Premium выполнен!**\n\n"
                        f"📅 Тип: {sub_type_ru}\n"
                        f"⏱️ {order['data']['sub_period']}\n"
                        f"📋 ID заказа: `{order_id}`\n\n"
                        f"Спасибо за покупку! 🙏",
                parse_mode="Markdown"
            )
        
        # Предлагаем оставить отзыв
        await bot.send_message(
            user_id,
            "📝 **Оставить отзыв?**",
            reply_markup=get_leave_review_keyboard(order_id, order_type)
        )
        
        # Обновляем статус заказа
        order['status'] = "completed"
        order['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        order['completed_by'] = str(ADMIN_ID)
        order['completion_photo'] = message.photo[-1].file_id
        save_data(orders_data, orders_file)
        
        await message.answer(
            f"✅ **Заказ успешно завершен!**\n\n"
            f"📋 ID: `{order_id}`\n"
            f"👤 Пользователь уведомлен.\n"
            f"💰 Голда начислена (для gold заказов).",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка завершения заказа: {e}")
        await message.answer("❌ Не удалось завершить заказ")
    
    await state.clear()

@dp.message(UserStates.waiting_skin_photo, F.text)
async def process_complete_photo_text(message: types.Message, state: FSMContext):
    """Обработка текста вместо фото"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await message.answer("❌ Пожалуйста, отправьте фото, а не текст")

# ===================== АДМИН: ЧАТ ДЛЯ PREMIUM =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('start_chat_'))
async def admin_start_chat(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        order_id = callback.data.split("_")[2]
        order = orders_subs.get(order_id)
        
        if not order:
            await callback.answer("❌ Заказ не найден!")
            return
        
        order['status'] = "in_progress"
        order['admin_started_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data(orders_subs, ORDERS_SUBS_FILE)
        
        user_id = order['user_id']
        active_chats[user_id] = {
            "order_id": order_id,
            "active": True,
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            await bot.send_message(
                user_id,
                f"✅ **Администратор в сети!**\n\n"
                f"👤 {ADMIN_USERNAME} готов помочь с вашим заказом.\n\n"
                f"📋 ID заказа: `{order_id}`\n\n"
                f"💬 Теперь вы можете общаться с администратором напрямую.\n"
                f"Просто отправьте сообщение в этот чат.\n\n"
                f"⚠️ Во время чата вы можете только отправлять сообщения.",
                parse_mode="Markdown",
                reply_markup=get_chat_keyboard()
            )
        except Exception as e:
            logger.error(f"Ошибка уведомления пользователя: {e}")
        
        # Редактируем сообщение админа
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=f"{callback.message.caption}\n\n✅ **ЧАТ АКТИВИРОВАН**\n⏰ {datetime.now().strftime('%H:%M:%S')}",
                    reply_markup=None
                )
            else:
                await callback.message.edit_text(
                    text=f"{callback.message.text}\n\n✅ **ЧАТ АКТИВИРОВАН**\n⏰ {datetime.now().strftime('%H:%M:%S')}",
                    reply_markup=None
                )
        except:
            pass
        
        # Отправляем админу кнопку для завершения чата
        await bot.send_message(
            ADMIN_ID,
            f"💬 **Активный чат** с пользователем {order['user_name']}\n"
            f"📋 Заказ: `{order_id}`\n\n"
            f"Нажмите кнопку ниже, чтобы завершить чат:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔚 Завершить заказ", callback_data=f"end_chat_{user_id}_{order_id}")]
            ])
        )
        
        await callback.answer("✅ Чат с пользователем активирован!")
    except Exception as e:
        logger.error(f"Ошибка в admin_start_chat: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(lambda c: c.data and c.data.startswith('end_chat_'))
async def admin_end_chat_confirm(callback: types.CallbackQuery, state: FSMContext):
    """Админ нажимает завершить чат - показываем подтверждение"""
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        parts = callback.data.split("_")
        user_id = parts[2]
        order_id = parts[3]
        
        # Сохраняем данные для подтверждения
        await state.update_data(
            end_chat_user_id=user_id,
            end_chat_order_id=order_id
        )
        
        await callback.message.answer(
            f"❓ **Вы точно хотите завершить чат?**\n\n"
            f"👤 Пользователь: {user_id}\n"
            f"📋 Заказ: `{order_id}`\n\n"
            f"Выберите действие:",
            parse_mode="Markdown",
            reply_markup=get_chat_end_confirm_keyboard()
        )
        await state.set_state(UserStates.waiting_chat_end_confirm)
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_end_chat_confirm: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_chat_end_confirm, F.text)
async def process_chat_end_confirm(message: types.Message, state: FSMContext):
    """Обработка подтверждения завершения чата"""
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Нет доступа!")
        await state.clear()
        return
    
    data = await state.get_data()
    user_id = data.get('end_chat_user_id')
    order_id = data.get('end_chat_order_id')
    
    if message.text == "✅ Да, завершить чат":
        # Завершаем чат
        if user_id in active_chats:
            chat_info = active_chats.pop(user_id)
            
            # Обновляем статус заказа
            if order_id in orders_subs:
                orders_subs[order_id]['status'] = "completed"
                orders_subs[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_data(orders_subs, ORDERS_SUBS_FILE)
            
            # Уведомляем пользователя
            try:
                await bot.send_message(
                    user_id,
                    f"✅ **Чат завершен администратором.**\n\n"
                    f"Спасибо за покупку! 🙏\n"
                    f"📋 Заказ: `{order_id}`\n\n"
                    f"Вы можете продолжить покупки в главном меню.",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard()
                )
                
                # Предлагаем оставить отзыв
                await bot.send_message(
                    user_id,
                    "📝 **Оставить отзыв?**",
                    reply_markup=get_leave_review_keyboard(order_id, "sub")
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления пользователя: {e}")
            
            await message.answer(
                f"✅ **Чат успешно завершен!**\n\n"
                f"👤 Пользователь уведомлен.\n"
                f"📋 Заказ: `{order_id}`",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer("❌ Чат уже неактивен")
    
    elif message.text == "❌ Нет, продолжить общение":
        await message.answer(
            "✅ Продолжаем общение с пользователем.\n"
            "Все сообщения будут пересылаться.",
            reply_markup=get_chat_keyboard()
        )
    
    await state.clear()

@dp.callback_query(lambda c: c.data and c.data.startswith('reject_sub_'))
async def admin_reject_sub(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        order_id = callback.data.split("_")[2]
        order = orders_subs.get(order_id)
        
        if order:
            order['status'] = "rejected"
            order['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_data(orders_subs, ORDERS_SUBS_FILE)
            
            try:
                await bot.send_message(
                    order['user_id'],
                    f"❌ **Заказ отклонен**\n\n"
                    f"📋 ID заказа: `{order_id}`\n"
                    f"👤 Администратор: {ADMIN_USERNAME}\n\n"
                    f"📞 По вопросам обращайтесь к администратору"
                )
            except:
                pass
        
        # Редактируем сообщение
        try:
            if callback.message.photo:
                await callback.message.edit_caption(
                    caption=f"{callback.message.caption}\n\n❌ **ЗАКАЗ ОТКЛОНЕН**",
                    reply_markup=None
                )
            else:
                await callback.message.edit_text(
                    text=f"{callback.message.text}\n\n❌ **ЗАКАЗ ОТКЛОНЕН**",
                    reply_markup=None
                )
        except:
            pass
        
        await callback.answer("❌ Заказ отклонен!")
    except Exception as e:
        logger.error(f"Ошибка в admin_reject_sub: {e}")
        await callback.answer("❌ Произошла ошибка")

# ===================== АДМИН: ВЫВОД ГОЛДЫ =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('buy_skin_'))
async def admin_buy_skin(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        withdrawal_id = callback.data.split("_")[2]
        withdrawal = withdrawals.get(withdrawal_id)
        
        if not withdrawal:
            await callback.answer("❌ Заявка не найдена!")
            return
        
        withdrawal['status'] = "admin_buying"
        withdrawal['admin_started_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        # Редактируем сообщение
        try:
            await callback.message.edit_text(
                text=f"{callback.message.text}\n\n🛒 **АДМИН ПОКУПАЕТ СКИН**\n⏰ {datetime.now().strftime('%H:%M:%S')}",
                reply_markup=None
            )
        except:
            pass
        
        await callback.message.answer(
            "✅ Отметьте, когда купите скин у покупателя:",
            reply_markup=get_admin_skin_purchased_keyboard(withdrawal_id)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_buy_skin: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(lambda c: c.data and c.data.startswith('skin_purchased_'))
async def admin_skin_purchased(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        withdrawal_id = callback.data.split("_")[2]
        withdrawal = withdrawals.get(withdrawal_id)
        
        if not withdrawal:
            await callback.answer("❌ Заявка не найдена!")
            return
        
        withdrawal['status'] = "skin_sent_to_buyer"
        withdrawal['skin_purchased_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        await callback.message.answer(
            "📸 Отправьте фото скина:",
            reply_markup=get_admin_ready_for_photo_keyboard(withdrawal_id)
        )
        
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_skin_purchased: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(lambda c: c.data and c.data.startswith('send_skin_'))
async def admin_send_skin(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        withdrawal_id = callback.data.split("_")[2]
        withdrawal = withdrawals.get(withdrawal_id)
        
        if not withdrawal:
            await callback.answer("❌ Заявка не найдена!")
            return
        
        await state.update_data(skin_withdrawal_id=withdrawal_id)
        
        await callback.message.answer(
            "📸 Отправьте фото скина (как подтверждение):",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state("waiting_skin_photo")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в admin_send_skin: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.message(F.photo, lambda message: message.state == "waiting_skin_photo")
async def process_skin_photo(message: types.Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ Нет доступа!")
        await state.clear()
        return
    
    data = await state.get_data()
    withdrawal_id = data.get('skin_withdrawal_id')
    withdrawal = withdrawals.get(withdrawal_id)
    
    if not withdrawal:
        await message.answer("❌ Заявка не найдена!")
        await state.clear()
        return
    
    user_id = withdrawal['user_id']
    
    try:
        # Отправляем фото пользователю
        await bot.send_photo(
            user_id,
            photo=message.photo[-1].file_id,
            caption=f"✅ **Скин куплен!**\n\n"
                    f"💰 Сумма: {withdrawal['amount']} голды\n"
                    f"📋 ID: `{withdrawal_id}`\n\n"
                    f"Спасибо за покупку! 🙏",
            parse_mode="Markdown"
        )
        
        # Предлагаем оставить отзыв
        await bot.send_message(
            user_id,
            "📝 **Оставить отзыв?**",
            reply_markup=get_leave_review_keyboard(withdrawal_id, "withdrawal")
        )
        
        # Обновляем статус
        withdrawal['status'] = "completed"
        withdrawal['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        # Списание голды с баланса
        if user_id in users:
            users[user_id]['balance'] = users[user_id].get('balance', 0) - withdrawal['amount']
            users[user_id]['orders_count'] = users[user_id].get('orders_count', 0) + 1
            save_data(users, USERS_FILE)
        
        await message.answer(
            f"✅ **Скин отправлен пользователю!**\n\n"
            f"💰 Сумма: {withdrawal['amount']} голды\n"
            f"📋 ID: `{withdrawal_id}`",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки скина: {e}")
        await message.answer("❌ Не удалось отправить фото пользователю")
    
    await state.clear()

@dp.callback_query(lambda c: c.data and c.data.startswith('reject_w_'))
async def admin_reject_withdrawal(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        withdrawal_id = callback.data.split("_")[2]
        withdrawal = withdrawals.get(withdrawal_id)
        
        if withdrawal:
            withdrawal['status'] = "rejected"
            withdrawal['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_data(withdrawals, WITHDRAWALS_FILE)
            
            try:
                await bot.send_message(
                    withdrawal['user_id'],
                    f"❌ **Заявка на вывод отклонена**\n\n"
                    f"💰 Сумма: {withdrawal['amount']} голды\n"
                    f"📋 ID: `{withdrawal_id}`\n\n"
                    f"📞 По вопросам обращайтесь к администратору"
                )
            except:
                pass
        
        # Редактируем сообщение
        try:
            await callback.message.edit_text(
                text=f"{callback.message.text}\n\n❌ **ЗАЯВКА ОТКЛОНЕНА**",
                reply_markup=None
            )
        except:
            pass
        
        await callback.answer("❌ Заявка отклонена!")
    except Exception as e:
        logger.error(f"Ошибка в admin_reject_withdrawal: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.callback_query(lambda c: c.data and c.data.startswith('skin_problem_'))
async def admin_skin_problem(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    try:
        withdrawal_id = callback.data.split("_")[2]
        withdrawal = withdrawals.get(withdrawal_id)
        
        if withdrawal:
            withdrawal['status'] = "problem"
            withdrawal['problem_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_data(withdrawals, WITHDRAWALS_FILE)
        
        # Редактируем сообщение
        try:
            await callback.message.edit_text(
                text=f"{callback.message.text}\n\n⚠️ **ПРОБЛЕМА С ЗАЯВКОЙ**\n⏰ {datetime.now().strftime('%H:%M:%S')}",
                reply_markup=None
            )
        except:
            pass
        
        await callback.answer("⚠️ Проблема отмечена")
    except Exception as e:
        logger.error(f"Ошибка в admin_skin_problem: {e}")
        await callback.answer("❌ Произошла ошибка")

# ===================== ОБРАБОТКА ОТЗЫВОВ =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('leave_review_'))
async def leave_review_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало процесса оставления отзыва"""
    try:
        # Формат: leave_review_{order_type}_{order_id}
        parts = callback.data.split("_")
        order_type = parts[2]
        order_id = "_".join(parts[3:])
        
        user_id = str(callback.from_user.id)
        
        # Сохраняем данные отзыва
        await state.update_data(
            review_order_id=order_id,
            review_order_type=order_type
        )
        
        await callback.message.answer(
            "📝 **Оставьте отзыв**\n\n"
            "Отправьте фото с отзывом (необязательно) или сразу напишите текст отзыва.\n\n"
            "Вы можете отправить:\n"
            "• 📸 Фото (с подписью или без)\n"
            "• ✏️ Текстовый отзыв\n\n"
            "Нажмите ❌ Отмена для выхода",
            parse_mode="Markdown",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(UserStates.waiting_review_photo)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в leave_review_start: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_review_photo, F.photo)
async def process_review_photo(message: types.Message, state: FSMContext):
    """Обработка фото для отзыва"""
    try:
        # Сохраняем фото
        photo = message.photo[-1].file_id
        caption = message.caption or ""
        
        await state.update_data(
            review_photo=photo,
            review_caption=caption
        )
        
        await message.answer(
            "📝 Теперь напишите текст отзыва:",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(UserStates.waiting_review_text)
        
    except Exception as e:
        logger.error(f"Ошибка в process_review_photo: {e}")
        await message.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_review_photo, F.text)
async def process_review_photo_skip(message: types.Message, state: FSMContext):
    """Пропуск фото и переход к тексту отзыва"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(review_photo=None)
    
    await message.answer(
        "📝 Напишите текст отзыва:",
        reply_markup=get_cancel_keyboard()
    )
    
    await state.set_state(UserStates.waiting_review_text)

@dp.message(UserStates.waiting_review_text, F.text)
async def process_review_text(message: types.Message, state: FSMContext):
    """Обработка текста отзыва"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    review_photo = data.get('review_photo')
    review_caption = data.get('review_caption', '')
    order_id = data.get('review_order_id')
    order_type = data.get('review_order_type')
    
    user_id = str(message.from_user.id)
    review_text = message.text
    
    # Сохраняем отзыв
    review_id = f"review_{int(time.time())}_{user_id[-4:]}"
    reviews[review_id] = {
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": message.from_user.username,
        "order_id": order_id,
        "order_type": order_type,
        "text": review_text,
        "photo": review_photo,
        "photo_caption": review_caption,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_data(reviews, REVIEWS_FILE)
    
    # Обновляем статистику пользователя
    if user_id in users:
        users[user_id]['reviews_count'] = users[user_id].get('reviews_count', 0) + 1
        save_data(users, USERS_FILE)
    
    # Отправляем админу
    review_caption_text = f"\n📝 Подпись к фото: {review_caption}" if review_caption else ""
    
    if review_photo:
        await bot.send_photo(
            ADMIN_ID,
            photo=review_photo,
            caption=f"📝 **НОВЫЙ ОТЗЫВ**\n\n"
                    f"👤 {message.from_user.full_name}\n"
                    f"📱 @{message.from_user.username}\n"
                    f"📋 Заказ: {order_type} | {order_id}\n\n"
                    f"💬 {review_text}{review_caption_text}",
            parse_mode="Markdown"
        )
    else:
        await bot.send_message(
            ADMIN_ID,
            f"📝 **НОВЫЙ ОТЗЫВ**\n\n"
            f"👤 {message.from_user.full_name}\n"
            f"📱 @{message.from_user.username}\n"
            f"📋 Заказ: {order_type} | {order_id}\n\n"
            f"💬 {review_text}",
            parse_mode="Markdown"
        )
    
    await message.answer(
        "✅ **Спасибо за отзыв!** 🙏",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

# ===================== ПЕРЕСЫЛКА СООБЩЕНИЙ В ЧАТЕ =====================
@dp.message(F.text | F.photo | F.document)
async def forward_messages(message: types.Message, state: FSMContext):
    """Пересылает сообщения между пользователем и админом в активном чате"""
    try:
        user_id = str(message.from_user.id)
        
        # Проверяем, находится ли пользователь в состоянии ввода
        current_state = await state.get_state()
        if current_state and current_state not in [None, UserStates.waiting_chat_end_confirm]:
            # Если пользователь в процессе заполнения формы - игнорируем
            return
        
        # ========== ПОЛЬЗОВАТЕЛЬ -> АДМИН ==========
        if user_id != str(ADMIN_ID) and user_id in active_chats:
            chat_info = active_chats[user_id]
            
            # Блокируем команды
            if message.text in ["/start", "💰 Мой баланс", "💸 Вывести голду", 
                               "📋 Мои заказы", "🆘 Поддержка", "🟡 Купить голду", "🎫 Купить BP",
                               "⭐️ Telegram Stars", "📅 Telegram Premium"]:
                await message.answer(
                    "❌ Во время чата с администратором нельзя использовать команды.\n"
                    "Вы можете только отправлять сообщения.",
                    reply_markup=get_chat_keyboard()
                )
                return
            
            if message.text == "🏠 Главное меню":
                await message.answer(
                    "🏠 **Главное меню**\n\n"
                    "💬 Вы все еще в чате с администратором!\n"
                    "Ваши сообщения продолжают пересылаться.\n\n"
                    "📌 Чтобы вернуться в чат - просто напишите сообщение.",
                    parse_mode="Markdown",
                    reply_markup=get_chat_keyboard()
                )
                return
            
            # Пересылаем сообщение админу
            try:
                if message.text:
                    await bot.send_message(
                        ADMIN_ID,
                        f"💬 **Сообщение от пользователя**\n"
                        f"👤 {message.from_user.full_name}\n"
                        f"📱 @{message.from_user.username}\n"
                        f"🆔 `{user_id}`\n"
                        f"📋 Заказ: `{chat_info['order_id']}`\n\n"
                        f"{message.text}",
                        parse_mode="Markdown"
                    )
                    await message.answer("✅ Сообщение отправлено администратору!")
                    
                elif message.photo:
                    await bot.send_photo(
                        ADMIN_ID,
                        photo=message.photo[-1].file_id,
                        caption=f"💬 **Фото от пользователя**\n"
                                f"👤 {message.from_user.full_name}\n"
                                f"📱 @{message.from_user.username}\n"
                                f"🆔 `{user_id}`\n"
                                f"📋 Заказ: `{chat_info['order_id']}`\n\n"
                                f"{message.caption or ''}",
                        parse_mode="Markdown"
                    )
                    await message.answer("✅ Фото отправлено администратору!")
                    
                elif message.document:
                    await bot.send_document(
                        ADMIN_ID,
                        document=message.document.file_id,
                        caption=f"💬 **Документ от пользователя**\n"
                                f"👤 {message.from_user.full_name}\n"
                                f"📱 @{message.from_user.username}\n"
                                f"🆔 `{user_id}`\n"
                                f"📋 Заказ: `{chat_info['order_id']}`\n\n"
                                f"{message.caption or ''}",
                        parse_mode="Markdown"
                    )
                    await message.answer("✅ Документ отправлен администратору!")
                
            except Exception as e:
                logger.error(f"Ошибка пересылки сообщения: {e}")
                await message.answer("❌ Не удалось отправить сообщение администратору")
        
        # ========== АДМИН -> ПОЛЬЗОВАТЕЛЬ ==========
        elif user_id == str(ADMIN_ID):
            
            # Админ отвечает на сообщение
            if message.reply_to_message:
                reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
                user_id_match = re.search(r'🆔 `(\d+)`', reply_text)
                
                if user_id_match:
                    target_user_id = user_id_match.group(1)
                    
                    if target_user_id in active_chats:
                        try:
                            if message.text:
                                await bot.send_message(
                                    target_user_id,
                                    f"💬 **Ответ администратора:**\n\n{message.text}",
                                    parse_mode="Markdown"
                                )
                                await message.answer("✅ Сообщение отправлено пользователю!")
                                
                            elif message.photo:
                                await bot.send_photo(
                                    target_user_id,
                                    photo=message.photo[-1].file_id,
                                    caption=f"💬 **Ответ администратора:**\n\n{message.caption or ''}",
                                    parse_mode="Markdown"
                                )
                                await message.answer("✅ Фото отправлено пользователю!")
                                
                            elif message.document:
                                await bot.send_document(
                                    target_user_id,
                                    document=message.document.file_id,
                                    caption=f"💬 **Ответ администратора:**\n\n{message.caption or ''}",
                                    parse_mode="Markdown"
                                )
                                await message.answer("✅ Документ отправлено пользователю!")
                            
                        except Exception as e:
                            logger.error(f"Ошибка отправки ответа пользователю: {e}")
                            await message.answer("❌ Не удалось отправить сообщение пользователю")
                    else:
                        await message.answer("❌ Чат с этим пользователем не активен")
            
            # Админ пишет просто текст - показываем список активных чатов
            elif message.text and message.text not in ["❌ Отмена", "🏠 Главное меню"]:
                if active_chats:
                    chat_list = "📋 **Активные чаты:**\n\n"
                    for uid, chat_info in active_chats.items():
                        user_info = users.get(uid, {})
                        user_name = user_info.get('full_name', 'Неизвестно')
                        username = user_info.get('username', 'Нет')
                        
                        chat_list += f"👤 {user_name}\n"
                        chat_list += f"📱 @{username}\n"
                        chat_list += f"🆔 `{uid}`\n"
                        chat_list += f"📋 Заказ: `{chat_info['order_id']}`\n\n"
                    
                    chat_list += "💡 **Чтобы написать пользователю:**\n"
                    chat_list += "1️⃣ Нажмите «Ответить» на его сообщение\n"
                    
                    await message.answer(chat_list, parse_mode="Markdown")
                else:
                    await message.answer("📭 Нет активных чатов")
    
    except Exception as e:
        logger.error(f"Ошибка в forward_messages: {e}")

@dp.callback_query(lambda c: c.data == "cancel")
async def cancel_callback(callback: types.CallbackQuery):
    """Отмена действия"""
    await callback.message.delete()
    await callback.answer("❌ Отменено")

# ===================== ОБРАБОТКА ОТМЕНЫ =====================
@dp.message(F.text == "❌ Отмена")
async def cancel_handler(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats and user_id != str(ADMIN_ID):
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.\n"
            "Вы можете только отправлять сообщения.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await state.clear()
    await message.answer("❌ Отменено", reply_markup=get_main_keyboard())

@dp.message(F.text == "🏠 Главное меню")
async def main_menu_handler(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats and user_id != str(ADMIN_ID):
        await message.answer(
            "🏠 **Главное меню**\n\n"
            "💬 Вы все еще в чате с администратором!\n"
            "Ваши сообщения продолжают пересылаться.\n\n"
            "📌 Чтобы вернуться в чат - просто напишите сообщение.",
            parse_mode="Markdown",
            reply_markup=get_chat_keyboard()
        )
        return
    
    await state.clear()
    await start_cmd(message)

@dp.message()
async def handle_unknown(message: types.Message, state: FSMContext):
    """Обработка неизвестных сообщений"""
    user_id = str(message.from_user.id)
    
    if user_id in active_chats and user_id != str(ADMIN_ID):
        await forward_messages(message, state)
        return
    
    if user_id == str(ADMIN_ID):
        await forward_messages(message, state)
        return
    
    if message.text and message.text not in ["❌ Отмена", "🏠 Главное меню"]:
        await message.answer(
            "🤖 Используйте кнопки меню ниже ⬇️\n"
            "Или нажмите /start для перезапуска",
            reply_markup=get_main_keyboard()
        )

# ===================== ЗАПУСК БОТА =====================
async def main():
    """Основная функция запуска бота"""
    logger.info("🚀 Запускаю Gold Bot...")
    
    for file in [USERS_FILE, ORDERS_GOLD_FILE, ORDERS_BP_FILE, 
                 ORDERS_STARS_FILE, ORDERS_SUBS_FILE, WITHDRAWALS_FILE, REVIEWS_FILE]:
        if not os.path.exists(file):
            save_data({}, file)
            logger.info(f"📁 Создан файл: {file}")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удален")
        
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        raise e

# ===================== ЗАПУСК ВСЕГО =====================
if __name__ == "__main__":
    try:
        print("=" * 50)
        print("🚀 GOLD BOT - ЗАПУСК")
        print("=" * 50)
        
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("✅ Flask запущен для пинга")
        
        time.sleep(2)
        
        print("🤖 Запускаю Telegram бота...")
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n❌ Бот остановлен пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("=" * 50)
        print("🛑 Бот завершил работу")
        print("=" * 50)
