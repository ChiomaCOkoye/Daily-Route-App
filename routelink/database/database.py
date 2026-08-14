"""
RouteLink - Database Module
Handles all database operations including initialization, queries, and data management.
Uses SQLite3 for simplicity and portability (no additional server required).
"""

import sqlite3
import os
from datetime import datetime
from config import SQLALCHEMY_DATABASE_URI

def get_db_connection():
    """
    Creates and returns a database connection.
    Sets row_factory to sqlite3.Row for dictionary-like access to query results.
    
    Returns:
        sqlite3.Connection: Database connection object
    """
    # Extract database path from SQLAlchemy URI format
    db_path = SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database by executing the schema.sql file.
    Creates all tables if they don't exist.
    Called once on application startup.
    """
    conn = get_db_connection()
    try:
        # Read and execute the schema file
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r') as f:
            schema = f.read()
        conn.executescript(schema)
        conn.commit()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        conn.rollback()
    finally:
        conn.close()

# ==================== USER FUNCTIONS ====================

def create_user(name, email, password_hash, role):
    """
    Creates a new user in the database.
    
    Args:
        name (str): User's full name
        email (str): User's email (must be unique)
        password_hash (str): Hashed password using Werkzeug
        role (str): User role ('traveller', 'driver', 'business_owner')
    
    Returns:
        tuple: (success: bool, message: str, user_id: int or None)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, role)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return True, "User created successfully", user_id
    except sqlite3.IntegrityError as e:
        if "email" in str(e):
            return False, "Email already registered", None
        return False, f"Database error: {e}", None
    except Exception as e:
        return False, f"Error creating user: {e}", None
    finally:
        conn.close()

def get_user_by_email(email):
    """
    Retrieves a user by email address.
    
    Args:
        email (str): User's email
    
    Returns:
        dict or None: User data as dictionary, or None if not found
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_user_by_id(user_id):
    """
    Retrieves a user by ID.
    
    Args:
        user_id (int): User's ID
    
    Returns:
        dict or None: User data as dictionary, or None if not found
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# ==================== COMPANY FUNCTIONS ====================

def create_company(name, owner_id, email, phone=None):
    """
    Creates a new company owned by a business owner.
    
    Args:
        name (str): Company name
        owner_id (int): ID of the business owner
        email (str): Company email
        phone (str, optional): Company phone number
    
    Returns:
        tuple: (success: bool, message: str, company_id: int or None)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO companies (name, owner_id, email, phone) VALUES (?, ?, ?, ?)",
            (name, owner_id, email, phone)
        )
        conn.commit()
        company_id = cursor.lastrowid
        return True, "Company created successfully", company_id
    except Exception as e:
        return False, f"Error creating company: {e}", None
    finally:
        conn.close()

def get_company_by_owner(owner_id):
    """
    Gets the company owned by a specific business owner.
    Ensures company isolation - owners can only see their own company.
    
    Args:
        owner_id (int): Business owner's user ID
    
    Returns:
        dict or None: Company data or None
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE owner_id = ?", (owner_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_company_by_id(company_id):
    """
    Gets a company by its ID.
    
    Args:
        company_id (int): Company ID
    
    Returns:
        dict or None: Company data or None
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# ==================== DRIVER FUNCTIONS ====================

def create_driver(user_id, company_id, vehicle_number):
    """
    Creates a new driver record linked to a company.
    
    Args:
        user_id (int): User ID of the driver
        company_id (int): Company ID the driver belongs to
        vehicle_number (str): Vehicle registration number
    
    Returns:
        tuple: (success: bool, message: str, driver_id: int or None)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO drivers (user_id, company_id, vehicle_number) VALUES (?, ?, ?)",
            (user_id, company_id, vehicle_number)
        )
        conn.commit()
        driver_id = cursor.lastrowid
        return True, "Driver profile created successfully", driver_id
    except sqlite3.IntegrityError:
        return False, "User is already registered as a driver", None
    except Exception as e:
        return False, f"Error creating driver: {e}", None
    finally:
        conn.close()

