@echo off
echo Starting SimpleChat AI...
python -m uvicorn backend.main:app --reload
pause
