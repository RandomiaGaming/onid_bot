import discord
import json
import os
import types
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from datetime import datetime
import asyncio
from typing import Union
import base64

# Bot authentication url
# https://discord.com/oauth2/authorize?client_id=1344219132027076629 PROD
# https://discord.com/oauth2/authorize?client_id=884651584225701900 DEV

# Simple file and json read/write helpers.
def WriteFile(filePath: str, contents: Union[str, bytes], binary: bool = False) -> None:
    filePath = os.path.realpath(filePath)
    dirPath = os.path.dirname(filePath)
    os.makedirs(dirPath, exist_ok=True)
    with open(filePath, "wb" if binary else "w", encoding=(None if binary else "UTF-8")) as file:
        file.write(contents)
def ReadFile(filePath: str, defaultContents: Union[str, bytes, None] = None, binary: bool = False) -> Union[str, bytes]:
    filePath = os.path.realpath(filePath)
    if not os.path.exists(filePath):
        if defaultContents != None:
            return defaultContents
    with open(filePath, "rb" if binary else "r", encoding=(None if binary else "UTF-8")) as file:
        return file.read()
def SerializeJson(object: Union[dict, types.SimpleNamespace], pretty: bool = False) -> None:
    if isinstance(object, types.SimpleNamespace):
        return json.dumps(vars(object), indent=(4 if pretty else None))
    else:
        return json.dumps(object, indent=(4 if pretty else None))
def DeserializeJson(jsonString: str, simple_namespace: bool = False) -> Union[dict, types.SimpleNamespace]:
    if simple_namespace:
        return json.loads(jsonString, object_hook=lambda obj: types.SimpleNamespace(**obj))
    else:
        return json.loads(jsonString)
def SerializeBase64(buffer: bytes) -> str:
    return base64.urlsafe_b64encode(buffer).decode("UTF-8")
def DeserializeBase64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("UTF-8"))

# Loading environment.json
ENV: types.SimpleNamespace = None
def LoadEnv() -> None:
    global ENV
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    ENV = DeserializeJson(ReadFile("./environment.json"), simple_namespace=True)
    if ENV.in_prod:
        ENV.discord_bot_token = ENV.discord_bot_token_prod
    else:
        ENV.discord_bot_token = ENV.discord_bot_token_dev
    ENV.verification_key = bytes.fromhex(ENV.verification_key)
    ENV.verification_iv = bytes.fromhex(ENV.verification_iv)
LoadEnv()

# Working with the main user database.
DB: dict[str] = None
def LoadDB() -> None:
    global DB
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    if os.path.isfile("./database.json"):
        DB = DeserializeJson(ReadFile("./database.json"))
    else:
        DB = {}
def SaveDB() -> None:
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    WriteFile("./database.json", SerializeJson(DB, pretty=True))
def DBGet(discord_id: str) -> Union[str, None]:
    if discord_id in DB:
        return DB[discord_id]
    else:
        return None
def DBSet(discord_id: str, onid_email: Union[str, None]) -> None:
    if onid_email == None:
        if discord_id in DB:
            del DB[discord_id]
    else:
        DB[discord_id] = onid_email
    SaveDB()
LoadDB()

# Looking up user information by ONID.
async def LookupOnidName(onid_email: str) -> Union[str, None]:
    def LookupOnidNameSync(onid_email: str) -> Union[str, None]:
        try:
            # Get a token
            response = requests.post("https://api.oregonstate.edu/oauth2/token", data={"grant_type": "client_credentials"}, auth=(ENV.osu_api_id, ENV.osu_api_secret))
            response.raise_for_status()
            token = response.json()["access_token"]

            # Send a request
            headers = { "Authorization": f"Bearer {token}", "Accept": "application/json" }
            response = requests.get(f"https://api.oregonstate.edu/v2/directory?filter[emailAddress]={onid_email}", headers=headers)
            response.raise_for_status()
            data = response.json()["data"]

            # Return output or None
            if len(data) != 1:
                return None
            return f"{data[0]['attributes']['firstName']} {data[0]['attributes']['lastName']}"
        except:
            return None
    return await asyncio.to_thread(LookupOnidNameSync, onid_email)

# Sending emails.
async def SendEmail(to: str, subject: str, body: str) -> None:
    def SendEmailSync(to: str, subject: str, body: str) -> None:
        # Auth with gmail
        with smtplib.SMTP("smtp-mail.outlook.com", 587) as smtp:
            smtp.starttls()
            smtp.login(ENV.email_address, ENV.email_password)

            # Construct email message
            msg = MIMEMultipart()
            msg["From"] = ENV.email_address
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            # Send message
            smtp.send_message(msg)
    return await asyncio.to_thread(SendEmailSync, to, subject, body)

# Generating codes and parsing them.
def CreateCode(discord_id: str, onid_email: str) -> str:
    token = { "magic": "d5bI8cRB4QDcp2yi", "discord_id": discord_id, "onid_email": onid_email }

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

    return token["discord_id"], token["onid_email"]

# WatchDog
watch_dog_log: dict[list[int]] = { }
def WatchDogTrim(discord_id: str) -> None:
    user_log = []
    if discord_id in watch_dog_log:
        user_log = watch_dog_log[discord_id]
    
    user_log = [ timestamp for timestamp in user_log if timestamp >= (int(datetime.now().timestamp()) - 86400) ]
    watch_dog_log[discord_id] = user_log
