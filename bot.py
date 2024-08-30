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
BOT_OWNER = int(os.getenv("BOT_OWNER"))

# Create discord bot
intents = disnake.Intents.default()
intents.members = True
bot = commands.InteractionBot(intents = intents)

async def update_role(guild: disnake.Guild, member: disnake.Member) -> str:
    # get role id based on Idena status
    address = await db.get_user_address(member.id)

    if address is None:
        # remove all bound roles from the member in that guild
        for new_role in member.roles:
            if new_role.id in list((await db.get_role_bindings(guild.id)).values()):
                try:
                    await member.remove_roles(new_role)
                    log.info(f"Removed role {new_role.name} from member {member.name}({member.id}) in guild {guild}({guild.id})")
                except Exception as e:
                    log.error(f"Error removing role {new_role.name} from member {member.name}({member.id}) in guild {guild}({guild.id}): {e}")
        return ""
    
    # idena state
    state = await idena.get_identity_state(address)
    if state.lower() not in ["undefined", "newbie", "verified", "human", "suspended", "zombie"]:
        state = "undefined"

    # role that should be assigned
    role_bindings = await db.get_role_bindings(guild.id)
    role_id = role_bindings[state.lower()]

    new_role = guild.get_role(role_id)
    if new_role is None:
        raise Exception(f"Role {role_id} not found in guild {guild}({guild.id})")
    
    # check if the user has the role already
    if role_id in [role.id for role in member.roles]:
        return role_id
    
    # get roles that should be removed
    roles_to_remove = [role for role in member.roles if role.id in list(role_bindings.values())]
    
    # update roles
    updated_roles = [new_role]
    updated_roles.extend([role for role in member.roles if role not in roles_to_remove])
    await member.edit(roles = updated_roles)
    
    if len(roles_to_remove):
        log.info(f"Removed roles {', '.join([role.name for role in roles_to_remove])} from member {member.name}({member.id}) in guild {guild}({guild.id})")
    log.info(f"Added role {new_role.name} to member {member.name}({member.id}) in guild {guild}({guild.id})")

    return role_id

async def update_all_roles(guild_id: int = None):
    log.info("Updating all roles")
    if guild_id:
        guilds = [guild_id]
    else:
        guilds = await db.get_guilds()

    users = await db.get_all_users()
    for guild_id in guilds:
        if not await db.is_guild_configured(guild_id):
            log.warning(f"Guild {await bot.fetch_guild(guild_id)}({guild_id}) not configured, skipping update")
            continue

        # fetch guild
        try:
            guild = await bot.fetch_guild(guild_id)
            log.info(f"Updating roles for guild {guild}({guild_id})")
        except disnake.errors.NotFound:
            log.error(f"Guild {guild_id} not found, skipping update")
            continue

        fetched_users = await guild.fetch_members().flatten()
        for user_id in users:
            try:
                user = next((user for user in fetched_users if user.id == user_id), None)
                if user is None:
                    continue
                await update_role(guild, user)
            except Exception as e:
                log.error(f"Error updating roles for user {(await bot.fetch_user(user_id)).name}({user_id}) in guild {guild}({guild_id}): {e}")

    log.info("All roles updated")

async def scheduled_update(hour, minute):
    # scheduled role update for all members
    while True:
        now = datetime.now()
        target_time = now.replace(hour = hour, minute = minute, second = 0)
        if now >= target_time:
            target_time += timedelta(days = 1)
        log.info(f"Next scheduled identities update at {target_time}")
        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        await update_all_roles()

async def hourly_update():
    # hourly update for bot status and database cleaning
    while True:
        log.info("HOURLY UPDATE")
        await db.clean()
        user_count = len(await db.get_all_users())
        await bot.change_presence(activity = disnake.Activity(type = disnake.ActivityType.watching, name = f"{user_count} Idena identities"))
        await asyncio.sleep(60 * 60)

