#!/bin/sh
# 本地启动后端。只监听本机，模拟器能连；真机要连的话把 127.0.0.1 换成 0.0.0.0，并在应用里填电脑的局域网地址
cd "$(dirname "$0")"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload --reload-dir app --timeout-graceful-shutdown 3
