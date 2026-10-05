import asyncio
import os
import html
import random
import aiohttp
import time
import re
import string
import json
import hashlib
import uuid
from contextlib import suppress
from datetime import datetime, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import (
    FSInputFile, ReplyKeyboardMarkup, KeyboardButton, 
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
)

import database as db 
import ai_engines
from ai_engines import AI_MODES, AI_MODE_EMOJIS

# ==========================================================
# ⚙️ Configuration
# ==========================================================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is required")
try:
    OWNER_ID = int(os.getenv("OWNER_ID", "0"))
except ValueError:
    raise RuntimeError("OWNER_ID must be an integer")
if OWNER_ID <= 0:
    raise RuntimeError("OWNER_ID is required")
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=float(os.getenv("HTTP_TIMEOUT", "15")))
MAX_BET = float(os.getenv("MAX_BET", "100000"))
MAX_LOSS = float(os.getenv("MAX_SESSION_LOSS", "100000"))
MAX_BETS_PER_SESSION = int(os.getenv("MAX_BETS_PER_SESSION", "1000"))
PAYOUT_MULTIPLIER = float(os.getenv("PAYOUT_MULTIPLIER", "0.96"))
http_session = None

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

active_sessions = {}
auto_tasks = {}
prediction_tasks = {}
user_locks = {}

# ==========================================================
# 🌐 API Configurations
# ==========================================================
SITE_CONFIGS = {
    "777BIGWIN": {
        "api_url": "https://api.bigwinqaz.com/api/webapi",
        "origin": "https://www.777bigwingame.app"
    },
    "6Lottery": {
        "api_url": "https://6lotteryapi.com/api/webapi",
        "origin": "https://www.6win566.com"
    },
    "CK LOTTERY": {
        "api_url": "https://ckygjf6r.com/api/webapi",
        "origin": "https://cklottery.cc"
    }
}

def get_signed_payload(payload: dict) -> dict:
    t = {k: v for k, v in payload.items() if k not in ['signature', 'timestamp']}
    
    if 'language' not in t:
        t['language'] = 7
    if 'random' not in t:
        t['random'] = uuid.uuid4().hex
        
    n = {}
    for key in sorted(t.keys()):
        val = t[key]
        if val is not None and val != "":
            n[key] = val
            
    json_str = json.dumps(n, separators=(',', ':'))
    signature = hashlib.md5(json_str.encode('utf-8')).hexdigest().upper()
    
    t['signature'] = signature
    t['timestamp'] = int(time.time())
    return t

def get_headers(site: str, token: str = "") -> dict:
    config = SITE_CONFIGS.get(site, SITE_CONFIGS["777BIGWIN"])
    headers = {
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json;charset=UTF-8',
        'origin': config["origin"],
        'referer': f'{config["origin"]}/',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
    }
    if token:
        headers['authorization'] = f'Bearer {token}'
    return headers

async def http_post(url, *, headers=None, json_data=None):
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)
    async with http_session.post(url, headers=headers, json=json_data) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


class _DeprecatedSessionGuard:
    async def __aenter__(self):
        global http_session
        if http_session is None or http_session.closed:
            http_session = aiohttp.ClientSession(timeout=REQUEST_TIMEOUT)
        return http_session
    async def __aexit__(self, exc_type, exc, tb):
        return False

def get_user_lock(user_id):
    return user_locks.setdefault(user_id, asyncio.Lock())

def validate_bet_amount(amount):
    amount = float(amount)
    if amount <= 0 or amount > MAX_BET:
        raise ValueError(f"Bet amount must be between 0 and {MAX_BET:g}")
    return amount

def get_select_type(bet_type: str) -> int:
    b = bet_type.lower()
    if b == "big":
        return 13
    elif b == "small":
        return 14
    elif b == "red":
        return 1
    elif b == "green":
        return 3
    elif b in ["violet", "purple"]:
        return 2
    return 13 

# ==========================================================
# 🌟 Premium Emojis & UI
# ==========================================================
TEXT_INFO = "Info"
TEXT_BALANCE = "Balance"
TEXT_STATUS = "Status"
TEXT_START = "Start Auto-Bet"
TEXT_STOP = "Stop Auto-Bet"
TEXT_GAMES = "Games"
TEXT_AI = "AI Mode"
TEXT_BETSIZE = "Set Bet-Size"
TEXT_PROFIT = "Profit Target"
TEXT_HIT = "Hit Betting"
TEXT_PREDICT = "AI Prediction"
TEXT_LOGOUT = "Logout"
TEXT_LOGIN = "Login"
TEXT_BACK = "Back"
TEXT_VIRTUAL_MODE = "Virtual Mode"
TEXT_REAL_MODE = "Real Mode"
TEXT_UPLOAD_CHANNEL = "Upload Channel"

E_INFO = KeyboardButton(text=TEXT_INFO, icon_custom_emoji_id="5868656545634689320", style="primary")
E_BALANCE = KeyboardButton(text=TEXT_BALANCE, icon_custom_emoji_id="5868108575387671725", style="primary")
E_STATUS = KeyboardButton(text=TEXT_STATUS, icon_custom_emoji_id="5877443460725739250", style="primary")
E_START = KeyboardButton(text=TEXT_START, icon_custom_emoji_id="5884248697980608904", style="success")
E_STOP = KeyboardButton(text=TEXT_STOP, icon_custom_emoji_id="5884289942371401145", style="danger")
E_GAMES = KeyboardButton(text=TEXT_GAMES, icon_custom_emoji_id="5868665489092263539", style="primary")
E_AI = KeyboardButton(text=TEXT_AI, icon_custom_emoji_id="5877652234091891383", style="primary")
E_BETSIZE = KeyboardButton(text=TEXT_BETSIZE, icon_custom_emoji_id="5877260593903177342", style="primary")
E_PROFIT = KeyboardButton(text=TEXT_PROFIT, icon_custom_emoji_id="5967574255670399788", style="primary")
E_HIT = KeyboardButton(text=TEXT_HIT, icon_custom_emoji_id="5869547610204280761", style="primary")
E_PREDICT = KeyboardButton(text=TEXT_PREDICT, icon_custom_emoji_id="5890997763331591703", style="primary")
E_LOGOUT = KeyboardButton(text=TEXT_LOGOUT, icon_custom_emoji_id="5875180111744995604", style="danger")
E_LOGIN = KeyboardButton(text=TEXT_LOGIN, icon_custom_emoji_id="5884041323843955199", style="primary")
E_BACK = KeyboardButton(text=TEXT_BACK, icon_custom_emoji_id="5848119413041431362", style="primary")
E_VIRTUAL = KeyboardButton(text=TEXT_VIRTUAL_MODE, icon_custom_emoji_id="5807868868886009920", style="primary")
E_REAL = KeyboardButton(text=TEXT_REAL_MODE, icon_custom_emoji_id="5868656545634689320", style="primary")
E_UPLOAD = KeyboardButton(text=TEXT_UPLOAD_CHANNEL, icon_custom_emoji_id="5890997763331591703", style="primary")

