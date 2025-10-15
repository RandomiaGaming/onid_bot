#!/usr/bin/bash
set -x

mkdir -p ~/public_html/
chmod 755 ~/public_html
mkdir -p ~/public_html/onid_bot
chmod 755 ~/public_html/onid_bot
mkdir -p ~/public_html/cgi-bin/
chmod 755 ~/public_html/cgi-bin
mkdir -p ~/public_html/cgi-bin/onid_bot
chmod 755 ~/public_html/cgi-bin/onid_bot

cp ./verify.html ~/public_html/onid_bot/verify.html
chmod 644 ~/public_html/onid_bot/verify.html
cp ./verify.py ~/public_html/cgi-bin/onid_bot/verify.py
chmod 755 ~/public_html/cgi-bin/onid_bot/verify.py
cp ./osu_font.otf ~/public_html/onid_bot/osu_font.otf
chmod 644 ~/public_html/onid_bot/osu_font.otf
cp ./assets_and_docs/logo.png ~/public_html/onid_bot/logo.png
chmod 644 ~/public_html/onid_bot/logo.png

chmod 755 ./onid_bot.py
chmod 755 ./api_broker.py

#rm -rf ./venv

#python -m venv venv
#source venv/bin/activate

#pip install --upgrade pip
#pip install discord requests cryptography
