#!/usr/bin/bash

mkdir -p ~/public_html/
chmod 755 ~/public_html
mkdir -p ~/public_html/onid_bot
chmod 755 ~/public_html/onid_bot
mkdir -p ~/public_html/cgi-bin/
chmod 755 ~/public_html/cgi-bin
mkdir -p ~/public_html/cgi-bin/onid_bot
chmod 755 ~/public_html/cgi-bin/onid_bot

cp ./verify.html ~/public_html/onid_bot/verify.html
chmod 744 ~/public_html/onid_bot/verify.html
cp ./verify.py ~/public_html/cgi-bin/onid_bot/verify.py
chmod 755 ~/public_html/cgi-bin/onid_bot/verify.py

chmod 755 ./onid_bot.py
chmod 755 ./api_broker.py

rm -rf ./venv

python -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install discord requests cryptography