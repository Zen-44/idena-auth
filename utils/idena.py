import aiohttp
import os
from aiocache import cached
from dotenv import load_dotenv
from utils.logger import get_logger

log = get_logger("IDENA-API")

load_dotenv(override = True)
NODE_URL = os.getenv("NODE_URL")
NODE_KEY = os.getenv("NODE_KEY")

@cached(ttl = 180)
async def get_identity_state(address: str) -> str:
    call_data = {
        "method": "dna_identity",
        "params": [address],
        "id": 1,
        "key": NODE_KEY
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(NODE_URL, json = call_data, headers = {'Content-Type': 'application/json'}) as response:
                identity = await response.json()
                if "result" in identity:
                    return identity["result"]["state"]
                else:
                    raise Exception(f"Error fetching identity state for {address}: {identity['error']}")
    except Exception as e:
        log.error(f"Error fetching identity state for {address}: {e}. Falling back to Idena API.")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.idena.io/api/Identity/{address}") as response:
                identity = await response.json()
        if "error" in identity:
            return "undefined"
        return identity["result"]["state"]
