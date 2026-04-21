/**
 * API Configuration and Service
 * Handles all API calls with proper base URL configuration
 */

// Get the API base URL from environment variables or use relative path for proxy
const API_BASE_URL = process.env.REACT_APP_API_URL || '';

/**
 * Make an API request with the configured base URL
 * @param {string} endpoint - API endpoint (e.g., '/api/remove-bg')
 * @param {object} options - Fetch options (method, body, headers, etc.)
 * @returns {Promise} - Fetch response
 */
export async function apiRequest(endpoint, options = {}) {
  const url = API_BASE_URL ? `${API_BASE_URL}${endpoint}` : endpoint;
  
  console.log(`API Request: ${options.method || 'GET'} ${url}`);
  
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
      }
    });
    
    if (!response.ok) {
      console.error(`API Error: ${response.status} ${response.statusText}`);
      throw new Error(`API error: ${response.status}`);
    }
    
    return response;
  } catch (error) {
    console.error('API Request Failed:', error);
    throw error;
  }
}

/**
 * Get current API base URL
 * @returns {string} - API base URL or relative path
 */
export function getApiBaseUrl() {
  return API_BASE_URL || '/';
}

// Common API endpoints
export const endpoints = {
  removeBg: '/api/remove-bg',
  tryon: '/api/tryon',
  wardrobeImages: '/api/wardrobe-images',
  fitAnalysis: '/api/fit-analysis',
  tryonResults: '/api/tryon-results',
  oauth: {
    googleCallback: '/api/oauth/google/callback'
  }
};

export default {
  apiRequest,
  getApiBaseUrl,
  endpoints
};
