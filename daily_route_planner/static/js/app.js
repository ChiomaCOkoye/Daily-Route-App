/**
 * Daily Route Planner - Main Application JavaScript
 * 
 * Handles all client-side functionality including:
 * - Map initialization and route visualization
 * - Stop management (add/remove)
 * - API communication for optimization
 * - Real-time WebSocket updates
 * - Export functionality
 * - User authentication
 * - PWA features
 * 
 * Author: Chioma Okoye
 * Year: 2026
 */

// ============================================================================
// GLOBAL STATE MANAGEMENT
// WHY: Centralized state for predictable data flow
// ============================================================================

let currentUser = null;
let stops = [];
let optimizedRoute = null;
let map = null;
let trackingMap = null;
let markers = [];
let routeLayer = null;
let poiMarkers = [];

// POI category icons mapping
const POI_ICONS = {
    hotel: '🏨',
    fuel: '⛽',
    restaurant: '🍽️',
    gym: '💪',
    museum: '🏛️',
    hospital: '🏥',
    parking: '🅿️',
    rest_area: '🛑'
};

// ============================================================================
// MAP INITIALIZATION
// WHY: Set up Leaflet map with proper configuration
// COMPLEXITY: O(1) - Single initialization
// ============================================================================

/**
 * Initialize the main route planning map
 * @returns {L.Map} Leaflet map instance
 */
function initMap() {
    // Default to Ireland (Dublin) coordinates - works globally for any country
    // User can pan/zoom to their location or input custom coordinates
    const defaultLat = 53.3498;  // Dublin latitude
    const defaultLon = -6.2603;  // Dublin longitude
    
    // Create map centered on Ireland by default (can be changed to user's location)
    map = L.map('map').setView([defaultLat, defaultLon], 7);
    
    // Add OpenStreetMap tiles (free, no API key required - works worldwide)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    return map;
}

/**
 * Initialize the tracking map for live driver locations
 * @returns {L.Map} Leaflet map instance
 */
function initTrackingMap() {
    // Default to Ireland (Dublin) coordinates - works globally for any country
    const defaultLat = 53.3498;  // Dublin latitude
    const defaultLon = -6.2603;  // Dublin longitude
    
    trackingMap = L.map('tracking-map').setView([defaultLat, defaultLon], 7);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(trackingMap);
    
    return trackingMap;
}

// ============================================================================
// STOP MANAGEMENT
// WHY: Handle user input for route stops
// COMPLEXITY: O(n) for rendering list
// ============================================================================

/**
 * Add a new stop to the route
 * WHY: Core functionality for building multi-stop routes
 * COMPLEXITY: O(n) where n is number of stops (for re-rendering)
 */
function addStop() {
    const name = document.getElementById('stop-name').value.trim();
    const lat = parseFloat(document.getElementById('stop-lat').value);
    const lon = parseFloat(document.getElementById('stop-lon').value);
    
    // Validate inputs
    if (!name || isNaN(lat) || isNaN(lon)) {
        alert('Please enter valid stop details');
        return;
    }
    
    // Validate coordinate ranges
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
        alert('Invalid coordinates. Latitude: -90 to 90, Longitude: -180 to 180');
        return;
    }
    
    // Add stop to array
    stops.push({ name, latitude: lat, longitude: lon });
    
    // Clear input fields
    document.getElementById('stop-name').value = '';
    document.getElementById('stop-lat').value = '';
    document.getElementById('stop-lon').value = '';
    
    // Update UI
    renderStopsList();
    updateMapMarkers();
}

/**
 * Add a quick location preset
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @param {string} name - Location name
 */
function addQuickLocation(lat, lon, name) {
    stops.push({ name, latitude: lat, longitude: lon });
    renderStopsList();
    updateMapMarkers();
}

/**
 * Remove a stop from the list
 * @param {number} index - Index of stop to remove
 */
function removeStop(index) {
    stops.splice(index, 1);
    renderStopsList();
    updateMapMarkers();
}

/**
 * Clear all stops
 */
function clearStops() {
    stops = [];
    renderStopsList();
    updateMapMarkers();
    document.getElementById('results-panel').style.display = 'none';
}

/**
 * Render the stops list in the UI
 * WHY: Visual feedback for user's added stops
 * COMPLEXITY: O(n) where n is number of stops
 */
