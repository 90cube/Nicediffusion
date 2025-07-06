@echo off
title Nice Diffusion Launcher

:: --- 현재 배치 파일이 있는 경로를 기준으로 작업 경로를 설정합니다. ---
cd /d "%~dp0"

echo.
echo =================================
echo  Starting Nicediff
echo =================================
echo.
echo  Project Path: %cd%
echo.

:: --- 가상환경의 Python을 직접 지정하여 main.py를 실행합니다. ---
echo  Starting the application...
echo  Using Python from: venv\Scripts\python.exe
echo.

venv\Scripts\python.exe main.py

:: --- 실행이 끝나면 창이 바로 닫히지 않도록 잠시 대기합니다. ---
echo.
echo =================================
echo  Application has been closed.
echo =================================
echo.
pause