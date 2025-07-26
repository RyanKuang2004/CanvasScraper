import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Canvas
    CANVAS_URL = 'https://canvas.lms.unimelb.edu.au/api/v1'
    CANVAS_API_TOKEN = os.getenv('CANVAS_API_TOKEN')
    
