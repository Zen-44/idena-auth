import os
import asyncio
import textwrap
import disnake
from disnake import Option, OptionType, Embed
from disnake.ext import commands
from dotenv import load_dotenv
from datetime import datetime, timedelta

from utils.logger import get_logger
import utils.idena as idena
import utils.db as db

log = get_logger("BOT")

load_dotenv(override = True)
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
AUTH_URL = os.getenv("AUTH_URL")

# Create discord bot
intents = disnake.Intents.default()
intents.members = True
bot = commands.InteractionBot(intents = intents)

async def update_role(guild_id, discord_id):
    # get role id based on Idena status
    address = await db.get_user_address(discord_id)
    if address is None:
        # remove all bound roles from the user in that guild
        guild = bot.get_guild(int(guild_id))
        if guild is None:
            log.error(f"Guild {guild_id} not found")
            return
        user = guild.get_member(int(discord_id))
        if user is None:
            log.warning(f"Member {discord_id} not found in guild {guild_id}")
            return
        for role in user.roles:
            if str(role.id) in list((await db.get_role_bindings(guild_id)).values()):
                log.info(f"Removing role {role.name} from member {discord_id} in guild {guild_id}")
                try:
                    await user.remove_roles(role)
                except Exception as e:
                    log.error(f"Error removing role {role.name} from member {discord_id} in guild {guild_id}: {e}")
        return
    
    state = await idena.get_identity_state(address)
    if state.lower() not in ["undefined", "newbie", "verified", "human", "suspended", "zombie"]:
        state = "undefined"
    role_id = (await db.get_role_bindings(guild_id))[state.lower()]

    # obtain guild, member and role objects
    guild = bot.get_guild(int(guild_id))
    if guild is None:
        log.error(f"Guild {guild_id} not found")
        return

    member = guild.get_member(int(discord_id))
    if member is None:
        log.info(f"Member {discord_id} not found in guild {guild_id}")
        return

    role = guild.get_role(int(role_id))
    if role is None:
        log.error(f"Role {role_id} not found in guild {guild_id}")
        return
    
    # check if the user has the role already
    if role_id in [str(role.id) for role in member.roles]:
        return
    
    # remove other (bound) roles
    for old_role in member.roles:
        if str(old_role.id) in list((await db.get_role_bindings(guild_id)).values()):
            log.info(f"Removing role {old_role.name} from member {discord_id}")
            try:
                await member.remove_roles(old_role)
            except Exception as e:
                log.error(f"Error removing role {old_role.name} from member {discord_id}: {e}")
    
    # add the new role
    await member.add_roles(role)
    log.info(f"Added role {role.name} to member {discord_id} in guild {guild_id}")

async def update_all_roles(guild_id = None):
    log.info("Updating all roles")
    if guild_id:
        guilds = [(guild_id,)]
    else:
        guilds = await db.get_guilds()

    users = await db.get_all_users()
    for guild in guilds:
        guild_id = guild[0]
        for user in users:
            discord_id = user[0]
            await update_role(guild_id, discord_id)
    log.info("All roles updated")

async def scheduled_update(hour, minute):
    # scheduled update for all members and cleanup pending auths
    while True:
        now = datetime.now()
        target_time = now.replace(hour = hour, minute = minute, second = 0)
        if now >= target_time:
            target_time += timedelta(days=1)
        log.info(f"Next scheduled status update at {target_time}")
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        await update_all_roles()
        await db.clean()

async def protect(cmd: disnake.CommandInteraction): # TODO embed message
    # checks if the user has permission to use the command
    bot_manager = await db.get_bot_manager(cmd.guild.id)
    if not cmd.author.guild_permissions.administrator and (bot_manager != None or bot_manager not in [role.id for role in cmd.author.roles]):
        log.warning(f"User {cmd.author} tried to use a command without permission")
        return await cmd.response.send_message("You do not have permission to use this command")
    return 1

