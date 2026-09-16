import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "").strip()
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is required")

client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
db = client[os.getenv("MONGO_DB_NAME", "autobet_db")]
users_collection = db["users"]
keys_collection = db["keys"]
allowed_uids_collection = db["allowed_uids"]
ai_states_collection = db["ai_states"]
game_history_collection = db["game_history"]

async def ensure_indexes():
    await users_collection.create_index("expire_date")
    await keys_collection.create_index("key", unique=True)
    await allowed_uids_collection.create_index("uid", unique=True)
    await ai_states_collection.create_index([("user_id", 1), ("model_name", 1)], unique=True)
    await game_history_collection.create_index([("site", 1), ("game_type", 1), ("issue", -1)])

async def get_user(user_id: int):
    return await users_collection.find_one({"_id": user_id})

async def save_user_login(user_id, phone, site_user_id, nickname, balance, login_time, ai_mode):
    await users_collection.update_one({"_id": user_id}, {"$set": {
        "phone": phone, "user_id": site_user_id, "nickname": nickname,
        "balance": balance, "last_login": login_time, "ai_mode": ai_mode
    }}, upsert=True)

async def update_user_ai_mode(user_id, ai_mode):
    await users_collection.update_one({"_id": user_id}, {"$set": {"ai_mode": ai_mode}}, upsert=True)

async def update_user_balance(user_id, balance):
    await users_collection.update_one({"_id": user_id}, {"$set": {"balance": balance}}, upsert=True)

async def add_allowed_uid(uid):
    await allowed_uids_collection.update_one({"uid": uid}, {"$set": {"uid": uid}}, upsert=True)

async def remove_allowed_uid(uid):
    await allowed_uids_collection.delete_one({"uid": uid})

async def is_uid_allowed(uid):
    return bool(await allowed_uids_collection.find_one({"uid": uid}, {"_id": 1}))

async def create_key(key_str, duration):
    await keys_collection.insert_one({"key": key_str, "duration": duration, "created_at": __import__('datetime').datetime.utcnow()})

async def consume_key(key_str):
    # Atomic one-time redemption; prevents two users redeeming the same key.
    return await keys_collection.find_one_and_delete({"key": key_str})

async def get_key(key_str):
    return await keys_collection.find_one({"key": key_str})

async def delete_key(key_str):
    await keys_collection.delete_one({"key": key_str})

async def update_user_subscription(user_id, expire_iso):
    await users_collection.update_one({"_id": user_id}, {"$set": {"expire_date": expire_iso}}, upsert=True)

async def get_user_subscription(user_id):
    user = await get_user(user_id)
    return user.get("expire_date") if user else None

async def set_virtual_balance(user_id, balance):
    await users_collection.update_one({"_id": user_id}, {"$set": {"virtual_balance": float(balance)}}, upsert=True)

async def get_virtual_balance(user_id):
    user = await get_user(user_id)
    return float(user.get("virtual_balance", 0.0)) if user else 0.0

async def update_virtual_balance(user_id, balance):
    await users_collection.update_one({"_id": user_id}, {"$set": {"virtual_balance": float(balance)}}, upsert=True)

async def save_ai_state(user_id, model_name, state_data):
    await ai_states_collection.update_one({"user_id": user_id, "model_name": model_name}, {"$set": {"state_data": state_data}}, upsert=True)

async def get_ai_state(user_id, model_name):
    doc = await ai_states_collection.find_one({"user_id": user_id, "model_name": model_name})
    return doc.get("state_data", {}) if doc else {}

async def save_game_record(site, game_type, issue, number, size):
    await game_history_collection.update_one(
        {"site": site, "game_type": game_type, "issue": str(issue)},
        {"$set": {"number": int(number), "size": size}}, upsert=True)

async def get_game_history(site, game_type, limit=5000):
    limit = max(1, min(int(limit), 10000))
    return await game_history_collection.find({"site": site, "game_type": game_type}).sort("issue", -1).limit(limit).to_list(length=limit)

async def delete_old_history(site, game_type, keep_count=9000):
    keep_count = max(100, int(keep_count))
    ids = await game_history_collection.find({"site": site, "game_type": game_type}, {"_id": 1}).sort("issue", -1).skip(keep_count).to_list(length=100000)
    if ids:
        await game_history_collection.delete_many({"_id": {"$in": [x["_id"] for x in ids]}})
