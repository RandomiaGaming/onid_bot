#!/bin/env sh
set -xeuo pipefail

rm -rf ./venv

python -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install discord requests cryptography