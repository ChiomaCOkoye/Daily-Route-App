"""
RouteLink - Main Flask Application
A web-based route planning, travel assistance, and driver management system.

This is a university final-year project prioritizing:
- Simplicity and readable code
- Clear comments for understanding
- Easy debugging
- Defensible architecture

Technology Stack:
- Backend: Python Flask, SQLite
- Frontend: HTML5, CSS3, Vanilla JavaScript
- Maps: Leaflet.js + OpenStreetMap
- Routing: OSRM (Open Source Routing Machine)
- Real-time: Flask-SocketIO
- Charts: Chart.js
- AI: Configurable external API (server-side only)
"""

import os
import json
import uuid
import secrets
import csv
import io
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit

from config import (
    SECRET_KEY, SQLALCHEMY_TRACK_MODIFICATIONS, PERMANENT_SESSION_LIFETIME,
    AI_API_KEY, AI_API_URL, AI_MODEL, LOCATION_UPDATE_INTERVAL, APP_URL,
    OSRM_SERVER, NOMINATIM_SERVER
)
from database.database import (
    init_db, get_db_connection, create_user, get_user_by_email, get_user_by_id,
    create_company, get_company_by_owner, get_company_by_id,
    create_driver, get_driver_by_user_id, get_drivers_by_company, update_driver_status,
    get_online_drivers_nearby,
    create_journey, complete_journey, get_journeys_by_driver, get_journeys_by_company,
    save_location, get_latest_location,
    create_sharing_link, get_sharing_link_by_token, deactivate_sharing_link,
    create_emergency_alert, get_active_emergencies, update_emergency_status,
    get_driver_performance_stats, get_company_stats
)

# ==================== APPLICATION INITIALIZATION ====================

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['PERMANENT_SESSION_LIFETIME'] = PERMANENT_SESSION_LIFETIME
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS

# Initialize Flask-SocketIO for real-time updates
# WebSockets allow bidirectional communication between server and clients
# This is essential for live location tracking and real-time dashboard updates
socketio = SocketIO(app, cors_allowed_origins="*")

# ==================== HELPER FUNCTIONS ====================

def login_required(f):
    """
    Decorator to require user authentication for a route.
    Redirects to login page if user is not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    """
    Decorator to restrict access based on user role.
    allowed_roles: list of roles that can access the route
    
    Example: @role_required(['driver', 'business_owner'])
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            
            user = get_user_by_id(session['user_id'])
            if not user or user['role'] not in allowed_roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def geocode_location(query):
    """
    Geocodes a location name to latitude/longitude using Nominatim (OpenStreetMap).
    This is a simple geocoding solution - free and doesn't require API keys.
    
    Args:
        query (str): Location name or address
    
    Returns:
        dict or None: {'lat': float, 'lng': float, 'display_name': str} or None
    """
    import urllib.request
    import urllib.parse
    
    try:
        # Encode the query for URL
        encoded_query = urllib.parse.quote(query)
        url = f"{NOMINATIM_SERVER}/search?format=json&q={encoded_query}&limit=1"
        
        # Set User-Agent as required by Nominatim
        headers = {'User-Agent': 'RouteLink/1.0'}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            if data and len(data) > 0:
                result = data[0]
                return {
                    'lat': float(result['lat']),
                    'lng': float(result['lon']),
                    'display_name': result.get('display_name', query)
                }
    except Exception as e:
        print(f"Geocoding error: {e}")
    
    return None

def calculate_route(coordinates):
    """
    Calculates a route using OSRM (Open Source Routing Machine).
    Sends coordinates to OSRM API and parses the response.
    
    Args:
        coordinates (list): List of [lng, lat] pairs in order
                           Format: [[start_lng, start_lat], [stop1_lng, stop1_lat], ...]
    
    Returns:
        dict: Route information including geometry, distance, duration
              or None if routing fails
    """
    import urllib.request
    
    try:
        # Format coordinates for OSRM: lng,lat;lng,lat;...
        coord_string = ";".join([f"{lng},{lat}" for lng, lat in coordinates])
        url = f"{OSRM_SERVER}/driving/{coord_string}?overview=full&geometries=geojson&alternatives=true"
        
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode())
            
            if data['code'] == 'Ok' and 'routes' in data and len(data['routes']) > 0:
                routes = []
                for route in data['routes']:
                    routes.append({
                        'geometry': route['geometry'],
                        'distance': route['distance'] / 1000,  # Convert meters to km
                        'duration': route['duration'] / 60,     # Convert seconds to minutes
                        'legs': route.get('legs', [])
                    })
                
                # Sort by distance to find shortest route
                routes.sort(key=lambda x: x['distance'])
                
                return {
                    'routes': routes,
                    'shortest_route': routes[0] if routes else None,
                    'waypoints': data.get('waypoints', [])
                }
    except Exception as e:
        print(f"Routing error: {e}")
    
    return None

