/**
 * RouteLink - Main JavaScript
 * University Final Year Project
 * 
 * This file contains utility functions and common interactions.
 * Page-specific JavaScript is included in respective templates.
 */

// ==================== NAVIGATION TOGGLE ====================
/**
 * Mobile navigation toggle functionality
 * Shows/hides the navigation menu on small screens
 */
document.addEventListener('DOMContentLoaded', function() {
    const navToggle = document.getElementById('navToggle');
    const navMenu = document.getElementById('navMenu');
    
    if (navToggle && navMenu) {
        navToggle.addEventListener('click', function() {
            navMenu.classList.toggle('active');
        });
        
        // Close menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!navToggle.contains(e.target) && !navMenu.contains(e.target)) {
                navMenu.classList.remove('active');
            }
        });
    }
    
    // Auto-hide flash messages after 5 seconds
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            message.style.opacity = '0';
            message.style.transition = 'opacity 0.3s';
            setTimeout(() => message.remove(), 300);
        }, 5000);
    });
});

// ==================== GEOLOCATION UTILITIES ====================
/**
 * Gets the user's current location using Browser Geolocation API
 * Returns a Promise that resolves to {latitude, longitude} or rejects with error
 * 
 * @param {Object} options - Geolocation options
 * @returns {Promise<{latitude: number, longitude: number}>}
 */
function getCurrentLocation(options = {}) {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation is not supported by your browser'));
            return;
        }
        
        const defaultOptions = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        };
        
        navigator.geolocation.getCurrentPosition(
            (position) => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy: position.coords.accuracy
                });
            },
            (error) => {
                let errorMessage;
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMessage = 'Location access denied. Please enable location permissions.';
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errorMessage = 'Location information unavailable.';
                        break;
                    case error.TIMEOUT:
                        errorMessage = 'Location request timed out.';
                        break;
                    default:
                        errorMessage = 'An unknown error occurred.';
                }
                reject(new Error(errorMessage));
            },
            { ...defaultOptions, ...options }
        );
    });
}

/**
 * Watches user's location continuously
 * Calls callback function with each location update
 * 
 * @param {Function} callback - Function to call with location updates
 * @param {number} interval - Update interval in milliseconds (default: 5000)
 * @returns {Function} Function to stop watching
 */
function watchLocation(callback, interval = 5000) {
    let watchId = null;
    let lastUpdate = 0;
    
    if (navigator.geolocation) {
        watchId = navigator.geolocation.watchPosition(
            (position) => {
                const now = Date.now();
                // Throttle updates to specified interval
                if (now - lastUpdate >= interval) {
                    lastUpdate = now;
                    callback({
                        latitude: position.coords.latitude,
                        longitude: position.coords.longitude,
                        accuracy: position.coords.accuracy,
                        timestamp: position.timestamp
                    });
                }
            },
            (error) => {
                console.error('Location watch error:', error);
            },
            {
                enableHighAccuracy: true,
                maximumAge: interval
            }
        );
    }
    
    // Return function to stop watching
    return () => {
        if (watchId !== null) {
            navigator.geolocation.clearWatch(watchId);
        }
    };
}

// ==================== API HELPER FUNCTIONS ====================
/**
 * Makes a fetch request with error handling
 * 
 * @param {string} url - Request URL
 * @param {Object} options - Fetch options
 * @returns {Promise<any>} Response data
 */
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...(options.headers || {})
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// ==================== UTILITY FUNCTIONS ====================
/**
 * Formats a distance value for display
 * 
 * @param {number} meters - Distance in meters
 * @returns {string} Formatted distance string
 */
function formatDistance(meters) {
    if (meters >= 1000) {
        return `${(meters / 1000).toFixed(2)} km`;
    }
    return `${Math.round(meters)} m`;
}

/**
 * Formats a duration value for display
 * 
 * @param {number} seconds - Duration in seconds
 * @returns {string} Formatted duration string
 */
function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes} min`;
}

/**
 * Debounce function to limit rapid function calls
 * Useful for search inputs and resize handlers
 * 
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Shows a loading spinner
 * 
 * @param {string} containerId - ID of container to show spinner in
 */
function showLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.innerHTML = '<div class="spinner"></div>';
    }
}

/**
 * Hides loading spinner
 * 
 * @param {string} containerId - ID of container
 */
function hideLoading(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        const spinner = container.querySelector('.spinner');
        if (spinner) spinner.remove();
    }
}

/**
 * Shows a toast notification
 * 
 * @param {string} message - Message to display
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `flash-message flash-${type}`;
    toast.textContent = message;
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'flash-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.onclick = () => toast.remove();
    
    toast.appendChild(closeBtn);
    
    const container = document.querySelector('.flash-messages') || document.body;
    container.insertBefore(toast, container.firstChild);
    
    // Auto-remove after 5 seconds
    setTimeout(() => toast.remove(), 5000);
}

// ==================== LOCAL STORAGE HELPERS ====================
/**
 * Safely get item from localStorage
 * 
 * @param {string} key - Storage key
 * @param {any} defaultValue - Default value if not found
 * @returns {any} Stored value or default
 */
function getStoredItem(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (e) {
        console.error('Error reading from localStorage:', e);
        return defaultValue;
    }
}

/**
 * Safely set item in localStorage
 * 
 * @param {string} key - Storage key
 * @param {any} value - Value to store
 */
function setStoredItem(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
        console.error('Error writing to localStorage:', e);
    }
}

// ==================== DATE/TIME UTILITIES ====================
/**
 * Formats a date string for display
 * 
 * @param {string|Date} date - Date to format
 * @param {boolean} includeTime - Whether to include time
 * @returns {string} Formatted date string
 */
function formatDate(date, includeTime = false) {
    const d = new Date(date);
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    };
    
    if (includeTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
    }
    
    return d.toLocaleDateString(undefined, options);
}

/**
 * Calculates relative time (e.g., "2 hours ago")
 * 
 * @param {string|Date} date - Date to compare
 * @returns {string} Relative time string
 */
function timeAgo(date) {
    const seconds = Math.floor((new Date() - new Date(date)) / 1000);
    
    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };
    
    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return `${interval} ${unit}${interval > 1 ? 's' : ''} ago`;
        }
    }
    
    return 'Just now';
}

// Export utilities for use in other scripts
window.RouteLinkUtils = {
    getCurrentLocation,
    watchLocation,
    apiRequest,
    formatDistance,
    formatDuration,
    debounce,
    showLoading,
    hideLoading,
    showToast,
    getStoredItem,
    setStoredItem,
    formatDate,
    timeAgo
};
