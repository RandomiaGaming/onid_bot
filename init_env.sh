#!/bin/env sh
set -xeuo pipefail

mkdir -p ~/public_html/ONIDbot
mkdir -p ~/public_html/cgi-bin/ONIDbot
chmod 755 ~/public_html
chmod 755 ~/public_html/ONIDbot
chmod 755 ~/public_html/cgi-bin
chmod 755 ~/public_html/cgi-bin/ONIDbot
cp ./verify.html ~/public_html/ONIDbot/Verify
cp ./verify.py ~/public_html/cgi-bin/ONIDbot/Verify
chmod 744 ~/public_html/ONIDbot/Verify
chmod 755 ~/public_html/cgi-bin/ONIDbot/Verify

rm -rf ./venv

python -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install discord requests cryptography