def haversine_distance(lat1, lng1, lat2, lng2):
    """
    Calculates the great-circle distance between two points using Haversine formula.
    Used for finding nearby drivers and calculating distances.
    
    Args:
        lat1, lng1: Coordinates of first point
        lat2, lng2: Coordinates of second point
    
    Returns:
        float: Distance in kilometers
    """
    import math
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def call_ai_api(messages, system_prompt=""):
    """
    Calls the configured AI API with messages.
    All AI communication happens server-side to protect API keys.
    The app works normally without AI - this is an optional enhancement.
    
    Args:
        messages (list): List of message dictionaries with 'role' and 'content'
        system_prompt (str): Optional system prompt to prepend
    
    Returns:
        str: AI response text or None if unavailable
    """
    if not AI_API_KEY:
        return None
    
    import urllib.request
    
    try:
        # Prepare messages with system prompt
        all_messages = []
        if system_prompt:
            all_messages.append({'role': 'system', 'content': system_prompt})
        all_messages.extend(messages)
        
        payload = {
            'model': AI_MODEL,
            'messages': all_messages,
            'max_tokens': 500,
            'temperature': 0.7
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {AI_API_KEY}'
        }
        
        req = urllib.request.Request(
            AI_API_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data['choices'][0]['message']['content'].strip()
    
    except Exception as e:
        print(f"AI API error: {e}")
        return None

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors gracefully"""
    return render_template('base.html', title='Page Not Found'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors gracefully - never expose stack traces"""
    return render_template('base.html', title='Server Error'), 500

# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    """
    Landing page with branding and feature cards.
    Accessible to guests and authenticated users.
    """
    user = get_user_by_id(session.get('user_id')) if 'user_id' in session else None
    return render_template('index.html', user=user)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration page.
    Handles account creation with role selection (traveller/driver/business_owner).
    Passwords are hashed using Werkzeug for security.
    """
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'traveller')
        
        # Validation
        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        
        if role not in ['traveller', 'driver', 'business_owner']:
            flash('Invalid role selected.', 'danger')
            return render_template('register.html')
        
        # Hash password using Werkzeug - this is secure one-way encryption
        # We store the hash, not the plain text password
        password_hash = generate_password_hash(password)
        
        success, message, user_id = create_user(name, email, password_hash, role)
        
        if success:
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'danger')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login page.
    Validates credentials and creates session.
    """
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        user = get_user_by_email(email)
        
        if user and check_password_hash(user['password_hash'], password):
            session.permanent = True
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['name']
            flash('Login successful!', 'success')
            
            # Redirect based on role
            if user['role'] == 'driver':
                return redirect(url_for('driver_dashboard'))
            elif user['role'] == 'business_owner':
                return redirect(url_for('business_dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logs out the user and clears session"""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# ==================== ROUTE PLANNER ====================

@app.route('/route-planner')
def route_planner():
    """
    Interactive route planner with Leaflet map.
    Accessible to guests and authenticated users.
    Supports multiple stops and alternative routes.
    """
    user = get_user_by_id(session.get('user_id')) if 'user_id' in session else None
    return render_template('route_planner.html', user=user)

@app.route('/api/geocode')
def api_geocode():
    """
    API endpoint for geocoding location names to coordinates.
    Uses Nominatim (OpenStreetMap) - free and no API key required.
    
    Query params:
        q: Location name or address
    
    Returns JSON:
        {'lat': float, 'lng': float, 'display_name': str} or error
    """
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    result = geocode_location(query)
    if result:
        return jsonify(result)
    else:
        return jsonify({'error': 'Location not found'}), 404

