#!/usr/bin/env python

import discord
import json
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from datetime import datetime
import asyncio
import io
import base64
import time

# Bot authentication url
# https://discord.com/oauth2/authorize?client_id=1344219132027076629

# Simple file and json read/write helpers.
def WriteFile(filePath, contents, binary=False):
    filePath = os.path.realpath(os.path.expanduser(filePath))
    dirPath = os.path.dirname(filePath)
    if not os.path.exists(dirPath):
        os.makedirs(dirPath)
    with io.open(filePath, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(contents)
def ReadFile(filePath, defaultContents=None, binary=False):
    filePath = os.path.realpath(os.path.expanduser(filePath))
    if defaultContents != None and not os.path.exists(filePath):
        return defaultContents
    with io.open(filePath, "rb" if binary else "r", encoding=None if binary else "utf-8") as f:
        return f.read()
def SerializeJson(obj):
    return json.dumps(obj)
def DeserializeJson(jsonString):
    return json.loads(jsonString)

# Loading environment.json
ENV = None
def LoadEnv():
    global ENV
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    ENV = DeserializeJson(ReadFile("./environment.json"))
LoadEnv()

# Working with the main user database.
DB = None
def LoadDB():
    global DB
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    if os.path.isfile("./database.json"):
        DB = DeserializeJson(ReadFile("./database.json"))
    else:
        DB = {}
def SaveDB():
    os.chdir(os.path.realpath(os.path.dirname(__file__)))
    WriteFile("./database.json", SerializeJson(DB))
def DBGet(discord_id):
    if discord_id in DB:
        return DB[discord_id]
    else:
        return None
def DBSet(discord_id, onid_email):
    if onid_email == None:
        if discord_id in DB:
            del DB[discord_id]
    else:
        DB[discord_id] = onid_email
    SaveDB()
LoadDB()

# Looking up user information by ONID.
async def LookupOnidName(onid_email):
    def LookupOnidNameSync(onid_email):
        try:
            # Get a token
            response = requests.post("https://api.oregonstate.edu/oauth2/token", data={"grant_type": "client_credentials"}, auth=(ENV["osu_api_id"], ENV["osu_api_secret"]))
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

# MSAath
# Returns refresh_token, access_token
def DoDeviceCodeFlow():
    # Tenant id is required for rooted scope paths on the device code endpoint.
    device_code_request_data = { "client_id": ENV["msauth_client_id"], "scope": " ".join(ENV["msauth_scopes"]) }
    device_code_request = requests.post("https://login.microsoftonline.com/" + ENV["msauth_tenant_id"] + "/oauth2/v2.0/devicecode", data=device_code_request_data)
    device_code_request.raise_for_status()
    device_code_response = device_code_request.json()
    print(device_code_response["message"])
    start = time.time()
    while time.time() - start < int(device_code_response["expires_in"]):
        time.sleep(int(device_code_response["interval"]))
        token_request_data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": ENV["msauth_client_id"],
            "device_code": device_code_response["device_code"],
        }
        token_request = requests.post("https://login.microsoftonline.com/" + ENV["msauth_tenant_id"] + "/oauth2/v2.0/token", data=token_request_data)
        if token_request.ok:
            token = token_request.json()
            return token["refresh_token"], token["access_token"]
        else:
            token_request_error = token_request.json()
            if token_request_error["error"] == "authorization_pending":
                continue
            else:
                raise Exception(token_request_error["error"])
    raise Exception("Timed out waiting for device authorization")
# Returns refresh_token, access_token
def DoRefreshFlow(refresh_token):
    token_request_data = {
        "grant_type": "refresh_token",
        "client_id": ENV["msauth_client_id"],
        "refresh_token": refresh_token,
        "scope": " ".join(ENV["msauth_scopes"]),
    }
    token_request = requests.post("https://login.microsoftonline.com/" + ENV["msauth_tenant_id"] + "/oauth2/v2.0/token", data=token_request_data)
    token_request.raise_for_status()
    token = token_request.json()
    return token["refresh_token"], token["access_token"]
# Returns the email address from a token by UPN
def EmailFromToken(access_token):
    token_body = access_token.split(".")[1]
    token_body += '=' * (-len(token_body) % 4)
    token_json = base64.urlsafe_b64decode(token_body).decode("utf-8")
    token_object = json.loads(token_json)
    return token_object["upn"]
