#!/usr/bin/env python3
"""
GOLD BOT - Полная версия с 5 разделами
Токен: 8546640668:AAEVHTdr4Qw2-CVyQlnFFKsVyvuods5Pibo
Админ: @Bahich_1 (6086536190)
TON кошелёк: UQCgVleFGU6aQUSyJ-8XNh52Igy9SBhq5jhEMK3PwDFvc0n8
"""

import asyncio
import logging
import json
import os
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8546640668:AAEVHTdr4Qw2-CVyQlnFFKsVyvuods5Pibo"
ADMIN_ID = 6086536190
ADMIN_USERNAME = "@Bahich_1"
HUMO_CARD = "9860 6067 4427 9617"
CARD_HOLDER = "R.M"

# Курсы
EXCHANGE_RATE = 150  # 150 сум = 1 голда
RUB_UZS_RATE = 170   # 1 RUB = 170 UZS (фиксировано)
TON_FEE = 0.55       # Комиссия TON
MIN_WITHDRAWAL = 100 # Мин. вывод голды

# TON адрес
TON_WALLET = "UQCgVleFGU6aQUSyJ-8XNh52Igy9SBhq5jhEMK3PwDFvc0n8"
# =====================================================

# Файлы баз данных
USERS_FILE = "users.json"
ORDERS_GOLD_FILE = "orders_gold.json"
ORDERS_BP_FILE = "orders_bp.json"
ORDERS_STARS_FILE = "orders_stars.json"
ORDERS_SUBS_FILE = "orders_subs.json"
WITHDRAWALS_FILE = "withdrawals.json"
REVIEWS_FILE = "reviews.json"

# Состояния
class UserStates(StatesGroup):
    # Для голды
    waiting_gold_amount = State()
    waiting_gold_receipt = State()
    waiting_withdraw_amount = State()
    
    # Для BP
    waiting_bp_choice = State()
    waiting_bp_id = State()
    waiting_bp_receipt = State()
    
    # Для Stars
    waiting_stars_choice = State()
    waiting_stars_username = State()
    waiting_stars_receipt = State()
    
    # Для подписок
    waiting_sub_choice = State()
    waiting_sub_type = State()
    waiting_sub_phone = State()
    waiting_sub_username = State()
    waiting_sub_receipt = State()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===================== УТИЛИТЫ =====================
def load_data(filename):
    """Загрузка данных из JSON файла"""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data, filename):
    """Сохранение данных в JSON файл"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения {filename}: {e}")

async def get_ton_rate():
    """Получение курса TON/RUB с Coinbase API"""
    try:
        url = "https://api.coinbase.com/v2/prices/TON-RUB/spot"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                return float(data['data']['amount'])
    except Exception as e:
        logger.error(f"Ошибка получения курса TON: {e}")
        return 114.79  # Запасной курс

async def calculate_ton_price(amount_sums):
    """Расчёт суммы в TON для оплаты"""
    # Шаг 1: UZS → RUB
    rub_amount = amount_sums / RUB_UZS_RATE
    
    # Шаг 2: RUB → TON
    ton_rate = await get_ton_rate()
    ton_amount = rub_amount / ton_rate
    
    # Шаг 3: + комиссия
    total_ton = ton_amount + TON_FEE
    
    return round(total_ton, 3), round(ton_rate, 2)

# Загрузка данных
users = load_data(USERS_FILE)
orders_gold = load_data(ORDERS_GOLD_FILE)
orders_bp = load_data(ORDERS_BP_FILE)
orders_stars = load_data(ORDERS_STARS_FILE)
orders_subs = load_data(ORDERS_SUBS_FILE)
withdrawals = load_data(WITHDRAWALS_FILE)
reviews = load_data(REVIEWS_FILE)

# ===================== КЛАВИАТУРЫ =====================
def get_main_keyboard():
    """Главное меню"""
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
    """Клавиатура отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

def get_payment_keyboard():
    """Выбор способа оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 HUMO", callback_data="pay_humo")],
        [InlineKeyboardButton(text="💎 TON", callback_data="pay_ton")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
    ])

def get_bp_keyboard():
    """Выбор BP пакета"""
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
    """Выбор пакета Stars"""
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
    """Выбор типа подписки"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Со входом в аккаунт")],
            [KeyboardButton(text="🎁 Без входа (подарочная)")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_sub_period_keyboard(sub_type):
    """Выбор срока подписки"""
    if sub_type == "with_login":
        keyboard = [
            [KeyboardButton(text="⭐ 1 месяц - 50,000 сум")],
            [KeyboardButton(text="⭐ 12 месяцев - 375,990 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ]
    else:  # gift
        keyboard = [
            [KeyboardButton(text="🎁 3 месяца - 170,000 сум")],
            [KeyboardButton(text="🎁 6 месяцев - 230,000 сум")],
            [KeyboardButton(text="🎁 12 месяцев - 400,000 сум")],
            [KeyboardButton(text="❌ Отмена")]
        ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# Админские клавиатуры
def get_admin_order_keyboard(order_id, order_type="gold"):
    """Клавиатура для подтверждения заказа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{order_type}_{order_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{order_type}_{order_id}")
        ]
    ])

def get_admin_withdrawal_keyboard(withdrawal_id):
    """Клавиатура для вывода"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Купить скин", callback_data=f"skin_{withdrawal_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_w_{withdrawal_id}")
        ]
    ])

def get_admin_complete_keyboard(order_id, order_type="gold"):
    """Клавиатура для завершения заказа"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Завершить заказ", callback_data=f"complete_{order_type}_{order_id}")]
    ])

# ===================== ОСНОВНЫЕ КОМАНДЫ =====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Команда /start"""
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "username": message.from_user.username,
            "full_name": message.from_user.full_name,
            "orders_count": 0
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

# ===================== РАЗДЕЛ 1: ПОКУПКА ГОЛДЫ =====================
@dp.message(F.text == "🟡 Купить голду")
async def buy_gold_start(message: types.Message, state: FSMContext):
    """Начало покупки голды"""
    await message.answer(
        "💵 Введите сумму в сумах:\n\nПример: 30000",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_gold_amount)

@dp.message(UserStates.waiting_gold_amount, F.text)
async def process_gold_amount(message: types.Message, state: FSMContext):
    """Обработка суммы для голды"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    try:
        amount_sums = int(message.text.strip())
        if amount_sums < EXCHANGE_RATE:
            await message.answer(f"Минимальная сумма: {EXCHANGE_RATE} сум")
            return
        
        gold_amount = amount_sums // EXCHANGE_RATE
        
        # Расчёт TON
        ton_total, ton_rate = await calculate_ton_price(amount_sums)
        
        await state.update_data(
            amount_sums=amount_sums,
            gold_amount=gold_amount,
            ton_total=ton_total,
            ton_rate=ton_rate
        )
        
        await message.answer(
            f"💎 Расчёт:\n"
            f"{amount_sums} сум = {gold_amount} голды\n\n"
            f"Вы получите: {gold_amount} голды\n\n"
            f"Выберите способ оплаты:",
            reply_markup=get_payment_keyboard(),
            parse_mode="Markdown"
        )
        
    except ValueError:
        await message.answer("❌ Введите число!\nПример: 30000")

# ===================== РАЗДЕЛ 2: ПОКУПКА BP =====================
@dp.message(F.text == "🎫 Купить BP")
async def buy_bp_start(message: types.Message, state: FSMContext):
    """Начало покупки BP"""
    await message.answer(
        "🎫 Выберите пакет BP:",
        reply_markup=get_bp_keyboard()
    )
    await state.set_state(UserStates.waiting_bp_choice)

@dp.message(UserStates.waiting_bp_choice, F.text)
async def process_bp_choice(message: types.Message, state: FSMContext):
    """Обработка выбора BP"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    # Маппинг пакетов к ценам
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
    
    # Расчёт TON
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        bp_package=message.text,
        bp_price=price,
        ton_total=ton_total,
        ton_rate=ton_rate
    )
    
    await message.answer(
        "🎮 Введите ваш ID в игре (цифры):\n\n"
        "Это нужно для активации BP",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_bp_id)

