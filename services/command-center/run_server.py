import sys
sys.path.insert(0, 'services/command-center')
import uvicorn
from main_minimal import app
print('Starting server...')
uvicorn.run(app, host='127.0.0.1', port=8000, log_level='info')