function renderStopsList() {
    const ul = document.getElementById('stops-ul');
    const count = document.getElementById('stop-count');
    
    count.textContent = stops.length;
    
    if (stops.length === 0) {
        ul.innerHTML = '<li style="color: #999;">No stops added yet</li>';
        return;
    }
    
    ul.innerHTML = stops.map((stop, index) => `
        <li>
            <span><strong>${index + 1}.</strong> ${stop.name}</span>
            <span class="remove-stop" onclick="removeStop(${index})">&times;</span>
        </li>
    `).join('');
}

/**
 * Update map markers to show current stops
 * WHY: Visual representation of route on map
 * COMPLEXITY: O(n) where n is number of stops
 */
function updateMapMarkers() {
    // Remove existing markers
    markers.forEach(marker => marker.remove());
    markers = [];
    
    // Add new markers for each stop
    stops.forEach((stop, index) => {
        const marker = L.marker([stop.latitude, stop.longitude])
            .addTo(map)
            .bindPopup(`<strong>${index + 1}. ${stop.name}</strong>`);
        
        markers.push(marker);
    });
    
    // Fit map to show all markers
    if (markers.length > 0) {
        const group = new L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

// ============================================================================
// ROUTE OPTIMIZATION
// WHY: Call backend API to optimize route using Nearest Neighbor
// COMPLEXITY: O(n²) on server side
// ============================================================================

/**
 * Send stops to backend for optimization
 * WHY: Core feature - finds shortest route through multiple stops
 * COMPLEXITY: O(n²) from Nearest Neighbor algorithm on server
 */
async function optimizeRoute() {
    if (stops.length < 2) {
        alert('Please add at least 2 stops');
        return;
    }
    
    try {
        // Show loading state
        const optimizeBtn = event.target;
        optimizeBtn.disabled = true;
        optimizeBtn.textContent = 'Optimizing...';
        
        // Call API endpoint
        const response = await fetch('/api/optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stops })
        });
        
        if (!response.ok) throw new Error('Optimization failed');
        
        const data = await response.json();
        optimizedRoute = data.route;
        
        // Display results
        displayOptimizationResults(data);
        
        // Draw optimized route on map
        drawOptimizedRoute(data.route.optimized_order);
        
        // Load nearby POIs
        loadPOIs('all');
        
    } catch (error) {
        console.error('Optimization error:', error);
        alert('Failed to optimize route. Please try again.');
    } finally {
        optimizeBtn.disabled = false;
        optimizeBtn.textContent = '🚀 Optimize Route';
    }
}

/**
 * Display optimization statistics in the UI with detailed segments table
 * @param {Object} data - Optimization result data containing route and predictions
 * WHY: Show comprehensive route information including before/after comparison
 *      and detailed segment-by-segment breakdown
 * COMPLEXITY: O(n) where n is number of segments
 */
function displayOptimizationResults(data) {
    const panel = document.getElementById('results-panel');
    panel.style.display = 'block';
    
    // Update comparison box (before/after)
    document.getElementById('original-distance').textContent = 
        `${data.route.original_distance} km`;
    document.getElementById('optimized-distance').textContent = 
        `${data.route.total_distance} km`;
    
    // Update stats cards
    document.getElementById('total-distance').textContent = 
        `${data.route.total_distance} km`;
    document.getElementById('total-duration').textContent = 
        `${data.route.total_duration} min`;
    document.getElementById('distance-saved').textContent = 
        `${data.route.distance_saved} km`;
    document.getElementById('improvement').textContent = 
        `${data.route.improvement_percent}%`;
    
    // Update AI predictions
    document.getElementById('ai-duration').textContent = 
        `${data.predictions.predicted_duration} min`;
    
    // Best departure times
    const bestTimesUl = document.getElementById('best-times');
    bestTimesUl.innerHTML = data.predictions.best_departure_times
        .map(t => `<li>🕐 ${t.display_time} (${t.predicted_duration} min)</li>`)
        .join('');
    
    // Fuel consumption
    document.getElementById('fuel-car').textContent = 
        data.predictions.fuel_consumption.car;
    document.getElementById('fuel-van').textContent = 
        data.predictions.fuel_consumption.van;
    document.getElementById('fuel-truck').textContent = 
        data.predictions.fuel_consumption.truck;
    
    // Populate detailed segments table
    populateSegmentsTable(data.route.segments, data.route.total_distance, data.route.total_duration);
    
    // Scroll to results
    panel.scrollIntoView({ behavior: 'smooth' });
}

/**
 * Populate the detailed route segments table
 * @param {Array} segments - Array of segment objects with from, to, distance
 * @param {number} totalDistance - Total route distance for footer
 * @param {number} totalDuration - Total route duration for footer
 * WHY: Users need to see each individual segment for planning purposes
 * COMPLEXITY: O(n) where n is number of segments
 */
function populateSegmentsTable(segments, totalDistance, totalDuration) {
    const tbody = document.getElementById('segments-tbody');
    const totalDistCell = document.getElementById('total-segments-distance');
    const totalTimeCell = document.getElementById('total-segments-time');
    
    if (!segments || segments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No segments available</td></tr>';
        totalDistCell.textContent = '-';
        totalTimeCell.textContent = '-';
        return;
    }
    
    // Build table rows for each segment
    tbody.innerHTML = segments.map((seg, index) => {
        // Calculate estimated time for this segment: distance / 50 km/h * 60 + 15 min buffer
        const estTime = Math.round((seg.distance / 50) * 60 + 15);
        return `
            <tr>
                <td>${index + 1}</td>
                <td>${seg.from}</td>
                <td>${seg.to}</td>
                <td><strong>${seg.distance.toFixed(2)}</strong></td>
                <td>⏱️ ${estTime} min</td>
            </tr>
        `;
    }).join('');
    
    // Update footer totals
    totalDistCell.textContent = `${totalDistance.toFixed(2)} km`;
    totalTimeCell.textContent = `${Math.round(totalDuration)} min`;
}

/**
 * Draw the optimized route polyline on map with distance and time labels
 * @param {Array} optimizedOrder - Array of stops in optimized order with segments
 * WHY: Visual feedback showing exact distance and estimated time between each stop
 * COMPLEXITY: O(n) where n is number of stops
 */
function drawOptimizedRoute(optimizedOrder) {
    // Remove existing route
    if (routeLayer) map.removeLayer(routeLayer);
    
    // Create array of coordinates for polyline
    const routeCoords = optimizedOrder.map(stop => [stop.latitude, stop.longitude]);
    
    // Draw polyline
    routeLayer = L.polyline(routeCoords, {
        color: '#4A90D9',
        weight: 4,
        opacity: 0.8,
        dashArray: '10, 10'
    }).addTo(map);
    
    // Add detailed labels to each segment showing distance and estimated time
    // WHY: Users need to see both distance AND time for planning purposes
    optimizedOrder.forEach((stop, index) => {
        if (index < optimizedOrder.length - 1) {
            const nextStop = optimizedOrder[index + 1];
            const midLat = (stop.latitude + nextStop.latitude) / 2;
            const midLon = (stop.longitude + nextStop.longitude) / 2;
            
            // Calculate segment distance using Haversine (same as backend)
            const segmentDistance = calculateHaversine(
                stop.latitude, stop.longitude,
                nextStop.latitude, nextStop.longitude
            );
            
            // Estimate time: distance / 50 km/h * 60 min + 15 min buffer per stop
            const segmentTime = Math.round((segmentDistance / 50) * 60 + 15);
            
            // Create informative label with both distance and time
            L.marker([midLat, midLon], {
                icon: L.divIcon({
                    className: 'distance-label',
                    html: `<div style="background: #4A90D9; color: white; padding: 4px 8px; border-radius: 6px; font-size: 11px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.3); text-align: center;">
                        <strong>${stop.name} → ${nextStop.name}</strong><br>
                        📏 ${segmentDistance.toFixed(1)} km | ⏱️ ${segmentTime} min
                    </div>`,
                    iconSize: [180, 50],
                    iconAnchor: [90, 25]
                })
            }).addTo(map);
        }
    });
    
    // Fit map to show entire route
    map.fitBounds(routeLayer.getBounds().pad(0.1));
}

/**
 * Calculate Haversine distance between two coordinates (client-side)
 * @param {number} lat1 - Latitude of point 1
 * @param {number} lon1 - Longitude of point 1
 * @param {number} lat2 - Latitude of point 2
 * @param {number} lon2 - Longitude of point 2
 * @returns {number} Distance in kilometers
 * WHY: Needed for displaying segment distances on map without server call
 * COMPLEXITY: O(1) - Fixed mathematical operations
 */
function calculateHaversine(lat1, lon1, lat2, lon2) {
    const R = 6371; // Earth's radius in km
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

/**
 * Convert degrees to radians
 * @param {number} deg - Degrees
 * @returns {number} Radians
 */
function toRad(deg) {
    return deg * (Math.PI / 180);
}

// ============================================================================
// POINTS OF INTEREST
// WHY: Find amenities along the route
// COMPLEXITY: O(n) where n is number of POIs
// ============================================================================

/**
 * Load points of interest near the route center
 * @param {string} category - POI category filter
 */
async function loadPOIs(category) {
    if (!optimizedRoute) return;
    
    // Get center of route
    const coords = optimizedRoute.optimized_order;
    const centerLat = coords.reduce((sum, s) => sum + s.latitude, 0) / coords.length;
    const centerLon = coords.reduce((sum, s) => sum + s.longitude, 0) / coords.length;
    
    try {
        const url = category === 'all' 
            ? `/api/pois?latitude=${centerLat}&longitude=${centerLon}&radius=5`
            : `/api/pois?latitude=${centerLat}&longitude=${centerLon}&radius=5&category=${category}`;
        
        const response = await fetch(url);
        if (!response.ok) throw new Error('Failed to load POIs');
        
        const pois = await response.json();
        displayPOIs(pois);
        
    } catch (error) {
        console.error('POI error:', error);
    }
}

/**
 * Display POIs in the results panel
 * @param {Array} pois - Array of POI objects
 */
function displayPOIs(pois) {
    const container = document.getElementById('poi-list');
    
    if (pois.length === 0) {
        container.innerHTML = '<p>No POIs found in this area</p>';
        return;
    }
    
    // Remove existing POI markers
    poiMarkers.forEach(m => m.remove());
    poiMarkers = [];
    
    container.innerHTML = pois.map(poi => `
        <div class="poi-item">
            <div class="poi-info">
                <h5>${POI_ICONS[poi.category] || '📍'} ${poi.name}</h5>
                <p>${poi.distance.toFixed(2)} km away • ⭐ ${poi.rating}</p>
            </div>
            <span class="poi-category">${poi.category}</span>
        </div>
    `).join('');
    
    // Add markers to map
    pois.forEach(poi => {
        const marker = L.marker([poi.lat, poi.lon])
            .addTo(map)
            .bindPopup(`
                <strong>${poi.name}</strong><br>
                Category: ${poi.category}<br>
                Distance: ${poi.distance.toFixed(2)} km<br>
                Rating: ⭐ ${poi.rating}
            `);
        
        poiMarkers.push(marker);
    });
}

// ============================================================================
// EXPORT FUNCTIONS
// WHY: Generate downloadable reports in various formats
// ============================================================================

/**
 * Export route report as PDF
 */
async function exportPDF() {
    if (!optimizedRoute) return;
    
    const reportData = {
        route: optimizedRoute,
        pois: [], // Could include current POI filter results
        predictions: getCurrentPredictions()
    };
    
    try {
        const response = await fetch('/api/export/pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reportData)
        });
        
        if (!response.ok) throw new Error('Export failed');
        
        // Trigger download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `route_report_${new Date().toISOString().slice(0,10)}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error('PDF export error:', error);
        alert('Failed to export PDF');
    }
}

/**
 * Export route report as Excel
 */
async function exportExcel() {
    if (!optimizedRoute) return;
    
    const reportData = {
        route: optimizedRoute,
        pois: [],
        history: []
    };
    
    try {
        const response = await fetch('/api/export/excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reportData)
        });
        
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `route_report_${new Date().toISOString().slice(0,10)}.xlsx`;
        a.click();
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error('Excel export error:', error);
    }
}