def WatchDogPunish(discord_id: str) -> None:
    user_log = []
    if discord_id in watch_dog_log:
        user_log = watch_dog_log[discord_id]
    
    user_log.append(int(datetime.now().timestamp()))
    watch_dog_log[discord_id] = user_log
def WatchDogForgive(discord_id: str) -> None:
    watch_dog_log[discord_id] = []
def WatchDogQuery(discord_id: str) -> int:
    WatchDogTrim(discord_id)
    if not discord_id in watch_dog_log:
        return 0
    else:
        return len(watch_dog_log[discord_id])
def WatchDogInGoodStanding(discord_id: str) -> bool:
    return WatchDogQuery(discord_id) < 10

# Initialize client and command tree classes.
discord_client = discord.Client(intents=discord.Intents.default())
discord_command_tree = discord.app_commands.CommandTree(discord_client)

# GUI interactions
class VerifyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get Verified!", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OnidInputModal())
class OnidInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="ONID Email", timeout=None, custom_id="onid_input_modal")
    
    onid_input = discord.ui.TextInput(label="Enter your ONID email address:", placeholder="onid@oregonstate.edu", required=True, custom_id="onid_input")
    async def on_submit(self, interaction: discord.Interaction):
        onid_email = str(self.onid_input.value).strip().lower()

        if not onid_email.endswith("@oregonstate.edu") or len(onid_email) <= len("@oregonstate.edu"):
            await interaction.response.send_message(f"The ONID you entered doesn't look quite right. Please try again.", ephemeral=True)
            return

        if not WatchDogInGoodStanding(str(interaction.user.id)):
            await interaction.response.send_message(f"TOO MANY REQUESTS! Please wait 24 hours.", ephemeral=True)
            return
        WatchDogPunish(str(interaction.user.id))

        code = CreateCode(str(interaction.user.id), onid_email)
        await SendEmail(onid_email, "Verification Code - OSU Climbing Club", f"Your verification code for the OSU Climbing Club's official Discord server is:\n\n{code}\n\nIf you did not request this code please reach out to Indoor.RockClimbing@oregonstate.edu and we will investigate.")
        
        await interaction.response.send_message(f"A verification code has been sent to {onid_email}.\n\nPlease allow up to 15 minutes for the code to arive, and **check spam.**", ephemeral=True)

# Commands
@discord_command_tree.command(name="post_verify_button", description="Posts the verification button to the current channel.")
async def instructions(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator and not interaction.guild.owner_id == interaction.user.id:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    await interaction.channel.send("", view=VerifyButtonView())
    await interaction.response.send_message("Done!", ephemeral=True)
@discord_command_tree.command(name="get_user_info", description="Posts a bunch of debug information on a target user just for you.")
async def get_user_info(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator and not interaction.guild.owner_id == interaction.user.id:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    user_id = str(user.id)
    user_mention = user.mention
    discord_verified_role_id: int = None
    for role in interaction.guild.roles:
        if role.name == "ONID-Verified":
            discord_verified_role_id = role.id
            break
    if discord_verified_role_id == None:
        raise Exception()
    verified_role = any([ role.id == discord_verified_role_id for role in user.roles ])
    onid_email = DBGet(user_id)
    onid_name = await LookupOnidName(onid_email)
    watchdog_requests = WatchDogQuery(user_id)
    await interaction.response.send_message(f"""User: {user_mention}\nUser ID: {user_id}\nVerified Role: {verified_role}\nONID: {onid_email}\nONID Name: {onid_name}\nWatchDog Requests: {watchdog_requests}""", ephemeral=True)

# Launch the bot and log ready message to console
@discord_client.event
async def on_ready():
    await discord_command_tree.sync()
    discord_client.add_view(VerifyButtonView())
    await discord_client.change_presence(activity=discord.CustomActivity("Verifying ONID email addresses..."), status=discord.Status.online)
    print(f"Online as {discord_client.user}")

"""
async def verify_code(code: str):

    try:
        discord_id, onid_email = ParseCode(code)
    except:
        return f"That code doesn't look right. Please try again."
            
    if not WatchDogInGoodStanding(discord_id):
        return f"TOO MANY REQUESTS! Please wait 24 hours."
    WatchDogPunish(discord_id)

    DBSet(discord_id, onid_email)
    discord_verified_role_id: int = None
    for role in interaction.guild.roles:
        if role.name == "ONID-Verified":
            discord_verified_role_id = role.id
            break
    if discord_verified_role_id == None:
        raise Exception()
    await interaction.user.add_roles(discord.Object(discord_verified_role_id))
    onid_name = await LookupOnidName(onid_email)
    if onid_name == None:
        print(f"Failed to lookup onid name for {onid_email}.")
    else:
        try:
            await interaction.user.edit(nick=onid_name)
        except:
            print(f"Failed to nick {interaction.user.id}.")

    await interaction.response.send_message(f"{interaction.user.mention} you have been verified as {onid_email}. ({onid_name})\n\nWelcome to the server. Don\'t forget to read the rules. :slight_smile:", ephemeral=True)
    """

async def handle_client(reader, writer):
    code = (await reader.readline()).decode(encoding="UTF-8").strip()
    print(f"Verifying code {code}")

    response = verify_code(code)

    writer.write(response.encode(encoding="UTF-8"))
    writer.close()

async def main():
    server = await asyncio.start_server(handle_client, "127.0.0.1", ENV.local_listen_port)
    print(f"Listening on 127.0.0.1:{ENV.local_listen_port}")
    async with server:
        await asyncio.gather(server.serve_forever(), discord_client.start(ENV.discord_bot_token))
asyncio.run(main())