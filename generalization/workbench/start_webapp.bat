@echo off
chcp 65001 >nul
title 数据整理与特征转换工作台 · Web 版
echo ============================================================
echo   数据整理与特征转换工作台 · Web 版
echo   配套「终极版数据集模板 v3」的前置自动化工具
echo ============================================================
echo.

REM ---- 检查 Python ----
where python >nul 2>nul
if %errorlevel%==0 (
    set PY=python
) else (
    where py >nul 2>nul
    if %errorlevel%==0 (
        set PY=py
    ) else (
        echo [错误] 未检测到 Python，请先安装 Python 3.8+：
        echo        https://www.python.org/downloads/
        echo        安装时请勾选 "Add Python to PATH"
        pause
        exit /b 1
    )
)

REM ---- 检查依赖并安装 ----
echo [1/3] 检查依赖库...
%PY% -c "import numpy, pandas, openpyxl" >nul 2>nul
if %errorlevel% neq 0 (
    echo       正在安装 numpy / pandas / openpyxl ...
    %PY% -m pip install numpy pandas openpyxl
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败，请检查网络后重试。
        pause
        exit /b 1
    )
)
echo       依赖就绪。

REM ---- 启动服务 ----
echo [2/3] 启动服务（端口 8765）...
cd /d "%~dp0webapp"
start "" %PY% server.py

echo [3/3] 浏览器将自动打开 http://127.0.0.1:8765
echo       若未自动打开，请手动在浏览器访问该地址。
echo       关闭服务：直接关闭弹出的黑色命令行窗口。
echo.
pause
