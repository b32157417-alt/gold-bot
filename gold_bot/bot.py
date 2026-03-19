#!/usr/bin/env python3
""" 
GOLD BOT - ИСПРАВЛЕННАЯ ВЕРСИЯ
С СТАТИСТИКОЙ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ И АДМИНА
И ИСПРАВЛЕННЫМИ ОТЗЫВАМИ
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
from datetime import datetime, timedelta
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
STATS_FILE = "stats.json"

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
    
    # Отзывы (НОВЫЕ СОСТОЯНИЯ)
    waiting_review_choice = State()           # Выбор типа отзыва
    waiting_review_photo = State()            # Ожидание фото
    waiting_review_text = State()             # Ожидание текста
    waiting_review_both_photo = State()       # Фото для отзыва с текстом
    waiting_review_both_text = State()        # Текст для отзыва с фото
    
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

# ===================== НОВЫЕ ФУНКЦИИ СТАТИСТИКИ =====================

def init_stats():
    """Инициализация статистики"""
    if not os.path.exists(STATS_FILE):
        stats = {
            "total_users": 0,
            "total_orders": 0,
            "total_revenue": 0,
            "total_profit": 0,
            "total_reviews": 0,
            "daily": {},
            "monthly": {},
            "orders_by_type": {
                "gold": 0,
                "bp": 0,
                "stars": 0,
                "sub": 0,
                "withdrawal": 0
            },
            "orders_by_status": {
                "pending": 0,
                "awaiting_purchase": 0,
                "completed": 0,
                "rejected": 0
            }
        }
        save_data(stats, STATS_FILE)
    return load_data(STATS_FILE)

def update_user_stats(user_id, action, data=None):
    """Обновление статистики пользователя"""
    if user_id not in users:
        return
    
    user = users[user_id]
    
    # Инициализируем stats если нет
    if "stats" not in user:
        user["stats"] = {
            "total_orders": 0,
            "total_spent_sums": 0,
            "total_deposited_sums": 0,
            "total_gold_earned": 0,
            "total_gold_spent": 0,
            "total_bonus_received": 0,
            "reviews_left": 0,
            "orders_by_type": {
                "gold": 0,
                "bp": 0,
                "stars": 0,
                "premium": 0,
                "withdrawal": 0
            },
            "last_orders": []
        }
    
    # Обновляем в зависимости от действия
    if action == "order_created":
        user["stats"]["total_orders"] += 1
        if data and "type" in data:
            if data["type"] in user["stats"]["orders_by_type"]:
                user["stats"]["orders_by_type"][data["type"]] += 1
        
        # Добавляем в историю последних заказов
        if len(user["stats"]["last_orders"]) >= 10:
            user["stats"]["last_orders"] = user["stats"]["last_orders"][-9:]
        
        user["stats"]["last_orders"].append({
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": data.get("type", "unknown"),
            "amount": data.get("amount", 0),
            "status": "pending"
        })
    
    elif action == "order_completed":
        if data and "amount" in data:
            user["stats"]["total_spent_sums"] += data["amount"]
        
        # Обновляем статус в истории
        for order in user["stats"]["last_orders"]:
            if order.get("date") == data.get("date"):
                order["status"] = "completed"
                break
    
    elif action == "deposit":
        if data and "amount" in data:
            user["stats"]["total_deposited_sums"] += data["amount"]
        if data and "gold" in data:
            user["stats"]["total_gold_earned"] += data["gold"]
    
    elif action == "withdrawal":
        if data and "gold" in data:
            user["stats"]["total_gold_spent"] += data["gold"]
    
    elif action == "bonus":
        if data and "amount" in data:
            user["stats"]["total_bonus_received"] += data["amount"]
    
    elif action == "review":
        user["stats"]["reviews_left"] += 1
    
    user["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(users, USERS_FILE)

def update_global_stats(order_data):
    """Обновление глобальной статистики"""
    stats = load_data(STATS_FILE)
    
    today = datetime.now().strftime("%Y-%m-%d")
    month = datetime.now().strftime("%Y-%m")
    
    # Инициализируем сегодняшнюю статистику
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "new_users": 0,
            "orders": 0,
            "revenue": 0,
            "profit": 0,
            "reviews": 0
        }
    
    # Инициализируем месячную статистику
    if month not in stats["monthly"]:
        stats["monthly"][month] = {
            "new_users": 0,
            "orders": 0,
            "revenue": 0,
            "profit": 0
        }
    
    # Обновляем счетчики
    if order_data.get("type") == "new_user":
        stats["total_users"] += 1
        stats["daily"][today]["new_users"] += 1
        stats["monthly"][month]["new_users"] += 1
    
    elif order_data.get("type") in ["gold", "bp", "stars", "sub"]:
        stats["total_orders"] += 1
        stats["daily"][today]["orders"] += 1
        stats["monthly"][month]["orders"] += 1
        
        if "amount" in order_data:
            stats["total_revenue"] += order_data["amount"]
            stats["daily"][today]["revenue"] += order_data["amount"]
            stats["monthly"][month]["revenue"] += order_data["amount"]
        
        if order_data.get("type") in stats["orders_by_type"]:
            stats["orders_by_type"][order_data["type"]] += 1
        
        if order_data.get("status") in stats["orders_by_status"]:
            stats["orders_by_status"][order_data["status"]] += 1
    
    elif order_data.get("type") == "review":
        stats["total_reviews"] += 1
        stats["daily"][today]["reviews"] += 1
    
    save_data(stats, STATS_FILE)

def get_user_stats(user_id):
    """Получение статистики пользователя"""
    if user_id not in users:
        return None
    
    user = users[user_id]
    
    if "stats" not in user:
        return {
            "total_orders": 0,
            "total_spent_sums": 0,
            "total_deposited_sums": 0,
            "total_gold_earned": 0,
            "total_gold_spent": 0,
            "total_bonus_received": 0,
            "reviews_left": 0,
            "orders_by_type": {
                "gold": 0,
                "bp": 0,
                "stars": 0,
                "premium": 0,
                "withdrawal": 0
            },
            "last_orders": []
        }
    
    return user["stats"]

def get_admin_stats():
    """Получение полной статистики для админа"""
    stats = load_data(STATS_FILE)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Подсчет активных сегодня
    active_today = 0
    online_now = 0
    
    for uid, user in users.items():
        last_active = user.get("last_active", "")
        if last_active.startswith(today):
            active_today += 1
        
        # Проверяем онлайн (активность в последние 5 минут)
        if last_active:
            try:
                last_time = datetime.strptime(last_active, "%Y-%m-%d %H:%M:%S")
                if datetime.now() - last_time < timedelta(minutes=5):
                    online_now += 1
            except:
                pass
    
    # Топ-10 балансов
    top_balances = []
    for uid, user in users.items():
        balance = user.get("balance", 0)
        if balance > 0:
            top_balances.append({
                "name": user.get("full_name", "Unknown"),
                "balance": balance
            })
    
    top_balances.sort(key=lambda x: x["balance"], reverse=True)
    top_balances = top_balances[:10]
    
    # Расчет прибыли (20% от оборота)
    profit = stats.get("total_revenue", 0) * 0.2
    
    return {
        "total_users": stats.get("total_users", 0),
        "new_today": stats["daily"].get(today, {}).get("new_users", 0),
        "active_today": active_today,
        "online_now": online_now,
        "total_revenue": stats.get("total_revenue", 0),
        "total_profit": int(profit),
        "avg_check": int(stats.get("total_revenue", 0) / max(stats.get("total_orders", 1), 1)),
        "total_orders": stats.get("total_orders", 0),
        "orders_by_type": stats.get("orders_by_type", {}),
        "orders_by_status": stats.get("orders_by_status", {}),
        "total_reviews": stats.get("total_reviews", 0),
        "reviews_today": stats["daily"].get(today, {}).get("reviews", 0),
        "total_gold": sum(u.get("balance", 0) for u in users.values()),
        "avg_gold": sum(u.get("balance", 0) for u in users.values()) / max(len(users), 1),
        "top_balances": top_balances,
        "daily_sales": stats["daily"].get(today, {}).get("revenue", 0),
        "daily_profit": int(stats["daily"].get(today, {}).get("revenue", 0) * 0.2),
        "daily_orders": stats["daily"].get(today, {}).get("orders", 0)
    }

# ===================== ЗАГРУЗКА ДАННЫХ =====================
users = load_data(USERS_FILE)
orders_gold = load_data(ORDERS_GOLD_FILE)
orders_bp = load_data(ORDERS_BP_FILE)
orders_stars = load_data(ORDERS_STARS_FILE)
orders_subs = load_data(ORDERS_SUBS_FILE)
withdrawals = load_data(WITHDRAWALS_FILE)
reviews = load_data(REVIEWS_FILE)

# Инициализируем статистику
stats = init_stats()

# ===================== НОВЫЕ КЛАВИАТУРЫ =====================

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟡 Купить голду")],
            [KeyboardButton(text="🎫 Купить BP")],
            [KeyboardButton(text="⭐️ Telegram Stars")],
            [KeyboardButton(text="📅 Telegram Premium")],
            [KeyboardButton(text="💰 Мой баланс"), KeyboardButton(text="💸 Вывести голду")],
            [KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="🆘 Поддержка")],
            [KeyboardButton(text="📊 Моя статистика")]
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

def get_review_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Отправить фото с отзывом")],
            [KeyboardButton(text="✏️ Написать текстовый отзыв")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

# ===================== ОСТАЛЬНЫЕ КЛАВИАТУРЫ (без изменений) =====================
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

# ===================== НОВЫЕ КОМАНДЫ СТАТИСТИКИ =====================

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
    
    # Новый пользователь
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "orders_count": 0,
            "reviews_count": 0,
            "total_bonus": 0,
            "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_data(users, USERS_FILE)
        
        # Обновляем глобальную статистику
        update_global_stats({"type": "new_user"})
    else:
        # Обновляем активность
        users[user_id]["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        users[user_id]["username"] = message.from_user.username
        users[user_id]["full_name"] = message.from_user.full_name
        save_data(users, USERS_FILE)
    
    # Получаем статистику пользователя
    user_stats = get_user_stats(user_id)
    
    welcome_text = f"""