@app.route('/api/route', methods=['POST'])
def api_route():
    """
    API endpoint for calculating routes using OSRM.
    
    Expects JSON:
        {'coordinates': [[lng, lat], [lng, lat], ...]}
    
    Returns JSON with route geometry, distance, duration, and alternatives.
    """
    data = request.get_json()
    if not data or 'coordinates' not in data:
        return jsonify({'error': 'Coordinates required'}), 400
    
    coordinates = data['coordinates']
    if len(coordinates) < 2:
        return jsonify({'error': 'At least 2 coordinates required'}), 400
    
    result = calculate_route(coordinates)
    if result:
        return jsonify(result)
    else:
        return jsonify({'error': 'Route calculation failed'}), 500

@app.route('/api/nearby-places')
def api_nearby_places():
    """
    API endpoint for finding nearby places using Overpass API (OpenStreetMap).
    
    Query params:
        lat: Latitude
        lng: Longitude
        radius: Search radius in meters (default: 1000)
        category: Place category (fuel, restaurant, hospital, etc.)
    
    Returns JSON list of nearby places.
    """
    import urllib.request
    import urllib.parse
    
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    radius = request.args.get('radius', default=1000, type=int)
    category = request.args.get('category', default='all')
    
    if not lat or not lng:
        return jsonify({'error': 'lat and lng required'}), 400
    
    # Map categories to Overpass queries
    category_map = {
        'fuel': '["amenity"="fuel"]',
        'restaurant': '["amenity"="restaurant"]',
        'cafe': '["amenity"="cafe"]',
        'hospital': '["amenity"="hospital"]',
        'bank': '["amenity"="bank"]',
        'pharmacy': '["amenity"="pharmacy"]',
        'hotel': '["tourism"="hotel"]',
        'parking': '["amenity"="parking"]',
        'museum': '["tourism"="museum"]',
        'library': '["amenity"="library"]',
        'church': '["amenity"="place_of_worship"]["religion"="christian"]',
        'shop': '["shop"]',
        'all': ''
    }
    
    filter_query = category_map.get(category, '')
    
    try:
        # Overpass API query
        overpass_url = "https://overpass-api.de/api/interpreter"
        query = f"""
        [out:json];
        (
          node{filter_query}(around:{radius},{lat},{lng});
          way{filter_query}(around:{radius},{lat},{lng});
        );
        out center;
        """
        
        encoded_query = urllib.parse.quote(query)
        full_url = f"{overpass_url}?data={encoded_query}"
        
        headers = {'User-Agent': 'RouteLink/1.0'}
        req = urllib.request.Request(full_url, headers=headers)
        
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            
            places = []
            for element in data.get('elements', []):
                if 'lat' in element:
                    lat_val = element['lat']
                    lng_val = element['lon']
                elif 'center' in element:
                    lat_val = element['center']['lat']
                    lng_val = element['center']['lon']
                else:
                    continue
                
                tags = element.get('tags', {})
                name = tags.get('name', 'Unnamed place')
                
                # Calculate distance
                distance = haversine_distance(lat, lng, lat_val, lng_val)
                
                places.append({
                    'name': name,
                    'category': category,
                    'lat': lat_val,
                    'lng': lng_val,
                    'distance': round(distance, 2),
                    'tags': tags
                })
            
            # Sort by distance
            places.sort(key=lambda x: x['distance'])
            
            return jsonify(places[:20])  # Return top 20 results
    
    except Exception as e:
        print(f"Nearby places error: {e}")
        return jsonify({'error': 'Failed to fetch nearby places'}), 500

# ==================== LOCATION SHARING ====================

@app.route('/share-location')
@login_required
def share_location():
    """
    Location sharing page for authenticated users.
    Uses Browser Geolocation API to track and share location.
    """
    user = get_user_by_id(session['user_id'])
    return render_template('share_location.html', user=user)

