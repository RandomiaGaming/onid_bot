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

def WriteFile(filePath, contents, binary=False):
    filePath = os.path.realpath(filePath)
    dirPath = os.path.dirname(filePath)
    os.makedirs(dirPath, exist_ok=True)
    with open(filePath, "wb" if binary else "w", encoding=(None if binary else "UTF-8")) as file:
        file.write(contents)
def ReadFile(filePath, defaultContents=None, binary=False):
    filePath = os.path.realpath(filePath)
    if not os.path.exists(filePath):
        if defaultContents != None:
            return defaultContents
    with open(filePath, "rb" if binary else "r", encoding=(None if binary else "UTF-8")) as file:
        return file.read()
def ParseJson(jsonString):
    return json.loads(jsonString, object_hook=lambda obj: types.SimpleNamespace(**obj))

os.chdir(os.path.realpath(os.path.dirname(__file__)))
ENV = ParseJson(ReadFile("./environment.json"))
ENV.verification_key = bytes.fromhex(ENV.verification_key)
ENV.verification_iv = bytes.fromhex(ENV.verification_iv)
ENV.verification_header = b"VERT"

smtp = smtplib.SMTP("smtp.gmail.com", 587)
smtp.starttls()
smtp.login(ENV.email_address, ENV.email_password)

client = discord.Client(intents=discord.Intents.default())
commandTree = discord.app_commands.CommandTree(client)

def OnidExists(onid):
    try:
        url = f"https://ne2vbpr3na.execute-api.us-west-2.amazonaws.com/prod/people?q={urllib.parse.quote(onid)}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return isinstance(data, list) and len(data) > 0
    except:
        return False
def GenerateCode(onid):
    plaintext = ENV.verification_header + onid.encode(encoding="UTF-8")

    padding_length = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([ padding_length ] * padding_length)

    cipher = Cipher(algorithms.AES(ENV.verification_key), modes.CBC(ENV.verification_iv))
    encryptor = cipher.encryptor()
    cyphertext = encryptor.update(padded) + encryptor.finalize()

    return cyphertext.hex()
def ParseCode(code):
    cyphertext = bytes.fromhex(code)

    cipher = Cipher(algorithms.AES(ENV.verification_key), modes.CBC(ENV.verification_iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(cyphertext) + decryptor.finalize()

    padding_length = padded[-1]
    plaintext = padded[:-padding_length]

    if len(plaintext) <= len(ENV.verification_header) or plaintext[:len(ENV.verification_header)] != ENV.verification_header:
        raise RuntimeError("Missing verification header.")

    return plaintext[len(ENV.verification_header):].decode(encoding="UTF-8")
def SendEmail(to, subject, body):
    msg = MIMEMultipart()
    msg["From"] = ENV.email_address
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    smtp.send_message(msg)

RateLimitByAccount = {}
RateLimitByONID = {}

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
        
        if not OnidExists(onid):
            await interaction.response.send_message(f"The ONID you entered {onid} doesn't exist. Please try again.", ephemeral=True)
            return
        
        try:
            code = GenerateCode(onid)
        except:
            await interaction.response.send_message(f"Failed to generate your verification code. Please try again.", ephemeral=True)
            return

        try:
            SendEmail(onid, "Verification Code - OSU Climbing Club", f"Your verification code for the OSU Climbing Club's official Discord server is:\n\n{code}\n\nIf you did not request this code please reach out to Indoor.RockClimbing@oregonstate.edu and we will investigate.")
        except:
            await interaction.response.send_message(f"Failed to send your verification code. Please try again.", ephemeral=True)
            return

        await interaction.response.send_message(f"A verification code has been sent to {onid}.\n\nPlease allow up to 15 minutes for the code to arive.", ephemeral=True)

class CodeInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Verification Code", timeout=None, custom_id="code_input_modal")
    
    code_input = discord.ui.TextInput(label="Enter your verification code:", placeholder="123456789abcdef...", required=True, custom_id="code_input")
    async def on_submit(self, interaction: discord.Interaction):
        code = str(self.code_input)

        try:
            onid = ParseCode(code)
        except:
            await interaction.response.send_message(f"That code doesn't look right. Please try again.", ephemeral=True)
            return



        await interaction.user.add_roles(interaction.guild.get_role(ENV.verified_role_id))

        await interaction.response.send_message(f"{interaction.user.mention} has been verified as **{onid}**.\n\nWelcome to the server. Don't forget to read the rules. :slight_smile:", ephemeral=True)

@commandTree.command(name="post_instructions", description="Posts the verification instructions in the current channel.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def post_instructions(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    await interaction.channel.send("Welcome to the OSU Climbing Club official Discord server.\n\nTo get access to the rest of the server you will need to verify your ONID email address.\n\u200b", view=VerifyButtonView())
    await interaction.response.send_message("Done!", ephemeral=True)

@commandTree.command(name="get_onid", description="Looks up the ONID email address of a given discord user if availible.", guilds=[ discord.Object(server_id) for server_id in ENV.server_ids ])
async def get_onid(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You need the administrator permission to run this command.", ephemeral=True)
        return
    
    await interaction.response.send_message(f"{member.name} is not verified.", ephemeral=True)

@client.event
async def on_ready():
    for server_id in ENV.server_ids:
        await commandTree.sync(guild=discord.Object(server_id))
    client.add_view(VerifyButtonView())
    print(f"Online as {client.user}")

client.run(ENV.token)