@dp.message(UserStates.waiting_bp_id, F.text)
async def process_bp_id(message: types.Message, state: FSMContext):
    """Обработка ID игры для BP"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    await state.update_data(game_id=message.text)
    
    data = await state.get_data()
    
    await message.answer(
        f"🎫 Пакет: {data['bp_package']}\n"
        f"💰 Цена: {data['bp_price']} сум\n"
        f"🆔 ID в игре: {data['game_id']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== РАЗДЕЛ 3: TELEGRAM STARS =====================
@dp.message(F.text == "⭐️ Telegram Stars")
async def buy_stars_start(message: types.Message, state: FSMContext):
    """Начало покупки Stars"""
    await message.answer(
        "⭐️ Выберите пакет Stars:",
        reply_markup=get_stars_keyboard()
    )
    await state.set_state(UserStates.waiting_stars_choice)

@dp.message(UserStates.waiting_stars_choice, F.text)
async def process_stars_choice(message: types.Message, state: FSMContext):
    """Обработка выбора Stars"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    # Маппинг пакетов к ценам
    stars_prices = {
        "⭐️ 50 stars - 13,000 сум": ("50 stars", 13000),
        "⭐️ 100 stars - 25,000 сум": ("100 stars", 25000),
        "⭐️ 150 stars - 37,000 сум": ("150 stars", 37000),
        "⭐️ 350 stars - 86,000 сум": ("350 stars", 86000),
        "⭐️ 500 stars - 125,000 сум": ("500 stars", 125000),
        "⭐️ 750 stars - 180,000 сум": ("750 stars", 180000),
        "⭐️ 1000 stars - 240,000 сум": ("1000 stars", 240000),
        "⭐️ 1500 stars - 360,000 сум": ("1500 stars", 360000),
        "⭐️ 2500 stars - 600,000 сум": ("2500 stars", 600000),
        "⭐️ 5000 stars - 1,200,000 сум": ("5000 stars", 1200000)
    }
    
    if message.text not in stars_prices:
        await message.answer("❌ Выберите пакет из списка")
        return
    
    package_name, price = stars_prices[message.text]
    
    # Расчёт TON
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        stars_package=package_name,
        stars_price=price,
        ton_total=ton_total,
        ton_rate=ton_rate
    )
    
    await message.answer(
        "📱 Введите юзернейм получателя (например @username):\n\n"
        "Stars будут отправлены этому пользователю",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_stars_username)

@dp.message(UserStates.waiting_stars_username, F.text)
async def process_stars_username(message: types.Message, state: FSMContext):
    """Обработка юзернейма для Stars"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if not message.text.startswith("@"):
        await message.answer("❌ Юзернейм должен начинаться с @\nПример: @username")
        return
    
    await state.update_data(stars_recipient=message.text)
    
    data = await state.get_data()
    
    await message.answer(
        f"⭐️ Пакет: {data['stars_package']}\n"
        f"💰 Цена: {data['stars_price']} сум\n"
        f"👤 Получатель: {data['stars_recipient']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== РАЗДЕЛ 4: TELEGRAM PREMIUM =====================
@dp.message(F.text == "📅 Telegram Premium")
async def buy_subs_start(message: types.Message, state: FSMContext):
    """Начало покупки подписки"""
    await message.answer(
        "📅 Выберите тип подписки:",
        reply_markup=get_subs_keyboard()
    )
    await state.set_state(UserStates.waiting_sub_type)

@dp.message(UserStates.waiting_sub_type, F.text)
async def process_sub_type(message: types.Message, state: FSMContext):
    """Обработка типа подписки"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if message.text not in ["📱 Со входом в аккаунт", "🎁 Без входа (подарочная)"]:
        await message.answer("❌ Выберите тип из списка")
        return
    
    sub_type = "with_login" if message.text == "📱 Со входом в аккаунт" else "gift"
    
    await state.update_data(sub_type=sub_type)
    
    await message.answer(
        "📅 Выберите срок подписки:",
        reply_markup=get_sub_period_keyboard(sub_type)
    )
    await state.set_state(UserStates.waiting_sub_choice)