@app.route('/api/location/update', methods=['POST'])
@login_required
def api_location_update():
    """
    API endpoint to update user's current location.
    Called periodically by frontend (every 5-10 seconds).
    
    Expects JSON:
        {'latitude': float, 'longitude': float}
    """
    data = request.get_json()
    if not data or 'latitude' not in data or 'longitude' not in data:
        return jsonify({'error': 'Latitude and longitude required'}), 400
    
    success = save_location(session['user_id'], data['latitude'], data['longitude'])
    
    if success:
        # Emit real-time update via WebSocket
        socketio.emit('location_update', {
            'user_id': session['user_id'],
            'latitude': data['latitude'],
            'longitude': data['longitude']
        })
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'error': 'Failed to save location'}), 500

@app.route('/api/location/sharing-link', methods=['POST'])
@login_required
def api_create_sharing_link():
    """
    Creates a unique sharing link for location sharing.
    Link expires after 24 hours by default.
    """
    token = secrets.token_urlsafe(32)
    success, message = create_sharing_link(session['user_id'], token)
    
    if success:
        sharing_url = f"{APP_URL}/view-location/{token}"
        return jsonify({'status': 'ok', 'url': sharing_url, 'token': token})
    else:
        return jsonify({'error': message}), 500

@app.route('/api/location/stop-sharing', methods=['POST'])
@login_required
def api_stop_sharing():
    """Deactivates all sharing links for the user"""
    success = deactivate_sharing_link(session['user_id'])
    return jsonify({'status': 'ok' if success else 'error'})

@app.route('/view-location/<token>')
def view_shared_location(token):
    """
    Public page to view a shared location.
    Only shows location if link is active and not expired.
    """
    link = get_sharing_link_by_token(token)
    
    if not link:
        flash('Invalid or expired sharing link.', 'danger')
        return redirect(url_for('index'))
    
    # Get latest location
    location = get_latest_location(link['user_id'])
    
    return render_template('view_location.html', 
                         link=link, 
                         location=location,
                         user=get_user_by_id(session.get('user_id')))

# ==================== DRIVER SYSTEM ====================

@app.route('/driver/dashboard')
@role_required(['driver'])
def driver_dashboard():
    """
    Driver dashboard - accessible only to driver role.
    Shows vehicle info, status controls, and journey management.
    """
    driver = get_driver_by_user_id(session['user_id'])
    return render_template('driver_dashboard.html', driver=driver)

@app.route('/driver/journeys')
@role_required(['driver'])
def driver_journeys():
    """Driver's journey history page"""
    driver = get_driver_by_user_id(session['user_id'])
    journeys = get_journeys_by_driver(driver['id']) if driver else []
    return render_template('driver_journeys.html', driver=driver, journeys=journeys)

@app.route('/api/driver/status', methods=['POST'])
@role_required(['driver'])
def api_update_driver_status():
    """
    Updates driver status (Offline, Online, On Journey, Emergency).
    Also updates current location if provided.
    """
    data = request.get_json()
    status = data.get('status')
    lat = data.get('latitude', type=float)
    lng = data.get('longitude', type=float)
    destination = data.get('destination', '')
    
    driver = get_driver_by_user_id(session['user_id'])
    if not driver:
        return jsonify({'error': 'Driver profile not found'}), 404
    
    success = update_driver_status(driver['id'], status, lat, lng, destination)
    
    if success:
        # Broadcast update to business owners via WebSocket
        socketio.emit('driver_status_update', {
            'driver_id': driver['id'],
            'status': status,
            'lat': lat,
            'lng': lng
        })
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'error': 'Failed to update status'}), 500

@app.route('/api/driver/journey/start', methods=['POST'])
@role_required(['driver'])
def api_start_journey():
    """
    Starts a new journey for the driver.
    Records start location, destination, route, and estimated distance/duration.
    """
    data = request.get_json()
    
    driver = get_driver_by_user_id(session['user_id'])
    if not driver:
        return jsonify({'error': 'Driver profile not found'}), 404
    
    start_lat = data.get('start_lat', type=float)
    start_lng = data.get('start_lng', type=float)
    dest_lat = data.get('dest_lat', type=float)
    dest_lng = data.get('dest_lng', type=float)
    route_data = json.dumps(data.get('route', {}))
    distance = data.get('distance', type=float)
    duration = data.get('duration', type=float)
    
    success, message, journey_id = create_journey(
        driver['id'], start_lat, start_lng, dest_lat, dest_lng,
        route_data, distance, duration
    )
    
    if success:
        # Update driver status
        update_driver_status(driver['id'], 'On Journey', start_lat, start_lng, data.get('destination', ''))
        
        return jsonify({'status': 'ok', 'journey_id': journey_id})
    else:
        return jsonify({'error': message}), 500

