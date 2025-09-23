import discord
import json
import os
import types
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import urllib.parse
from datetime import datetime

# Bot authentication url
# https://discord.com/oauth2/authorize?client_id=1344219132027076629&scope=bot%20applications.commands&permissions=8

# Simple file and json read/write helpers.
def WriteFile(filePath: str, contents: str | bytes, binary: bool = False) -> None:
    filePath = os.path.realpath(filePath)
    dirPath = os.path.dirname(filePath)
    os.makedirs(dirPath, exist_ok=True)
    with open(filePath, "wb" if binary else "w", encoding=(None if binary else "UTF-8")) as file:
        file.write(contents)
def ReadFile(filePath: str, defaultContents: str | bytes | None = None, binary: bool = False) -> str | bytes:
    filePath = os.path.realpath(filePath)
    if not os.path.exists(filePath):
        if defaultContents != None:
            return defaultContents
    with open(filePath, "rb" if binary else "r", encoding=(None if binary else "UTF-8")) as file:
        return file.read()
def SerializeJson(object: dict | types.SimpleNamespace) -> None:
    if isinstance(object, types.SimpleNamespace):
        return json.dumps(vars(object))
    else:
        return json.dumps(object)
def DeserializeJson(jsonString: str, simple_namespace: bool = False) -> dict | types.SimpleNamespace:
    if simple_namespace:
        return json.loads(jsonString, object_hook=lambda obj: types.SimpleNamespace(**obj))
    else:
        return json.loads(jsonString)

# Loading environment.json
ENV: types.SimpleNamespace = None
def LoadEnv() -> None:
    global ENV
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    ENV = DeserializeJson(ReadFile("./environment.json"), simple_namespace=True)
    ENV.verification_key = bytes.fromhex(ENV.verification_key)
    ENV.verification_iv = bytes.fromhex(ENV.verification_iv)
LoadEnv()

# Working with the main user database.
# Struct { "username": username, "first": first, "last": last, "onid": onid }
DB: dict[dict[str, str, str, str]] = None
def LoadDB() -> None:
    global DB
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    if os.path.isfile("./database.json"):
        DB = DeserializeJson(ReadFile("./database.json"))
    else:
        DB = {}
def SaveDB() -> None:
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    if DB == None:
        raise Exception("DB has not been loaded yet.")
    WriteFile("./database.json", SerializeJson(DB))
def DBGet(discord_id: str) -> str | None:
    if not isinstance(discord_id, str):
        discord_id = str(discord_id)
    
    if discord_id in DB:
        return DB[discord_id]
    else:
        return None
def DBSet(discord_id: str, onid: str | None) -> None:
    if not isinstance(discord_id, str):
        discord_id = str(discord_id)

    if onid == None:
        if discord_id in DB:
            del DB[discord_id]
    else:
        DB[discord_id] = onid
LoadDB()

# Looking up user information by ONID.
def OnidLookupName(onid: str) -> str | None:
    try:
        url = f"https://ne2vbpr3na.execute-api.us-west-2.amazonaws.com/prod/people?q={urllib.parse.quote(onid)}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list) or len(data) != 1:
            return None
        else:
            return f"{data[0]["firstName"]} {data[0]["lastName"]}" 
    except:
        return None

# Sending emails.
def SendEmail(to: str, subject: str, body: str) -> None:
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(ENV.email_address, ENV.email_password)
        
        msg = MIMEMultipart()
        msg["From"] = ENV.email_address
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        smtp.send_message(msg)

# Generating codes and parsing them.
def GenerateCode(discord_id: str, onid: str) -> str:
    if not isinstance(discord_id, str):
        discord_id = str(discord_id)

    token = { "magic": "d5bI8cRB4QDcp2yi", "discord_id": discord_id, "onid": onid }

    plaintext = SerializeJson(token).encode(encoding="UTF-8")

    padding_length = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([ padding_length ] * padding_length)

    cipher = Cipher(algorithms.AES(ENV.verification_key), modes.CBC(ENV.verification_iv))
    encryptor = cipher.encryptor()
    cyphertext = encryptor.update(padded) + encryptor.finalize()

    return cyphertext.hex()