/**
 * Export route stops as CSV
 */
async function exportCSV() {
    if (!optimizedRoute) return;
    
    const reportData = { route: optimizedRoute };
    
    try {
        const response = await fetch('/api/export/csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reportData)
        });
        
        if (!response.ok) throw new Error('Export failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `route_stops_${new Date().toISOString().slice(0,10)}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error('CSV export error:', error);
    }
}

/**
 * Generate and download QR code for route sharing
 */
async function exportQR() {
    const routeUrl = window.location.href;
    
    try {
        const response = await fetch('/api/export/qr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: routeUrl })
        });
        
        if (!response.ok) throw new Error('QR generation failed');
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'route_qr_code.png';
        a.click();
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error('QR export error:', error);
    }
}

/**
 * Get current predictions from displayed values
 * @returns {Object} Current prediction data
 */
function getCurrentPredictions() {
    return {
        predicted_duration: document.getElementById('ai-duration').textContent,
        best_departure_times: [],
        fuel_consumption: {
            car: document.getElementById('fuel-car').textContent,
            van: document.getElementById('fuel-van').textContent,
            truck: document.getElementById('fuel-truck').textContent
        }
    };
}

// ============================================================================
// USER AUTHENTICATION
// WHY: Handle login, registration, and session management
// ============================================================================

