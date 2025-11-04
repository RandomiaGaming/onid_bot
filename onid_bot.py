#!/usr/bin/env python

import discord
import json
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import asyncio
import io
import base64
from datetime import datetime, timezone
import time
import hmac
import hashlib

# Bot authentication url
# https://discord.com/oauth2/authorize?client_id=1344219132027076629

# region File IO
def IO_WriteFile(filePath, contents, binary=False):
    filePath = os.path.realpath(os.path.expanduser(filePath))
    dirPath = os.path.dirname(filePath)
    if not os.path.exists(dirPath):
        os.makedirs(dirPath)
    with io.open(filePath, "wb" if binary else "w", encoding=None if binary else "utf-8") as f:
        f.write(contents)
def IO_ReadFile(filePath, defaultContents=None, binary=False):
    filePath = os.path.realpath(os.path.expanduser(filePath))
    if defaultContents != None and not os.path.exists(filePath):
        return defaultContents
    with io.open(filePath, "rb" if binary else "r", encoding=None if binary else "utf-8") as f:
        return f.read()
def IO_SerializeJson(obj, compact=False):
    return json.dumps(obj, indent=None if compact else 4)
def IO_DeserializeJson(jsonString):
    return json.loads(jsonString)
def IO_EncodeBase64(payloadBytes):
    return base64.urlsafe_b64encode(payloadBytes).decode(encoding="utf-8").replace("=", "")
def IO_DecodeBase64(base64String):
    base64String += "=" * ((-len(base64String)) % 4)
    return base64.urlsafe_b64decode(base64String.encode(encoding="utf-8"))
def IO_GetEpoch():
    return int(time.time()) + time.localtime().tm_gmtoff
def IO_GetTime():
    epoch = IO_GetEpoch()
    timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return timestamp.strftime("%I:%M%p %m/%d").lower()
# endregion

# region Environment
ENV = None
def Env_Load():
    global ENV
    env_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "environment.json")
    ENV = IO_DeserializeJson(IO_ReadFile(env_path))
def Env_Save():
    env_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "environment.json")
    IO_WriteFile(env_path, IO_SerializeJson(ENV))
Env_Load()
# endregion

# region Logs
def Log_Generic(message, log_type, ansi_color):
    padding = " " * (8 - len(log_type)) if len(log_type) < 8 else ""
    formatted_message = f"{log_type}{padding}({IO_GetTime()} {IO_GetEpoch()}): {message}"
    print(f"\033[{ansi_color}m{formatted_message}\033[0m", flush=True)
    log_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "log.txt")
    log_contents = ""
    if os.path.exists(log_path):
        log_contents = IO_ReadFile(log_path)
    IO_WriteFile(log_path, log_contents + f"{formatted_message}\n")
def Log_Info(message):
    Log_Generic(message, "Info", "37")
def Log_Warning(message):
    Log_Generic(message, "Warning", "33")
def Log_Error(message):
    Log_Generic(message, "ERROR", "31")
def Log_Exception(ex):
    tb = ex.__traceback__
    while tb is not None:
        if os.path.realpath(tb.tb_frame.f_code.co_filename) == os.path.realpath(__file__):
            message = str(ex)
            funcname = "<module>" if tb.tb_frame.f_code.co_name == "<module>" else tb.tb_frame.f_code.co_name + "()"
            lineno = tb.tb_lineno
            line = IO_ReadFile(tb.tb_frame.f_code.co_filename).splitlines()[lineno - 1].strip()
            Log_Generic(f"{message} in {funcname} line {lineno}: {line}", "ERROR", "31")
            return
        tb = tb.tb_next
    Log_Generic(f"{str(ex)} at unknown location", "ERROR", "31")
# endregion

# Working with the main user database.
DB = None
def DB_Backup():
    db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "database.json")
    backup_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), f"backups/{IO_GetEpoch()}.json")
    backups_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "backups")
    latest_backup = 0
    for backup_time in [int(os.path.splitext(backup_path)[0]) for backup_path in os.listdir(backups_path)]:
        if backup_time > latest_backup:
            latest_backup = backup_time
    if IO_GetEpoch() - latest_backup > 24 * 60 * 60:
        IO_WriteFile(backup_path, IO_ReadFile(db_path))
        Log_Info(f"Backed up database.json to {backup_path}")