@app.route('/api/driver/journey/complete/<int:journey_id>', methods=['POST'])
@role_required(['driver'])
def api_complete_journey(journey_id):
    """Marks a journey as completed"""
    driver = get_driver_by_user_id(session['user_id'])
    if not driver:
        return jsonify({'error': 'Driver profile not found'}), 404
    
    success = complete_journey(journey_id)
    
    if success:
        # Update driver status to Online
        update_driver_status(driver['id'], 'Online')
        return jsonify({'status': 'ok'})
    else:
        return jsonify({'error': 'Failed to complete journey'}), 500

@app.route('/drivers/nearby')
@login_required
def drivers_nearby():
    """
    Shows nearby online drivers for logged-in users.
    Uses Haversine formula for distance calculation.
    """
    user = get_user_by_id(session['user_id'])
    
    # Get user's current location (most recent)
    location = get_latest_location(session['user_id'])
    
    nearby_drivers = []
    if location:
        # Get current user's driver ID if they are a driver
        exclude_id = None
        if user['role'] == 'driver':
            driver_profile = get_driver_by_user_id(session['user_id'])
            exclude_id = driver_profile['id'] if driver_profile else None
        
        nearby_drivers = get_online_drivers_nearby(
            location['latitude'], 
            location['longitude'],
            radius_km=10,
            exclude_driver_id=exclude_id
        )
    
    return render_template('nearby_drivers.html', 
                         user=user, 
                         nearby_drivers=nearby_drivers,
                         current_location=location)

# ==================== EMERGENCY ALERTS ====================

@app.route('/emergency')
def emergency_dashboard():
    """
    Emergency alerts dashboard showing active emergencies.
    Accessible to all authenticated users.
    """
    user = get_user_by_id(session.get('user_id')) if 'user_id' in session else None
    emergencies = get_active_emergencies()
    return render_template('emergency_dashboard.html', 
                         user=user, 
                         emergencies=emergencies)

@app.route('/api/emergency/alert', methods=['POST'])
@login_required
def api_create_emergency():
    """
    Creates an emergency alert.
    Can include AI-suggested category and priority.
    """
    data = request.get_json()
    lat = data.get('latitude', type=float)
    lng = data.get('longitude', type=float)
    message = data.get('message', '')
    category = data.get('category', 'Other')
    priority = data.get('priority', 'MEDIUM')
    ai_suggested = data.get('ai_suggested', False)
    
    if not lat or not lng:
        # Try to get from latest location
        location = get_latest_location(session['user_id'])
        if location:
            lat = location['latitude']
            lng = location['longitude']
        else:
            return jsonify({'error': 'Location required'}), 400
    
    success, msg, alert_id = create_emergency_alert(
        session['user_id'], lat, lng, message, category, priority, ai_suggested
    )
    
    if success:
        # Broadcast to business owners
        socketio.emit('emergency_alert', {
            'alert_id': alert_id,
            'lat': lat,
            'lng': lng,
            'message': message,
            'priority': priority
        })
        return jsonify({'status': 'ok', 'alert_id': alert_id})
    else:
        return jsonify({'error': msg}), 500

@app.route('/api/emergency/<int:alert_id>/resolve', methods=['POST'])
@login_required
def api_resolve_emergency(alert_id):
    """Resolves an emergency alert (for authorized users)"""
    success = update_emergency_status(alert_id, 'resolved')
    return jsonify({'status': 'ok' if success else 'error'})

# ==================== BUSINESS OWNER SYSTEM ====================

@app.route('/business/dashboard')
@role_required(['business_owner'])
def business_dashboard():
    """
    Business owner dashboard.
    Shows company stats, live driver map, and quick actions.
    Critical: Only shows data for the owner's own company.
    """
    company = get_company_by_owner(session['user_id'])
    
    if not company:
        flash('Company not found. Please contact support.', 'danger')
        return redirect(url_for('index'))
    
    stats = get_company_stats(company['id'])
    drivers = get_drivers_by_company(company['id'])
    
    return render_template('business_dashboard.html',
                         company=company,
                         stats=stats,
                         drivers=drivers)