/**
 * Show login modal
 */
function showLoginModal() {
    document.getElementById('login-modal').style.display = 'block';
}

/**
 * Show register modal
 */
function showRegisterModal() {
    document.getElementById('register-modal').style.display = 'block';
}

/**
 * Close modal by ID
 * @param {string} modalId - Modal element ID
 */
function closeModal(modalId) {
    document.getElementById(modalId).style.display = 'none';
}

/**
 * Handle login form submission
 * @param {Event} event - Form submit event
 */
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            updateUIForLoggedInUser();
            closeModal('login-modal');
            alert('Login successful!');
        } else {
            alert(data.error || 'Login failed');
        }
        
    } catch (error) {
        console.error('Login error:', error);
        alert('Login failed. Please try again.');
    }
}

/**
 * Handle registration form submission
 * @param {Event} event - Form submit event
 */
async function handleRegister(event) {
    event.preventDefault();
    
    const userData = {
        username: document.getElementById('reg-username').value,
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-password').value,
        user_type: document.getElementById('reg-type').value,
        business_name: document.getElementById('reg-business').value,
        vehicle_type: document.getElementById('reg-vehicle').value
    };
    
    try {
        const response = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert('Registration successful! Please login.');
            closeModal('register-modal');
            showLoginModal();
        } else {
            alert(data.error || 'Registration failed');
        }
        
    } catch (error) {
        console.error('Register error:', error);
        alert('Registration failed. Please try again.');
    }
}