def DB_Load():
    global DB
    db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "database.json")
    if os.path.isfile(db_path):
        DB = IO_DeserializeJson(IO_ReadFile(db_path))
    else:
        DB = {}
        DB_Save()
def DB_Save():
    db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "database.json")
    IO_WriteFile(db_path, IO_SerializeJson(DB))
    DB_Backup()
def DB_Get(discord_id):
    if discord_id in DB:
        return DB[discord_id]
    else:
        return None
def DB_Set(discord_id, onid_email):
    if onid_email == None:
        if discord_id in DB:
            del DB[discord_id]
    else:
        DB[discord_id] = onid_email
    DB_Save()
DB_Load()

# region OSU API
def OSU_LookupOnidName(onid_email):
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

        # Manual Override For christj@oregonstate.edu
        if onid_email == "christj@oregonstate.edu":
            data = [ { "attributes": { "firstName": "Finlay", "lastName": "Christ" } } ]

        # Return output or None
        if len(data) == 1:
            output = f"{data[0]['attributes']['firstName']} {data[0]['attributes']['lastName']}"
            Log_Info(f"OSU directory lookup for {onid_email} returned {output}")
            return output
        else:
            Log_Warning(f"OSU directory lookup for {onid_email} returned no data.")
            return None
    except Exception as ex:
        Log_Exception(ex)
        return None
async def OSU_LookupOnidNameAsync(onid_email):
    return await asyncio.to_thread(OSU_LookupOnidName, onid_email)
# endregion

# region MSAath/Outlook
def MS_DoManualAuthFlow():
    # Tenant id is required for rooted scope paths on the device code endpoint.
    device_code_request_data = { "client_id": ENV["msauth_client_id"], "scope": " ".join(ENV["msauth_scopes"]) }
    device_code_request = requests.post("https://login.microsoftonline.com/" + ENV["msauth_tenant_id"] + "/oauth2/v2.0/devicecode", data=device_code_request_data)
    device_code_request.raise_for_status()
    device_code_response = device_code_request.json()
    Log_Info(device_code_response["message"])
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
            ENV["msauth_refresh_token"] = token_request.json()["refresh_token"]
            Env_Save()
            return
        else:
            token_request_error = token_request.json()
            if token_request_error["error"] == "authorization_pending":
                continue
            else:
                raise Exception(token_request_error["error"])
    raise Exception("Timed out waiting for device authorization")
def MS_GetAccessToken():
    token_request_data = {
        "grant_type": "refresh_token",
        "client_id": ENV["msauth_client_id"],
        "refresh_token": ENV["msauth_refresh_token"],
        "scope": " ".join(ENV["msauth_scopes"]),
    }
    token_request = requests.post("https://login.microsoftonline.com/" + ENV["msauth_tenant_id"] + "/oauth2/v2.0/token", data=token_request_data)
    token_request.raise_for_status()
    token = token_request.json()
    ENV["msauth_refresh_token"] = token["refresh_token"]
    Env_Save()
    return token["access_token"]
def MS_EmailFromToken(access_token):
    token_body = access_token.split(".")[1]
    token_body += "=" * (-len(token_body) % 4)
    token_json = base64.urlsafe_b64decode(token_body).decode("utf-8")
    token_object = json.loads(token_json)
    return token_object["upn"]
def MS_SendEmail(to, subject, body):
    access_token = MS_GetAccessToken()
    email = MS_EmailFromToken(access_token)
    with smtplib.SMTP("smtp.office365.com", 587) as smtp:
        smtp.starttls()
        smtp.ehlo() # Required before auth. Handshake to agree on supported features.
        auth_code = base64.b64encode(("user=" + email + "\x01auth=Bearer " + access_token + "\x01\x01").encode("utf-8")).decode("utf-8")
        code, resp = smtp.docmd("AUTH", "XOAUTH2 " + auth_code)
        if code != 235:
            raise Exception("SMTP auth failure " + str(code) + " " + resp.decode(encoding="utf-8"))

        msg = MIMEMultipart()
        msg["From"] = email
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        smtp.send_message(msg)
        Log_Info(f"Sent email to {to} with subject {subject}")
async def MS_SendEmailAsync(to, subject, body):
    return await asyncio.to_thread(MS_SendEmail, to, subject, body)
if not "msauth_refresh_token" in ENV:
    MS_DoManualAuthFlow()
