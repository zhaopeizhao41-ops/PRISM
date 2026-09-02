@echo off
chcp 65001 >nul
title PRISM - 启动前端服务
cd /d "%~dp0frontend"
echo 正在启动 PRISM 前端服务 (端口: 3000)...
call npm.cmd run dev
pause
