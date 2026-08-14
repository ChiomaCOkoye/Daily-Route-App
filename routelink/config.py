# Flask Configuration
import os
from datetime import timedelta

# Base directory for the application
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Secret key for session management and CSRF protection
# IMPORTANT: Change this in production! Use a random secure string.
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# SQLite database configuration
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 
    'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'routelink.db'))
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Session configuration
PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

# AI API Configuration (optional - app works without it)
# Get your API key from https://platform.openai.com or other providers
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_API_URL = os.environ.get('AI_API_URL', 'https://api.openai.com/v1/chat/completions')
AI_MODEL = os.environ.get('AI_MODEL', 'gpt-3.5-turbo')

# Location sharing interval in seconds
LOCATION_UPDATE_INTERVAL = 5

# Application URL for QR code generation
APP_URL = os.environ.get('APP_URL', 'http://localhost:5000')

# OSRM Routing Server (Open Source Routing Machine)
# Using public demo server - for production, set up your own OSRM instance
OSRM_SERVER = os.environ.get('OSRM_SERVER', 'http://router.project-osrm.org/route/v1')

# Nominatim Geocoding Server (OpenStreetMap)
NOMINATIM_SERVER = os.environ.get('NOMINATIM_SERVER', 'https://nominatim.openstreetmap.org')

# Disable Flask debug mode to prevent reloader issues with background processes
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')
