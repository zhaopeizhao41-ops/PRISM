@echo off
chcp 65001 >nul
title PRISM - 启动全栈服务
echo ========================================================
echo               正在启动 PRISM 全栈服务
echo ========================================================
echo.
echo 前端访问地址: http://localhost:3000
echo 后端 API 地址: http://localhost:5001
echo.
echo 注意: 首次使用前请确保项目根目录 .env 文件中的 API KEY 已填写。
echo ========================================================
echo.

cd /d "%~dp0"
call npm.cmd run dev
pause