/**
 * Logout current user
 */
async function logout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        currentUser = null;
        updateUIForLoggedOutUser();
        alert('Logged out successfully');
    } catch (error) {
        console.error('Logout error:', error);
    }
}

/**
 * Update UI when user logs in
 */
function updateUIForLoggedInUser() {
    document.getElementById('nav-auth').style.display = 'none';
    document.getElementById('nav-user').style.display = 'flex';
    document.getElementById('user-display').textContent = 
        `👤 ${currentUser.username}`;
    
    // Show role-specific links
    if (currentUser.user_type === 'business') {
        document.getElementById('tracking-link').style.display = 'inline';
        document.getElementById('reports-link').style.display = 'inline';
        loadDrivers();
    } else if (currentUser.user_type === 'driver') {
        document.getElementById('tracking-link').style.display = 'inline';
        startDriverTracking();
    }
    
    // Update profile section
    document.getElementById('profile-username').textContent = currentUser.username;
    document.getElementById('profile-type').textContent = currentUser.user_type;
    document.getElementById('profile-email').textContent = currentUser.email || 'Not provided';
    
    // Load saved locations
    loadSavedLocations();
}

/**
 * Update UI when user logs out
 */
function updateUIForLoggedOutUser() {
    document.getElementById('nav-auth').style.display = 'flex';
    document.getElementById('nav-user').style.display = 'none';
    document.getElementById('tracking-link').style.display = 'none';
    document.getElementById('reports-link').style.display = 'none';
}

// ============================================================================
// DRIVER TRACKING (WebSocket)
// WHY: Real-time location updates via WebSocket
// ============================================================================

let ws = null;

/**
 * Start driver location broadcasting (for drivers)
 */
function startDriverTracking() {
    if (!currentUser || currentUser.user_type !== 'driver') return;
    
    // Connect to WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/driver-location`);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        
        // Send location updates every 5 seconds
        setInterval(() => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(position => {
                    ws.send(JSON.stringify({
                        type: 'update',
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        speed: position.coords.speed || 0
                    }));
                });
            }
        }, 5000);
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Location update sent:', data);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