@dp.message(UserStates.waiting_sub_choice, F.text)
async def process_sub_choice(message: types.Message, state: FSMContext):
    """Обработка выбора срока подписки"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    data = await state.get_data()
    sub_type = data['sub_type']
    
    # Маппинг цен
    if sub_type == "with_login":
        sub_prices = {
            "⭐ 1 месяц - 50,000 сум": ("1 месяц", 50000),
            "⭐ 12 месяцев - 375,990 сум": ("12 месяцев", 375990)
        }
    else:  # gift
        sub_prices = {
            "🎁 3 месяца - 170,000 сум": ("3 месяца", 170000),
            "🎁 6 месяцев - 230,000 сум": ("6 месяцев", 230000),
            "🎁 12 месяцев - 400,000 сум": ("12 месяцев", 400000)
        }
    
    if message.text not in sub_prices:
        await message.answer("❌ Выберите срок из списка")
        return
    
    period, price = sub_prices[message.text]
    
    # Расчёт TON
    ton_total, ton_rate = await calculate_ton_price(price)
    
    await state.update_data(
        sub_period=period,
        sub_price=price,
        ton_total=ton_total,
        ton_rate=ton_rate
    )
    
    if sub_type == "with_login":
        await message.answer(
            "📱 Введите номер телефона аккаунта:\n\n"
            "Пример: +998901234567",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_phone)
    else:  # gift
        await message.answer(
            "👤 Введите юзернейм получателя (например @username):\n\n"
            "Подарочная ссылка будет отправлена этому пользователю",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(UserStates.waiting_sub_username)

@dp.message(UserStates.waiting_sub_phone, F.text)
async def process_sub_phone(message: types.Message, state: FSMContext):
    """Обработка телефона для подписки со входом"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if not message.text.startswith("+"):
        await message.answer("❌ Введите номер в формате +998901234567")
        return
    
    await state.update_data(phone_number=message.text)
    
    data = await state.get_data()
    
    instructions = (
        "⚠️ **Перед оплатой подготовьте аккаунт:**\n"
        "1. Будьте онлайн в Telegram\n"
        "2. Включите уведомления от бота @Gold_stars_prem_donatuzbbot\n"
        "3. Отключите двухфакторную аутентификацию (если включена)\n\n"
    )
    
    await message.answer(
        f"{instructions}"
        f"📅 Подписка: Telegram Premium\n"
        f"📱 Тип: Со входом в аккаунт\n"
        f"⏳ Срок: {data['sub_period']}\n"
        f"💰 Цена: {data['sub_price']} сум\n"
        f"📞 Телефон: {data['phone_number']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard(),
        parse_mode="Markdown"
    )

@dp.message(UserStates.waiting_sub_username, F.text)
async def process_sub_username(message: types.Message, state: FSMContext):
    """Обработка юзернейма для подарочной подписки"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    if not message.text.startswith("@"):
        await message.answer("❌ Юзернейм должен начинаться с @\nПример: @username")
        return
    
    await state.update_data(gift_recipient=message.text)
    
    data = await state.get_data()
    
    await message.answer(
        f"📅 Подписка: Telegram Premium\n"
        f"🎁 Тип: Подарочная (без входа)\n"
        f"⏳ Срок: {data['sub_period']}\n"
        f"💰 Цена: {data['sub_price']} сум\n"
        f"👤 Получатель: {data['gift_recipient']}\n\n"
        f"Выберите способ оплаты:",
        reply_markup=get_payment_keyboard()
    )

# ===================== ОБРАБОТКА ОПЛАТЫ =====================
@dp.callback_query(F.data == "pay_humo")
async def show_humo_details(callback: types.CallbackQuery, state: FSMContext):
    """Показ реквизитов HUMO"""
    data = await state.get_data()
    
    # Определяем тип заказа
    if 'gold_amount' in data:
        order_type = "gold"
        amount_sums = data['amount_sums']
        details = f"Получите: {data['gold_amount']} голды"
    elif 'bp_package' in data:
        order_type = "bp"
        amount_sums = data['bp_price']
        details = f"Пакет: {data['bp_package']}\nID игры: {data.get('game_id', 'не указан')}"
    elif 'stars_package' in data:
        order_type = "stars"
        amount_sums = data['stars_price']
        details = f"Пакет: {data['stars_package']}\nПолучатель: {data.get('stars_recipient', 'не указан')}"
    elif 'sub_period' in data:
        order_type = "sub"
        amount_sums = data['sub_price']
        if data['sub_type'] == "with_login":
            details = f"Тип: Со входом\nСрок: {data['sub_period']}\nТелефон: {data.get('phone_number', 'не указан')}"
        else:
            details = f"Тип: Подарочная\nСрок: {data['sub_period']}\nПолучатель: {data.get('gift_recipient', 'не указан')}"
    else:
        await callback.answer("❌ Ошибка данных")
        return
    
    payment_text = f"""
💳 ОПЛАТА HUMO

🏦 Номер карты: {HUMO_CARD}
👤 Владелец: {CARD_HOLDER}
💰 Сумма: {amount_sums} сум

📋 Детали:
{details}

📋 Инструкция:
1. Переведите {amount_sums} сум на карту выше
2. Сделайте скриншот чека об оплате
3. Отправьте скриншот в этот чат

⚠️ Важно: Отправляйте ТОЛЬКО скриншот чека!
"""
    
    await callback.message.edit_text(payment_text, parse_mode="Markdown")
    await state.set_state(UserStates.waiting_gold_receipt)
    await callback.answer()

@dp.callback_query(F.data == "pay_ton")
async def show_ton_details(callback: types.CallbackQuery, state: FSMContext):
    """Показ реквизитов TON"""
    data = await state.get_data()
    
    # Определяем тип заказа
    if 'gold_amount' in data:
        order_type = "gold"
        amount_sums = data['amount_sums']
        details = f"Получите: {data['gold_amount']} голды"
        ton_total = data['ton_total']
        ton_rate = data['ton_rate']
    elif 'bp_package' in data:
        order_type = "bp"
        amount_sums = data['bp_price']
        details = f"Пакет: {data['bp_package']}\nID игры: {data.get('game_id', 'не указан')}"
        ton_total = data['ton_total']
        ton_rate = data['ton_rate']
    elif 'stars_package' in data:
        order_type = "stars"
        amount_sums = data['stars_price']
        details = f"Пакет: {data['stars_package']}\nПолучатель: {data.get('stars_recipient', 'не указан')}"
        ton_total = data['ton_total']
        ton_rate = data['ton_rate']
    elif 'sub_period' in data:
        order_type = "sub"
        amount_sums = data['sub_price']
        if data['sub_type'] == "with_login":
            details = f"Тип: Со входом\nСрок: {data['sub_period']}\nТелефон: {data.get('phone_number', 'не указан')}"
        else:
            details = f"Тип: Подарочная\nСрок: {data['sub_period']}\nПолучатель: {data.get('gift_recipient', 'не указан')}"
        ton_total = data['ton_total']
        ton_rate = data['ton_rate']
    else:
        await callback.answer("❌ Ошибка данных")
        return
    
        
    payment_text = f"""
💎 ОПЛАТА TON