#
# bind role command
#
@bot.slash_command(description = "Bind Idena statuses to roles",
                   options = [Option("status", "Idena status", OptionType.string, choices = ["Not Validated", "Newbie", "Verified", "Human", "Suspended", "Zombie"]),
                              Option("role", "Discord role", OptionType.role),
                              Option("force", "Force bind even if role is already bound", OptionType.boolean)])
async def bindrole(cmd: disnake.CommandInteraction, status: str, role: disnake.Role, force: bool = False):
    if await protect(cmd) != 1:
        return
    
    # warn if the status is bound already
    if status.lower() not in ["undefined", "newbie", "verified", "human", "suspended", "zombie"]:
        status = "undefined"
    if (await db.get_role_bindings(cmd.guild.id))[status.lower()] != None and not force:
        # Role is already bound
        description = f"This status already has a role bound to it.\nIf you want to change it, run the command again with force set to true.\nThe bot will no longer handle the old role (needs to be removed manually)."
        embed = Embed(title="Role Already Bound", description=description, color=0xFF0000)
        return await cmd.response.send_message(embed = embed)

    # bind the role
    if status == "undefined":
        status = "Not Validated"
    await db.bind_role(cmd.guild.id, status, role.id)
    description = f"Role <@&{role.id}> was bound to Idena status **{status}**!\nPlease note that it may take a bit for the changes to reflect in /getbindings due to caching."
    embed = Embed(title=":white_check_mark: Role Bound", description=description, color=0x00FF00)
    await cmd.response.send_message(embed = embed)

#
# get bindings command
#
@bot.slash_command(description = "Get role bindings")
async def getbindings(cmd: disnake.CommandInteraction):
    if await protect(cmd) != 1:
        return

    # retrieve role bindings
    role_bindings = await db.get_role_bindings(cmd.guild.id)
    role_bindings = {key: f"<@&{role_bindings[key]}>" if role_bindings[key] is not None else "Not set" for key in role_bindings}
    bot_manager = await db.get_bot_manager(cmd.guild.id)
    if bot_manager is not None:
        role_bindings["bot_manager"] = f"<@&{bot_manager}>"
    else:
        role_bindings["bot_manager"] = "Not set"

    description = textwrap.dedent(f"""
        **Not Validated:** {role_bindings['undefined']}
        **Newbie:** {role_bindings['newbie']}
        **Verified:** {role_bindings['verified']}
        **Human:** {role_bindings['human']}
        **Suspended:** {role_bindings['suspended']}
        **Zombie:** {role_bindings['zombie']}

        **Bot Manager**: {role_bindings['bot_manager']}""")
    embed = Embed(title = "Role Bindings", description = description, color = 0x00ff00)
    await cmd.response.send_message(embed = embed)

#
# set bot manager command
#
@bot.slash_command(description = "Role that has access to all bot commands")
async def setbotmanager(cmd: disnake.CommandInteraction, role: disnake.Role):
    if await protect(cmd) != 1:
        return

    await db.set_bot_manager(cmd.guild.id, role.id)
    description = f"Bot manager role set to <@&{role.id}>"
    embed = Embed(title = ":white_check_mark: Bot Manager Role Set", description = description, color = 0x00ff00)
    await cmd.response.send_message(embed = embed)

#
# force update all command
#
@commands.cooldown(1, 60 * 60, commands.BucketType.guild)
@bot.slash_command(description = "Force update all roles for all users")
async def forceupdateall(cmd: disnake.CommandInteraction):
    if await protect(cmd) != 1:
        return

    await update_all_roles(cmd.guild.id)
    description = "All roles have been updated for all users!"
    embed = Embed(title = ":white_check_mark: Roles Updated", description = description, color = 0x00ff00)
    await cmd.response.send_message(embed = embed)

