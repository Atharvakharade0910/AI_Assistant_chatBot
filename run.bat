@echo off
setlocal
cd /d "%~dp0"
echo Starting SimpleChat AI...
python -m uvicorn backend.main:app --reload
pause