@app.route('/business/drivers')
@role_required(['business_owner'])
def business_drivers():
    """
    Manage company drivers.
    Add, view, activate, deactivate drivers.
    Company isolation enforced.
    """
    company = get_company_by_owner(session['user_id'])
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('index'))
    
    drivers = get_drivers_by_company(company['id'])
    return render_template('business_drivers.html', company=company, drivers=drivers)

@app.route('/business/reports')
@role_required(['business_owner'])
def business_reports():
    """
    Business reports with filtering.
    Shows driver performance scores and journey statistics.
    Uses documented formula: 50% on-time + 30% completed + 20% efficiency.
    """
    company = get_company_by_owner(session['user_id'])
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('index'))
    
    # Get filter parameters
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    driver_id = request.args.get('driver_id', type=int)
    
    # Get journeys with filters
    journeys = get_journeys_by_company(company['id'], start_date, end_date, driver_id)
    
    # Get driver performance stats
    drivers = get_drivers_by_company(company['id'])
    driver_stats = []
    for driver in drivers:
        stats = get_driver_performance_stats(driver['id'], company['id'])
        stats['driver_name'] = driver['name']
        stats['vehicle_number'] = driver['vehicle_number']
        driver_stats.append(stats)
    
    return render_template('business_reports.html',
                         company=company,
                         drivers=drivers,
                         driver_stats=driver_stats,
                         journeys=journeys,
                         start_date=start_date,
                         end_date=end_date,
                         selected_driver_id=driver_id)

@app.route('/business/ai-assistant')
@role_required(['business_owner'])
def business_ai_assistant():
    """
    AI-powered business assistant.
    Allows business owners to ask questions about their company data.
    AI interprets verified data - does NOT invent statistics.
    """
    company = get_company_by_owner(session['user_id'])
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('index'))
    
    stats = get_company_stats(company['id'])
    drivers = get_drivers_by_company(company['id'])
    
    return render_template('business_ai.html',
                         company=company,
                         stats=stats,
                         drivers=drivers)

@app.route('/api/business/add-driver', methods=['POST'])
@role_required(['business_owner'])
def api_add_driver():
    """
    Adds a new driver to the company.
    Creates user account and driver profile.
    """
    company = get_company_by_owner(session['user_id'])
    if not company:
        return jsonify({'error': 'Company not found'}), 404
    
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    vehicle_number = data.get('vehicle_number', '').strip()
    
    if not name or not email or not vehicle_number:
        return jsonify({'error': 'All fields required'}), 400
    
    # Check if email exists
    existing_user = get_user_by_email(email)
    if existing_user:
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create temporary password
    temp_password = secrets.token_urlsafe(8)
    password_hash = generate_password_hash(temp_password)
    
    # Create user with driver role
    success, message, user_id = create_user(name, email, password_hash, 'driver')
    
    if not success:
        return jsonify({'error': message}), 500
    
    # Create driver profile
    success, message, driver_id = create_driver(user_id, company['id'], vehicle_number)
    
    if success:
        return jsonify({'status': 'ok', 'message': f'Driver added. Temporary password: {temp_password}'})
    else:
        return jsonify({'error': message}), 500