/**
 * Load and display all driver locations (for business owners)
 */
async function loadDrivers() {
    try {
        const response = await fetch('/api/drivers');
        if (!response.ok) throw new Error('Failed to load drivers');
        
        const drivers = await response.json();
        displayDrivers(drivers);
        
    } catch (error) {
        console.error('Load drivers error:', error);
    }
}

/**
 * Display drivers in the table
 * @param {Array} drivers - Array of driver objects
 */
function displayDrivers(drivers) {
    const tbody = document.getElementById('drivers-tbody');
    
    if (drivers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6">No drivers found</td></tr>';
        return;
    }
    
    tbody.innerHTML = drivers.map(driver => `
        <tr>
            <td>${driver.username}</td>
            <td>${driver.vehicle_type || 'N/A'}</td>
            <td>${driver.total_trips || 0}</td>
            <td>${driver.total_distance ? driver.total_distance.toFixed(1) + ' km' : '0 km'}</td>
            <td>⭐ ${driver.average_rating ? driver.average_rating.toFixed(1) : '5.0'}</td>
            <td>${driver.on_time_percentage ? driver.on_time_percentage.toFixed(0) + '%' : '100%'}</td>
        </tr>
    `).join('');
}

// ============================================================================
// SAVED LOCATIONS
// WHY: Personalize experience with favorite locations
// ============================================================================

/**
 * Load user's saved locations
 */
async function loadSavedLocations() {
    try {
        const response = await fetch('/api/locations');
        if (!response.ok) throw new Error('Failed to load locations');
        
        const locations = await response.json();
        displaySavedLocations(locations);
        
    } catch (error) {
        console.error('Load locations error:', error);
    }
}

/**
 * Display saved locations in profile
 * @param {Array} locations - Array of location objects
 */
function displaySavedLocations(locations) {
    const container = document.getElementById('saved-locations-list');
    
    if (locations.length === 0) {
        container.innerHTML = '<p>No saved locations yet</p>';
        return;
    }
    
    container.innerHTML = locations.map(loc => `
        <div class="poi-item">
            <div class="poi-info">
                <h5>📍 ${loc.name}</h5>
                <p>${loc.latitude.toFixed(4)}, ${loc.longitude.toFixed(4)}</p>
            </div>
            <button class="btn-small" onclick='addStopFromSaved(${JSON.stringify(loc)})'>Add to Route</button>
        </div>
    `).join('');
}

/**
 * Add a saved location to current route
 * @param {Object} loc - Location object
 */
function addStopFromSaved(loc) {
    stops.push({
        name: loc.name,
        latitude: loc.latitude,
        longitude: loc.longitude
    });
    renderStopsList();
    updateMapMarkers();
}

// ============================================================================
// NAVIGATION & SECTION MANAGEMENT
// WHY: Single-page application navigation
// ============================================================================

/**
 * Show a specific section and hide others
 * @param {string} sectionName - Name of section to show
 */
function showSection(sectionName) {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.classList.remove('active');
    });
    
    // Show target section
    const targetSection = document.getElementById(`${sectionName}-section`);
    if (targetSection) {
        targetSection.classList.add('active');
    }
    
    // Initialize maps when needed
    if (sectionName === 'planner' && !map) {
        setTimeout(() => initMap(), 100);
    }
    
    if (sectionName === 'tracking' && !trackingMap) {
        setTimeout(() => initTrackingMap(), 100);
    }
}

// ============================================================================
// INITIALIZATION
// WHY: Set up app when DOM is ready
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('Daily Route Planner initialized');
    console.log('Author: Chioma Okoye | Year: 2026');
    
    // Initialize map when planner section is first shown
    // Maps are lazy-loaded for performance
    
    // Check if user is already logged in (session persists)
    checkSession();
});

/**
 * Check if user has active session
 */
async function checkSession() {
    // Simple check - in production would verify with backend
    const navAuth = document.getElementById('nav-auth');
    if (navAuth.style.display === 'none') {
        // User appears to be logged in
        // Would need to fetch user data from session
    }
}

// Close modals when clicking outside
window.onclick = (event) => {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
    }
};
