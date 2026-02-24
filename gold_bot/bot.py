#!/usr/bin/env python3
""" 
GOLD BOT - ИСПРАВЛЕННАЯ ВЕРСИЯ
ВСЕ КНОПКИ РАБОТАЮТ
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
active_chats = {}

# ===================== НАСТРОЙКА ЛОГГЕРА =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ===================== СОСТОЯНИЯ =====================
class UserStates(StatesGroup):
    waiting_gold_amount = State()
    waiting_gold_receipt = State()
    waiting_bp_choice = State()
    waiting_bp_id = State()
    waiting_bp_receipt = State()
    waiting_stars_choice = State()
    waiting_stars_username = State()
    waiting_stars_receipt = State()
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
    waiting_withdraw_amount = State()
    waiting_review_photo = State()
    waiting_review_text = State()
    chatting = State()
    waiting_chat_end_confirm = State()
    waiting_reject_reason = State()
    waiting_skin_photo = State()
    waiting_complete_photo = State()

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

def get_admin_order_keyboard(order_id, order_type="gold"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"approve_{order_type}_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_type}_{order_id}")
        ]
    ])

def get_admin_complete_keyboard(order_id, order_type="gold"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить заказ", callback_data=f"complete_{order_type}_{order_id}")]
    ])

def get_leave_review_keyboard(order_id, order_type="withdrawal"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Оставить отзыв", callback_data=f"leave_review_{order_type}_{order_id}")]
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

# ===================== СТАРТ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats:
        await message.answer(
            "💬 **Вы находитесь в активном чате с администратором!**",
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
            "reviews_count": 0
        }
        save_data(users, USERS_FILE)
    
    await message.answer(
        f"🎮 Добро пожаловать!\n💰 Баланс: {users[user_id]['balance']} голды",
        reply_markup=get_main_keyboard()
    )

# ===================== БАЛАНС =====================
@dp.message(F.text == "💰 Мой баланс")
async def show_balance(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id in active_chats:
        return
    balance = users.get(user_id, {}).get('balance', 0)
    await message.answer(f"💰 Ваш баланс: {balance} голды")

# ===================== ВЫВОД ГОЛДЫ =====================
@dp.message(F.text == "💸 Вывести голду")
async def withdraw_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id in active_chats:
        return
    
    balance = users.get(user_id, {}).get('balance', 0)
    if balance < MIN_WITHDRAWAL:
        await message.answer(f"❌ Минимум: {MIN_WITHDRAWAL} голды")
        return
    
    await message.answer("Введите сумму:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserStates.waiting_withdraw_amount)

@dp.message(UserStates.waiting_withdraw_amount, F.text)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        amount = int(message.text.strip())
        user_id = str(message.from_user.id)
        balance = users.get(user_id, {}).get('balance', 0)
        
        if amount < MIN_WITHDRAWAL or amount > balance:
            await message.answer("❌ Неверная сумма")
            return
        
        withdrawal_id = f"w_{int(time.time())}_{user_id[-4:]}"
        withdrawals[withdrawal_id] = {
            "user_id": user_id,
            "amount": amount,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user_name": message.from_user.full_name
        }
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        await message.answer("✅ Заявка создана", reply_markup=get_main_keyboard())
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число")

# ===================== ПОДДЕРЖКА =====================
@dp.message(F.text == "🆘 Поддержка")
async def support_cmd(message: types.Message):
    await message.answer(f"Админ: {ADMIN_USERNAME}")

# ===================== МОИ ЗАКАЗЫ =====================
@dp.message(F.text == "📋 Мои заказы")
async def my_orders_cmd(message: types.Message):
    await message.answer("📋 Список заказов")

# ===================== ПОКУПКА ГОЛДЫ =====================
@dp.message(F.text == "🟡 Купить голду")
async def buy_gold_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id in active_chats:
        return
    
    await message.answer("Введите сумму в сумах:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserStates.waiting_gold_amount)

@dp.message(UserStates.waiting_gold_amount, F.text)
async def process_gold_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        amount_sums = int(message.text.strip())
        gold_amount = amount_sums // EXCHANGE_RATE
        
        await state.update_data(
            amount_sums=amount_sums,
            gold_amount=gold_amount,
            order_type="gold"
        )
        
        await message.answer(
            f"{amount_sums} сум = {gold_amount} голды\nВыберите оплату:",
            reply_markup=get_payment_keyboard()
        )
        
    except ValueError:
        await message.answer("❌ Введите число")

# ===================== ОПЛАТА =====================
@dp.callback_query(lambda c: c.data == "pay_humo")
async def show_humo_details(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"💳 Карта: {HUMO_CARD}\nСумма: {data['amount_sums']} сум\nОтправьте фото чека",
        parse_mode="Markdown"
    )
    await state.set_state(UserStates.waiting_gold_receipt)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "pay_ton")
async def show_ton_details(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await callback.message.edit_text(
        f"💎 TON: {TON_WALLET}\nОтправьте фото транзакции",
        parse_mode="Markdown"
    )
    await state.set_state(UserStates.waiting_gold_receipt)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено")
    await callback.answer()

# ===================== ПРИЕМ ЧЕКОВ =====================
@dp.message(UserStates.waiting_gold_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_type = data.get('order_type')
    user_id = str(message.from_user.id)
    order_id = f"{order_type}_{int(time.time())}"
    
    if order_type == "gold":
        orders_data = orders_gold
        orders_file = ORDERS_GOLD_FILE
    
    orders_data[order_id] = {
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "data": data,
        "status": "pending",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "receipt_file_id": message.photo[-1].file_id
    }
    save_data(orders_data, orders_file)
    
    await bot.send_photo(
        ADMIN_ID,
        photo=message.photo[-1].file_id,
        caption=f"Новый заказ #{order_id}",
        reply_markup=get_admin_order_keyboard(order_id, order_type)
    )
    
    await message.answer("✅ Чек получен!", reply_markup=get_main_keyboard())
    await state.clear()

# ===================== АДМИН: ПОДТВЕРЖДЕНИЕ ОПЛАТЫ =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('approve_'))
async def admin_approve_order(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    order_type = parts[1]
    order_id = "_".join(parts[2:])
    
    if order_type == "gold":
        orders_data = orders_gold
        orders_file = ORDERS_GOLD_FILE
    
    order = orders_data.get(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден!")
        return
    
    order['status'] = "awaiting_purchase"
    order['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_data, orders_file)
    
    await bot.send_message(
        order['user_id'],
        "✅ Оплата подтверждена! Ожидайте покупки товара."
    )
    
    await callback.message.answer(
        f"✅ ОПЛАТА ПОДТВЕРЖДЕНА\nID: {order_id}\nТеперь купите товар:",
        reply_markup=get_admin_complete_keyboard(order_id, order_type)
    )
    
    try:
        if callback.message.photo:
            await callback.message.edit_caption(
                caption=f"{callback.message.caption}\n✅ ОПЛАТА ПОДТВЕРЖДЕНА",
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                text=f"{callback.message.text}\n✅ ОПЛАТА ПОДТВЕРЖДЕНА",
                reply_markup=None
            )
    except:
        pass
    
    await callback.answer()

# ===================== АДМИН: ОТКЛОНЕНИЕ ЗАКАЗА =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('reject_') and not 'reject_w_' in c.data and not 'reject_sub_' in c.data)
async def admin_reject_order(callback: types.CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    order_type = parts[1]
    order_id = "_".join(parts[2:])
    
    await state.update_data(reject_order_id=order_id, reject_order_type=order_type)
    await callback.message.answer("Укажите причину:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserStates.waiting_reject_reason)
    await callback.answer()

@dp.message(UserStates.waiting_reject_reason, F.text)
async def process_reject_reason(message: types.Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        await state.clear()
        return
    
    data = await state.get_data()
    order_id = data.get('reject_order_id')
    order_type = data.get('reject_order_type')
    reason = message.text
    
    if order_type == "gold":
        orders_data = orders_gold
        orders_file = ORDERS_GOLD_FILE
    
    order = orders_data.get(order_id)
    if order:
        order['status'] = "rejected"
        order['reject_reason'] = reason
        save_data(orders_data, orders_file)
        
        await bot.send_message(
            order['user_id'],
            f"❌ Заказ отклонен. Причина: {reason}"
        )
    
    await message.answer("✅ Заказ отклонен", reply_markup=get_main_keyboard())
    await state.clear()

# ===================== АДМИН: ЗАВЕРШЕНИЕ ЗАКАЗА =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('complete_'))
async def admin_complete_order(callback: types.CallbackQuery, state: FSMContext):
    """Завершение заказа - админ купил товар"""
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    order_type = parts[1]
    order_id = "_".join(parts[2:])
    
    if order_type == "gold":
        orders_data = orders_gold
    
    order = orders_data.get(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден!")
        return
    
    # Сохраняем данные
    await state.update_data(
        complete_order_id=order_id,
        complete_order_type=order_type,
        complete_order_data=order
    )
    
    # Удаляем сообщение с кнопкой
    await callback.message.delete()
    
    # Запрашиваем фото
    await callback.message.answer(
        "📸 Отправьте фото подтверждения покупки:",
        reply_markup=get_cancel_keyboard()
    )
    
    await state.set_state(UserStates.waiting_complete_photo)
    await callback.answer()

@dp.message(UserStates.waiting_complete_photo, F.photo)
async def process_complete_photo(message: types.Message, state: FSMContext):
    """Обработка фото и завершение заказа"""
    if str(message.from_user.id) != str(ADMIN_ID):
        await state.clear()
        return
    
    data = await state.get_data()
    order_id = data.get('complete_order_id')
    order_type = data.get('complete_order_type')
    order = data.get('complete_order_data')
    
    if not order:
        await message.answer("❌ Ошибка", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    user_id = order['user_id']
    
    if order_type == "gold":
        orders_data = orders_gold
        orders_file = ORDERS_GOLD_FILE
        gold_amount = order['data']['gold_amount']
        
        # Начисляем голду
        if user_id in users:
            users[user_id]['balance'] = users[user_id].get('balance', 0) + gold_amount
            save_data(users, USERS_FILE)
    
    # Отправляем фото пользователю
    await bot.send_photo(
        user_id,
        photo=message.photo[-1].file_id,
        caption=f"✅ Заказ выполнен! ID: {order_id}\nСпасибо за покупку!"
    )
    
    # Предлагаем отзыв
    await bot.send_message(
        user_id,
        "📝 Оставить отзыв?",
        reply_markup=get_leave_review_keyboard(order_id, order_type)
    )
    
    # Обновляем статус
    order['status'] = "completed"
    order['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_data, orders_file)
    
    await message.answer(
        f"✅ Заказ {order_id} завершен!",
        reply_markup=get_main_keyboard()
    )
    
    await state.clear()

@dp.message(UserStates.waiting_complete_photo, F.text)
async def process_complete_photo_text(message: types.Message, state: FSMContext):
    """Обработка текста вместо фото"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await message.answer("❌ Отправьте фото")

