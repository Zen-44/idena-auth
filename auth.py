import os
from flask import Flask, jsonify, request, send_from_directory
from eth_keys.main import PublicKey, Signature
from Crypto.Hash import keccak
from dotenv import load_dotenv
import utils.db as db
from utils.logger import get_logger

app = Flask(__name__)

log = get_logger("AUTH")
app.logger.setLevel("INFO")
app.logger.addHandler(log)

load_dotenv(override = True)
SITE_URL = os.getenv("AUTH_URL")

async def validate_sig(body):
    # get nonce from db
    nonce = await db.get_nonce(body['token'])
    address = await db.get_pending_address(body['token'])
    signature = body['signature']

    hash = keccak.new(digest_bits=256)
    hash.update(nonce.encode('utf-8'))
    nonce_hash = hash.digest()
    hash = keccak.new(digest_bits=256)
    hash.update(nonce_hash)
    nonce_hash = hash.digest()

    new_address = PublicKey.recover_from_msg_hash(nonce_hash, Signature(bytes.fromhex(signature[2:]))).to_address()

    return address == new_address

@app.route('/favicon.ico')
def favicon():
    return send_from_directory("resources", "favicon.ico", mimetype='image/vnd.microsoft.icon')

@app.route("/resources/bot_img.png")
def bot_img():
    return send_from_directory("resources", "bot_img.png", mimetype='image/png')

@app.route("/")
def index():
    return send_from_directory("resources", "index.html")

@app.route("/success")
def success_page():
    return send_from_directory("resources", "success.html")

@app.route("/start-session", methods=["POST"])
async def start_session():
    req = request.get_json()
    token = req["token"]
    address = req["address"]
    discord_id = await db.get_discord_id(token)
    log.info(f"Begin authentication for user {discord_id}")

    if (discord_id is None):
        log.warning(f"Invalid token {token}")
        return jsonify({
            "success": False,
            "error": "Invalid token"
        })

    nonce = await db.generate_nonce(token, address)
    return jsonify({
        "success": True,
        "data": {
            "nonce": nonce
        }
    })

@app.route("/authenticate", methods=["POST"])
async def authenticate():
    req = request.get_json()

    if not await validate_sig(req):
        log.warning(f"Invalid signature for token {req['token']}")
        return jsonify({
            "success": False,
            "error": "Invalid signature!"
        })
    
    address = await db.get_pending_address(req['token'])
    user_id = await db.get_discord_id(req['token'])
    if not await db.set_user(user_id, address):
        return jsonify({
            "success": False,
            "error": "Address is logged in already!"
        })
    
    await db.remove_pending_auth(req['token'])
    log.info(f"User id {user_id} successfully authenticated as {address}")

    return jsonify({
      "success": True,
      "data": {
        "authenticated": True
      }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0")