async def protect(cmd: disnake.CommandInteraction):
    # checks if the user has permission to use the command
    bot_manager = await db.get_bot_manager(cmd.guild.id)
    if not cmd.author.guild_permissions.administrator and (bot_manager == None or bot_manager not in [role.id for role in cmd.author.roles]):
        log.warning(f"User {cmd.author}({cmd.author.id}) tried to use a command without permission")
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
        embed = Embed(title = "Role Already Bound", description = description, color = 0xf04947)
        return await cmd.response.send_message(embed = embed)

    # bind the role
    if status == "undefined":
        status = "Not Validated"
    await db.bind_role(cmd.guild.id, status, role.id)
    description = f"Role <@&{role.id}> was bound to Idena status **{status}**!\nPlease note that it may take a bit for the changes to reflect due to caching."
    embed = Embed(title = "<a:tick:1279114111963369503> Role Bound", description = description, color = 0x43b481)
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
    embed = Embed(title = "Role Bindings", description = description, color = 0x43b481)
    await cmd.response.send_message(embed = embed)

#
# set bot manager command
#
@bot.slash_command(description = "Role that can change bot settings")
async def setbotmanager(cmd: disnake.CommandInteraction, role: disnake.Role):
    if await protect(cmd) != 1:
        return

    await db.set_bot_manager(cmd.guild.id, role.id)
    description = f"Bot manager role set to <@&{role.id}>"
    embed = Embed(title = "<a:tick:1279114111963369503> Bot Manager Role Set", description = description, color = 0x43b481)
    await cmd.response.send_message(embed = embed)

#
# force update all command
#
@commands.cooldown(1, 60 * 60, commands.BucketType.guild)
@bot.slash_command(description = "Force update all roles for all users")
async def forceupdateall(cmd: disnake.CommandInteraction):
    if await protect(cmd) != 1:
        return
    
    if not await db.is_guild_configured(cmd.guild.id):
        description = "This server is not configured! Please bind roles to Idena statuses."
        embed = Embed(title = "<a:cross:1279119277705789450> Guild Not Configured", description = description, color = 0xf04947)
        return await cmd.response.send_message(embed = embed)

    if datetime.now() >= datetime.now().replace(hour = 15, minute = 30, second = 0) and datetime.now() <= datetime.now().replace(hour = 16, minute = 0, second = 0):
        description = "Running this command right now might interfere with the auto update feature.\nAuto update will take place at 15:45 UTC."
        embed = Embed(title = "<a:cross:1279119277705789450> Please wait", description = description, color = 0xf04947)
        return await cmd.response.send_message(embed = embed)
    
    await cmd.response.defer()

    await update_all_roles(cmd.guild.id)

    description = "Roles have been updated for all users!"
    embed = Embed(title = "<a:tick:1279114111963369503> Roles Updated", description = description, color = 0x43b481)
    await cmd.edit_original_message(embed = embed)

#
# dev force update all
#
@bot.slash_command(description = "Command used for debugging purposes by the bot developer")
async def dev_forceupdateall(cmd: disnake.CommandInteraction, guild_id: str = None):
    guild_id = int(guild_id) if guild_id else None
    if cmd.author.id != BOT_OWNER:
        log.info(f"User {cmd.author.name} denied permission for dev command")
        description = "Only the bot owner can run this command."
        embed = Embed(title = "<a:cross:1279119277705789450> Permission denied", description = description, color = 0xf04947)
        return await cmd.response.send_message(embed = embed)
    
    if guild_id and not await db.guild_exists(guild_id, add_to_db = False):
        description = "The guild provided is not in the database."
        embed = Embed(title = "<a:cross:1279119277705789450> Error", description = description, color = 0xf04947)
        return await cmd.response.send_message(embed = embed)

    await cmd.response.defer()
    await update_all_roles(guild_id)

    description = "Roles have been updated for all users!"
    embed = Embed(title = "<a:tick:1279114111963369503> Roles Updated", description = description, color = 0x43b481)
    return await cmd.edit_original_message(embed = embed)