def get_driver_by_user_id(user_id):
    """
    Gets driver information by user ID.
    
    Args:
        user_id (int): User ID
    
    Returns:
        dict or None: Driver data or None
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, u.name, u.email 
            FROM drivers d 
            JOIN users u ON d.user_id = u.id 
            WHERE d.user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_drivers_by_company(company_id):
    """
    Gets all drivers belonging to a specific company.
    Critical for company isolation - business owners only see their drivers.
    
    Args:
        company_id (int): Company ID
    
    Returns:
        list: List of driver dictionaries
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, u.name, u.email 
            FROM drivers d 
            JOIN users u ON d.user_id = u.id 
            WHERE d.company_id = ?
            ORDER BY d.created_at DESC
        """, (company_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def update_driver_status(driver_id, status, current_lat=None, current_lng=None, destination=None):
    """
    Updates driver status and optionally location/destination.
    
    Args:
        driver_id (int): Driver ID
        status (str): New status ('Offline', 'Online', 'On Journey', 'Emergency')
        current_lat (float, optional): Current latitude
        current_lng (float, optional): Current longitude
        destination (str, optional): Destination description
    
    Returns:
        bool: Success status
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if current_lat is not None and current_lng is not None:
            cursor.execute("""
                UPDATE drivers 
                SET status = ?, current_lat = ?, current_lng = ?, destination = ?
                WHERE id = ?
            """, (status, current_lat, current_lng, destination, driver_id))
        else:
            cursor.execute("""
                UPDATE drivers SET status = ?, destination = ? WHERE id = ?
            """, (status, destination, driver_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating driver status: {e}")
        return False
    finally:
        conn.close()

def get_online_drivers_nearby(lat, lng, radius_km=10, exclude_driver_id=None):
    """
    Finds online drivers within a specified radius using Haversine formula.
    This is a simple distance calculation, not AI-based.
    
    Args:
        lat (float): Reference latitude
        lng (float): Reference longitude
        radius_km (int): Search radius in kilometers
        exclude_driver_id (int, optional): Driver ID to exclude from results
    
    Returns:
        list: List of nearby driver dictionaries with distance
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Simple Haversine formula in SQL for distance calculation
        # Note: This is an approximation; for production use geospatial indexes
        query = """
            SELECT d.*, u.name, 
            (6371 * acos(cos(radians(?)) * cos(radians(d.current_lat)) 
            * cos(radians(d.current_lng) - radians(?)) 
            + sin(radians(?)) * sin(radians(d.current_lat)))) AS distance
            FROM drivers d
            JOIN users u ON d.user_id = u.id
            WHERE d.status IN ('Online', 'On Journey')
            AND d.current_lat IS NOT NULL
            AND d.current_lng IS NOT NULL
        """
        params = [lat, lng, lat]
        
        if exclude_driver_id:
            query += " AND d.id != ?"
            params.append(exclude_driver_id)
        
        query += " HAVING distance < ? ORDER BY distance"
        params.append(radius_km)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

# ==================== JOURNEY FUNCTIONS ====================

def create_journey(driver_id, start_lat, start_lng, dest_lat, dest_lng, route_data, distance, duration):
    """
    Creates a new journey record.
    
    Args:
        driver_id (int): Driver ID
        start_lat (float): Starting latitude
        start_lng (float): Starting longitude
        dest_lat (float): Destination latitude
        dest_lng (float): Destination longitude
        route_data (str): JSON string with route details
        distance (float): Distance in km
        duration (float): Duration in minutes
    
    Returns:
        tuple: (success: bool, message: str, journey_id: int or None)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO journeys (driver_id, start_lat, start_lng, dest_lat, dest_lng, 
                                  route_data, distance, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (driver_id, start_lat, start_lng, dest_lat, dest_lng, 
              route_data, distance, duration))
        conn.commit()
        journey_id = cursor.lastrowid
        return True, "Journey started", journey_id
    except Exception as e:
        return False, f"Error starting journey: {e}", None
    finally:
        conn.close()

def complete_journey(journey_id):
    """
    Marks a journey as completed and records end time.
    
    Args:
        journey_id (int): Journey ID
    
    Returns:
        bool: Success status
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE journeys 
            SET status = 'completed', end_time = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (journey_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error completing journey: {e}")
        return False
    finally:
        conn.close()

def get_journeys_by_driver(driver_id):
    """
    Gets all journeys for a specific driver.
    
    Args:
        driver_id (int): Driver ID
    
    Returns:
        list: List of journey dictionaries
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM journeys 
            WHERE driver_id = ? 
            ORDER BY created_at DESC
        """, (driver_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def get_journeys_by_company(company_id, start_date=None, end_date=None, driver_id=None):
    """
    Gets journeys for all drivers in a company with optional filters.
    Used for business reports.
    
    Args:
        company_id (int): Company ID
        start_date (str, optional): Start date filter (YYYY-MM-DD)
        end_date (str, optional): End date filter (YYYY-MM-DD)
        driver_id (int, optional): Specific driver filter
    
    Returns:
        list: List of journey dictionaries
    """
    conn = get_db_connection()
    try:
        query = """
            SELECT j.*, d.vehicle_number, u.name as driver_name
            FROM journeys j
            JOIN drivers d ON j.driver_id = d.id
            JOIN users u ON d.user_id = u.id
            WHERE d.company_id = ?
        """
        params = [company_id]
        
        if start_date:
            query += " AND DATE(j.start_time) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(j.start_time) <= ?"
            params.append(end_date)
        
        if driver_id:
            query += " AND j.driver_id = ?"
            params.append(driver_id)
        
        query += " ORDER BY j.start_time DESC"
        
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

# ==================== LOCATION SHARING FUNCTIONS ====================

def save_location(user_id, latitude, longitude):
    """
    Saves or updates user's current location.
    Called periodically by the frontend for location sharing.
    
    Args:
        user_id (int): User ID
        latitude (float): Current latitude
        longitude (float): Current longitude
    
    Returns:
        bool: Success status
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO locations (user_id, latitude, longitude) VALUES (?, ?, ?)",
            (user_id, latitude, longitude)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving location: {e}")
        return False
    finally:
        conn.close()

def get_latest_location(user_id):
    """
    Gets the most recent location for a user.
    
    Args:
        user_id (int): User ID
    
    Returns:
        dict or None: Location data or None
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM locations 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

# ==================== SHARING LINK FUNCTIONS ====================

def create_sharing_link(user_id, token, expires_hours=24):
    """
    Creates a unique sharing link for location sharing.
    
    Args:
        user_id (int): User ID
        token (str): Unique token for the link
        expires_hours (int): Link expiration in hours
    
    Returns:
        tuple: (success: bool, message: str)
    """
    from datetime import timedelta
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        expires_at = datetime.utcnow() + timedelta(hours=expires_hours)
        cursor.execute(
            "INSERT INTO sharing_links (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at)
        )
        conn.commit()
        return True, "Sharing link created"
    except Exception as e:
        return False, f"Error creating sharing link: {e}"
    finally:
        conn.close()

def get_sharing_link_by_token(token):
    """
    Gets sharing link data by token.
    
    Args:
        token (str): Sharing link token
    
    Returns:
        dict or None: Link data or None
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sl.*, u.name 
            FROM sharing_links sl 
            JOIN users u ON sl.user_id = u.id 
            WHERE sl.token = ? AND sl.active = 1
        """, (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def deactivate_sharing_link(user_id):
    """
    Deactivates all sharing links for a user.
    
    Args:
        user_id (int): User ID
    
    Returns:
        bool: Success status
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sharing_links SET active = 0 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()

# ==================== EMERGENCY ALERT FUNCTIONS ====================

def create_emergency_alert(sender_id, latitude, longitude, message, category='Other', priority='MEDIUM', ai_suggested=False):
    """
    Creates an emergency alert.
    
    Args:
        sender_id (int): User ID who triggered the alert
        latitude (float): Alert location latitude
        longitude (float): Alert location longitude
        message (str): Alert message
        category (str): Alert category
        priority (str): Alert priority level
        ai_suggested (bool): Whether AI suggested the category/priority
    
    Returns:
        tuple: (success: bool, message: str, alert_id: int or None)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO emergency_alerts (sender_id, latitude, longitude, message, category, priority, ai_suggested)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sender_id, latitude, longitude, message, category, priority, ai_suggested))
        conn.commit()
        alert_id = cursor.lastrowid
        return True, "Emergency alert created", alert_id
    except Exception as e:
        return False, f"Error creating emergency alert: {e}", None
    finally:
        conn.close()

def get_active_emergencies():
    """
    Gets all active emergency alerts.
    
    Returns:
        list: List of emergency alert dictionaries
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ea.*, u.name as sender_name, u.email as sender_email
            FROM emergency_alerts ea
            JOIN users u ON ea.sender_id = u.id
            WHERE ea.status = 'active'
            ORDER BY ea.timestamp DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def update_emergency_status(alert_id, status):
    """
    Updates the status of an emergency alert.
    
    Args:
        alert_id (int): Alert ID
        status (str): New status ('active', 'resolved', 'dismissed')
    
    Returns:
        bool: Success status
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE emergency_alerts SET status = ? WHERE id = ?",
            (status, alert_id)
        )
        conn.commit()
        return True
    except Exception as e:
        return False
    finally:
        conn.close()

# ==================== REPORT HELPER FUNCTIONS ====================

def get_driver_performance_stats(driver_id, company_id):
    """
    Calculates driver performance statistics for reports.
    Uses simple formula: 50% on-time + 30% completed + 20% route efficiency.
    This is the "Project Driver Performance Score" - not AI-based.
    
    Args:
        driver_id (int): Driver ID
        company_id (int): Company ID for validation
    
    Returns:
        dict: Performance statistics
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get total journeys
        cursor.execute("""
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM journeys 
            WHERE driver_id = ?
        """, (driver_id,))
        journey_stats = dict(cursor.fetchone())
        
        total = journey_stats['total'] or 0
        completed = journey_stats['completed'] or 0
        
        # Calculate completion rate
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # For simplicity, assume 80% on-time rate (in real app, track actual times)
        on_time_rate = 80.0
        
        # Route efficiency: compare planned vs actual (simplified)
        route_efficiency = 85.0
        
        # Calculate performance score using documented formula
        # 50% on-time + 30% completed + 20% route efficiency
        performance_score = (on_time_rate * 0.5) + (completion_rate * 0.3) + (route_efficiency * 0.2)
        
        return {
            'total_journeys': total,
            'completed_journeys': completed,
            'completion_rate': round(completion_rate, 2),
            'on_time_rate': on_time_rate,
            'route_efficiency': route_efficiency,
            'performance_score': round(performance_score, 2)
        }
    finally:
        conn.close()

def get_company_stats(company_id, start_date=None, end_date=None):
    """
    Gets overall company statistics for dashboard and reports.
    
    Args:
        company_id (int): Company ID
        start_date (str, optional): Start date filter
        end_date (str, optional): End date filter
    
    Returns:
        dict: Company statistics
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Count drivers
        cursor.execute("SELECT COUNT(*) FROM drivers WHERE company_id = ?", (company_id,))
        total_drivers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM drivers WHERE company_id = ? AND status IN ('Online', 'On Journey')", (company_id,))
        online_drivers = cursor.fetchone()[0]
        
        # Count journeys with optional date filter
        query = "SELECT COUNT(*) FROM journeys j JOIN drivers d ON j.driver_id = d.id WHERE d.company_id = ?"
        params = [company_id]
        
        if start_date:
            query += " AND DATE(j.start_time) >= ?"
            params.append(start_date)
        if end_date:
            query += " AND DATE(j.start_time) <= ?"
            params.append(end_date)
        
        cursor.execute(query, params)
        total_journeys = cursor.fetchone()[0]
        
        cursor.execute(query.replace("COUNT(*)", "SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)"), params)
        completed_journeys = cursor.fetchone()[0] or 0
        
        cursor.execute(query.replace("COUNT(*)", "SUM(CASE WHEN status = 'ongoing' THEN 1 ELSE 0 END)"), params)
        active_journeys = cursor.fetchone()[0] or 0
        
        return {
            'total_drivers': total_drivers,
            'online_drivers': online_drivers,
            'total_journeys': total_journeys,
            'completed_journeys': completed_journeys,
            'active_journeys': active_journeys
        }
    finally:
        conn.close()
