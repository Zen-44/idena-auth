import sqlite3
import secrets
from aiocache import cached
from utils.logger import get_logger

log = get_logger("DB")

conn = sqlite3.connect("bot.db", check_same_thread = False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS guilds (guild_id TEXT PRIMARY KEY, undefined_role_id TEXT, newbie_role_id TEXT, verified_role_id TEXT, human_role_id TEXT, suspended_role_id TEXT, zombie_role_id TEXT, bot_manager_role_id TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, address TEXT UNIQUE)") # discord user id
cursor.execute("CREATE TABLE IF NOT EXISTS pending_auth (user_id TEXT PRIMARY KEY, token TEXT UNIQUE NOT NULL, address TEXT, nonce TEXT, created DATETIME DEFAULT CURRENT_TIMESTAMP)")

async def add_guild(guild_id):
    cursor.execute("INSERT INTO guilds (guild_id) VALUES (?)", (guild_id,))
    log.info(f"Added guild {guild_id} to the database")
    conn.commit()

async def remove_guild(guild_id):
    cursor.execute("DELETE FROM guilds WHERE guild_id = ?", (guild_id,))
    log.info(f"Removed guild {guild_id} from the database")
    conn.commit()

async def set_bot_manager(guild_id, role_id):
    cursor.execute("UPDATE guilds SET bot_manager_role_id = ? WHERE guild_id = ?", (role_id, guild_id))
    log.info(f"Set bot manager role {role_id} in guild {guild_id}")
    conn.commit()

@cached(ttl = 15)
async def get_bot_manager(guild_id):
    cursor.execute("SELECT bot_manager_role_id FROM guilds WHERE guild_id = ?", (guild_id,))
    bot_manager = cursor.fetchone()
    if bot_manager[0] is None:
        return None
    return int(bot_manager[0])

async def bind_role(guild_id, status: str, role_id):
    if status == "Not Validated":
        status = "undefined"
    cursor.execute(f"UPDATE guilds SET {status.lower()}_role_id = ? WHERE guild_id = ?", (role_id, guild_id))
    log.info(f"Bound role {role_id} to Idena status {status} in guild {guild_id}")
    conn.commit()

@cached(ttl = 15)
async def get_role_bindings(guild_id):
    if await guild_exists(guild_id) is False:
        return {"undefined": None, "newbie": None, "verified": None, "human": None, "suspended": None, "zombie": None}
    
    cursor.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,))
    guild_roles = cursor.fetchone()
    guild_roles = [int(role) if role is not None else None for role in guild_roles]
    role_bindings = {"undefined": guild_roles[1], "newbie": guild_roles[2], "verified": guild_roles[3], "human": guild_roles[4], "suspended": guild_roles[5], "zombie": guild_roles[6]}
    return role_bindings

async def is_guild_configured(guild_id) -> bool:
    role_bindings = await get_role_bindings(guild_id)
    if None in list(role_bindings.values()):
        return False
    return True

async def get_guilds():
    cursor.execute("SELECT guild_id FROM guilds")
    guilds = cursor.fetchall()
    guilds = [int(guild[0]) for guild in guilds]
    return guilds

async def guild_exists(guild_id) -> bool:
    cursor.execute("SELECT * FROM guilds WHERE guild_id = ?", (guild_id,))
    guild = cursor.fetchone()
    if guild is None:
        await add_guild(guild_id)
        return False
    return True

# Auth functions

async def generate_token(user_id) -> str:
    token = secrets.token_hex(16)
    cursor.execute("DELETE FROM pending_auth WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO pending_auth (user_id, token) VALUES (?, ?)", (user_id, token))
    conn.commit()
    log.info(f"Generated token {token} for user id {user_id}")
    return token

async def generate_nonce(token, address) -> str:
    nonce = "signin-" + secrets.token_hex(16)
    cursor.execute("UPDATE pending_auth SET nonce = ?, address = ? WHERE token = ?", (nonce, address, token))
    conn.commit()
    log.info(f"Generated nonce {nonce} for token {token}")
    return nonce

async def set_user(user_id, address):
    try:
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        cursor.execute("INSERT INTO users (user_id, address) VALUES (?, ?)", (user_id, address))
    except sqlite3.IntegrityError:
        log.warning(f"User id {user_id} tried to login with an already existing address: {address}")
        conn.rollback()
        return False
    conn.commit()
    log.info(f"Set user {user_id} to address {address}")
    return True

async def delete_user(user_id):
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()

async def get_discord_id(token) -> str:
    cursor.execute("SELECT user_id FROM pending_auth WHERE token = ?", (token,))
    user_id = cursor.fetchone()
    if user_id is None:
        return None
    return int(user_id[0])

async def get_nonce(token) -> str:
    cursor.execute("SELECT nonce FROM pending_auth WHERE token = ?", (token,))
    nonce = cursor.fetchone()
    if nonce is None:
        return None
    return nonce[0]

async def get_pending_address(token) -> str:
    cursor.execute("SELECT address FROM pending_auth WHERE token = ?", (token,))
    address = cursor.fetchone()
    if address is None:
        return None
    return address[0]

async def get_all_users():
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    users = [int(user[0]) for user in users]
    return users

async def get_user_address(user_id) -> str:
    cursor.execute("SELECT address FROM users WHERE user_id = ?", (user_id,))
    address = cursor.fetchone()
    if address is None:
        return None
    return address[0]

async def remove_pending_auth(token):
    cursor.execute("DELETE FROM pending_auth WHERE token = ?", (token,))
    conn.commit()

# cleanup function
async def clean():
    cursor.execute("DELETE FROM pending_auth WHERE created < datetime('now', '-1 hour')")
    rows_deleted = cursor.rowcount
    conn.commit()
    if rows_deleted > 0:
        log.info(f"Cleaned up {rows_deleted} expired tokens")