def ParseCode(code: str) -> tuple[str, str]:
    cyphertext = bytes.fromhex(code)

    cipher = Cipher(algorithms.AES(ENV.verification_key), modes.CBC(ENV.verification_iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(cyphertext) + decryptor.finalize()

    padding_length = padded[-1]
    plaintext = padded[:-padding_length].decode(encoding="UTF-8")

    token =  DeserializeJson(plaintext)
    if token["magic"] != "d5bI8cRB4QDcp2yi":
        raise Exception("Bad token magic.")

    return token["discord_id"], token["onid"]

# WatchDog - Keeps a list of users who have requested too much in the last 24 hours.
WatchDogLog: dict[list[int]] = {}
def WatchDogRequestAllowed(discord_id: str) -> bool:
    if not isinstance(discord_id, str):
        discord_id = str(discord_id)
    
    if not discord_id in WatchDogLog:
        WatchDogLog[discord_id] = []
    
    WatchDogLog[discord_id] = [ timestamp for timestamp in WatchDogLog[discord_id] if timestamp >= (int(datetime.now().timestamp()) - 86400) ]

    WatchDogLog[discord_id].append(int(datetime.now().timestamp()))

    return len(WatchDogLog[discord_id]) < 5
def WatchDogForgive(discord_id: str) -> None:
    if not isinstance(discord_id, str):
        discord_id = str(discord_id)
    
    WatchDogLog[discord_id] = []    

# Initialize client and command tree classes.
client = discord.Client(intents=discord.Intents.default())
commandTree = discord.app_commands.CommandTree(client)

# GUI interactions
class VerifyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Verification Code", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OnidInputModal())

    @discord.ui.button(label="Enter Verification Code", style=discord.ButtonStyle.success, custom_id="enter_code_button")
    async def enter_code_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CodeInputModal())
class OnidInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="ONID Email", timeout=None, custom_id="onid_input_modal")
    
    onid_input = discord.ui.TextInput(label="Enter your ONID email address:", placeholder="onid@oregonstate.edu", required=True, custom_id="onid_input")
    async def on_submit(self, interaction: discord.Interaction):
        onid = str(self.onid_input.value).strip().lower()

        if not onid.endswith("@oregonstate.edu") or len(onid) <= len("@oregonstate.edu"):
            await interaction.response.send_message(f"The ONID you entered doesn't look quite right. Please try again.", ephemeral=True)
            return

        if not WatchDogRequestAllowed(str(interaction.user.id)):
            await interaction.response.send_message(f"TOO MANY REQUESTS! Please wait 24 hours.", ephemeral=True)
            return

        if OnidLookupName(onid) == None:
            await interaction.response.send_message(f"The ONID you entered {onid} doesn't exist. Please try again.", ephemeral=True)
            return
        
        code = GenerateCode(onid, str(interaction.user.id))
        SendEmail(onid, "Verification Code - OSU Climbing Club", f"Your verification code for the OSU Climbing Club's official Discord server is:\n\n{code}\n\nIf you did not request this code please reach out to Indoor.RockClimbing@oregonstate.edu and we will investigate.")
        
        await interaction.response.send_message(f"A verification code has been sent to {onid}.\n\nPlease allow up to 15 minutes for the code to arive.", ephemeral=True)
class CodeInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Verification Code", timeout=None, custom_id="code_input_modal")
    
    code_input = discord.ui.TextInput(label="Enter your verification code:", placeholder="123456789abcdef...", required=True, custom_id="code_input")
    async def on_submit(self, interaction: discord.Interaction):
        code = str(self.code_input)

        try:
            discord_id, onid = ParseCode(code)
            if discord_id != str(interaction.user.id):
                raise Exception("That code is for someone else.")
        except:
            await interaction.response.send_message(f"That code doesn't look right. Please try again.", ephemeral=True)
            return

        onid_name = OnidLookupName(onid)
        DBSet(str(interaction.user.id), onid)
        await interaction.user.add_roles(interaction.guild.get_role(ENV.verified_role_id))
        try:
            await interaction.user.edit(nick=onid_name)
        except:
            await interaction.response.send_message(f"FAILED TO NICK", ephemeral=True)
            return

        await interaction.response.send_message(f"{interaction.user.mention} you have been verified as {onid}. ({onid_name})\n\nWelcome to the server. Don't forget to read the rules. :slight_smile:", ephemeral=True)