REFRESH_TOKEN = None
def MSAuthInit():
    global REFRESH_TOKEN
    REFRESH_TOKEN, _ = DoDeviceCodeFlow()
def MSAuthGetAccessToken():
    global REFRESH_TOKEN
    REFRESH_TOKEN, access_token = DoRefreshFlow(REFRESH_TOKEN)
    return access_token

# Sending emails.
async def SendEmail(to, subject, body):
    def SendEmailSync(to, subject, body):
        access_token = MSAuthGetAccessToken()
        email = EmailFromToken(access_token)
        with smtplib.SMTP("smtp.office365.com", 587) as smtp:
            smtp.starttls()
            smtp.ehlo() # Required before auth. Handshake to agree on supported features.
            auth_code = base64.b64encode(("user=" + email + "\x01auth=Bearer " + access_token + "\x01\x01").encode("utf-8")).decode("utf-8")
            code, resp = smtp.docmd("AUTH", "XOAUTH2 " + auth_code)
            if code != 235:
                raise Exception("AUTH failed: " + str(code) + " " + resp.decode(encoding="utf-8"))

            msg = MIMEMultipart()
            msg["From"] = email
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html"))

            smtp.send_message(msg)
    return await asyncio.to_thread(SendEmailSync, to, subject, body)

# Generating codes and parsing them.
def CreateCode(discord_id, onid_email):
    token = { "magic": "d5bI8cRB4QDcp2yi", "discord_id": discord_id, "onid_email": onid_email }

    plaintext = SerializeJson(token).encode(encoding="UTF-8")

    padding_length = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([ padding_length ] * padding_length)

    cipher = Cipher(algorithms.AES(bytes.fromhex(ENV["verification_key"])), modes.CBC(bytes.fromhex(ENV["verification_iv"])))
    encryptor = cipher.encryptor()
    cyphertext = encryptor.update(padded) + encryptor.finalize()

    return cyphertext.hex()
def ParseCode(code):
    cyphertext = bytes.fromhex(code)

    cipher = Cipher(algorithms.AES(bytes.fromhex(ENV["verification_key"])), modes.CBC(bytes.fromhex(ENV["verification_iv"])))
    decryptor = cipher.decryptor()
    padded = decryptor.update(cyphertext) + decryptor.finalize()

    padding_length = padded[-1]
    plaintext = padded[:-padding_length].decode(encoding="UTF-8")

    token =  DeserializeJson(plaintext)
    if token["magic"] != "d5bI8cRB4QDcp2yi":
        raise Exception("Bad token magic.")

    return token["discord_id"], token["onid_email"]

# WatchDog
watch_dog_log = { }
def WatchDogTrim(discord_id):
    user_log = []
    if discord_id in watch_dog_log:
        user_log = watch_dog_log[discord_id]
    
    user_log = [ timestamp for timestamp in user_log if timestamp >= (int(datetime.now().timestamp()) - 86400) ]
    watch_dog_log[discord_id] = user_log
def WatchDogPunish(discord_id):
    user_log = []
    if discord_id in watch_dog_log:
        user_log = watch_dog_log[discord_id]
    
    user_log.append(int(datetime.now().timestamp()))
    watch_dog_log[discord_id] = user_log
def WatchDogForgive(discord_id):
    watch_dog_log[discord_id] = []
def WatchDogQuery(discord_id):
    WatchDogTrim(discord_id)
    if not discord_id in watch_dog_log:
        return 0
    else:
        return len(watch_dog_log[discord_id])
def WatchDogInGoodStanding(discord_id):
    return WatchDogQuery(discord_id) < 10

# Initialize client and command tree classes.
discord_client = discord.Client(intents=discord.Intents.default())
discord_command_tree = discord.app_commands.CommandTree(discord_client)
discord_server = discord.Object(ENV["discord_server_id"])
discord_verified_role = discord.Object(ENV["discord_verified_role_id"])
discord_unverified_role = discord.Object(ENV["discord_unverified_role_id"])

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
        email = ReadFile("./email.html").replace("##ONIDbotCode##", code).replace("##DiscordAt##", "@" + interaction.user.name).replace("##ONIDEmail##", onid_email)
        await SendEmail(onid_email, "Get Verified - ONIDbot", email)
        
        await interaction.response.send_message(f"A verification code has been sent to {onid_email}.\n\nPlease allow up to 15 minutes for the code to arive, and **check spam.**", ephemeral=True)