P_1 = '<tg-emoji emoji-id="5890997763331591703">⚙️</tg-emoji>'
P_2 = '<tg-emoji emoji-id="5875180111744995604">⚙️</tg-emoji>'
P_3 = '<tg-emoji emoji-id="5877443460725739250">⚙️</tg-emoji>'
P_4 = '<tg-emoji emoji-id="5967574255670399788">⚙️</tg-emoji>'
P_5 = '<tg-emoji emoji-id="5807868868886009920">⚙️</tg-emoji>'
P_6 = '<tg-emoji emoji-id="5807461353799030682">⚙️</tg-emoji>'
E_SETTING = '<tg-emoji emoji-id="5877260593903177342">⚙️</tg-emoji>'
E_CROWN   = '<tg-emoji emoji-id="5807868868886009920">👑</tg-emoji>'
E_LOSS    = '<tg-emoji emoji-id="5807461353799030682">💸</tg-emoji>'
E_GRID    = '<tg-emoji emoji-id="5884290437459480896">🔠</tg-emoji>'
E_EDIT    = '<tg-emoji emoji-id="5985774024968379294">📝</tg-emoji>'
E_DOC     = '<tg-emoji emoji-id="5956561916573782596">📄</tg-emoji>'
E_FLOWER  = '<tg-emoji emoji-id="5967574255670399788">🌸</tg-emoji>'

# ==========================================================
# 🛠️ Helpers & Middleware
# ==========================================================
def extract_balance(bal_str: str) -> float:
    try:
        clean_str = re.sub(r'[^\d.]', '', str(bal_str))
        if clean_str:
            return float(clean_str)
        return 0.0
    except Exception:
        return 0.0

async def delete_message_later(msg: types.Message, delay: int = 5):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass

def parse_duration(duration_str: str):
    duration_str = duration_str.upper()
    if duration_str.endswith('H') and duration_str[:-1].isdigit():
        return timedelta(hours=int(duration_str[:-1]))
    elif duration_str.endswith('D') and duration_str[:-1].isdigit():
        return timedelta(days=int(duration_str[:-1]))
    return None

def get_myanmar_time() -> datetime:
    return datetime.utcnow() + timedelta(hours=6, minutes=30)

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user_id = None
        text = None
        
        if isinstance(event, types.Message):
            user_id = event.from_user.id
            text = event.text or ""
        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id
            
        if user_id:
            if user_id == OWNER_ID:
                return await handler(event, data)
                
            is_whitelisted = await db.is_uid_allowed(str(user_id))
            if is_whitelisted:
                return await handler(event, data)
                
            if text and text.startswith("PSP-") and len(text) == 20:
                return await handler(event, data)
                
            expire_iso = await db.get_user_subscription(user_id)
            is_authorized = False
            
            if expire_iso:
                expire_time = datetime.fromisoformat(expire_iso)
                if get_myanmar_time() < expire_time:
                    is_authorized = True
            
            if not is_authorized:
                if isinstance(event, types.Message):
                    await event.answer("ᴄᴏɴᴛᴀᴄᴛ ᴜꜱ @iwillgoforwardsalone")
                elif isinstance(event, types.CallbackQuery):
                    await event.answer("အသုံးပြုခွင့် သက်တမ်းကုန်သွားပါပြီ။", show_alert=True)
                return 
        
        return await handler(event, data)

dp.message.middleware(AuthMiddleware())
dp.callback_query.middleware(AuthMiddleware())

VALID_AI_NAMES = [m["name"] for m in ai_engines.AI_MODES.values()]

class LoginForm(StatesGroup):
    select_site = State()
    enter_phone = State()
    enter_password = State()
    main_menu = State()
    select_game_type = State()
    enter_bet_sequence = State()
    enter_profit_target = State()
    enter_custom_pattern = State()
    enter_virtual_balance = State() 

# ==========================================================
# ⌨️ Keyboards
# ==========================================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[E_LOGIN]], resize_keyboard=True)

def get_site_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="777BIGWIN", style="success"), KeyboardButton(text="6Lottery", style="danger")],
            [KeyboardButton(text="CK LOTTERY", style="primary")],
            [E_BACK]
        ],
        resize_keyboard=True
    )

def get_logged_in_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [E_INFO, E_BALANCE, E_STATUS],
            [E_START, E_STOP],
            [E_GAMES, E_AI],
            [E_BETSIZE, E_PROFIT],
            [E_HIT, E_PREDICT],
            [E_VIRTUAL, E_REAL],
            [E_UPLOAD, E_LOGOUT]
        ],
        resize_keyboard=True
    )

def get_game_type_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Win Go 30s", style="success"), KeyboardButton(text="Win Go 1m", style="primary")],
            [E_BACK]
        ],
        resize_keyboard=True
    )

def get_upload_toggle_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Upload ON", style="success"), KeyboardButton(text="❌ Upload OFF", style="danger")],
            [E_BACK]
        ],
        resize_keyboard=True
    )

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Cancel")]], resize_keyboard=True)

def get_ai_mode_keyboard():
    standard_modes = [m for k, m in AI_MODES.items() if not k.startswith("pro_") and k != "babathapai"]
    keyboard = []
    row = []
    
    for mode in standard_modes:
        emoji_id = AI_MODE_EMOJIS.get(mode["name"], "5868656545634689320")
        btn = KeyboardButton(text=mode["name"], icon_custom_emoji_id=emoji_id, style="primary")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
            
    if row:
        keyboard.append(row)
        
    pro_btn = KeyboardButton(text="Pro AI Features", icon_custom_emoji_id="5807868868886009920", style="success")
    back_btn = KeyboardButton(text="BACK", icon_custom_emoji_id="5848119413041431362", style="primary")
    keyboard.append([pro_btn])
    keyboard.append([back_btn])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_pro_ai_mode_keyboard():
    pro_modes = [m for k, m in AI_MODES.items() if k.startswith("pro_") or k == "babathapai"]
    keyboard = []
    row = []
    
    for mode in pro_modes:
        btn = KeyboardButton(text=mode["name"], icon_custom_emoji_id="5807868868886009920", style="primary")
        row.append(btn)
        if len(row) == 2:
            keyboard.append(row)
            row = []
            
    if row:
        keyboard.append(row)
        
    back_btn = KeyboardButton(text="BACK", icon_custom_emoji_id="5848119413041431362", style="danger")
    keyboard.append([back_btn])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_hit_betting_inline_keyboard(current_wait: int = 0):
    keyboard = []
    number_buttons = []
    
    for i in range(1, 10):
        btn_style = "success" if current_wait == i else "primary"
        btn = InlineKeyboardButton(text=str(i), callback_data=f"hitbet_{i}", style=btn_style)
        number_buttons.append(btn)
        
    for i in range(0, 9, 3):
        keyboard.append(number_buttons[i:i+3])
        
    disable_text = "0 (Disabled)" if current_wait == 0 else "0 (Disable)"
    disable_btn = InlineKeyboardButton(text=disable_text, callback_data="hitbet_0", style="danger")
    keyboard.append([disable_btn])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_ai_prediction_toggle_keyboard(is_enabled: bool):
    btn_text = "🟢 Enabled" if is_enabled else "🔴 Disabled"
    btn_style = "success" if is_enabled else "danger"
    btn = InlineKeyboardButton(text=btn_text, callback_data="toggle_aipred", style=btn_style)
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])

