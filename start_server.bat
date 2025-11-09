@echo off
cd /d c:\Users\jonmi\OneDrive\Documents\AetherLink
set PYTHONPATH=c:\Users\jonmi\OneDrive\Documents\AetherLink
python -c "import sys; sys.path.insert(0, 'services/command-center'); import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8000, log_level='info')"