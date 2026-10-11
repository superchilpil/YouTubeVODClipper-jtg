@echo off
setlocal EnableExtensions
cd /d "%~dp0"
py -3.11 --version >nul 2>&1
if errorlevel 1 (
  echo Python 3.11 was not found. Install Python 3.11+ with the Python Launcher enabled.
  pause
  exit /b 1
)
call build_exe.bat
if errorlevel 1 exit /b 1
start "" "%CD%\dist\YouTubeVODClipper.exe"