💰 Сумма: {amount_sums} сум

📋 Детали:
{details}

💎 ИТОГ к оплате: {ton_total} TON

🏦 Адрес TON:
{TON_WALLET}

📋 Инструкция:
1. Переведите {ton_total} TON на адрес выше
2. Сделайте скриншот транзакции
3. Отправьте скриншот в этот чат

⚠️ Важно: Проверяйте сумму перед отправкой!
"""
    
    await callback.message.edit_text(payment_text, parse_mode="Markdown")
    await state.set_state(UserStates.waiting_gold_receipt)
    await callback.answer()

@dp.message(UserStates.waiting_gold_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    """Обработка скриншота чека"""
    user_id = str(message.from_user.id)
    data = await state.get_data()
    
    # Определяем тип заказа
    if 'gold_amount' in data:
        await process_gold_receipt(message, state, user_id, data)
    elif 'bp_package' in data:
        await process_bp_receipt(message, state, user_id, data)
    elif 'stars_package' in data:
        await process_stars_receipt(message, state, user_id, data)
    elif 'sub_period' in data:
        await process_sub_receipt(message, state, user_id, data)
    else:
        await message.answer("❌ Ошибка данных")
        await state.clear()

async def process_gold_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    """Создание заказа на голду"""
    order_id = datetime.now().strftime("G%Y%m%d%H%M%S")
    
    orders_gold[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "amount_sums": data['amount_sums'],
        "gold_amount": data['gold_amount'],
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "gold"
    }
    save_data(orders_gold, ORDERS_GOLD_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "gold")
    await state.clear()

async def process_bp_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    """Создание заказа на BP"""
    order_id = datetime.now().strftime("B%Y%m%d%H%M%S")
    
    orders_bp[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "bp_package": data['bp_package'],
        "price": data['bp_price'],
        "game_id": data.get('game_id', 'не указан'),
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "bp"
    }
    save_data(orders_bp, ORDERS_BP_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "bp")
    await state.clear()

async def process_stars_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    """Создание заказа на Stars"""
    order_id = datetime.now().strftime("S%Y%m%d%H%M%S")
    
    orders_stars[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "stars_package": data['stars_package'],
        "price": data['stars_price'],
        "recipient": data.get('stars_recipient', 'не указан'),
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "stars"
    }
    save_data(orders_stars, ORDERS_STARS_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "stars")
    await state.clear()

async def process_sub_receipt(message: types.Message, state: FSMContext, user_id: str, data: dict):
    """Создание заказа на подписку"""
    order_id = datetime.now().strftime("P%Y%m%d%H%M%S")
    
    orders_subs[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "user_name": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
        "sub_type": data['sub_type'],
        "sub_period": data['sub_period'],
        "price": data['sub_price'],
        "phone_number": data.get('phone_number'),
        "recipient": data.get('gift_recipient'),
        "status": "pending",
        "receipt_photo_id": message.photo[-1].file_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "order_type": "sub"
    }
    save_data(orders_subs, ORDERS_SUBS_FILE)
    
    await message.answer(
        "✅ Чек получен! ⏳\nОжидайте подтверждения администратора",
        reply_markup=get_main_keyboard()
    )
    
    await notify_admin_about_order(order_id, "sub")
    await state.clear()

@dp.message(UserStates.waiting_gold_receipt)
async def wrong_receipt_format(message: types.Message):
    """Неправильный формат чека"""
    await message.answer(
        "❌ Отправьте СКРИНШОТ ЧЕКА (фото)\n\nОтправляйте только фото!",
        reply_markup=get_cancel_keyboard()
    )

# ===================== УВЕДОМЛЕНИЯ АДМИНУ =====================
async def notify_admin_about_order(order_id: str, order_type: str):
    """Уведомление админа о новом заказе"""
    if order_type == "gold":
        order = orders_gold.get(order_id)
        emoji = "🟡"
        product_info = f"Голда: {order['gold_amount']} голды\nСумма: {order['amount_sums']} сум"
    elif order_type == "bp":
        order = orders_bp.get(order_id)
        emoji = "🎫"
        product_info = f"Пакет: {order['bp_package']}\nЦена: {order['price']} сум\nID игры: {order.get('game_id', 'не указан')}"
    elif order_type == "stars":
        order = orders_stars.get(order_id)
        emoji = "⭐️"
        product_info = f"Пакет: {order['stars_package']}\nЦена: {order['price']} сум\nПолучатель: {order.get('recipient', 'не указан')}"
    elif order_type == "sub":
        order = orders_subs.get(order_id)
        emoji = "📅"
        sub_type_ru = "Со входом" if order['sub_type'] == "with_login" else "Подарочная"
        product_info = f"Тип: {sub_type_ru}\nСрок: {order['sub_period']}\nЦена: {order['price']} сум"
        if order['sub_type'] == "with_login":
            product_info += f"\nТелефон: {order.get('phone_number', 'не указан')}"
        else:
            product_info += f"\nПолучатель: {order.get('recipient', 'не указан')}"
    else:
        return
    
    admin_text = f"""
{emoji} НОВЫЙ ЗАКАЗ!

📊 Информация:
ID: {order_id}
Тип: {order_type}
Пользователь: {order['user_name']}
Username: {order['username']}
ID: {order['user_id']}

📦 Детали:
{product_info}