@app.route('/api/ai/chat', methods=['POST'])
@login_required
def api_ai_chat():
    """
    General AI chat endpoint.
    Used by both travel assistant and business assistant.
    All AI communication is server-side to protect API key.
    """
    if not AI_API_KEY:
        return jsonify({'error': 'AI not configured', 'response': 'AI assistant is not available. Please configure AI_API_KEY in environment variables.'}), 500
    
    data = request.get_json()
    messages = data.get('messages', [])
    context_type = data.get('context_type', 'general')
    context_data = data.get('context_data', {})
    
    # Build system prompt based on context
    if context_type == 'travel':
        system_prompt = """You are RouteLink Travel Assistant, a helpful AI that provides route planning advice.
IMPORTANT RULES:
- Only use the route data provided to you - do NOT invent distances, times, or locations.
- If data is missing, say so clearly.
- Distinguish between "Shortest route" (based on distance) and "AI recommended route" (considering other factors).
- Be concise and practical.
- Never claim to guarantee safety or replace emergency services."""
        
        # Add route context to messages
        if context_data:
            route_info = f"Route Context: Start={context_data.get('start', 'N/A')}, Destination={context_data.get('destination', 'N/A')}, Stops={context_data.get('stops', [])}, Total Distance={context_data.get('distance', 'N/A')} km, Duration={context_data.get('duration', 'N/A')} min"
            messages.insert(0, {'role': 'system', 'content': route_info})
    
    elif context_type == 'business':
        system_prompt = """You are RouteLink Business Assistant, helping business owners understand their company data.
IMPORTANT RULES:
- Only interpret the verified statistics provided - do NOT invent numbers.
- If asked about data not provided, say you don't have that information.
- Do NOT make financial or HR decisions - only provide insights.
- Always suggest viewing underlying data for transparency.
- Be professional and concise."""
        
        # Add company stats context
        if context_data:
            stats_info = f"Company Stats: Total Drivers={context_data.get('total_drivers', 0)}, Online={context_data.get('online_drivers', 0)}, Total Journeys={context_data.get('total_journeys', 0)}, Completed={context_data.get('completed_journeys', 0)}"
            messages.insert(0, {'role': 'system', 'content': stats_info})
    
    elif context_type == 'emergency':
        system_prompt = """You are RouteLink Emergency Support AI.
IMPORTANT RULES:
- Classify emergencies into: Road Accident, Vehicle Breakdown, Medical Concern, Unsafe Situation, Road Obstruction, Lost/Stranded, Other.
- Suggest priority: CRITICAL (life-threatening), HIGH (urgent), MEDIUM (important), LOW (minor).
- NEVER make medical diagnoses.
- NEVER claim to guarantee safety.
- ALWAYS recommend contacting emergency services for serious situations.
- Be calm and supportive."""
    
    else:
        system_prompt = "You are RouteLink Assistant, a helpful AI for route planning and travel assistance."
    
    response = call_ai_api(messages, system_prompt)
    
    if response:
        return jsonify({'response': response})
    else:
        return jsonify({'error': 'AI service unavailable', 'response': 'AI assistant is currently unavailable. Please try again later.'}), 500

@app.route('/api/ai/classify-emergency', methods=['POST'])
@login_required
def api_classify_emergency():
    """
    AI-powered emergency classification.
    Analyzes user message and suggests category and priority.
    User can override AI suggestions.
    """
    if not AI_API_KEY:
        return jsonify({'error': 'AI not configured'}), 500
    
    data = request.get_json()
    message = data.get('message', '')
    
    if not message:
        return jsonify({'error': 'Message required'}), 400
    
    system_prompt = """You are RouteLink Emergency Support AI.
Analyze the emergency message and classify it.

Respond ONLY with valid JSON in this exact format:
{
    "category": "Road Accident" | "Vehicle Breakdown" | "Medical Concern" | "Unsafe Situation" | "Road Obstruction" | "Lost/Stranded" | "Other",
    "priority": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
    "reasoning": "Brief explanation"
}

IMPORTANT:
- NEVER make medical diagnoses.
- NEVER claim to guarantee safety.
- For life-threatening situations, suggest CRITICAL priority.
- Be conservative - when in doubt, suggest higher priority."""

    messages = [{'role': 'user', 'content': f"Classify this emergency: {message}"}]
    response = call_ai_api(messages, system_prompt)
    
    if response:
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result['ai_suggested'] = True
                return jsonify(result)
        except:
            pass
    
    return jsonify({'error': 'Could not classify emergency'}), 500