🎮 **Добро пожаловать в Gold Bot!** 

📌 **ЧТО МЫ ПРОДАЕМ:**
🟡 Gold для игр - {EXCHANGE_RATE} сум = 1 голда
🎫 Battle Pass для игр
⭐️ Telegram Stars
📅 Telegram Premium

💰 **ВАШ БАЛАНС:** {users[user_id]['balance']} голды
📊 **ВАША СТАТИСТИКА:**
• Всего заказов: {user_stats['total_orders']}
• Отзывов оставлено: {user_stats['reviews_left']}
• Всего потрачено: {user_stats['total_spent_sums']:,} сум

💎 **Курс:** {EXCHANGE_RATE} сум = 1 голда
💸 **Мин. вывод:** {MIN_WITHDRAWAL} голды

📋 **ДОСТУПНЫЕ КОМАНДЫ:**
/start - Это меню
/mystats - Моя статистика
/balance - Мой баланс
/orders - Мои заказы
/support - Поддержка

👇 **Используйте кнопки ниже для покупок**
"""
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@dp.message(Command("mystats"))
@dp.message(F.text == "📊 Моя статистика")
async def user_stats_cmd(message: types.Message):
    """Личная статистика пользователя"""
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    stats = get_user_stats(user_id)
    
    # Формируем список последних действий
    last_actions = ""
    for order in stats.get("last_orders", [])[-5:]:
        emoji = "✅" if order.get("status") == "completed" else "⏳"
        last_actions += f"{emoji} {order['date']}: {order['type']} - {order['amount']} сум\n"
    
    if not last_actions:
        last_actions = "Нет действий"
    
    stats_text = f"""