⏰ Время: {order['created_at']}
"""
    
    try:
        admin_message = await bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="Markdown",
            reply_markup=get_admin_order_keyboard(order_id, order_type)
        )
        
        await bot.send_photo(
            ADMIN_ID,
            photo=order['receipt_photo_id'],
            caption=f"📸 Чек для заказа {order_id}"
        )
        
        # Сохраняем ID сообщения для обновления
        if order_type == "gold":
            orders_gold[order_id]['admin_message_id'] = admin_message.message_id
            save_data(orders_gold, ORDERS_GOLD_FILE)
        elif order_type == "bp":
            orders_bp[order_id]['admin_message_id'] = admin_message.message_id
            save_data(orders_bp, ORDERS_BP_FILE)
        elif order_type == "stars":
            orders_stars[order_id]['admin_message_id'] = admin_message.message_id
            save_data(orders_stars, ORDERS_STARS_FILE)
        elif order_type == "sub":
            orders_subs[order_id]['admin_message_id'] = admin_message.message_id
            save_data(orders_subs, ORDERS_SUBS_FILE)
        
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")

# ===================== ВЫВОД ГОЛДЫ =====================
@dp.message(F.text == "💰 Мой баланс")
async def show_balance(message: types.Message):
    """Показать баланс"""
    user_id = str(message.from_user.id)
    balance = users.get(user_id, {}).get('balance', 0)
    await message.answer(f"💰 Ваш баланс: {balance} голды")

@dp.message(F.text == "💸 Вывести голду")
async def withdraw_start(message: types.Message, state: FSMContext):
    """Начало вывода голды"""
    user_id = str(message.from_user.id)
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
        f"Баланс: {balance} голды\n"
        f"Минимум: {MIN_WITHDRAWAL} голды\n\n"
        f"Сколько вывести?",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(UserStates.waiting_withdraw_amount)

@dp.message(UserStates.waiting_withdraw_amount, F.text)
async def process_withdraw_amount(message: types.Message, state: FSMContext):
    """Обработка суммы вывода"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("❌ Отменено", reply_markup=get_main_keyboard())
        return
    
    user_id = str(message.from_user.id)
    balance = users[user_id]['balance']
    
    try:
        withdraw_amount = int(message.text.strip())
        
        if withdraw_amount < MIN_WITHDRAWAL:
            await message.answer(f"Минимум: {MIN_WITHDRAWAL} голды")
            return
        if withdraw_amount > balance:
            await message.answer(f"❌ Недостаточно!\nБаланс: {balance} голды")
            return
        
        withdrawal_id = datetime.now().strftime("W%Y%m%d%H%M%S")
        withdrawals[withdrawal_id] = {
            "withdrawal_id": withdrawal_id,
            "user_id": user_id,
            "user_name": message.from_user.full_name,
            "username": f"@{message.from_user.username}" if message.from_user.username else "Нет username",
            "amount": withdraw_amount,
            "status": "pending",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        await message.answer(
            f"✅ Запрос на вывод {withdraw_amount} голды отправлен!\nОжидайте ответа.",
            reply_markup=get_main_keyboard()
        )
        
        await notify_admin_about_withdrawal(withdrawal_id)
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите число!\nПример: 100")

async def notify_admin_about_withdrawal(withdrawal_id: str):
    """Уведомление админа о выводе"""
    withdrawal = withdrawals[withdrawal_id]
    
    admin_text = f"""
💸 ЗАПРОС НА ВЫВОД!

👤 Пользователь:
Имя: {withdrawal['user_name']}
Username: {withdrawal['username']}
ID: {withdrawal['user_id']}

💰 Сумма: {withdrawal['amount']} голды
⏰ Время: {withdrawal['created_at']}
ID: {withdrawal_id}
"""
    
    try:
        admin_message = await bot.send_message(
            ADMIN_ID,
            admin_text,
            parse_mode="Markdown",
            reply_markup=get_admin_withdrawal_keyboard(withdrawal_id)
        )
        
        withdrawals[withdrawal_id]['admin_message_id'] = admin_message.message_id
        save_data(withdrawals, WITHDRAWALS_FILE)
        
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")

# ===================== АДМИНСКИЕ ОБРАБОТЧИКИ =====================
@dp.callback_query(F.data.startswith("approve_"))
async def admin_approve_order(callback: types.CallbackQuery):
    """Подтверждение заказа админом"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных")
        return
    
    order_type = parts[1]
    order_id = parts[2]
    
    if order_type == "gold":
        await approve_gold_order(callback, order_id)
    elif order_type == "bp":
        await approve_bp_order(callback, order_id)
    elif order_type == "stars":
        await approve_stars_order(callback, order_id)
    elif order_type == "sub":
        await approve_sub_order(callback, order_id)
    else:
        await callback.answer("❌ Неизвестный тип заказа")

async def approve_gold_order(callback: types.CallbackQuery, order_id: str):
    """Подтверждение заказа голды"""
    order = orders_gold.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    user_id = order['user_id']
    gold_amount = order['gold_amount']
    
    if user_id in users:
        users[user_id]['balance'] = users[user_id].get('balance', 0) + gold_amount
        users[user_id]['orders_count'] = users[user_id].get('orders_count', 0) + 1
        save_data(users, USERS_FILE)
    
    orders_gold[order_id]['status'] = "approved"
    orders_gold[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_gold, ORDERS_GOLD_FILE)
    
    try:
        await bot.send_message(
            user_id,
            f"✅ Заказ подтвержден!\n\n"
            f"Начислено: {gold_amount} голды\n"
            f"ID заказа: {order_id}\n"
            f"💰 Баланс: {users[user_id]['balance']} голды\n\n"
            f"_Оставьте отзыв: @{ADMIN_USERNAME[1:]}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Голда\n"
        f"Пользователь: {order['user_name']}\n"
        f"Сумма: {gold_amount} голды\n\n"
        f"Баланс пользователя обновлен",
        reply_markup=get_admin_complete_keyboard(order_id, "gold")
    )
    await callback.answer("✅ Подтверждено!")

async def approve_bp_order(callback: types.CallbackQuery, order_id: str):
    """Подтверждение заказа BP"""
    order = orders_bp.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_bp[order_id]['status'] = "approved"
    orders_bp[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_bp, ORDERS_BP_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ Заказ BP подтвержден!\n\n"
            f"Пакет: {order['bp_package']}\n"
            f"ID заказа: {order_id}\n"
            f"🆔 ID в игре: {order.get('game_id', 'не указан')}\n\n"
            f"Админ активирует BP в ближайшее время\n"
            f"_Оставьте отзыв: @{ADMIN_USERNAME[1:]}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: BP\n"
        f"Пользователь: {order['user_name']}\n"
        f"Пакет: {order['bp_package']}\n"
        f"ID игры: {order.get('game_id', 'не указан')}\n\n"
        f"Пользователь уведомлен",
        reply_markup=get_admin_complete_keyboard(order_id, "bp")
    )
    await callback.answer("✅ Подтверждено!")

async def approve_stars_order(callback: types.CallbackQuery, order_id: str):
    """Подтверждение заказа Stars"""
    order = orders_stars.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_stars[order_id]['status'] = "approved"
    orders_stars[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_stars, ORDERS_STARS_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"✅ Заказ Stars подтвержден!\n\n"
            f"Пакет: {order['stars_package']}\n"
            f"ID заказа: {order_id}\n"
            f"👤 Получатель: {order.get('recipient', 'не указан')}\n\n"
            f"Админ отправит Stars в ближайшее время\n"
            f"_Оставьте отзыв: @{ADMIN_USERNAME[1:]}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Stars\n"
        f"Пользователь: {order['user_name']}\n"
        f"Пакет: {order['stars_package']}\n"
        f"Получатель: {order.get('recipient', 'не указан')}\n\n"
        f"Пользователь уведомлен",
        reply_markup=get_admin_complete_keyboard(order_id, "stars")
    )
    await callback.answer("✅ Подтверждено!")

async def approve_sub_order(callback: types.CallbackQuery, order_id: str):
    """Подтверждение заказа подписки"""
    order = orders_subs.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_subs[order_id]['status'] = "approved"
    orders_subs[order_id]['approved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_subs, ORDERS_SUBS_FILE)
    
    sub_type_ru = "Со входом в аккаунт" if order['sub_type'] == "with_login" else "Подарочная"
    
    try:
        message_text = f"✅ Заказ подписки подтвержден!\n\n"
        message_text += f"Тип: {sub_type_ru}\n"
        message_text += f"Срок: {order['sub_period']}\n"
        message_text += f"ID заказа: {order_id}\n\n"
        
        if order['sub_type'] == "with_login":
            message_text += f"📱 Телефон: {order.get('phone_number', 'не указан')}\n"
            message_text += "Подготовьте аккаунт:\n"
            message_text += "1. Будьте онлайн\n"
            message_text += "2. Включите уведомления от @Gold_stars_prem_donatuzbbot\n"
            message_text += "3. Отключите 2FA (если включена)\n\n"
        else:
            message_text += f"👤 Получатель: {order.get('recipient', 'не указан')}\n"
            message_text += "Подарочная ссылка будет отправлена получателю\n\n"
        
        message_text += f"_Оставьте отзыв: @{ADMIN_USERNAME[1:]}"
        
        await bot.send_message(order['user_id'], message_text)
    except:
        pass
    
    admin_text = f"✅ ЗАКАЗ ПОДТВЕРЖДЕН\n\nID: {order_id}\nТип: Подписка\n"
    admin_text += f"Пользователь: {order['user_name']}\nТип: {sub_type_ru}\n"
    admin_text += f"Срок: {order['sub_period']}\n\nПользователь уведомлен"
    
    await callback.message.edit_text(
        admin_text,
        reply_markup=get_admin_complete_keyboard(order_id, "sub")
    )
    await callback.answer("✅ Подтверждено!")

@dp.callback_query(F.data.startswith("reject_"))
async def admin_reject_order(callback: types.CallbackQuery):
    """Отклонение заказа админом"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных")
        return
    
    order_type = parts[1]
    order_id = parts[2]
    
    if order_type == "gold":
        await reject_gold_order(callback, order_id)
    elif order_type == "bp":
        await reject_bp_order(callback, order_id)
    elif order_type == "stars":
        await reject_stars_order(callback, order_id)
    elif order_type == "sub":
        await reject_sub_order(callback, order_id)
    elif order_type == "w":  # withdrawal
        withdrawal_id = parts[2]
        await reject_withdrawal(callback, withdrawal_id)
    else:
        await callback.answer("❌ Неизвестный тип")

