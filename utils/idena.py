import aiohttp

async def get_identity_state(address: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.idena.io/api/Identity/{address}") as response: # maybe use another api?
            identity = await response.json()
    if "error" in identity:
        return "undefined"
    return identity["result"]["state"]
