# What is ONIDbot?
ONIDbot is a free and open source Discord bot which can be added to any server for free.
It was developed by Finlay Christ a cybersecurity major at Oregon State University.
ONIDbot is designed to collect and verify the OregonState.edu email addresses of your server's members.
You have full control over which permissions are granted to everyone and which require ONID verification.

# Why do I even need ONIDbot?
As soon as a Discord server invite link gets posted on social media that server becomes a public space.
People from around the world can join regardless of student status or intentions.
Even the links you post on IdealLogic are public!
While banning a single account is easy creating alt accounts to bypass a ban is equally as easy.
With ONIDbot you can hold users accountable for their actions by requiring their ONID email which is linked to their full name.

# Addinging The Bot/Permissions:
Adding ONIDbot to your server is easy.
Just click the link below and following Discord's instructions to add ONIDbot to your server
https://discord.com/oauth2/authorize?client_id=1344219132027076629
ONIDbot asks for 3 permissions, each of which is essential for the bot to function correctly.
Manage Roles is required in order to give members the ONID-Verified role after completing verification.
Manage Nicknames allows the bot to change each member's nickname to their full name after verification.
Send Messages is required to post the "Get Verified" button and to show the "Enter your ONID email address" popup.

# Roles Setup:
Next you will need to create a role which is given to verified members.
Go to Server Settings > Roles and press Create Role.
Name the role Verified and give members the View Channels permission.
Then go to @everyone and take away the View Channels permission.
Then type "/set_verified_role @Verified".

# Channel Setup:
Right now @everyone can't see any channels. That means they can't even see the "Get Verified" button.
To fix that create a new channel called get-verified.
Go to Edit Channel > Permissions and give @everyone the View Channel and Read Message History permissions.
You may also want to give members the Send Messages in Threads and Posts permission and create a help thread.
Or you could simply instruct members with technical issues to reach out in DMs.
Finally run "/post_verify_button" to post the "Get Verified" button into the get-verified channel.

Setup should be complete but I recommend double checking by going through the verification process on an alt account.