async def reject_gold_order(callback: types.CallbackQuery, order_id: str):
    """Отклонение заказа голды"""
    order = orders_gold.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_gold[order_id]['status'] = "rejected"
    orders_gold[order_id]['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_gold, ORDERS_GOLD_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"❌ Заказ отклонен\n\n"
            f"ID заказа: {order_id}\n"
            f"Сумма: {order['amount_sums']} сум\n\n"
            f"📞 Свяжитесь с админом: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"❌ ЗАКАЗ ОТКЛОНЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Голда\n"
        f"Пользователь уведомлен"
    )
    await callback.answer("❌ Отклонено!")

async def reject_bp_order(callback: types.CallbackQuery, order_id: str):
    """Отклонение заказа BP"""
    order = orders_bp.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_bp[order_id]['status'] = "rejected"
    orders_bp[order_id]['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_bp, ORDERS_BP_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"❌ Заказ BP отклонен\n\n"
            f"ID заказа: {order_id}\n"
            f"Пакет: {order['bp_package']}\n\n"
            f"📞 Свяжитесь с админом: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"❌ ЗАКАЗ ОТКЛОНЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: BP\n"
        f"Пользователь уведомлен"
    )
    await callback.answer("❌ Отклонено!")

async def reject_stars_order(callback: types.CallbackQuery, order_id: str):
    """Отклонение заказа Stars"""
    order = orders_stars.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_stars[order_id]['status'] = "rejected"
    orders_stars[order_id]['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_stars, ORDERS_STARS_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"❌ Заказ Stars отклонен\n\n"
            f"ID заказа: {order_id}\n"
            f"Пакет: {order['stars_package']}\n\n"
            f"📞 Свяжитесь с админом: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"❌ ЗАКАЗ ОТКЛОНЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Stars\n"
        f"Пользователь уведомлен"
    )
    await callback.answer("❌ Отклонено!")

async def reject_sub_order(callback: types.CallbackQuery, order_id: str):
    """Отклонение заказа подписки"""
    order = orders_subs.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_subs[order_id]['status'] = "rejected"
    orders_subs[order_id]['rejected_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_subs, ORDERS_SUBS_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"❌ Заказ подписки отклонен\n\n"
            f"ID заказа: {order_id}\n"
            f"Срок: {order['sub_period']}\n\n"
            f"📞 Свяжитесь с админом: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"❌ ЗАКАЗ ОТКЛОНЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Подписка\n"
        f"Пользователь уведомлен"
    )
    await callback.answer("❌ Отклонено!")

async def reject_withdrawal(callback: types.CallbackQuery, withdrawal_id: str):
    """Отклонение вывода"""
    withdrawal = withdrawals.get(withdrawal_id)
    
    if not withdrawal:
        await callback.answer("Запрос не найден!")
        return
    
    withdrawals[withdrawal_id]['status'] = "rejected"
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    try:
        await bot.send_message(
            withdrawal['user_id'],
            f"❌ Вывод отклонен\n\n"
            f"Сумма: {withdrawal['amount']} голды\n"
            f"ID: {withdrawal_id}\n\n"
            f"📞 По вопросам: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"❌ ВЫВОД ОТКЛОНЕН\n\n"
        f"ID: {withdrawal_id}\n"
        f"Пользователь уведомлен"
    )
    await callback.answer("❌ Отклонено!")