# Instructions command
@commandTree.command(name="post_instructions", description="Posts the verification instructions in the current channel.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def instructions(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    await interaction.channel.send("Welcome to the OSU Climbing Club official Discord server.\n\nTo get access to the rest of the server you will need to verify your ONID email address.\n\u200b", view=VerifyButtonView())
    await interaction.response.send_message("Done!", ephemeral=True)

# WatchDog commands
@commandTree.command(name="watchdog_forgive", description="Forgive a user in the eyes of the watch dog by setting their request cound in the last 24 hours to 0.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def watchdog_forgive(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return

    WatchDogForgive(str(user.id))
    await interaction.response.send_message(f"{user.mention} has been forgiven by the watch dog.", ephemeral=True)
@commandTree.command(name="watchdog_query", description="Checks how many requests the watch dog recorded for a given user in the last 24 hours.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def watchdog_query(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return

    request_count = len(WatchDogLog[str(user.id)]) if str(user.id) in WatchDogLog else 0
    await interaction.response.send_message(f"{user.mention} has made {request_count} requests in the last 24 hours.", ephemeral=True)

# Data lookup commands
@commandTree.command(name="get_user_info", description="Looks up the ONID email address and verification status of a given user.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def get_user_info(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    onid = DBGet(str(user.id))
    await interaction.response.send_message(f"User: {user.mention}\nVerified: {interaction.guild.get_role(ENV.verified_role_id) in user.roles}\nONID: {onid}", ephemeral=True)
@commandTree.command(name="get_onid_name", description="Looks up the full name associated with the given ONID email address.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def get_onid_name(interaction: discord.Interaction, onid: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    onid_name = OnidLookupName(onid)
    await interaction.response.send_message(f"ONID: {onid}\nName: {onid_name}", ephemeral=True)
@commandTree.command(name="get_user_name", description="Looks up the full name associated with a verified user.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def get_user_name(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    onid = DBGet(str(user.id))
    if onid == None:
        await interaction.response.send_message(f"Error {user.mention} is not associated with any ONID.", ephemeral=True)
    else:
        onid_name = OnidLookupName(onid)
        await interaction.response.send_message(f"User: {user.mention}\nONID: {onid}\nName: {onid_name}", ephemeral=True)

# Administration commands
@commandTree.command(name="verify", description="Manually verify someone by setting their ONID email address, roles, and nickname.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def verify(interaction: discord.Interaction, user: discord.Member, onid: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return

    DBSet(str(user.id), onid)
    await user.add_roles(interaction.guild.get_role(ENV.verified_role_id))

    onid_name = OnidLookupName(onid)
    DBSet(str(user.id), onid)
    await user.add_roles(interaction.guild.get_role(ENV.verified_role_id))
    await user.edit(nick=onid_name)

    await interaction.response.send_message(f"{user.mention} has been manually verified as {onid}. ({onid_name})", ephemeral=True)

@commandTree.command(name="unverify", description="Manually unverify someone by clearing their ONID email address and roles.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def unverify(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return

    DBSet(str(user.id), None)
    await user.remove_roles(interaction.guild.get_role(ENV.verified_role_id))

    await interaction.response.send_message(f"{user.mention} has been manually unverified.", ephemeral=True)

# Launch the bot and log ready message to console
@client.event
async def on_ready():
    for server_id in ENV.server_ids:
        await commandTree.sync(guild=discord.Object(server_id))
    client.add_view(VerifyButtonView())
    print(f"Online as {client.user}")
client.run(ENV.token)