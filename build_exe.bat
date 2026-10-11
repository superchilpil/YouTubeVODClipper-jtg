@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JTG YouTube VOD Clipper - Build

echo.
echo ========================================
echo   YouTube VOD Clipper - Windows Build
echo ========================================

py -3.11 -m pip install --upgrade pip
if errorlevel 1 goto :error
py -3.11 -m pip install -r requirements.txt
if errorlevel 1 goto :error
py -3.11 -m pip install --upgrade pyinstaller
if errorlevel 1 goto :error

echo Preparing bundled FFmpeg...
py -3.11 scripts\prepare_ffmpeg.py
if errorlevel 1 goto :error
if not exist "tools\ffmpeg\ffmpeg.exe" goto :error

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
py -3.11 -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "YouTubeVODClipper" ^
  --collect-all customtkinter ^
  --collect-all tkwry ^
  --hidden-import imageio_ffmpeg ^
  --add-binary "%CD%\tools\ffmpeg\ffmpeg.exe;." ^
  "src\youtube_vod_clipper\app.py"
if errorlevel 1 goto :error
if not exist "dist\YouTubeVODClipper.exe" goto :error

echo.
echo BUILD SUCCESSFUL: dist\YouTubeVODClipper.exe
pause
exit /b 0
:error
echo.
echo BUILD FAILED. Check the output above.
pause
exit /b 1