@dp.callback_query(F.data.startswith("complete_"))
async def admin_complete_order(callback: types.CallbackQuery):
    """Завершение заказа админом"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа!")
        return
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных")
        return
    
    order_type = parts[1]
    order_id = parts[2]
    
    if order_type == "gold":
        await complete_gold_order(callback, order_id)
    elif order_type == "bp":
        await complete_bp_order(callback, order_id)
    elif order_type == "stars":
        await complete_stars_order(callback, order_id)
    elif order_type == "sub":
        await complete_sub_order(callback, order_id)
    else:
        await callback.answer("❌ Неизвестный тип")

async def complete_gold_order(callback: types.CallbackQuery, order_id: str):
    """Завершение заказа голды"""
    order = orders_gold.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_gold[order_id]['status'] = "completed"
    orders_gold[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_gold, ORDERS_GOLD_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"🎉 Заказ успешно обработан!\n\n"
            f"Спасибо за покупку голды! 💎\n\n"
            f"📍 **ОБЯЗАТЕЛЬНО ОСТАВЬТЕ ОТЗЫВ:**\n"
            f"1. Сделайте скриншот баланса в игре\n"
            f"2. Напишите текст отзыва\n"
            f"3. Отправьте админу: {ADMIN_USERNAME}\n\n"
            f"⚠️ **ВНИМАНИЕ:**\n"
            f"• При оплате в TON проверяйте курс\n"
            f"• Если возникли ошибки — пишите админу сразу\n"
            f"• Сохраняйте скриншоты оплаты\n\n"
            f"📞 Поддержка: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Голда\n"
        f"Пользователь получил уведомление"
    )
    await callback.answer("✅ Завершено!")

async def complete_bp_order(callback: types.CallbackQuery, order_id: str):
    """Завершение заказа BP"""
    order = orders_bp.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_bp[order_id]['status'] = "completed"
    orders_bp[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_bp, ORDERS_BP_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"🎉 Заказ успешно обработан!\n\n"
            f"Спасибо за покупку BP! 🎮\n\n"
            f"📍 **ОБЯЗАТЕЛЬНО ОСТАВЬТЕ ОТЗЫВ:**\n"
            f"1. Сделайте скриншот активированного BP\n"
            f"2. Напишите текст отзыва\n"
            f"3. Отправьте админу: {ADMIN_USERNAME}\n\n"
            f"⚠️ **ВНИМАНИЕ:**\n"
            f"• При оплате в TON проверяйте курс\n"
            f"• Если возникли ошибки — пишите админу сразу\n"
            f"• Сохраняйте скриншоты оплаты\n\n"
            f"📞 Поддержка: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: BP\n"
        f"Пользователь получил уведомление"
    )
    await callback.answer("✅ Завершено!")

async def complete_stars_order(callback: types.CallbackQuery, order_id: str):
    """Завершение заказа Stars"""
    order = orders_stars.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_stars[order_id]['status'] = "completed"
    orders_stars[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_stars, ORDERS_STARS_FILE)
    
    try:
        await bot.send_message(
            order['user_id'],
            f"🎉 Заказ успешно обработан!\n\n"
            f"Спасибо за покупку Stars! ⭐️\n\n"
            f"📍 **ОБЯЗАТЕЛЬНО ОСТАВЬТЕ ОТЗЫВ:**\n"
            f"1. Сделайте скриншот полученных Stars\n"
            f"2. Напишите текст отзыва\n"
            f"3. Отправьте админу: {ADMIN_USERNAME}\n\n"
            f"⚠️ **ВНИМАНИЕ:**\n"
            f"• При оплате в TON проверяйте курс\n"
            f"• Если возникли ошибки — пишите админу сразу\n"
            f"• Сохраняйте скриншоты оплаты\n\n"
            f"📞 Поддержка: {ADMIN_USERNAME}"
        )
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Stars\n"
        f"Пользователь получил уведомление"
    )
    await callback.answer("✅ Завершено!")

async def complete_sub_order(callback: types.CallbackQuery, order_id: str):
    """Завершение заказа подписки"""
    order = orders_subs.get(order_id)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    orders_subs[order_id]['status'] = "completed"
    orders_subs[order_id]['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_data(orders_subs, ORDERS_SUBS_FILE)
    
    sub_type_ru = "Со входом в аккаунт" if order['sub_type'] == "with_login" else "Подарочная"
    
    try:
        message_text = f"🎉 Заказ успешно обработан!\n\n"
        message_text += f"Спасибо за покупку подписки! 📅\n\n"
        message_text += f"📍 **ОБЯЗАТЕЛЬНО ОСТАВЬТЕ ОТЗЫВ:**\n"
        message_text += f"1. Сделайте скриншот активной подписки\n"
        message_text += f"2. Напишите текст отзыва\n"
        message_text += f"3. Отправьте админу: {ADMIN_USERNAME}\n\n"
        message_text += f"⚠️ **ВНИМАНИЕ:**\n"
        message_text += f"• При оплате в TON проверяйте курс\n"
        message_text += f"• Если возникли ошибки — пишите админу сразу\n"
        message_text += f"• Сохраняйте скриншоты оплаты\n\n"
        message_text += f"📞 Поддержка: {ADMIN_USERNAME}"
        
        await bot.send_message(order['user_id'], message_text)
    except:
        pass
    
    await callback.message.edit_text(
        f"🎉 ЗАКАЗ ЗАВЕРШЕН\n\n"
        f"ID: {order_id}\n"
        f"Тип: Подписка ({sub_type_ru})\n"
        f"Пользователь получил уведомление"
    )
    await callback.answer("✅ Завершено!")

@dp.callback_query(F.data.startswith("skin_"))
async def admin_buy_skin(callback: types.CallbackQuery):
    """Админ покупает скин для вывода"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Нет доступа!")
        return
    
    withdrawal_id = callback.data.split("_")[1]
    withdrawal = withdrawals.get(withdrawal_id)
    
    if not withdrawal:
        await callback.answer("Запрос не найден!")
        return
    
    # Сохраняем ID вывода для обработки фото скина
    withdrawals[withdrawal_id]['admin_processing'] = True
    save_data(withdrawals, WITHDRAWALS_FILE)
    
    await callback.message.edit_text(
        f"🛒 КУПИТЬ СКИН\n\n"
        f"Для пользователя: {withdrawal['user_name']}\n"
        f"На сумму: {withdrawal['amount']} голды\n\n"
        f"1. Купите скин на эту сумму\n"
        f"2. Отправьте фото скина в этот чат\n"
        f"3. Напишите цену скина в подписи к фото\n\n"
        f"ID запроса: {withdrawal_id}\n\n"
        f"⚠️ **Фото и цена автоматически отправятся покупателю!**"
    )
    await callback.answer("🛒 Покупайте скин...")