📊 **МОЯ СТАТИСТИКА**

👤 **ПРОФИЛЬ:**
• Дата регистрации: {users[user_id].get('created_at', 'Неизвестно')}
• Всего заказов: {stats['total_orders']}
• Отзывов оставлено: {stats['reviews_left']}
• Бонусов получено: {stats['total_bonus_received']} голды

💰 **ФИНАНСЫ:**
• Текущий баланс: {users[user_id].get('balance', 0)} голды
• Всего пополнено: {stats['total_deposited_sums']:,} сум
• Всего потрачено: {stats['total_spent_sums']:,} сум
• Голды получено: {stats['total_gold_earned']}

📦 **МОИ ПОКУПКИ:**
• Gold: {stats['orders_by_type'].get('gold', 0)} раз
• BP: {stats['orders_by_type'].get('bp', 0)} раз
• Stars: {stats['orders_by_type'].get('stars', 0)} раз
• Premium: {stats['orders_by_type'].get('premium', 0)} раз
• Выводов: {stats['orders_by_type'].get('withdrawal', 0)} раз

🎁 **ПОСЛЕДНИЕ ДЕЙСТВИЯ:**
{last_actions}
"""
    
    await message.answer(stats_text, parse_mode="Markdown")

@dp.message(Command("balance"))
async def quick_balance_cmd(message: types.Message):
    """Быстрый просмотр баланса"""
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    balance = users.get(user_id, {}).get('balance', 0)
    stats = get_user_stats(user_id)
    
    await message.answer(
        f"💰 **ВАШ БАЛАНС**\n\n"
        f"Текущий баланс: {balance} голды\n"
        f"Всего заработано: {stats['total_gold_earned']} голды\n"
        f"Всего потрачено: {stats['total_gold_spent']} голды\n\n"
        f"💎 1 голда = {EXCHANGE_RATE} сум",
        parse_mode="Markdown"
    )

@dp.message(Command("orders"))
async def quick_orders_cmd(message: types.Message):
    """Быстрый просмотр заказов"""
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.",
            reply_markup=get_chat_keyboard()
        )
        return
    
    stats = get_user_stats(user_id)
    
    orders_text = "📋 **ПОСЛЕДНИЕ ЗАКАЗЫ:**\n\n"
    
    for order in stats.get("last_orders", [])[-5:]:
        status_emoji = "✅" if order.get("status") == "completed" else "⏳"
        orders_text += f"{status_emoji} {order['date']}\n"
        orders_text += f"   {order['type']} - {order['amount']} сум\n\n"
    
    if not stats.get("last_orders"):
        orders_text = "📭 У вас нет заказов"
    
    await message.answer(orders_text, parse_mode="Markdown")

@dp.message(Command("support"))
async def support_cmd(message: types.Message):
    """Поддержка"""
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "❌ Во время чата с администратором нельзя использовать команды.",
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

# ===================== АДМИН КОМАНДЫ =====================

@dp.message(Command("admin"))
@dp.message(Command("stats"))
async def admin_stats_cmd(message: types.Message):
    """Полная статистика для админа"""
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    stats = get_admin_stats()
    
    # Формируем топ-10 балансов
    top_balances_text = ""
    for i, user in enumerate(stats["top_balances"], 1):
        top_balances_text += f"{i}. {user['name']}: {user['balance']} голды\n"
    
    if not top_balances_text:
        top_balances_text = "Нет данных"
    
    admin_text = f"""