# endregion

# region Verification Codes
def Code_Generate(discord_id, onid_email):
    payload_obj = { "version": 2, "timestamp": IO_GetEpoch(), "discord_id": discord_id, "onid_email": onid_email }
    payload_bytes = IO_SerializeJson(payload_obj, compact=True).encode(encoding="utf-8")
    signing_key_bytes = bytes.fromhex(ENV["signing_key"])
    signature_bytes = hmac.new(signing_key_bytes, payload_bytes, hashlib.sha256).digest()
    code = IO_EncodeBase64(payload_bytes) + "." + IO_EncodeBase64(signature_bytes)
    code = IO_EncodeBase64(code.encode(encoding="utf-8"))
    Log_Info(f"Issued new code for discord_id {discord_id} and onid_email {onid_email}")
    return code
def Code_ParseAndVerify(code):
    code = IO_DecodeBase64(code).decode(encoding="utf-8")
    index = code.index(".")
    if index == -1 or index == 0 or index == len(code) - 1:
        raise Exception("Bad or missing separator")
    payload_bytes = IO_DecodeBase64(code[:index])
    signature_bytes = IO_DecodeBase64(code[index + 1:])
    signing_key_bytes = bytes.fromhex(ENV["signing_key"])
    expected_signature_bytes = hmac.new(signing_key_bytes, payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature_bytes, expected_signature_bytes):
        raise Exception("Invalid signature")
    payload_obj = IO_DeserializeJson(payload_bytes.decode(encoding="utf-8"))
    if payload_obj["version"] != 2:
        raise Exception("Incompatible version")
    if IO_GetEpoch() - payload_obj["timestamp"] > (60 * 60 * 24 * 7):
        raise Exception("Code expired")
    return payload_obj
# endregion

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

        code = Code_Generate(str(interaction.user.id), onid_email)
        email = IO_ReadFile("./email.html").replace("##ONIDbotCode##", code).replace("##DiscordAt##", "@" + interaction.user.name).replace("##ONIDEmail##", onid_email)
        await MS_SendEmailAsync(onid_email, "Get Verified - ONIDbot", email)
        
        await interaction.response.send_message(f"A verification code has been sent to {onid_email}.\n\nPlease allow up to 15 minutes for the code to arive, and **check spam.**", ephemeral=True)

# Commands
@discord_command_tree.command(name="post_verify_button", description="Posts the get verified button to the current channel.", guild=discord_server)
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
    onid_email = DB_Get(user_id)
    onid_name = None if onid_email == None else await OSU_LookupOnidNameAsync(onid_email)
    watchdog_requests = WatchDogQuery(user_id)
    await interaction.response.send_message(f"""User: {user_mention}\nUser ID: {user_id}\nVerified Role: {verified_role}\nUnverified Role: {unverified_role}\nONID: {onid_email}\nONID Name: {onid_name}\nWatchDog Requests: {watchdog_requests}""", ephemeral=True)
@discord_client.event
async def on_ready():
    await discord_command_tree.sync(guild=discord_server)
    discord_client.add_view(VerifyButtonView())
    await discord_client.change_presence(activity=discord.CustomActivity("Verifying ONID email addresses..."), status=discord.Status.online)
    print(f"Online as {discord_client.user}")

# Web API
async def ApiVerifyCode(code):
    try:
        code_obj = Code_ParseAndVerify(code)
        discord_id = code_obj["discord_id"]
        onid_email = code_obj["onid_email"]
    except:
        return f"That code doesn't look right. Please try again."
    
    if not WatchDogInGoodStanding(discord_id):
        return f"TOO MANY REQUESTS! Please wait 24 hours."
    WatchDogPunish(discord_id)

    DB_Set(discord_id, onid_email)

    discord_server_obj = discord_client.get_guild(ENV["discord_server_id"])
    if discord_server_obj is None:
        discord_server_obj = await discord_client.fetch_guild(ENV["discord_server_id"])

    discord_user_obj = discord_server_obj.get_member(discord_id)
    if discord_user_obj is None:
        discord_user_obj = await discord_server_obj.fetch_member(discord_id)

    await discord_user_obj.add_roles(discord_verified_role)
    await discord_user_obj.remove_roles(discord_unverified_role)
    onid_name = await OSU_LookupOnidNameAsync(onid_email)
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
asyncio.run(Main())