# ==========================================================
# 👑 Owner Commands
# ==========================================================
@dp.message(F.text.startswith(".key "))
async def cmd_generate_key(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
        
    parts = message.text.split(" ")
    if len(parts) < 2:
        await message.answer("⚠️ Format: <code>.key 2H</code>")
        return
        
    duration = parts[1].strip().upper()
    if not parse_duration(duration):
        await message.answer("⚠️ Format: <code>2H</code>")
        return
        
    date_prefix = get_myanmar_time().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    key_str = f"PSP-{date_prefix}{random_str}"
    
    await db.create_key(key_str, duration)
    await message.answer(f"✅ Key: <code>{key_str}</code>\n⏱️ Duration: <b>{duration}</b>")

@dp.message(F.text.startswith(".gen "))
async def cmd_gen_keys(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
        
    parts = message.text.split(" ")
    try:
        count = int(parts[1])
        duration = parts[2].strip().upper()
    except Exception:
        await message.answer("⚠️ Format: <code>.gen 5 2H</code>")
        return
        
    keys = []
    date_prefix = get_myanmar_time().strftime('%Y%m%d')
    
    for _ in range(count):
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        k = f"PSP-{date_prefix}{random_str}"
        await db.create_key(k, duration)
        keys.append(f"<code>{k}</code>")
        
    keys_text = "\n".join(keys)
    await message.answer(f"✅ Keys {count} created.\n\n{keys_text}")

@dp.message(F.text.startswith(".add "))
async def cmd_add_uid(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    target_id = message.text.split(" ")[1].strip()
    await db.add_allowed_uid(target_id)
    await message.answer("✅ UID added.")

@dp.message(F.text.startswith(".del "))
async def cmd_del_uid(message: types.Message):
    if message.from_user.id != OWNER_ID:
        return
        
    target_id = message.text.split(" ")[1].strip()
    await db.remove_allowed_uid(target_id)
    await message.answer("🗑️ UID removed.")

@dp.message(lambda msg: msg.text and msg.text.startswith("PSP-") and len(msg.text) == 20)
async def process_key_redemption(message: types.Message):
    key_str = message.text.strip()
    key_data = await db.consume_key(key_str)
    
    if key_data:
        td = parse_duration(key_data["duration"]) or timedelta(days=1)
        current_expire = get_myanmar_time()
        
        existing_expire_iso = await db.get_user_subscription(message.from_user.id)
        if existing_expire_iso:
            existing_time = datetime.fromisoformat(existing_expire_iso)
            if existing_time > current_expire:
                current_expire = existing_time
                
        new_expire = current_expire + td
        await db.update_user_subscription(message.from_user.id, new_expire.isoformat())
        
        formatted_expire = new_expire.strftime('%Y-%m-%d %I:%M %p')
        await message.answer(f"ʟɪᴄᴇɴsေ ᴋေʏ ᴀᴄᴛɪᴠေ\nေxᴘɪʀေ ᴛɪᴍေ <b>{formatted_expire}</b> (MMT)")
    else:
        await message.answer("ɪɴᴄᴏʀʀေᴄᴛ ᴋေʏ")

# ==========================================================
# 🤖 Authentication & Login API
# ==========================================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("An ဝင်ရန် Login ကိုနှိပ်ပါ", reply_markup=get_main_keyboard())

@dp.message(F.text == TEXT_LOGIN)
async def login_start(message: types.Message, state: FSMContext):
    await state.set_state(LoginForm.select_site)
    await message.answer("Site ရွေးပါ", reply_markup=get_site_keyboard())

@dp.message(LoginForm.select_site)
async def process_site(message: types.Message, state: FSMContext):
    if message.text == "Back":
        await state.clear()
        await message.answer("Cancelled", reply_markup=get_main_keyboard())
        return
        
    await state.update_data(site=message.text)
    await state.set_state(LoginForm.enter_phone)
    await message.answer("Phone", reply_markup=ReplyKeyboardRemove())

@dp.message(LoginForm.enter_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(LoginForm.enter_password)
    await message.answer("Password")

async def api_get_user_info(site: str, token: str):
    config = SITE_CONFIGS.get(site)
    url = f"{config['api_url']}/GetUserInfo"
    headers = get_headers(site, token)
    payload = get_signed_payload({'language': 7})
    
    async with _DeprecatedSessionGuard() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            return await resp.json()

@dp.message(LoginForm.enter_password)
async def process_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    username = data.get('phone')
    site_name = data.get('site', '777BIGWIN')
    user_tg_id = message.from_user.id
    
    loading_msg = await message.answer("🔄 Login...")

    try:
        config = SITE_CONFIGS.get(site_name)
        login_url = f"{config['api_url']}/Login"
        
        payload = {
            'username': username,
            'pwd': message.text,
            'phonetype': 1,
            'logintype': 'mobile',
            'deviceId': uuid.uuid4().hex,
            'language': 7
        }
        
        headers = get_headers(site_name)
        signed_payload = get_signed_payload(payload)
        
        async with _DeprecatedSessionGuard() as session:
            async with session.post(login_url, headers=headers, json=signed_payload) as resp:
                api_result = await resp.json()
                
        if api_result.get("code") == 0 or api_result.get("msg") == "success":
            data_field = api_result.get("data")
            token = data_field.get("token", "") if isinstance(data_field, dict) else str(data_field)
            
            user_info = await api_get_user_info(site_name, token)
            info_data = user_info.get("data", {}) if user_info.get("code") == 0 else {}
            
            user_id = str(info_data.get("userId", info_data.get("id", "N/A")))
            nickname = info_data.get("nickName", "Unknown")
            balance_val = info_data.get('balance', info_data.get('amount', 0.0))
            balance_text = f"{balance_val} Ks"
            
            db_user = await db.get_user(user_tg_id)
            ai_mode = db_user.get("ai_mode", "Last 4 Pattern") if db_user else "Last 4 Pattern"
            if ai_mode not in VALID_AI_NAMES:
                ai_mode = "Last 4 Pattern"

            login_time = get_myanmar_time().strftime("%Y-%m-%d %H:%M:%S")
            await db.save_user_login(user_tg_id, username, user_id, nickname, balance_text, login_time, ai_mode)
            
            persisted_virtual_balance = await db.get_virtual_balance(user_tg_id)
            active_sessions[user_tg_id] = {
                "site": site_name, 
                "token": token, 
                "game_type_id": 30, 
                "game_type_name": "WINGO_30S",
                "is_auto_betting": False, 
                "ai_mode": ai_mode, 
                "bet_sequence": [10, 20, 40, 80, 160, 320], 
                "current_bet_step": 0,          
                "profit_target": 0, 
                "balance": balance_text,
                "start_balance": extract_balance(balance_text), 
                "session_profit": 0.0, 
                "hit_wait": 0, 
                "current_misses": 0, 
                "is_ai_prediction_enabled": False, 
                "last_predicted_issue": None,
                "is_virtual_mode": False, 
                "virtual_balance": persisted_virtual_balance, 
                "virtual_session_profit": 0.0,
                "upload_channel": False, 
                "model_accuracies": {}, 
                "last_prediction_value": None
            }
            
            await loading_msg.delete()
            success_text = f"🏆 <b>LOGIN SUCCESSFUL!</b>\n{nickname} | {balance_text}"
            await message.answer(success_text, reply_markup=get_logged_in_keyboard())
            await state.set_state(LoginForm.main_menu)
        else:
            await loading_msg.delete()
            err_msg = api_result.get('msg', 'Unknown Error')
            await message.answer(f"❌ Login Failed: {err_msg}", reply_markup=get_main_keyboard())
            await state.clear()
            
    except Exception as e:
        await loading_msg.delete()
        await message.answer(f"⚠️ Error: {e}", reply_markup=get_main_keyboard())
        await state.clear()

# ==========================================================
# 📊 API & Database Deep Scanning Logic
# ==========================================================
async def get_latest_game_result(target_issue, user_tg_id):
    session_data = active_sessions.get(user_tg_id, {})
    site = session_data.get("site")
    token = session_data.get("token")
    type_id = session_data.get("game_type_id", 30)
    
    config = SITE_CONFIGS.get(site)
    url = f"{config['api_url']}/GetNoaverageEmerdList"
    
    payload = {'pageSize': 100, 'pageNo': 1, 'typeId': type_id, 'language': 7}
    headers = get_headers(site, token)
    signed_payload = get_signed_payload(payload)
    
    try:
        async with _DeprecatedSessionGuard() as session:
            async with session.post(url, headers=headers, json=signed_payload) as resp:
                api_result = await resp.json()
                records = api_result.get('data', {}).get('list', [])
                
        for item in records:
            if str(item['issueNumber']) == str(target_issue):
                num = int(item['number'])
                size = "BIG" if num >= 5 else "SMALL"
                return f"{num} | {size}"
    except Exception:
        pass
        
    return "? | ?"

# ==========================================================
# 🧠 GET AI PREDICTION (PSP_AI_PREDICT Version)
# ==========================================================
async def get_ai_prediction(user_tg_id):
    session_data = active_sessions.get(user_tg_id, {})
    if not session_data:
        return None, 0, None, None
        
    site = session_data.get("site")
    token = session_data.get("token")
    type_id = session_data.get("game_type_id", 30)
    
    config = SITE_CONFIGS.get(site)
    url = f"{config['api_url']}/GetNoaverageEmerdList"
    
    payload = {'pageSize': 100, 'pageNo': 1, 'typeId': type_id, 'language': 7}
    headers = get_headers(site, token)
    signed_payload = get_signed_payload(payload)

    try:
        async with _DeprecatedSessionGuard() as session:
            async with session.post(url, headers=headers, json=signed_payload) as resp:
                api_result = await resp.json()
                records = api_result.get('data', {}).get('list', [])
                
        if not records:
            return None, 0, None, None
            
        last_completed_issue = records[0]['issueNumber']
        next_issue = str(int(last_completed_issue) + 1)
        
        for item in records:
            num = int(item['number'])
            size_text = "BIG" if num >= 5 else "SMALL"
            await db.save_game_record(site, type_id, item['issueNumber'], num, size_text)
        
        db_records = await db.get_game_history(site, type_id, limit=5000)
        
        history_list = []
        for item in db_records:
            history_list.append(item['size'])
        
        if not history_list:
            for item in records:
                num = int(item['number'])
                size_text = "BIG" if num >= 5 else "SMALL"
                history_list.append(size_text)
        
        from ai_engines import psp_ai_predict
        
        result = psp_ai_predict(history_list)
        
        predicted_size = result["prediction"]
        confidence = result["confidence"]
        reason = result["reason"]
        display = result["display"]
        
        user_ai_name = session_data.get("ai_mode", "PSP_AI_PREDICT")
        
        if user_ai_name == "Set Pattern":
            pat = session_data.get("custom_pattern", ["BIG"])
            step = session_data.get("custom_pattern_step", 0)
            target_bet = pat[step]
            
            if step == 0:
                recent_num = int(records[0]['number'])
                recent_size = "BIG" if recent_num >= 5 else "SMALL"
                trigger_size = "SMALL" if target_bet == "BIG" else "BIG"
                if recent_size != trigger_size:
                    return "wait", 100, next_issue, user_ai_name
                    
            return target_bet.lower(), 100, next_issue, user_ai_name
        
        elif user_ai_name != "PSP_AI_PREDICT":
            mode_key = "pattern"
            for key, val in ai_engines.AI_MODES.items():
                if val["name"] == user_ai_name:
                    mode_key = key
                    break
            
            model_acc = session_data.get("model_accuracies", {})
            predicted_size, _, confidence, _ = ai_engines.get_prediction(
                history_docs=db_records,
                mode=mode_key,
                model_accuracies=model_acc
            )
            return predicted_size.lower(), confidence, next_issue, user_ai_name
        
        return predicted_size.lower(), confidence, next_issue, user_ai_name
        
    except Exception as e:
        print(f"Prediction Error: {e}")
        return None, 0, None, None

async def place_auto_bet(user_tg_id, current_issue, bet_type, total_amount=10, silent=False):
    try:
        session = active_sessions.get(user_tg_id)
        if not session or "token" not in session:
            return False
            
        site = session["site"]
        token = session["token"]
        type_id = session.get("game_type_id", 30)
        
        if total_amount >= 10000:
            base, count = 10000, total_amount // 10000
        elif total_amount >= 1000:
            base, count = 1000, total_amount // 1000
        elif total_amount >= 100:
            base, count = 100, total_amount // 100
        else:
            base, count = 10, total_amount // 10
            
        payload = {
            'typeId': type_id, 
            'issuenumber': current_issue, 
            'amount': base, 
            'betCount': count, 
            'gameType': 2, 
            'selectType': get_select_type(bet_type), 
            'language': 7
        }
        
        config = SITE_CONFIGS.get(site)
        url = f"{config['api_url']}/GameBetting"
        headers = get_headers(site, token)
        signed_payload = get_signed_payload(payload)
        
        async with aiohttp.ClientSession() as http:
            async with http.post(url, headers=headers, json=signed_payload) as resp:
                res = await resp.json()
                
        if res.get("code") == 0 or res.get("msg") == "success":
            return True
        return False
        
    except Exception:
        return False

def update_model_accuracies(user_tg_id, actual_result_size):
    if user_tg_id not in active_sessions:
        return
        
    session = active_sessions[user_tg_id]
    if "model_accuracies" not in session:
        session["model_accuracies"] = {}
        
    active_ai = session.get("ai_mode")
    last_pred = session.get("last_prediction_value")
    
    if last_pred and actual_result_size and last_pred != "wait" and actual_result_size != "?":
        is_win = (last_pred.lower() == actual_result_size.lower())
        current_acc = session["model_accuracies"].get(active_ai, 0.5)
        new_acc = (current_acc * 0.8) + (1.0 if is_win else 0.0) * 0.2
        session["model_accuracies"][active_ai] = new_acc

# ==========================================================
# 🔮 AI Loops & Features
# ==========================================================
@dp.message(F.text == TEXT_PREDICT)
async def btn_ai_prediction_toggle(message: types.Message):
    if message.from_user.id not in active_sessions:
        await message.answer("Login ဝင်ပေးပါ။")
        return
        
    is_enabled = active_sessions[message.from_user.id].get("is_ai_prediction_enabled", False)
    await message.answer("AI Prediction Broadcast", reply_markup=get_ai_prediction_toggle_keyboard(is_enabled))

@dp.callback_query(F.data == "toggle_aipred")
async def process_toggle_aipred(callback: types.CallbackQuery):
    user_tg_id = callback.from_user.id
    if user_tg_id not in active_sessions:
        await callback.answer("Session Expired.")
        return
        
    new_state = not active_sessions[user_tg_id].get("is_ai_prediction_enabled", False)
    active_sessions[user_tg_id]["is_ai_prediction_enabled"] = new_state
    
    await callback.message.edit_reply_markup(reply_markup=get_ai_prediction_toggle_keyboard(new_state))
    if new_state:
        if not prediction_tasks.get(user_tg_id) or prediction_tasks[user_tg_id].done():
            task = asyncio.create_task(prediction_broadcast_loop(user_tg_id, callback.message), name=f"prediction-{user_tg_id}")
            prediction_tasks[user_tg_id] = task
            task.add_done_callback(lambda t, uid=user_tg_id: prediction_tasks.pop(uid, None))

async def prediction_broadcast_loop(user_tg_id, message: types.Message):
    if "current_win_streak" not in active_sessions.get(user_tg_id, {}):
        active_sessions[user_tg_id].update({
            "current_win_streak": 0, 
            "current_lose_streak": 0, 
            "longest_win_streak": 0, 
            "longest_lose_streak": 0
        })
        
    while active_sessions.get(user_tg_id, {}).get("is_ai_prediction_enabled", False):
        try:
            pred, conf, issue, ai_name = await get_ai_prediction(user_tg_id)
            if pred == "wait":
                await asyncio.sleep(2)
                continue
                
            last_issue = active_sessions[user_tg_id].get("last_predicted_issue")
            gn = active_sessions[user_tg_id].get("game_type_name", "WINGO_30S")

            if issue and issue != last_issue:
                if gn == "WINGO_1M":
                    await asyncio.sleep(30)
                elif gn == "WINGO_30S":
                    await asyncio.sleep(10)
                    
                active_sessions[user_tg_id]["last_predicted_issue"] = issue
                active_sessions[user_tg_id]["last_prediction_value"] = pred
                
                lw = active_sessions[user_tg_id]["longest_win_streak"]
                ll = active_sessions[user_tg_id]["longest_lose_streak"]
                
                txt = (
                    f"<blockquote>\n"
                    f"☉ Ai Prediction - Live\n"
                    f"☉ {gn} : <code>{issue}</code>\n"
                    f"☉ Prediction : <b>{pred.upper()}</b> 〔 {lw} 〕|〔 {ll} 〕\n"
                    f"☉ Status : Waiting...\n"
                    f"</blockquote>"
                )
                pred_msg = await message.answer(txt)
                
                ch_msg_id = None
                if active_sessions[user_tg_id].get("upload_channel") and CHANNEL_ID:
                    ch_msg = await bot.send_message(chat_id=CHANNEL_ID, text=txt)
                    ch_msg_id = ch_msg.message_id
                
                res = "? | ?"
                wait_limit = 60 if gn == "WINGO_1M" else 30
                
                for _ in range(wait_limit):
                    if not active_sessions.get(user_tg_id, {}).get("is_ai_prediction_enabled", False):
                        break
                    await asyncio.sleep(1)
                    res = await get_latest_game_result(issue, user_tg_id)
                    if res != "? | ?":
                        break
                
                if res != "? | ?":
                    actual = res.split(" | ")[1].strip().lower()
                    update_model_accuracies(user_tg_id, actual)
                    
                    if pred.lower() == actual:
                        stat = f"✔WIN{res}"
                        active_sessions[user_tg_id]["current_win_streak"] += 1
                        active_sessions[user_tg_id]["current_lose_streak"] = 0
                        new_max_win = max(active_sessions[user_tg_id]["longest_win_streak"], active_sessions[user_tg_id]["current_win_streak"])
                        active_sessions[user_tg_id]["longest_win_streak"] = new_max_win
                    else:
                        stat = f"✖LOSE{res}"
                        active_sessions[user_tg_id]["current_lose_streak"] += 1
                        active_sessions[user_tg_id]["current_win_streak"] = 0
                        new_max_lose = max(active_sessions[user_tg_id]["longest_lose_streak"], active_sessions[user_tg_id]["current_lose_streak"])
                        active_sessions[user_tg_id]["longest_lose_streak"] = new_max_lose
                else:
                    stat = "DRAW"
                
                lw = active_sessions[user_tg_id]["longest_win_streak"]
                ll = active_sessions[user_tg_id]["longest_lose_streak"]
                
                try:
                    ftxt = (
                        f"<blockquote>\n"
                        f"☉ Ai Prediction - Live\n"
                        f"☉ {gn} : <code>{issue}</code>\n"
                        f"☉ Prediction : <b>{pred.upper()}</b> 〔 {lw} 〕|〔 {ll} 〕\n"
                        f"☉ Status : {stat}\n"
                        f"</blockquote>"
                    )
                    await pred_msg.edit_text(ftxt)
                    if ch_msg_id:
                        await bot.edit_message_text(chat_id=CHANNEL_ID, message_id=ch_msg_id, text=ftxt)
                except Exception:
                    pass
                    
            await asyncio.sleep(2)
        except Exception:
            await asyncio.sleep(5)

async def auto_bet_loop(user_tg_id, message: types.Message):
    await message.answer("🚀 Auto-Bet စတင်ပါပြီ! 🛑 Stop Auto-Bet ဖြင့် ရပ်တန့်ပါ။")
    
    last_issue = None
    session = active_sessions[user_tg_id]
    is_virtual = session.get("is_virtual_mode", False)
    gn = session.get("game_type_name", "WINGO_30S")
    
    current_win_streak = 0
    current_lose_streak = 0
    longest_win_streak = 0
    longest_lose_streak = 0
    total_bets = 0
    total_wins = 0
    total_losses = 0
    
    if not is_virtual:
        site_config = SITE_CONFIGS.get(session['site'])
        bal_url = f"{site_config['api_url']}/GetBalance"
        bal_headers = get_headers(session["site"], session["token"])

    while active_sessions.get(user_tg_id, {}).get("is_auto_betting", False):
        try:
            pred, _, issue, ai_name = await get_ai_prediction(user_tg_id)
            
            if issue and issue != last_issue:
                if gn == "WINGO_1M":
                    await asyncio.sleep(30)
                    
                if pred == "wait":
                    msg_txt = (
                        f"<blockquote>\n"
                        f"☉ Trigger စောင့်နေပါသည်\n"
                        f"☉ {gn} : <code>{issue}</code>\n"
                        f"</blockquote>"
                    )
                    msg = await message.answer(msg_txt)
                    last_issue = issue
                    asyncio.create_task(delete_message_later(msg, 7))
                    await asyncio.sleep(2)
                    continue 
                    
                hw = session.get("hit_wait", 0)
                cm = session.get("current_misses", 0)
                
                if hw > 0 and cm < hw:
                    hit_txt = (
                        f"<blockquote>\n"
                        f"☉ Hit Wait: {cm}/{hw}\n"
                        f"☉ {gn} : <code>{issue}</code>\n"
                        f"☉ Pred: {pred.upper()}\n"
                        f"</blockquote>"
                    )
                    msg = await message.answer(hit_txt)
                    
                    res = "? | ?"
                    for _ in range(45):
                        if not active_sessions.get(user_tg_id, {}).get("is_auto_betting"):
                            break
                        await asyncio.sleep(2)
                        res = await get_latest_game_result(issue, user_tg_id)
                        if res != "? | ?":
                            break
                            
                    try:
                        actual = res.split(" | ")[1].strip().lower()
                        update_model_accuracies(user_tg_id, actual)
                        
                        if pred.lower() == actual:
                            active_sessions[user_tg_id]["current_misses"] = 0
                            await msg.edit_text(f"AI အမှန်ခန့်မှန်း (Reset)\nResult: {res}")
                        elif actual != "?": 
                            active_sessions[user_tg_id]["current_misses"] += 1
                            if active_sessions[user_tg_id]["current_misses"] >= hw:
                                await msg.edit_text("🎯 Target Reached!")
                            else:
                                await msg.edit_text(f"❌ Loss: {active_sessions[user_tg_id]['current_misses']}/{hw}")
                                
                        asyncio.create_task(delete_message_later(msg, 5)) 
                    except Exception:
                        pass
                        
                    last_issue = issue
                    await asyncio.sleep(2)
                    continue 

                seq = session.get("bet_sequence", [10])
                step = session.get("current_bet_step", 0)
                if step >= len(seq):
                    step = 0
                amt = seq[step]

                if is_virtual:
                    c_bal = session.get("virtual_balance", 0.0)
                else:
                    async with aiohttp.ClientSession() as http:
                        payload = get_signed_payload({'language': 7})
                        async with http.post(bal_url, headers=bal_headers, json=payload) as resp:
                            bal_data = (await resp.json()).get("data", {})
                            c_bal_raw = bal_data.get("balance", bal_data.get("amount", 0.0)) if isinstance(bal_data, dict) else bal_data
                            c_bal = float(c_bal_raw)
                
                if c_bal < amt:
                    await message.answer("လက်ကျန်ငွေမလုံလောက်ပါ။")
                    active_sessions[user_tg_id]["is_auto_betting"] = False
                    break

                active_sessions[user_tg_id]["last_prediction_value"] = pred
                bet_txt = (
                    f"<blockquote>\n"
                    f"☉ {gn} : <code>{issue}</code>\n"
                    f"☉ {ai_name}\n"
                    f"☉ Pred: <b>{pred.upper()}</b> | {amt} Ks\n"
                    f"</blockquote>"
                )
                await message.answer(bet_txt)
                last_issue = issue
                await asyncio.sleep(7) 

                # ✅ FIX: Virtual Mode မှာ Random မသုံးတော့ပါ။ API Real Data ကိုသာ စောင့်ယူမည်။
                if is_virtual:
                    res = await get_latest_game_result(issue, user_tg_id)
                    for _ in range(45):
                        if not active_sessions.get(user_tg_id, {}).get("is_auto_betting"):
                            break 
                        if res != "? | ?":
                            break
                        await asyncio.sleep(2)
                        res = await get_latest_game_result(issue, user_tg_id)
                else: 
                    success = await place_auto_bet(user_tg_id, issue, pred, amt, True)
                    if not success:
                        await asyncio.sleep(5)
                        continue
                        
                    res = "? | ?"
                    for _ in range(45):
                        if not active_sessions.get(user_tg_id, {}).get("is_auto_betting"):
                            break 
                        await asyncio.sleep(2)
                        res = await get_latest_game_result(issue, user_tg_id)
                        if res != "? | ?":
                            break 
                
                if is_virtual:
                    try:
                        actual_str = res.split(" | ")[1].strip().lower()
                        if pred.lower() == actual_str:
                            session["virtual_balance"] += amt * 0.96
                        else:
                            session["virtual_balance"] -= amt
                        n_bal = session["virtual_balance"]
                        await db.update_virtual_balance(user_tg_id, n_bal)
                    except Exception:
                        pass
                else:
                    async with aiohttp.ClientSession() as http:
                        payload = get_signed_payload({'language': 7})
                        async with http.post(bal_url, headers=bal_headers, json=payload) as resp:
                            bal_data = (await resp.json()).get("data", {})
                            n_bal_raw = bal_data.get("balance", bal_data.get("amount", 0.0)) if isinstance(bal_data, dict) else bal_data
                            n_bal = float(n_bal_raw)

                try:
                    actual = res.split(" | ")[1].strip().lower() 
                    update_model_accuracies(user_tg_id, actual)
                    
                    total_bets += 1
                    
                    if pred.lower() == actual:
                        prof = amt * 0.96
                        stat = f"☉ <b>WIN</b> ✔ +{prof} Ks"
                        
                        if is_virtual:
                            session["virtual_session_profit"] += prof
                        else:
                            active_sessions[user_tg_id]["session_profit"] += prof
                            
                        active_sessions[user_tg_id]["current_bet_step"] = 0
                        active_sessions[user_tg_id]["current_misses"] = 0
                        
                        current_win_streak += 1
                        current_lose_streak = 0
                        total_wins += 1
                        
                        if current_win_streak > longest_win_streak:
                            longest_win_streak = current_win_streak
                        
                    elif actual == "?":
                        stat = "⚙️ DRAW (Pending)"
                    else:
                        stat = f"☉ <b>LOSE</b> ✖ {amt} Ks"
                        
                        if is_virtual:
                            session["virtual_session_profit"] -= amt
                        else:
                            active_sessions[user_tg_id]["session_profit"] -= amt
                            
                        active_sessions[user_tg_id]["current_bet_step"] = (step + 1) % len(seq)
                        
                        current_lose_streak += 1
                        current_win_streak = 0
                        total_losses += 1
                        
                        if current_lose_streak > longest_lose_streak:
                            longest_lose_streak = current_lose_streak
                        
                    if ai_name == "Set Pattern" and actual != "?":
                        current_c_step = session.get("custom_pattern_step", 0)
                        pat_len = len(session.get("custom_pattern", ["BIG"]))
                        active_sessions[user_tg_id]["custom_pattern_step"] = (current_c_step + 1) % pat_len
                        
                    if is_virtual:
                        c_prof = session.get("virtual_session_profit", 0.0)
                    else:
                        c_prof = active_sessions[user_tg_id].get("session_profit", 0.0)
                    
                    win_rate = (total_wins / total_bets) * 100 if total_bets > 0 else 0.0
                    
                    result_txt = (
                        f"<blockquote>\n"
                        f"{stat}\n"
                        f"───────────────\n"
                        f"☉ {gn} : <code>{issue}</code>\n"
                        f"☉ Result: <code>{res}</code>\n"
                        f"☉ Bal: K{n_bal:,.2f} 〔{longest_win_streak} | {longest_lose_streak}〕\n"
                        f"☉ Total Profit: {c_prof:,.2f} Ks\n"
                        f"</blockquote>"
                    )
                    
                    await message.answer(result_txt)
                    
                    if not is_virtual:
                        await db.update_user_balance(user_tg_id, f"{n_bal:.2f} Ks")
                        
                    profit_target = session.get("profit_target", 0)
                    if profit_target > 0 and c_prof >= profit_target:
                        await message.answer("🎉 Target ပြည့်ပါပြီ။ Stop.")
                        active_sessions[user_tg_id]["is_auto_betting"] = False
                        break
                        
                except Exception:
                    pass
            else:
                await asyncio.sleep(5) 
                
        except Exception as e:
            print(f"Loop Error: {e}")
            await asyncio.sleep(5)

# ==========================================================
# 🎯 Feature Handlers
# ==========================================================

@dp.message(F.text == TEXT_UPLOAD_CHANNEL)
async def cmd_upload_channel_menu(msg: types.Message):
    if msg.from_user.id not in active_sessions:
        return
    is_on = active_sessions[msg.from_user.id].get('upload_channel')
    status_str = 'ON 🟢' if is_on else 'OFF 🔴'
    await msg.answer(f"📡 <b>Upload Channel</b>\nလက်ရှိ: {status_str}", reply_markup=get_upload_toggle_keyboard())

@dp.message(F.text.in_(["✅ Upload ON", "❌ Upload OFF"]))
async def cmd_toggle_upload(msg: types.Message):
    if msg.from_user.id not in active_sessions:
        return
    is_on = (msg.text == "✅ Upload ON")
    active_sessions[msg.from_user.id]["upload_channel"] = is_on
    await msg.answer(f"✅ Upload Channel: {'ON' if is_on else 'OFF'}", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_HIT)
async def btn_hit_betting(msg: types.Message):
    if msg.from_user.id in active_sessions:
        current_wait = active_sessions[msg.from_user.id].get("hit_wait", 0)
        await msg.answer("🎯 Hit Betting", reply_markup=get_hit_betting_inline_keyboard(current_wait))

@dp.callback_query(F.data.startswith("hitbet_"))
async def process_hit_bet(cb: types.CallbackQuery):
    user_id = cb.from_user.id
    if user_id in active_sessions:
        wait_val = int(cb.data.split("_")[1])
        active_sessions[user_id]["hit_wait"] = wait_val
        active_sessions[user_id]["current_misses"] = 0
        await cb.message.edit_reply_markup(reply_markup=get_hit_betting_inline_keyboard(wait_val))

@dp.message(F.text == TEXT_PROFIT)
async def btn_set_profit(msg: types.Message, state: FSMContext):
    if msg.from_user.id in active_sessions:
        target = active_sessions[msg.from_user.id].get('profit_target', 0)
        await state.set_state(LoginForm.enter_profit_target)
        await msg.answer(f"🎯 Target: {target}", reply_markup=get_cancel_keyboard())

@dp.message(LoginForm.enter_profit_target)
async def process_profit(msg: types.Message, state: FSMContext):
    if msg.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        await msg.answer("❌ Cancelled", reply_markup=get_logged_in_keyboard())
        return
        
    if msg.text.isdigit():
        active_sessions[msg.from_user.id]["profit_target"] = int(msg.text)
        await state.set_state(LoginForm.main_menu)
        await msg.answer(f"✅ Profit: {msg.text}", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_AI)
async def cmd_ai_mode(msg: types.Message):
    if msg.from_user.id in active_sessions:
        current_mode = active_sessions[msg.from_user.id].get('ai_mode')
        await msg.answer(f"🤖 Mode: {current_mode}", reply_markup=get_ai_mode_keyboard())

@dp.message(F.text.in_(VALID_AI_NAMES))
async def set_ai_mode(msg: types.Message, state: FSMContext):
    if msg.text == "Set Pattern":
        await state.set_state(LoginForm.enter_custom_pattern)
        await msg.answer("🛠️ ဥပမာ: BSBS", reply_markup=get_cancel_keyboard())
        return
        
    active_sessions[msg.from_user.id]["ai_mode"] = msg.text
    await db.update_user_ai_mode(msg.from_user.id, msg.text)
    await msg.answer(f"✅ AI: {msg.text}", reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.enter_custom_pattern)
async def process_custom_pattern(msg: types.Message, state: FSMContext):
    if msg.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        await msg.answer("❌ Cancelled", reply_markup=get_logged_in_keyboard())
        return
        
    rp = msg.text.upper().replace(" ", "")
    if not all(c in ['B', 'S'] for c in rp) or not rp:
        await msg.answer("❌ B/S သာရိုက်ပါ။")
        return
        
    if msg.from_user.id in active_sessions:
        pattern_list = ["BIG" if c == 'B' else "SMALL" for c in rp]
        active_sessions[msg.from_user.id].update({
            "custom_pattern": pattern_list, 
            "custom_pattern_step": 0, 
            "ai_mode": "Set Pattern"
        })
        
    await db.update_user_ai_mode(msg.from_user.id, "Set Pattern")
    await state.set_state(LoginForm.main_menu)
    await msg.answer(f"✅ Pattern: {rp}", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == "BACK")
async def back_to_main(msg: types.Message):
    await msg.answer("Menu", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_BETSIZE)
async def btn_set_betsize(msg: types.Message, state: FSMContext):
    if msg.from_user.id in active_sessions:
        seq = active_sessions[msg.from_user.id].get('bet_sequence', [10])
        seq_str = '-'.join(map(str, seq))
        await state.set_state(LoginForm.enter_bet_sequence)
        await msg.answer(f"⚙️ Seq: {seq_str}", reply_markup=get_cancel_keyboard())

@dp.message(LoginForm.enter_bet_sequence)
async def process_bet_seq(msg: types.Message, state: FSMContext):
    if msg.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        await msg.answer("❌ Cancelled", reply_markup=get_logged_in_keyboard())
        return
        
    try:
        s = [int(x.strip()) for x in msg.text.split('-')]
        if not s or any(x <= 0 or x > MAX_BET for x in s):
            raise ValueError
            
        active_sessions[msg.from_user.id].update({
            "bet_sequence": s, 
            "current_bet_step": 0
        })
        
        await state.set_state(LoginForm.main_menu)
        await msg.answer(f"✅ Seq: {'-'.join(map(str, s))}", reply_markup=get_logged_in_keyboard())
        
    except Exception:
        await msg.answer("❌ မှားယွင်းနေပါသည်။ ဥပမာ: 10-20-40")

@dp.message(F.text == TEXT_START)
async def btn_start(msg: types.Message):
    user_id = msg.from_user.id
    if user_id in active_sessions and not active_sessions[user_id].get("is_auto_betting"):
        if "bet_sequence" not in active_sessions[user_id]:
            active_sessions[user_id].update({"bet_sequence": [10, 20, 40, 80, 160, 320], "current_bet_step": 0})
            
        if auto_tasks.get(user_id) and not auto_tasks[user_id].done():
            await msg.answer("⚠️ Auto-Bet is already running.")
            return
        active_sessions[user_id].update({"is_auto_betting": True, "session_profit": 0.0, "virtual_session_profit": 0.0, "current_bet_step": 0})
        task = asyncio.create_task(auto_bet_loop(user_id, msg), name=f"auto-bet-{user_id}")
        auto_tasks[user_id] = task
        task.add_done_callback(lambda t, uid=user_id: auto_tasks.pop(uid, None))

@dp.message(F.text == TEXT_STOP)
async def btn_stop(msg: types.Message):
    if msg.from_user.id in active_sessions:
        active_sessions[msg.from_user.id]["is_auto_betting"] = False
        task = auto_tasks.get(msg.from_user.id)
        if task and not task.done():
            task.cancel()
        await msg.answer("🛑 Stopped.")

@dp.message(F.text == TEXT_STATUS)
async def btn_status(msg: types.Message):
    if msg.from_user.id in active_sessions:
        s = active_sessions[msg.from_user.id]
        v = s.get("is_virtual_mode")
        
        mode_str = 'Virtual' if v else 'Real'
        running_str = 'Running 🟢' if s.get('is_auto_betting') else 'Stopped 🔴'
        seq_str = '-'.join(map(str, s.get('bet_sequence', [])))
        step_str = s.get('current_bet_step', 0) + 1
        
        if v:
            bal_val = s.get('virtual_balance', 0.0)
            prof_val = s.get('virtual_session_profit', 0.0)
        else:
            bal_val = s.get('start_balance', 0.0)
            prof_val = s.get('session_profit', 0.0)
            
        txt = (
            f"📊 Status: {mode_str} | {running_str}\n"
            f"🤖 AI: {s.get('ai_mode')}\n"
            f"⚙️ Seq: {seq_str} (Step {step_str})\n"
            f"💰 Bal: {bal_val:.2f}\n"
            f"📈 Profit: {prof_val:.2f}"
        )
        await msg.answer(txt)

@dp.message(LoginForm.main_menu, F.text == TEXT_BALANCE)
async def check_balance(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in active_sessions:
        return
        
    s = active_sessions[msg.from_user.id]
    lm = await msg.answer("🔄 Checking...")
    
    try:
        if s.get("is_virtual_mode"):
            bal = f"{s.get('virtual_balance', 0.0):.2f} Ks"
        else:
            url = f"{SITE_CONFIGS[s['site']]['api_url']}/GetBalance"
            headers = get_headers(s["site"], s["token"])
            payload = get_signed_payload({'language': 7})
            
            async with _DeprecatedSessionGuard() as http:
                async with http.post(url, headers=headers, json=payload) as resp:
                    resp_json = await resp.json()
                    d = resp_json.get("data", {})
                    
                    if isinstance(d, dict):
                        bal_raw = d.get('balance', d.get('amount', 0.0))
                    else:
                        bal_raw = d
                        
                    bal = f"{float(bal_raw):.2f} Ks"
                    
        await state.update_data(balance=bal)
        await lm.delete()
        await msg.answer(f"💰 Balance: {bal}", reply_markup=get_logged_in_keyboard())
        
    except Exception:
        await lm.delete()
        await msg.answer("⚠️ Error", reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.main_menu, F.text == TEXT_INFO)
async def show_info(msg: types.Message, state: FSMContext):
    d = await state.get_data()
    s = active_sessions.get(msg.from_user.id, {})
    exp = await db.get_user_subscription(msg.from_user.id)
    
    exp_str = datetime.fromisoformat(exp).strftime('%Y-%m-%d %I:%M %p') if exp else 'N/A'
    
    info_txt = (
        f"👤 User: {d.get('username')}\n"
        f"🌐 Site: {s.get('site')}\n"
        f"💰 Bal: {d.get('balance')}\n"
        f"🔑 Exp: {exp_str}"
    )
    await msg.answer(info_txt, reply_markup=get_logged_in_keyboard())

@dp.message(LoginForm.main_menu, F.text == TEXT_LOGOUT)
async def logout(msg: types.Message, state: FSMContext):
    if msg.from_user.id in active_sessions:
        del active_sessions[msg.from_user.id]
        
    await state.clear()
    await msg.answer("👋 Logged out.", reply_markup=get_main_keyboard())

@dp.message(F.text == "Pro AI Features")
async def cmd_pro_ai_menu(msg: types.Message):
    if msg.from_user.id in active_sessions:
        await msg.answer("Pro AI Features (Advanced Deep Scan)", reply_markup=get_pro_ai_mode_keyboard())

@dp.message(F.text == TEXT_GAMES)
async def cmd_games(msg: types.Message, state: FSMContext):
    if msg.from_user.id in active_sessions:
        gn = active_sessions[msg.from_user.id].get('game_type_name')
        await state.set_state(LoginForm.select_game_type)
        await msg.answer(f"🎮 Current: {gn}", reply_markup=get_game_type_keyboard())

@dp.message(LoginForm.select_game_type)
async def process_game_type(msg: types.Message, state: FSMContext):
    if msg.text.upper() == "BACK":
        await state.set_state(LoginForm.main_menu)
        await msg.answer("Menu", reply_markup=get_logged_in_keyboard())
        return
        
    if msg.text in ["Win Go 30s", "Win Go 1m"]:
        is_30s = (msg.text == "Win Go 30s")
        active_sessions[msg.from_user.id].update({
            "game_type_id": 30 if is_30s else 1, 
            "game_type_name": "WINGO_30S" if is_30s else "WINGO_1M"
        })
        
        await state.set_state(LoginForm.main_menu)
        await msg.answer(f"✅ Game: {msg.text}", reply_markup=get_logged_in_keyboard())

@dp.message(F.text == TEXT_VIRTUAL_MODE)
async def cmd_virtual_mode(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in active_sessions:
        return
        
    if active_sessions[msg.from_user.id].get("is_virtual_mode"):
        await msg.answer("✅ Virtual Mode active.")
        return
        
    await state.set_state(LoginForm.enter_virtual_balance)
    await msg.answer("🧪 Virtual Balance? (e.g. 10000)", reply_markup=get_cancel_keyboard())

@dp.message(LoginForm.enter_virtual_balance)
async def process_virtual_bal(msg: types.Message, state: FSMContext):
    if msg.text.lower() == 'cancel':
        await state.set_state(LoginForm.main_menu)
        await msg.answer("❌ Cancelled", reply_markup=get_logged_in_keyboard())
        return
        
    try:
        vb = float(msg.text.replace(",", ""))
        active_sessions[msg.from_user.id].update({
            "is_virtual_mode": True, 
            "virtual_balance": vb, 
            "virtual_session_profit": 0.0, 
            "start_balance": vb
        })
        
        await db.set_virtual_balance(msg.from_user.id, vb)
        await state.set_state(LoginForm.main_menu)
        await msg.answer(f"🧪 Virtual Mode Started (K{vb:,.2f})", reply_markup=get_logged_in_keyboard())
        
    except Exception:
        await msg.answer("❌ Number only.", reply_markup=get_cancel_keyboard())

@dp.message(F.text == TEXT_REAL_MODE)
async def cmd_real_mode(msg: types.Message):
    user_id = msg.from_user.id
    if user_id in active_sessions and active_sessions[user_id].get("is_virtual_mode"):
        balance_str = active_sessions[user_id].get("balance", "0.00 Ks")
        active_sessions[user_id].update({
            "is_virtual_mode": False, 
            "session_profit": 0.0, 
            "start_balance": extract_balance(balance_str)
        })
        await msg.answer("🔴 Real Mode Started", reply_markup=get_logged_in_keyboard())

async def main():
    global http_session
    print("🚀 Auto-Bet Bot Started")
    await db.ensure_indexes()
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        for task in list(auto_tasks.values()) + list(prediction_tasks.values()):
            task.cancel()
        if http_session and not http_session.closed:
            await http_session.close()
        await db.client.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")