📊 **АДМИН ПАНЕЛЬ**

👥 **ПОЛЬЗОВАТЕЛИ:**
• Всего: {stats['total_users']}
• Новых сегодня: {stats['new_today']}
• Активных сегодня: {stats['active_today']}
• Онлайн сейчас: {stats['online_now']}

💰 **ФИНАНСЫ:**
• Общий оборот: {stats['total_revenue']:,} сум
• Прибыль (20%): {stats['total_profit']:,} сум
• Средний чек: {stats['avg_check']:,} сум

📦 **ЗАКАЗЫ:**
• Всего: {stats['total_orders']}
   - Gold: {stats['orders_by_type'].get('gold', 0)} 🟡
   - BP: {stats['orders_by_type'].get('bp', 0)} 🎫
   - Stars: {stats['orders_by_type'].get('stars', 0)} ⭐️
   - Premium: {stats['orders_by_type'].get('sub', 0)} 📅
   - Выводы: {stats['orders_by_type'].get('withdrawal', 0)} 💸

• По статусам:
   - ✅ Выполнено: {stats['orders_by_status'].get('completed', 0)}
   - ⏳ В обработке: {stats['orders_by_status'].get('pending', 0) + stats['orders_by_status'].get('awaiting_purchase', 0)}
   - ❌ Отклонено: {stats['orders_by_status'].get('rejected', 0)}

⭐️ **ОТЗЫВЫ:**
• Всего: {stats['total_reviews']}
• Сегодня: {stats['reviews_today']}

