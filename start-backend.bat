@echo off
chcp 65001 >nul
title PRISM - 启动后端服务
cd /d "%~dp0backend"
echo 正在启动 PRISM 后端服务 (端口: 5001)...
uv run python run.py
pause