#
# login command
#
@commands.cooldown(3, 60, commands.BucketType.user)
@bot.slash_command(description = "Log in with Idena")
async def login(cmd: disnake.CommandInteraction):
    # create auth URL
    discord_id = str(cmd.author.id)
    token = await db.generate_token(discord_id)
    URL = "https://app.idena.io/dna/signin?token=" + token + "&callback_url=" + AUTH_URL +  "&nonce_endpoint=" + AUTH_URL + "/start-session" + "&authentication_endpoint=" + AUTH_URL + "/authenticate" + "&favicon_url=" + AUTH_URL + "/favicon.ico"

    # check if the user is already logged in
    if await db.get_user_address(cmd.author.id) is not None:
        description = f"You are already logged in as `{await db.get_user_address(cmd.author.id)}`!\nIf you want to switch accounts, you can proceed [signing in with Idena]({URL})"
        embed = Embed(title = ":yellow_square: Already Logged In", description = description, color = 0xFFFF00)
        return await cmd.response.send_message(embed = embed, ephemeral = True)

    description = f"In order to log in, [authenticate with Idena]({URL})"
    embed = Embed(title = "Login with Idena", description = description, color = 0x00ff00)
    await cmd.response.send_message(embed = embed, ephemeral = True)

#
# update command
#
@commands.cooldown(3, 60, commands.BucketType.user)
@bot.slash_command(description = "Update your roles")
async def update(cmd: disnake.CommandInteraction):
    await update_role(cmd.guild.id, cmd.author.id)
    description = f"Your roles have been updated!\nYou are logged in as `{await db.get_user_address(cmd.author.id)}`"
    embed = Embed(title = ":white_check_mark: Roles Updated", description = description, color = 0x00ff00)
    await cmd.response.send_message(embed = embed, ephemeral = True)


#
# logout command
#
@commands.cooldown(2, 60, commands.BucketType.user)
@bot.slash_command(description = "Log out from all servers")
async def logout(cmd: disnake.CommandInteraction):
    # check if the user is logged in
    if await db.get_user_address(cmd.author.id) is None:
        description = "You are not logged in!"
        embed = Embed(title = ":x: Not Logged In", description = description, color = 0xFF0000)
        return await cmd.response.send_message(embed = embed, ephemeral = True)
    
    # remove user from database and remove roles from all guilds
    discord_id = cmd.author.id
    await db.delete_user(discord_id)
    for guild in await db.get_guilds():
        guild = guild[0]
        await update_role(guild, discord_id)

    log.info(f"User {discord_id} logged out!")
    description = "You have been logged out from all servers!"
    embed = Embed(title = ":white_check_mark: Logged Out", description = description, color = 0x00ff00)
    await cmd.response.send_message(embed = embed, ephemeral = True)

@bot.before_slash_command_invoke
async def before_slash_command_invoke(cmd: disnake.CommandInteraction):
    log.info(f"User {cmd.author} used command {cmd.data.name} in guild {cmd.guild}")

# Bot events
@bot.event
async def on_guild_join(guild):
    await db.add_guild(guild.id)

@bot.event
async def on_guild_remove(guild):
    log.info(f"Bot was removed from guild {guild}")

@bot.event
async def on_slash_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        log.info(f"User {ctx.author} was rate limited on command {ctx.data.name} in guild {ctx.guild}")
        description = f"This command is on cooldown. Try again in {error.retry_after:.0f} seconds."
        embed = Embed(title = ":x: Command on Cooldown", description = description, color = 0xFF0000)
        await ctx.response.send_message(embed = embed, ephemeral = True)
    else:
        if ctx.guild is None:
            description = f"You can not use this command in a DM channel."
            embed = Embed(title = ":x: Error", description = description, color = 0xFF0000)
            return await ctx.response.send_message(embed = embed, ephemeral = True)
        log.error(f"An error occurred in command {ctx.data.name} in guild {ctx.guild}: {error}")
        description = f"Something went wrong! :("
        embed = Embed(title = ":x: Error", description = description, color = 0xFF0000)
        await ctx.response.send_message(embed = embed, ephemeral = True)
        
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")
    asyncio.create_task(scheduled_update(15, 45))

bot.run(DISCORD_TOKEN)