# Commands
@discord_command_tree.command(name="post_verify_button", description="Posts the verification button in the current channel.", guild=discord_server)
async def instructions(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    await interaction.channel.send("", view=VerifyButtonView())
    await interaction.response.send_message("Done!", ephemeral=True)
@discord_command_tree.command(name="get_user_info", description="Posts a bunch of debug information on a target user just for you.", guild=discord_server)
async def get_user_info(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    user_id = str(user.id)
    user_mention = user.mention
    verified_role = any([ role.id == discord_verified_role.id for role in user.roles ])
    unverified_role = any([ role.id == discord_unverified_role.id for role in user.roles ])
    onid_email = DBGet(user_id)
    onid_name = await LookupOnidName(onid_email)
    watchdog_requests = WatchDogQuery(user_id)
    await interaction.response.send_message(f"""User: {user_mention}\nUser ID: {user_id}\nVerified Role: {verified_role}\nUnverified Role: {unverified_role}\nONID: {onid_email}\nONID Name: {onid_name}\nWatchDog Requests: {watchdog_requests}""", ephemeral=True)
@discord_client.event
async def on_ready():
    await discord_command_tree.sync(guild=discord_server)
    discord_client.add_view(VerifyButtonView())
    await discord_client.change_presence(activity=discord.CustomActivity("Verifying ONID email addresses..."), status=discord.Status.online)
    print(f"Online as {discord_client.user}")
    #asyncio.create_task(test())
async def test():
    discord_ids = []
    for discord_id in DB:
        discord_ids.append(discord_id)
    for discord_id in discord_ids:
        try:
            discord_server_obj = discord_client.get_guild(ENV["discord_server_id"])
            if discord_server_obj is None:
                discord_server_obj = await discord_client.fetch_guild(ENV["discord_server_id"])
            discord_user_obj = discord_server_obj.get_member(discord_id)
            if discord_user_obj is None:
                discord_user_obj = await discord_server_obj.fetch_member(discord_id)
            print(discord_id)
        except Exception as ex:
            print(discord_id + " ", end="")
            print(str(ex))
        await asyncio.sleep(0.5)

# Web API
async def ApiVerifyCode(code):
    try:
        discord_id, onid_email = ParseCode(code)
    except:
        return f"That code doesn't look right. Please try again."
    
    if not WatchDogInGoodStanding(discord_id):
        return f"TOO MANY REQUESTS! Please wait 24 hours."
    WatchDogPunish(discord_id)

    DBSet(discord_id, onid_email)

    discord_server_obj = discord_client.get_guild(ENV["discord_server_id"])
    if discord_server_obj is None:
        discord_server_obj = await discord_client.fetch_guild(ENV["discord_server_id"])

    discord_user_obj = discord_server_obj.get_member(discord_id)
    if discord_user_obj is None:
        discord_user_obj = await discord_server_obj.fetch_member(discord_id)

    await discord_user_obj.add_roles(discord_verified_role)
    await discord_user_obj.remove_roles(discord_unverified_role)
    onid_name = await LookupOnidName(onid_email)
    if onid_name == None:
        print(f"Failed to lookup onid name for {onid_email}.")
    else:
        try:
            await discord_user_obj.edit(nick=onid_name)
        except:
            print(f"Failed to nick {discord_id}.")

    return f"Success your Discord account (@{discord_user_obj.name}) has been linked with your ONID email ({onid_email}).<br />You may now close this tab and return to Discord."
async def ApiHandleClient(reader, writer):
    try:
        code = (await reader.readline()).decode("utf-8").strip()
        response = await ApiVerifyCode(code)
        writer.write(response.encode("utf-8"))
        writer.close()
    except:
        pass
async def ApiRunServer():
    server = await asyncio.start_server(ApiHandleClient, "127.0.0.1", ENV["local_api_port"])
    print("API Server running on 127.0.0.1:" + str(ENV["local_api_port"]) + ".")
    async with server:
        await server.serve_forever()

# Main
async def Main():
    await asyncio.gather(
        ApiRunServer(),
        discord_client.start(ENV["discord_token"])
    )
MSAuthInit()
asyncio.run(Main())