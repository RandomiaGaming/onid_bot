import discord
import json


class MyBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in and running as {self.user}.")

    async def on_message(self, message):
        if message.author == self.user:
            return

        if not self.user.mentioned_in(message):
            return

        content = message.content
        if content.startswith("<@"):
            content = content[content.index(">") + 1:]
        content = content.trim()
        if content.startswith("nick"):


            # Load environment
with open("environment.json", "r") as file:
    environment = json.load(file)

# Set up bot intents
intents = discord.Intents.default()
intents.messages = True

# Start bot
bot = MyBot(intents=intents)
bot.run(environment["token"])
