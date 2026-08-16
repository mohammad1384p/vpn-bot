#!/bin/bash
cd /root/vpn-bot
export PYTHONPATH=$PWD:$PWD/bot
/root/vpn-bot/venv/bin/python bot/main.py