#
# send bot interactive message
#
@bot.slash_command(description = "Send a message with buttons for users to click")
async def send_interactive_message(cmd: disnake.CommandInteraction, channel: disnake.TextChannel):
    if await protect(cmd) != 1:
        return

    # create buttons
    login_button = disnake.ui.Button(style = disnake.ButtonStyle.primary, label = "Login", custom_id = "login")
    update_button = disnake.ui.Button(style = disnake.ButtonStyle.primary, label = "Update my roles", custom_id = "update")
    logout_button = disnake.ui.Button(style = disnake.ButtonStyle.danger, label = "Logout", custom_id = "logout")

    # create interactive message
    idena_emoji = bot.get_emoji(685155510131097625)
    description = "This server uses an Idena Identity verification system.\nYou can obtain roles based on your Idena status by signing in with Idena using the buttons below."
    embed = disnake.Embed(title = f"{idena_emoji} Idena Auth", description = description, color = 0x1215b5)
    await channel.send(embed = embed, components = [disnake.ui.ActionRow(login_button, update_button, logout_button)])

    # respond to the command
    embed = disnake.Embed(title = "<a:tick:1279114111963369503> Message sent", description = f"The interactive message has been sent to <#{channel.id}>", color = 0x43b481)
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
    URL = "https://app.idena.io/dna/signin?token=" + token + "&callback_url=" + AUTH_URL + "/success" +  "&nonce_endpoint=" + AUTH_URL + "/start-session" + "&authentication_endpoint=" + AUTH_URL + "/authenticate" + "&favicon_url=" + AUTH_URL + "/favicon.ico"

    # check if the user is already logged in
    if await db.get_user_address(cmd.author.id) is not None:
        description = f"You are already logged in as `{await db.get_user_address(cmd.author.id)}`!\nIf you want to switch accounts, you can proceed [signing in with Idena]({URL})"
        embed = Embed(title = "Already Logged In", description = description, color = 0xfdcb58)
        return await cmd.response.send_message(embed = embed, ephemeral = True)

    description = f"In order to log in, [authenticate with Idena]({URL})"
    embed = Embed(title = "Login with Idena", description = description, color = 0x43b481)
    await cmd.response.send_message(embed = embed, ephemeral = True)

#
# update command
#
@commands.cooldown(3, 60, commands.BucketType.user)
@bot.slash_command(description = "Update your roles")
async def update(cmd: disnake.CommandInteraction):
    role_id = await update_role(cmd.guild, cmd.author)

    if role_id == "":
        description = "You are not logged in!"
        embed = Embed(title = "<a:cross:1279119277705789450> Not Logged In", description = description, color = 0xf04947)
        return await cmd.response.send_message(embed = embed, ephemeral = True)
    
    description = f"Your role has been updated to <@&{role_id}>!\nYou are logged in as `{await db.get_user_address(cmd.author.id)}`"
    embed = Embed(title = "<a:tick:1279114111963369503> Roles Updated", description = description, color = 0x43b481)
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
        embed = Embed(title = "<a:cross:1279119277705789450> Not Logged In", description = description, color = 0xf04947)
        return await cmd.response.send_message(embed = embed, ephemeral = True)
    
    await cmd.response.defer(with_message = True, ephemeral = True)

    # remove user from database and remove roles from all guilds
    await db.delete_user(cmd.author.id)
    for guild_id in await db.get_guilds():
        try:
            guild = await bot.fetch_guild(guild_id)
            member = await guild.fetch_member(cmd.author.id)
            await update_role(guild, member)
        except disnake.errors.NotFound:
            log.debug(f"Member {cmd.author.name}({cmd.author.id}) not found in guild {guild}({guild.id})")
        except Exception as e:
            log.error(f"Error removing roles for user {cmd.author.name}({cmd.author.id}): {e}")

    log.info(f"User {cmd.author.name}({cmd.author.id}) logged out!")
    description = "You have been logged out from all servers!"
    embed = Embed(title = "<a:tick:1279114111963369503> Logged Out", description = description, color = 0x43b481)
    await cmd.edit_original_message(embed = embed)

