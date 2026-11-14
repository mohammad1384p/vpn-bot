#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="$PWD:$PWD/bot"
./venv/bin/python bot/main.py