💎 **БАЛАНСЫ:**
• Всего голды: {stats['total_gold']}
• Средний баланс: {stats['avg_gold']:.1f}

🏆 **ТОП-10 БАЛАНСОВ:**
{top_balances_text}

📊 **СТАТИСТИКА ЗА СЕГОДНЯ:**
• Продажи: {stats['daily_sales']:,} сум
• Заработано: {stats['daily_profit']:,} сум
• Заказов: {stats['daily_orders']}
"""
    
    await message.answer(admin_text, parse_mode="Markdown")

@dp.message(Command("users"))
async def admin_users_cmd(message: types.Message):
    """Список пользователей"""
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    users_text = "👥 **ВСЕ ПОЛЬЗОВАТЕЛИ:**\n\n"
    
    for uid, user in users.items():
        users_text += f"👤 {user.get('full_name', 'Unknown')}\n"
        users_text += f"📱 @{user.get('username', 'Нет')}\n"
        users_text += f"🆔 `{uid}`\n"
        users_text += f"💰 {user.get('balance', 0)} голды\n"
        users_text += f"📅 {user.get('created_at', 'Unknown')}\n"
        users_text += f"📊 Заказов: {user.get('orders_count', 0)}\n"
        users_text += f"⭐️ Отзывов: {user.get('reviews_count', 0)}\n"
        users_text += "-" * 30 + "\n"
        
        if len(users_text) > 3000:
            users_text += "... и другие"
            break
    
    await message.answer(users_text, parse_mode="Markdown")

@dp.message(Command("reviews"))
async def admin_reviews_cmd(message: types.Message):
    """Все отзывы"""
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    if not reviews:
        await message.answer("📭 Нет отзывов")
        return
    
    for review_id, review in list(reviews.items())[-10:]:  # Последние 10
        review_text = f"""
📝 **ОТЗЫВ #{review_id}**

👤 {review.get('user_name', 'Unknown')}
📱 @{review.get('username', 'Нет')}
🆔 `{review.get('user_id')}`

📋 Заказ: {review.get('order_type')} | {review.get('order_id')}
📅 {review.get('created_at')}