@bot.before_slash_command_invoke
async def before_slash_command_invoke(cmd: disnake.CommandInteraction):
    if cmd.guild:
        log.info(f"User {cmd.author}({cmd.author.id}) used command {cmd.data.name} in guild {cmd.guild}({cmd.guild.id})")
    else:
        log.info(f"User {cmd.author}({cmd.author.id}) used command {cmd.data.name}")

button_cooldowns = {}
@bot.listen("on_button_click")
async def button_listener(inter: disnake.MessageInteraction):
    try:
        user_id = inter.author.id
        button_id = inter.component.custom_id

        log.info(f"User {inter.author.name}({inter.author.id}) clicked button {button_id} in guild {inter.guild}({inter.guild.id})")

        # cooldown
        if user_id in button_cooldowns and button_id in button_cooldowns[user_id]:
            last_clicked = button_cooldowns[user_id][button_id]

            if datetime.now() < last_clicked + timedelta(seconds=15):
                log.info(f"User {inter.author.name}({user_id}) rate limited on button {button_id} in guild {inter.guild}({inter.guild.id})")

                description = "You are clicking too fast! Please wait a moment."
                embed = Embed(title = "<a:cross:1279119277705789450> Cooldown", description = description, color = 0xf04947)
                return await inter.response.send_message(embed = embed, ephemeral=True)

        if user_id not in button_cooldowns:
            button_cooldowns[user_id] = {}
        button_cooldowns[user_id][button_id] = datetime.now()

        # process button click
        # calling the functions with a different Interaction type works because they use common attributes, gotta be careful
        if inter.component.custom_id == "login":
            await login(inter)
        elif inter.component.custom_id == "update":
            await update(inter)
        elif inter.component.custom_id == "logout":
            await logout(inter)
    except Exception as e:
        log.error(f"An error occurred in button interaction: {e}")
        description = f"Something went wrong! :("
        embed = disnake.Embed(title = "<a:cross:1279119277705789450> Error", description = description, color = 0xf04947)
        await inter.response.send_message(embed = embed, ephemeral = True)

# Bot events
@bot.event
async def on_guild_join(guild):
    await db.add_guild(guild.id)

@bot.event
async def on_guild_remove(guild):
    log.info(f"Bot was removed from guild {guild}({guild.id})")

@bot.event
async def on_slash_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        log.info(f"User {ctx.author}({ctx.author.id}) was rate limited on command {ctx.data.name} in guild {ctx.guild}({ctx.guild.id})")
        description = f"This command is on cooldown. Try again in {error.retry_after:.0f} seconds."
        embed = Embed(title = "<a:cross:1279119277705789450> Command on Cooldown", description = description, color = 0xf04947)
        await ctx.response.send_message(embed = embed, ephemeral = True)
    else:
        if ctx.guild is None:
            description = f"You can not use this command in a DM channel."
            embed = Embed(title = "<a:cross:1279119277705789450> Error", description = description, color = 0xf04947)
            return await ctx.response.send_message(embed = embed, ephemeral = True)
        log.error(f"An error occurred in command {ctx.data.name}: {error}")
        description = f"Something went wrong! :("
        embed = Embed(title = "<a:cross:1279119277705789450> Error", description = description, color = 0xf04947)
        try:
            await ctx.response.send_message(embed = embed, ephemeral = True)
        except Exception:
            await ctx.edit_original_message(embed = embed)
        
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")
    asyncio.create_task(scheduled_update(15, 45))
    asyncio.create_task(hourly_update())

bot.run(DISCORD_TOKEN)