@app.route('/reports/download/csv')
@role_required(['business_owner'])
def download_reports_csv():
    """
    Downloads journey reports as CSV file.
    Uses Python's built-in csv module.
    """
    company = get_company_by_owner(session['user_id'])
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('index'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    journeys = get_journeys_by_company(company['id'], start_date, end_date)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow(['Journey ID', 'Driver', 'Vehicle', 'Start Time', 'End Time', 
                    'Start Lat', 'Start Lng', 'Dest Lat', 'Dest Lng',
                    'Distance (km)', 'Duration (min)', 'Status'])
    
    # Data rows
    for journey in journeys:
        writer.writerow([
            journey['id'],
            journey.get('driver_name', 'N/A'),
            journey.get('vehicle_number', 'N/A'),
            journey['start_time'],
            journey.get('end_time', 'Ongoing'),
            journey['start_lat'],
            journey['start_lng'],
            journey['dest_lat'],
            journey['dest_lng'],
            journey.get('distance', 'N/A'),
            journey.get('duration', 'N/A'),
            journey['status']
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=journey_report.csv'
    response.headers['Content-type'] = 'text/csv'
    
    return response

# ==================== NEARBY PLACES ====================

@app.route('/nearby-places')
def nearby_places():
    """
    Nearby places search page.
    Categories: Fuel, Banks, Churches, Museums, Libraries, Restaurants, Cafés, Hospitals, Hotels, Parking, Shops, Pharmacies, Tourist Attractions.
    Uses OpenStreetMap data via Overpass API.
    """
    user = get_user_by_id(session.get('user_id')) if 'user_id' in session else None
    return render_template('nearby_places.html', user=user)

# ==================== PWA SUPPORT ====================

@app.route('/manifest.json')
def manifest():
    """
    PWA manifest file.
    Makes the app installable on mobile devices.
    """
    manifest_data = {
        'name': 'RouteLink',
        'short_name': 'RouteLink',
        'description': 'Plan Your Route. Track Your Journey. Stay Connected.',
        'start_url': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#2563eb',
        'icons': [
            {
                'src': '/static/icons/icon-192.png',
                'sizes': '192x192',
                'type': 'image/png'
            },
            {
                'src': '/static/icons/icon-512.png',
                'sizes': '512x512',
                'type': 'image/png'
            }
        ]
    }
    return jsonify(manifest_data)

@app.route('/service-worker.js')
def service_worker():
    """
    Service worker for PWA offline support.
    Caches static assets for offline use.
    """
    return send_from_directory('.', 'service-worker.js', mimetype='application/javascript')

@app.route('/download')
def download_page():
    """
    Download page with QR code for PWA installation.
    Generates QR code linking to APP_URL.
    """
    import qrcode
    from PIL import Image
    
    # Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(APP_URL)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img_path = os.path.join(app.instance_path, 'qrcode.png')
    img.save(img_path)
    
    return render_template('download.html', app_url=APP_URL)

@app.route('/qr-code.png')
def serve_qr_code():
    """Serves the generated QR code image"""
    return send_from_directory(app.instance_path, 'qrcode.png', mimetype='image/png')

# ==================== WEBSOCKET EVENTS ====================

@socketio.on('connect')
def handle_connect():
    """Called when a client connects via WebSocket"""
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    """Called when a client disconnects"""
    print(f'Client disconnected: {request.sid}')

@socketio.on('request_location_update')
def handle_location_request(data):
    """
    Handles requests for location updates.
    Used by business dashboard to get live driver locations.
    """
    # Emit current driver locations to requester
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user and user['role'] == 'business_owner':
            company = get_company_by_owner(session['user_id'])
            if company:
                drivers = get_drivers_by_company(company['id'])
                driver_locations = []
                for driver in drivers:
                    if driver['current_lat'] and driver['current_lng']:
                        driver_locations.append({
                            'driver_id': driver['id'],
                            'name': driver['name'],
                            'vehicle': driver['vehicle_number'],
                            'status': driver['status'],
                            'lat': driver['current_lat'],
                            'lng': driver['current_lng'],
                            'destination': driver.get('destination', '')
                        })
                
                emit('driver_locations', {'drivers': driver_locations})

# ==================== DATABASE INITIALIZATION ====================

def setup_database():
    """Initializes database and creates admin user if needed"""
    init_db()
    
    # Create instance directory if it doesn't exist
    os.makedirs(app.instance_path, exist_ok=True)

# ==================== MAIN ENTRY POINT ====================

if __name__ == '__main__':
    setup_database()
    # Run with debug mode for development
    # For production, use: socketio.run(app, host='0.0.0.0', port=5000)
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
