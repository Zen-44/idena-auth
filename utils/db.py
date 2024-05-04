import sqlite3
import secrets
from utils.logger import get_logger

log = get_logger("DB")

conn = sqlite3.connect("bot.db", check_same_thread = False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS guilds (guild_id TEXT PRIMARY KEY, undefined_role_id TEXT, newbie_role_id TEXT, verified_role_id TEXT, human_role_id TEXT, suspended_role_id TEXT, zombie_role_id TEXT, bot_manager_role_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, address TEXT)") # discord user id
cursor.execute("CREATE TABLE IF NOT EXISTS pending_auth (user_id TEXT PRIMARY KEY, address TEXT, nonce TEXT)")

async def add_guild(guild_id: str):
    cursor.execute("INSERT INTO guilds (guild_id) VALUES (?)", (guild_id,))
    log.info(f"Added guild {guild_id} to the database")
    conn.commit()

async def remove_guild(guild_id: str):
    cursor.execute("DELETE FROM guilds WHERE guild_id = ?", (guild_id,))
    log.info(f"Removed guild {guild_id} from the database")
    conn.commit()

async def set_bot_manager(guild_id: str, role_id: str):
    cursor.execute("UPDATE guilds SET bot_manager_role_id = ? WHERE guild_id = ?", (role_id, guild_id))
    log.info(f"Set bot manager role {role_id} in guild {guild_id}")
    conn.commit()

async def get_bot_manager(guild_id: str):
    cursor.execute("SELECT bot_manager_role_id FROM guilds WHERE guild_id = ?", (guild_id,))
    bot_manager = cursor.fetchone()
    return bot_manager[0]

async def bind_role(guild_id: str, status: str, role_id: str):
    if status == "Not Validated":
        status = "undefined"
    cursor.execute(f"UPDATE guilds SET {status.lower()}_role_id = ? WHERE guild_id = ?", (role_id, guild_id))
    log.info(f"Bound role {role_id} to Idena status {status} in guild {guild_id}")
    conn.commit()

async def get_role_bindings(guild_id: str):
    cursor.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,))
    guild_roles = cursor.fetchone()
    if guild_roles is None:             # should probably perform this check in other cases too
        await add_guild(guild_id)
        return {"undefined": None, "newbie": None, "verified": None, "human": None, "suspended": None, "zombie": None}
    role_bindings = {"undefined": guild_roles[1], "newbie": guild_roles[2], "verified": guild_roles[3], "human": guild_roles[4], "suspended": guild_roles[5], "zombie": guild_roles[6]}
    return role_bindings

async def is_guild_configured(guild_id: str) -> bool:
    cursor.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,))
    guild_roles = cursor.fetchone()
    if None in guild_roles:
        return False
    return True

async def get_guilds():
    cursor.execute("SELECT guild_id FROM guilds")
    guilds = cursor.fetchall()
    return guilds

# Auth functions

async def generate_nonce(user_id: str, address: str) -> str:
    nonce = "signin-" + secrets.token_hex(16)
    cursor.execute("DELETE FROM pending_auth WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO pending_auth (user_id, address, nonce) VALUES (?, ?, ?)", (user_id, address, nonce))
    conn.commit()
    return nonce

async def set_user(user_id: str, address: str):
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO users (user_id, address) VALUES (?, ?)", (user_id, address))
    conn.commit()

async def delete_user(user_id: str):
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()

async def get_nonce(user_id: str) -> str:
    cursor.execute("SELECT nonce FROM pending_auth WHERE user_id = ?", (user_id,))
    nonce = cursor.fetchone()
    return nonce[0]

async def get_pending_address(user_id: str) -> str:
    cursor.execute("SELECT address FROM pending_auth WHERE user_id = ?", (user_id,))
    address = cursor.fetchone()
    if address is None:
        return None
    return address[0]

async def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    return users

async def get_user_address(user_id: str) -> str:
    cursor.execute("SELECT address FROM users WHERE user_id = ?", (user_id,))
    address = cursor.fetchone()
    if address is None:
        return None
    return address[0]

async def remove_pending_auth(user_id: str):
    cursor.execute("DELETE FROM pending_auth WHERE user_id = ?", (user_id,))
    conn.commit()