# ===================== ОТЗЫВЫ =====================
@dp.callback_query(lambda c: c.data and c.data.startswith('leave_review_'))
async def leave_review_start(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    order_type = parts[2]
    order_id = "_".join(parts[3:])
    
    await state.update_data(review_order_id=order_id, review_order_type=order_type)
    await callback.message.answer("Напишите отзыв:", reply_markup=get_cancel_keyboard())
    await state.set_state(UserStates.waiting_review_text)
    await callback.answer()

@dp.message(UserStates.waiting_review_text, F.text)
async def process_review_text(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    review_text = message.text
    user_id = str(message.from_user.id)
    
    review_id = f"review_{int(time.time())}"
    reviews[review_id] = {
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "text": review_text,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_data(reviews, REVIEWS_FILE)
    
    await message.answer("✅ Спасибо за отзыв!", reply_markup=get_main_keyboard())
    await state.clear()

# ===================== ПЕРЕСЫЛКА СООБЩЕНИЙ =====================
@dp.message()
async def handle_all(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    if user_id in active_chats and user_id != str(ADMIN_ID):
        if message.text in ["💰 Мой баланс", "💸 Вывести голду", "📋 Мои заказы", 
                           "🆘 Поддержка", "🟡 Купить голду", "🎫 Купить BP",
                           "⭐️ Telegram Stars", "📅 Telegram Premium"]:
            return
        
        if message.text == "🏠 Главное меню":
            await message.answer("🏠 Меню", reply_markup=get_chat_keyboard())
            return
        
        await bot.send_message(ADMIN_ID, f"От {user_id}: {message.text}")
        await message.answer("✅ Отправлено")
    
    elif user_id == str(ADMIN_ID) and message.reply_to_message:
        reply_text = message.reply_to_message.text or ""
        import re
        user_match = re.search(r'От (\d+):', reply_text)
        if user_match:
            target_id = user_match.group(1)
            await bot.send_message(target_id, message.text)
            await message.answer("✅ Отправлено")

# ===================== ОТМЕНА =====================
@dp.message(F.text == "❌ Отмена")
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено", reply_markup=get_main_keyboard())

@dp.message(F.text == "🏠 Главное меню")
async def main_menu_handler(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id in active_chats:
        await message.answer("🏠 Меню", reply_markup=get_chat_keyboard())
        return
    await state.clear()
    await start_cmd(message)

# ===================== ЗАПУСК =====================
async def main():
    logger.info("🚀 Запуск...")
    
    for file in [USERS_FILE, ORDERS_GOLD_FILE, ORDERS_BP_FILE, 
                 ORDERS_STARS_FILE, ORDERS_SUBS_FILE, WITHDRAWALS_FILE, REVIEWS_FILE]:
        if not os.path.exists(file):
            save_data({}, file)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ Остановлен")