💬 {review.get('text', '')}
"""
        
        if review.get('photo'):
            try:
                await bot.send_photo(
                    ADMIN_ID,
                    photo=review['photo'],
                    caption=review_text,
                    parse_mode="Markdown"
                )
            except:
                await message.answer(review_text + "\n❌ Не удалось загрузить фото")
        else:
            await message.answer(review_text, parse_mode="Markdown")
        
        await asyncio.sleep(0.5)  # Небольшая задержка

@dp.message(Command("orders_all"))
async def admin_all_orders_cmd(message: types.Message):
    """Все заказы"""
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    all_orders = []
    
    # Собираем все заказы
    for order_id, order in orders_gold.items():
        all_orders.append({
            "id": order_id,
            "type": "gold",
            "user": order.get('user_name'),
            "amount": order.get('amount'),
            "status": order.get('status'),
            "date": order.get('created_at')
        })
    
    for order_id, order in orders_bp.items():
        all_orders.append({
            "id": order_id,
            "type": "bp",
            "user": order.get('user_name'),
            "amount": order.get('amount'),
            "status": order.get('status'),
            "date": order.get('created_at')
        })
    
    for order_id, order in orders_stars.items():
        all_orders.append({
            "id": order_id,
            "type": "stars",
            "user": order.get('user_name'),
            "amount": order.get('amount'),
            "status": order.get('status'),
            "date": order.get('created_at')
        })
    
    for order_id, order in orders_subs.items():
        all_orders.append({
            "id": order_id,
            "type": "premium",
            "user": order.get('user_name'),
            "amount": order.get('amount'),
            "status": order.get('status'),
            "date": order.get('created_at')
        })
    
    for withdrawal_id, withdrawal in withdrawals.items():
        all_orders.append({
            "id": withdrawal_id,
            "type": "withdrawal",
            "user": withdrawal.get('user_name'),
            "amount": withdrawal.get('amount'),
            "status": withdrawal.get('status'),
            "date": withdrawal.get('created_at')
        })
    
    # Сортируем по дате (новые сверху)
    all_orders.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    orders_text = "📋 **ПОСЛЕДНИЕ ЗАКАЗЫ:**\n\n"
    
    for order in all_orders[:20]:  # Последние 20
        status_emoji = {
            "pending": "⏳",
            "awaiting_purchase": "🛒",
            "completed": "✅",
            "rejected": "❌",
            "admin_buying": "🛒",
            "skin_sent_to_buyer": "📸"
        }.get(order['status'], "❓")
        
        orders_text += f"{status_emoji} **{order['type'].upper()}**\n"
        orders_text += f"👤 {order['user']}\n"
        orders_text += f"💰 {order['amount']} сум\n"
        orders_text += f"📅 {order['date']}\n"
        orders_text += f"📋 `{order['id']}`\n\n"
    
    await message.answer(orders_text, parse_mode="Markdown")

# ===================== ИСПРАВЛЕННАЯ СИСТЕМА ОТЗЫВОВ =====================

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
            "Выберите, как хотите оставить отзыв:\n\n"
            "📸 **Фото с текстом** - отправьте фото и напишите текст\n"
            "✏️ **Только текст** - напишите текстовый отзыв\n"
            "📷 **Только фото** - отправьте фото без текста\n\n"
            "👇 Сделайте выбор:",
            parse_mode="Markdown",
            reply_markup=get_review_type_keyboard()
        )
        
        await state.set_state(UserStates.waiting_review_choice)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в leave_review_start: {e}")
        await callback.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_review_choice, F.text)
async def process_review_choice(message: types.Message, state: FSMContext):
    """Обработка выбора типа отзыва"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text == "📸 Отправить фото с отзывом":
        await message.answer(
            "📸 Отправьте фото (можно с подписью):",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_review_both_photo)
        
    elif message.text == "✏️ Написать текстовый отзыв":
        await message.answer(
            "✏️ Напишите текст отзыва:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_review_text)
        
    elif message.text == "📷 Только фото":
        await message.answer(
            "📸 Отправьте фото без текста:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_review_photo)
        
    else:
        await message.answer("❌ Пожалуйста, выберите вариант из меню")

@dp.message(UserStates.waiting_review_both_photo, F.photo)
async def process_review_both_photo(message: types.Message, state: FSMContext):
    """Обработка фото для отзыва с текстом"""
    try:
        # Сохраняем фото
        photo = message.photo[-1].file_id
        caption = message.caption or ""
        
        await state.update_data(
            review_photo=photo,
            review_photo_caption=caption
        )
        
        await message.answer(
            "✏️ Теперь напишите текст отзыва:",
            reply_markup=get_cancel_keyboard()
        )
        
        await state.set_state(UserStates.waiting_review_both_text)
        
    except Exception as e:
        logger.error(f"Ошибка в process_review_both_photo: {e}")
        await message.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_review_both_text, F.text)
async def process_review_both_text(message: types.Message, state: FSMContext):
    """Обработка текста для отзыва с фото"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    review_photo = data.get('review_photo')
    review_photo_caption = data.get('review_photo_caption', '')
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
        "photo_caption": review_photo_caption,
        "type": "photo_with_text",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_data(reviews, REVIEWS_FILE)
    
    # Обновляем статистику
    if user_id in users:
        users[user_id]['reviews_count'] = users[user_id].get('reviews_count', 0) + 1
        save_data(users, USERS_FILE)
    
    update_user_stats(user_id, "review")
    update_global_stats({"type": "review"})
    
    # Отправляем админу
    caption = f"""
📝 **НОВЫЙ ОТЗЫВ (Фото + Текст)**

👤 {message.from_user.full_name}
📱 @{message.from_user.username}
🆔 `{user_id}`

📋 Заказ: {order_type} | {order_id}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💬 **Текст отзыва:**
{review_text}

📸 **Подпись к фото:** {review_photo_caption if review_photo_caption else 'Нет'}
"""
    
    await bot.send_photo(
        ADMIN_ID,
        photo=review_photo,
        caption=caption,
        parse_mode="Markdown"
    )
    
    await message.answer(
        "✅ **Спасибо за отзыв!** 🙏\n\n"
        "Ваш отзыв с фото и текстом отправлен администратору.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

@dp.message(UserStates.waiting_review_photo, F.photo)
async def process_review_photo_only(message: types.Message, state: FSMContext):
    """Обработка отзыва только с фото"""
    try:
        data = await state.get_data()
        order_id = data.get('review_order_id')
        order_type = data.get('review_order_type')
        
        user_id = str(message.from_user.id)
        photo = message.photo[-1].file_id
        caption = message.caption or ""
        
        # Сохраняем отзыв
        review_id = f"review_{int(time.time())}_{user_id[-4:]}"
        reviews[review_id] = {
            "user_id": user_id,
            "user_name": message.from_user.full_name,
            "username": message.from_user.username,
            "order_id": order_id,
            "order_type": order_type,
            "text": None,
            "photo": photo,
            "photo_caption": caption,
            "type": "photo_only",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_data(reviews, REVIEWS_FILE)
        
        # Обновляем статистику
        if user_id in users:
            users[user_id]['reviews_count'] = users[user_id].get('reviews_count', 0) + 1
            save_data(users, USERS_FILE)
        
        update_user_stats(user_id, "review")
        update_global_stats({"type": "review"})
        
        # Отправляем админу
        admin_caption = f"""
📝 **НОВЫЙ ОТЗЫВ (Только фото)**

👤 {message.from_user.full_name}
📱 @{message.from_user.username}
🆔 `{user_id}`

📋 Заказ: {order_type} | {order_id}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📸 **Подпись к фото:** {caption if caption else 'Нет'}
"""
        
        await bot.send_photo(
            ADMIN_ID,
            photo=photo,
            caption=admin_caption,
            parse_mode="Markdown"
        )
        
        await message.answer(
            "✅ **Спасибо за отзыв!** 🙏\n\n"
            "Ваше фото отправлено администратору.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка в process_review_photo_only: {e}")
        await message.answer("❌ Произошла ошибка")

@dp.message(UserStates.waiting_review_text, F.text)
async def process_review_text_only(message: types.Message, state: FSMContext):
    """Обработка отзыва только с текстом"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
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
        "photo": None,
        "type": "text_only",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_data(reviews, REVIEWS_FILE)
    
    # Обновляем статистику
    if user_id in users:
        users[user_id]['reviews_count'] = users[user_id].get('reviews_count', 0) + 1
        save_data(users, USERS_FILE)
    
    update_user_stats(user_id, "review")
    update_global_stats({"type": "review"})
    
    # Отправляем админу
    await bot.send_message(
        ADMIN_ID,
        f"""
📝 **НОВЫЙ ОТЗЫВ (Только текст)**

👤 {message.from_user.full_name}
📱 @{message.from_user.username}
🆔 `{user_id}`

📋 Заказ: {order_type} | {order_id}
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💬 **Текст отзыва:**
{review_text}
""",
        parse_mode="Markdown"
    )
    
    await message.answer(
        "✅ **Спасибо за отзыв!** 🙏\n\n"
        "Ваш отзыв отправлен администратору.",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

@dp.message(UserStates.waiting_review_photo, F.text)
@dp.message(UserStates.waiting_review_both_photo, F.text)
async def process_review_invalid_input(message: types.Message, state: FSMContext):
    """Обработка неверного ввода при ожидании фото"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await message.answer("❌ Пожалуйста, отправьте фото")

# ===================== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ (без изменений) =====================
# Здесь идут все остальные обработчики из вашего исходного кода:
# - Баланс
# - Вывод голды
# - Покупка голды
# - Покупка BP
# - Покупка Stars
# - Покупка Premium
# - Оплата
# - Прием чеков
# - Админ: подтверждение оплаты
# - Админ: отклонение заказа
# - Админ: завершение заказа
# - Админ: чат для Premium
# - Админ: вывод голды
# - Пересылка сообщений в чате
# - Обработка отмены

# ===================== ЗАПУСК БОТА =====================
async def main():
    """Основная функция запуска бота"""
    logger.info("🚀 Запускаю Gold Bot...")
    
    for file in [USERS_FILE, ORDERS_GOLD_FILE, ORDERS_BP_FILE, 
                 ORDERS_STARS_FILE, ORDERS_SUBS_FILE, WITHDRAWALS_FILE, 
                 REVIEWS_FILE, STATS_FILE]:
        if not os.path.exists(file):
            if file == STATS_FILE:
                init_stats()
            else:
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