# Обработка фото скина от админа
@dp.message(F.photo, F.from_user.id == ADMIN_ID)
async def handle_skin_photo(message: types.Message):
    """Обработка фото скина от админа"""
    # Ищем активный вывод
    withdrawal_id = None
    for w_id, withdrawal in withdrawals.items():
        if withdrawal.get('admin_processing') and withdrawal.get('status') == 'pending':
            withdrawal_id = w_id
            break
    
    if not withdrawal_id:
        return
    
    withdrawal = withdrawals[withdrawal_id]
    
    # Отправляем фото и описание покупателю
    try:
        caption = message.caption or "🎮 Скин для вывода голды"
        await bot.send_photo(
            withdrawal['user_id'],
            photo=message.photo[-1].file_id,
            caption=f"{caption}\n\n"
                   f"✅ Админ купил скин для вашего вывода {withdrawal['amount']} голды\n"
                   f"📞 По вопросам: {ADMIN_USERNAME}"
        )
        
        # Обновляем статус
        withdrawals[withdrawal_id]['status'] = "skin_sent"
        withdrawals[withdrawal_id]['skin_photo_id'] = message.photo[-1].file_id
        withdrawals[withdrawal_id]['skin_price'] = message.caption or "Цена не указана"
        withdrawals[withdrawal_id]['skin_sent_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        withdrawals[withdrawal_id]['admin_processing'] = False
        save_data(withdrawals, WITHDRAWALS_FILE)
        
        # Уведомляем админа
        await bot.send_message(
            ADMIN_ID,
            f"✅ Фото скина отправлено покупателю!\n\n"
            f"Пользователь: {withdrawal['user_name']}\n"
            f"Сумма: {withdrawal['amount']} голды\n"
            f"ID вывода: {withdrawal_id}\n\n"
            f"Покупатель получил уведомление с фото скина."
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки фото скина: {e}")
        await bot.send_message(
            ADMIN_ID,
            f"❌ Ошибка отправки фото скина: {e}"
        )

# ===================== ИСТОРИЯ ЗАКАЗОВ =====================
@dp.message(F.text == "📋 Мои заказы")
async def my_orders_cmd(message: types.Message):
    """Показать историю заказов"""
    user_id = str(message.from_user.id)
    
    # Собираем все заказы пользователя
    all_orders = []
    
    # Заказы голды
    for order_id, order in orders_gold.items():
        if order['user_id'] == user_id:
            order['type'] = "Голда"
            all_orders.append(order)
    
    # Заказы BP
    for order_id, order in orders_bp.items():
        if order['user_id'] == user_id:
            order['type'] = "BP"
            all_orders.append(order)
    
    # Заказы Stars
    for order_id, order in orders_stars.items():
        if order['user_id'] == user_id:
            order['type'] = "Stars"
            all_orders.append(order)
    
    # Заказы подписок
    for order_id, order in orders_subs.items():
        if order['user_id'] == user_id:
            order['type'] = "Подписка"
            all_orders.append(order)
    
    if not all_orders:
        await message.answer("📭 У вас нет заказов")
        return
    
    # Сортируем по дате (новые первые)
    all_orders.sort(key=lambda x: x['created_at'], reverse=True)
    
    orders_text = "📋 Ваши заказы (последние 10):\n\n"
    
    for order in all_orders[:10]:
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "completed": "🎉",
            "skin_sent": "🎮"
        }.get(order['status'], "❓")
        
        orders_text += f"{status_emoji} {order['type']} {order['order_id'][-6:]}\n"
        
        if order['type'] == "Голда":
            orders_text += f"💰 {order['amount_sums']} сум = {order['gold_amount']} голды\n"
        elif order['type'] == "BP":
            orders_text += f"🎮 {order['bp_package']}\n"
        elif order['type'] == "Stars":
            orders_text += f"⭐️ {order['stars_package']}\n"
        elif order['type'] == "Подписка":
            sub_type = "Со входом" if order.get('sub_type') == "with_login" else "Подарочная"
            orders_text += f"📅 {sub_type} - {order['sub_period']}\n"
        
        orders_text += f"📅 {order['created_at']}\n"
        orders_text += f"Статус: {order['status']}\n\n"
    
    await message.answer(orders_text, parse_mode="Markdown")

# ===================== ПОДДЕРЖКА =====================
@dp.message(F.text == "🆘 Поддержка")
async def support_cmd(message: types.Message):
    """Команда поддержки"""
    support_text = f"""
🆘 ПОДДЕРЖКА

📍 Администратор: {ADMIN_USERNAME}
🤖 Бот: @Gold_stars_prem_donatuzbbot

📞 По вопросам:
• Не пришла голда / товар
• Проблемы с оплатой
• Ошибки в боте
• Другие вопросы

💎 Курс: {EXCHANGE_RATE} сум = 1 голда
💸 Мин. вывод: {MIN_WITHDRAWAL} голды

💳 Реквизиты HUMO:
{HUMO_CARD}
👤 {CARD_HOLDER}

💎 Реквизиты TON:
{TON_WALLET}
"""
    await message.answer(support_text, parse_mode="Markdown")

@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    """Отмена оплаты"""
    await state.clear()
    await callback.message.edit_text("❌ Оплата отменена")
    await callback.answer()

# ===================== ЗАПУСК БОТА =====================
async def main():
    """Основная функция запуска бота"""
    logger.info("🚀 Запускаю Gold Bot...")
    logger.info(f"🤖 Бот: @Gold_stars_prem_donatuzbbot")
    logger.info(f"👑 Админ: {ADMIN_USERNAME}")
    logger.info(f"💳 HUMO карта: {HUMO_CARD}")
    logger.info(f"💎 TON кошелёк: {TON_WALLET}")
    logger.info(f"💰 Курс RUB/UZS: {RUB_UZS_RATE}")
    logger.info(f"💎 Комиссия TON: {TON_FEE}")
    
    # Создаём файлы если их нет
    for file in [USERS_FILE, ORDERS_GOLD_FILE, ORDERS_BP_FILE, 
                 ORDERS_STARS_FILE, ORDERS_SUBS_FILE, WITHDRAWALS_FILE]:
        if not os.path.exists(file):
            save_data({}, file)
            logger.info(f"📁 Создан файл: {file}")
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())