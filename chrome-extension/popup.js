// ============================
// API Configuration
// ============================
// 🔧 DEVELOPMENT MODE: Uncomment the line below for local development
// const API_BASE_URL = 'http://localhost:5000';

// 🚀 PRODUCTION MODE: Uncomment the line below when deploying to GCP
// Replace 'YOUR_VM_IP' with your actual GCP VM's external IP address
const API_BASE_URL = 'http://35.198.124.100:5000';

// 📝 Instructions:
// - For LOCAL testing: Keep the localhost line uncommented
// - For PRODUCTION: Comment out localhost, uncomment the VM IP line and replace YOUR_VM_IP
// Example: const API_BASE_URL = 'http://34.123.45.67:5000';

// Global garment item counter for unique IDs
let garmentItemCounter = 0;

// Unified garment item structure generator
function createGarmentItemHTML(options = {}) {
  const {
    src,
    alt = 'Garment',
    title = 'Fashion Item',
    price = null,
    store = null,
    type = null,
    url = null, // Product or source URL for premium try-on
    isFavorited = false,
    source = 'unknown', // 'explorer', 'wardrobe', 'uploaded', 'placeholder'
    index = null,
    garmentId = null,
    extraData = {},
    showRemoveButton = false,
    additionalClasses = '',
    itemNumber = null,
    wardrobeId = null
  } = options;
  
  garmentItemCounter++;
  const uniqueId = `garment-item-${garmentItemCounter}`;
  
  // Common CSS classes for all garment items
  const commonClasses = 'garment-item-tryon';
  const sourceClass = `${source}-item`;
  const favoriteClass = isFavorited ? 'favorited' : '';
  
  // Build data attributes
  const dataAttributes = [
    src ? `data-src="${src}"` : '',
    title ? `data-title="${title}"` : '',
    price ? `data-price="${price}"` : '',
    store ? `data-store="${store}"` : '',
    type ? `data-type="${type}"` : '',
    url ? `data-url="${url}"` : '',
    index !== null ? `data-index="${index}"` : '',
    garmentId ? `data-garment-id="${garmentId}"` : '',
    wardrobeId ? `data-wardrobe-item="${wardrobeId}"` : '',
    `data-source="${source}"`
  ].filter(Boolean).join(' ');
  
  // Additional data attributes from extraData
  const extraDataAttrs = Object.entries(extraData)
    .map(([key, value]) => `data-${key}="${value}"`)
    .join(' ');
  
  return `
    <div class="${commonClasses} ${sourceClass} ${favoriteClass} ${additionalClasses}" 
         id="${uniqueId}"
         ${dataAttributes}
         ${extraDataAttrs}>
      
      <!-- Image Container -->
      <div class="garment-item-image-container">
        ${src ? `
          <img src="${src}" 
               alt="${alt}" 
               class="garment-item-image"
               onload="console.log('✅ Image loaded:', '${title}', '${src}');"
               onerror="console.error('❌ Image failed:', '${title}', '${src}'); this.style.display='none'; this.parentElement.innerHTML += '<div class=\\'garment-image-unavailable\\'>Image<br/>Unavailable</div>';" />
        ` : `
          <div class="garment-placeholder-content">
            <span class="upload-text">${title}</span>
          </div>
        `}
        
        <!-- Favorite Button -->
        <button class="favorite-btn ${favoriteClass}" type="button">
          <span class="heart-icon">${isFavorited ? '♥' : '♡'}</span>
        </button>
        
        ${showRemoveButton ? `
          <!-- Remove Button -->
          <button class="garment-remove-btn" data-remove-index="${index}" title="Remove garment">
            ×
          </button>
        ` : ''}
        
        ${source === 'wardrobe' ? `
          <!-- Wardrobe Badge -->
          <div class="garment-source-badge wardrobe-badge">
            Wardrobe
          </div>
        ` : ''}
        
        ${itemNumber ? `
          <!-- Item Number Badge -->
          <div class="garment-number-badge">
            ${itemNumber}
          </div>
        ` : ''}
      </div>
      
      <!-- Item Info -->
      ${src ? `
        <div class="garment-item-info">
          <div class="garment-item-title" title="${title}">
            ${title}
          </div>
          ${price ? `<div class="garment-item-price">${price}</div>` : ''}
          ${store ? `<div class="garment-item-store">${store}</div>` : ''}
          ${type ? `<div class="garment-type-badge">${type.toUpperCase()}</div>` : ''}
          
          ${url && source === 'explorer' ? `
            <!-- Premium Try-On Button -->
            <button class="premium-tryon-btn" data-url="${url}" title="View on ${store || 'Store'}">
              <span class="premium-text">Premium Try-On</span>
            </button>
          ` : ''}
        </div>
      ` : ''}
      
      <!-- Try-on Hover Badge -->
      <div class="tryon-hover-badge">
        Try On
      </div>
    </div>
  `;
}

document.addEventListener('DOMContentLoaded', function() {

  // ===== MEMORY MANAGEMENT =====
  // Track blob URLs for cleanup
  const blobUrls = new Set();
  const originalCreateObjectURL = URL.createObjectURL;
  const originalRevokeObjectURL = URL.revokeObjectURL;

  // Override URL.createObjectURL to track all blob URLs
  URL.createObjectURL = function(blob) {
    const url = originalCreateObjectURL(blob);
    blobUrls.add(url);
    return url;
  };

  // Override URL.revokeObjectURL to remove from tracking
  URL.revokeObjectURL = function(url) {
    blobUrls.delete(url);
    originalRevokeObjectURL(url);
  };

  // Function to cleanup all tracked blob URLs
  function cleanupAllBlobUrls() {
    for (const url of blobUrls) {
      originalRevokeObjectURL(url);
    }
    blobUrls.clear();
    console.log('🧹 Cleaned up all blob URLs');
  }

  // Cleanup on page unload
  window.addEventListener('beforeunload', cleanupAllBlobUrls);

  // Function to ensure proper grid layout for empty states
  function ensureGridLayout() {
    const garmentPreview = document.getElementById('garment-preview');
    if (garmentPreview) {
      garmentPreview.style.display = 'grid';
      
      // If the container is empty or has less than 2 items, show placeholders
      const children = garmentPreview.children;
      if (children.length < 2) {
        garmentPreview.innerHTML = `
          <div class="upload-placeholder">
            <span class="upload-text">Upload or find garments</span>
          </div>
          <div class="upload-placeholder">
            <span class="upload-text">Upload or find garments</span>
          </div>
          <div class="upload-placeholder">
            <span class="upload-text">Upload or find garments</span>
          </div>
          <div class="upload-placeholder">
            <span class="upload-text">Upload or find garments</span>
          </div>
        `;
      }
    }
  }

  // ===== GLOBAL VARIABLES =====
  // Wardrobe functionality
  let currentUser = null; // Will store user info after sign-in
  let wardrobeItems = []; // Cache for wardrobe items

  // Garment source toggle
  let currentGarmentSource = 'page'; // 'page' or 'wardrobe'
  let isShowingWardrobe = false;

  // Garment preview display flag
  let currentDisplayMode = 'online'; // 'online' for page images, 'wardrobe' for wardrobe images

  // AI Model selection
  let selectedAIModel = 'rembg'; // Default to Rembg for faster processing

  // Multi-garment try-on selection
  let selectedGarments = []; // Array to track selected garment images for multi-try-on

  // ===== CLEAR CACHED IMAGES ON POPUP LOAD =====
  // Force fresh extraction every time the popup is opened
  console.log('🧹 Clearing image cache on popup load for fresh extraction');
  
  // Initialize display mode flag
  console.log('🔄 Initializing display mode to: online');
  // Note: currentDisplayMode is already initialized to 'online' in global variables

  // ===== FIRST PRIORITY: BRAND DOMAIN CHECK =====
  // This MUST run first when extension opens/reopens
  let useGarmentCheckbox = false;
  
  // Call brand domain check immediately and handle garment extraction
  async function initializeBrandCheck() {
    try {
      const isBrandPage = await checkBrandDomain();
      useGarmentCheckbox = isBrandPage;
      console.log('🔍 Initial brand domain check completed. Result:', isBrandPage);
      
      // If it's a brand page, trigger garment extraction IMMEDIATELY
      if (isBrandPage) {
        console.log('🎯 Brand page detected - triggering fresh garment extraction NOW');
        currentGarmentSource = 'page'; // Set to show page garments initially
        
        // Clear any cached images first
        allExtractedImages = [];
        currentImagePage = 0;
        
        // Wait a brief moment for DOM to be ready, then extract garments
        setTimeout(() => {
          extractGarmentsFromPage();
          // Update toggle button state after extraction
          setTimeout(() => {
            console.log('🔄 Updating toggle button state after brand page detection');
            updateToggleButtonState();
          }, 200);
        }, 100);
      } else {
        console.log('ℹ️ Not a brand page - toggle button will be hidden');
        currentGarmentSource = 'page'; // Default state
        
        // ✨ NEW: Load wardrobe items as default for non-brand pages
        console.log('📦 Non-brand page detected - loading wardrobe items after initialization');
        setTimeout(() => {
          console.log('🔄 Triggering wardrobe fallback for non-brand page');
          loadWardrobeAsFallback();
        }, 500); // Wait for user data to be loaded
      }
    } catch (error) {
      console.error('❌ Initial brand domain check failed:', error);
      useGarmentCheckbox = false;
      currentGarmentSource = 'page';
      
      // ✨ NEW: Load wardrobe on error too
      console.log('📦 Brand check failed - loading wardrobe items as fallback');
      setTimeout(() => {
        loadWardrobeAsFallback();
      }, 500);
    }
  }
  
  // Start brand check immediately
  initializeBrandCheck();

  // Sign In Page Elements
  const signinPage = document.getElementById('signin-page');
  const mainApp = document.getElementById('main-app');
  const signinBtn = document.getElementById('signin-btn');
  const guestBtn = document.getElementById('guest-btn');
  const signinEmail = document.getElementById('signin-email');
  const signinPassword = document.getElementById('signin-password');

  // Account Creation Page Elements
  const accountCreationPage = document.getElementById('account-creation-page');
  const createAccountLink = document.getElementById('create-account');
  const backToSigninLink = document.getElementById('back-to-signin');
  const createAccountBtn = document.getElementById('create-account-btn');

  // Account Creation Form Fields
  const createEmail = document.getElementById('create-email');
  const createFirstname = document.getElementById('create-firstname');
  const createLastname = document.getElementById('create-lastname');
  const createPassword = document.getElementById('create-password');
  const createAge = document.getElementById('create-age');
  const createGender = document.getElementById('create-gender');
  const createWeight = document.getElementById('create-weight');
  const createHeight = document.getElementById('create-height');

  // User Profile Page Elements
  const userProfilePage = document.getElementById('user-profile-page');
  const userBtn = document.getElementById('user-btn');
  const backToMainLink = document.getElementById('back-to-main');
  const editProfileBtn = document.getElementById('edit-profile-btn');
  const saveProfileBtn = document.getElementById('save-profile-btn');
  const cancelEditBtn = document.getElementById('cancel-edit-btn');

  // User Profile Form Fields
  const profileUserid = document.getElementById('profile-userid');
  const profileEmail = document.getElementById('profile-email');
  const profileFirstname = document.getElementById('profile-firstname');
  const profileLastname = document.getElementById('profile-lastname');
  const profileAge = document.getElementById('profile-age');
  const profileGender = document.getElementById('profile-gender');
  const profileWeight = document.getElementById('profile-weight');
  const profileHeight = document.getElementById('profile-height');

  // ===== BRAND DOMAIN CHECK FUNCTION =====
  // Function to check if current page URL matches any brand domain and contains garment types
  async function checkBrandDomain() {
    try {
      let brandFound = false;
      let garmentFound = false;
      let foundGarmentType = '';
      // Define garment type categories (English and German)
      const garmentTypes = {
        upper: [
          'shirt', 'hemd', 't-shirt', 'tshirt', 
          'top', 'oberteil', 'blouse', 'bluse', 'jacket', 'jacke',
          'sweater', 'pullover', 'hoodie', 'kapuzenpullover', 'cardigan', 'strickjacke',
          'polo', 'poloshirt', 'dress', 'tank', 'tanktop', 'vest', 'weste',
          'blazer', 'sakko', 'coat', 'mantel', 'sweatshirt', 'sweatshirt'
        ],
        lower: [
          'trouser', 'hose', 'pants', 'hose', 'jeans', 'jeans', 'shorts', 'shorts',
          'skirt', 'rock', 'leggings', 'leggings', 'chinos', 'chinos', 'slacks', 'stoffhose',
          'joggers', 'jogginghose', 'sweatpants', 'jogginghose', 'trackpants', 'trainingshose', 'capri', 'caprihose'
        ]
      };
      
      // Load the brands.json file
      const response = await fetch(chrome.runtime.getURL('brands.json'));
      const brandsData = await response.json();
      
      // Get the current active tab URL
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const currentURL = tabs[0]?.url || '';
      
      console.log('🔍 Checking current URL:', currentURL);
      
      // Check if current URL contains any brand domain
      
      for (const brand of brandsData.brands) {
        if (currentURL.toLowerCase().includes(brand.domain.toLowerCase())) {
          console.log('✅ Brand domain found:', brand.domain);
          brandFound = true;
          break;
        }
      }
      
      if (!brandFound) {
        console.log('❌ No brand domain found - useGarmentCheckbox will be set to FALSE');
        return false;
      }
      
      // Check if URL contains any garment type
      const urlLower = currentURL.toLowerCase();

      // Check upper garments
      for (const garment of garmentTypes.upper) {
        if (urlLower.includes(garment.toLowerCase())) {
          garmentFound = true;
          foundGarmentType = `upper (${garment})`;
          break;
        }
      }
      
      // Check lower garments if no upper garment found
      if (!garmentFound) {
        for (const garment of garmentTypes.lower) {
          if (urlLower.includes(garment.toLowerCase())) {
            garmentFound = true;
            foundGarmentType = `lower (${garment})`;
            break;
          }
        }
      }
      
      if (brandFound && garmentFound) {
        console.log('✅ Brand URL and garment type found in URL:', brandFound, garmentFound, foundGarmentType, '- useGarmentCheckbox will be set to TRUE');
        return true;
      } else {
        console.log('❌ No garment type found in URL - useGarmentCheckbox will be set to FALSE');
        return false;
      }
      
    } catch (error) {
      console.error('❌ Error checking brand domain:', error);
      return false;
    }
  }

  // ===== GARMENT EXTRACTION FUNCTIONS =====
  // Function to extract garments from page when useGarmentCheckbox is true
  async function extractGarmentsFromPage() {
    if (!useGarmentCheckbox) {
      console.log('❌ useGarmentCheckbox is false - skipping garment extraction');
      return;
    }
    
    console.log('🔍 Extracting fresh garments from page...');
    
    // Clear previously extracted images to ensure fresh extraction
    allExtractedImages = [];
    currentImagePage = 0;
    
    try {
      // Get the current active tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      console.log('Active tab:', tab.url, 'ID:', tab.id);
      
      // Always inject content script fresh to ensure it's up to date
      console.log('🔄 Injecting fresh content script...');
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content-script.js']
      });
      
      // Wait a moment for content script to load, then send message
      setTimeout(() => {
        chrome.tabs.sendMessage(tab.id, { type: 'GET_IMAGES_ON_PAGE' }, (response) => {
          if (chrome.runtime.lastError) {
            console.error('Content script error:', chrome.runtime.lastError.message || chrome.runtime.lastError);
            console.log('Trying direct image search as fallback...');
            executeDirectImageSearch(tab.id);
            return;
          }
          
          console.log('📨 Raw response:', response);
          console.log('📨 Response.images:', response?.images);
          console.log('📨 Response type:', typeof response);
          
          // Handle different response formats
          let images = [];
          if (Array.isArray(response)) {
            images = response;
          } else if (response?.images && Array.isArray(response.images)) {
            images = response.images;
          } else if (response && typeof response === 'object') {
            images = Object.values(response).filter(item => item && item.src);
          }
          
          console.log('🎯 Final extracted images:', images.length, 'found');
          if (images.length === 0) {
            console.log('⚠️ No images found, trying direct extraction...');
            executeDirectImageSearch(tab.id);
          } else {
            displayImagesInPlaceholders(images);
          }
        });
      }, 300); // Give content script time to initialize
      
    } catch (error) {
      console.error('Error injecting content script or extracting garments:', error.message || error);
      console.log('Falling back to direct image search...');
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.id) {
        executeDirectImageSearch(tab.id);
      } else {
        console.log('❌ No active tab found - loading wardrobe as fallback');
        loadWardrobeAsFallback();
      }
    }
  }

  // Fallback function to search for images directly via script injection
  function executeDirectImageSearch(tabId) {
    console.log('🔄 Executing direct image search as fallback...');
    
    // Clear cache before direct search
    allExtractedImages = [];
    currentImagePage = 0;
    
    chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: function() {
        console.log('🔍 Direct image search: scanning page for images...');
        
        // Enhanced image collection with garment filtering
        const images = Array.from(document.images)
          .filter(img => {
            // Basic size filter
            if (!img.src || img.naturalWidth < 100 || img.naturalHeight < 100) return false;
            
            // Check for garment-related keywords in src or alt
            const src = img.src.toLowerCase();
            const alt = (img.alt || '').toLowerCase();
            const garmentKeywords = ['shirt', 'dress', 'pants', 'jeans', 'jacket', 'coat', 'sweater', 'clothing', 'apparel', 'fashion', 'product', 'item'];
            
            const hasGarmentKeyword = garmentKeywords.some(keyword => 
              src.includes(keyword) || alt.includes(keyword)
            );
            
            // Exclude obvious non-garment images
            const excludeKeywords = ['logo', 'icon', 'banner', 'header', 'footer', 'nav', 'menu'];
            const hasExcludeKeyword = excludeKeywords.some(keyword => 
              src.includes(keyword) || alt.includes(keyword)
            );
            
            // Return images that have garment keywords or are reasonably sized, but not excluded
            return !hasExcludeKeyword && (hasGarmentKeyword || (img.naturalWidth >= 200 && img.naturalHeight >= 200));
          })
          .slice(0, 12) // Get up to 12 images
          .map(img => ({
            src: img.src,
            width: img.naturalWidth,
            height: img.naturalHeight,
            alt: img.alt || '',
            type: 'img-direct'
          }));
          
        console.log('🔍 Direct search found', images.length, 'images');
        return images;
      }
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error('Direct script execution failed:', chrome.runtime.lastError.message);
        // Load wardrobe as final fallback
        console.log('📦 All extraction methods failed - loading wardrobe as final fallback');
        loadWardrobeAsFallback();
        return;
      }
      
      const images = results?.[0]?.result || [];
      console.log('✅ Direct search completed - found', images.length, 'images');
      
      // If no images found, load wardrobe items as fallback
      if (images.length === 0) {
        console.log('📦 No images on page - loading wardrobe items as fallback...');
        loadWardrobeAsFallback();
      } else {
        displayImagesInPlaceholders(images);
      }
    });
  }

  // Function to load wardrobe items when no images are found on page
  async function loadWardrobeAsFallback() {
    console.log('📦 Loading wardrobe items as fallback...');
    
    try {
      // Get userId from chrome storage
      const storageResult = await new Promise((resolve) => {
        chrome.storage.local.get(['userId'], (result) => resolve(result));
      });
      
      const userId = storageResult.userId || (currentUser && currentUser.userID);
      
      if (!userId) {
        console.log('⚠️ No user logged in - showing empty placeholders');
        showEmptyPlaceholders('Sign in to see your wardrobe items');
        return;
      }
      
      console.log('🔍 Loading wardrobe for user:', userId);
      
      // Fetch wardrobe items from API
      const response = await fetch(`${API_BASE_URL}/api/wardrobe/user/${userId}`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch wardrobe: ${response.status}`);
      }
      
      const wardrobeItems = await response.json();
      console.log(`📦 Loaded ${wardrobeItems.length} wardrobe items from database`);
      
      if (wardrobeItems.length === 0) {
        console.log('⚠️ Wardrobe is empty - showing empty placeholders');
        showEmptyPlaceholders('Your wardrobe is empty. Add items to get started!');
        return;
      }
      
      // Convert wardrobe items to the format expected by displayImagesInPlaceholders
      // Add width/height to ensure they pass the validation filter
      const formattedImages = wardrobeItems.map((item, index) => ({
        src: item.garment_image, // Base64 image
        type: 'wardrobe',
        garment_id: item.garment_id,
        garment_type: item.garment_type,
        garment_url: item.garment_url,
        id: `wardrobe-${index}`,
        width: 500, // Set sufficient dimensions to pass validation
        height: 500,
        isWardrobeFallback: true // Flag to prevent infinite loop
      }));
      
      console.log('✅ Displaying wardrobe items in garment-preview');
      
      // Directly set the images without calling displayImagesInPlaceholders 
      // to avoid infinite loop if wardrobe images also fail validation
      allExtractedImages = formattedImages;
      currentImagePage = 0;
      currentDisplayMode = 'wardrobe';
      
      renderImagePage();
      
      // Update the page indicator to show it's from wardrobe
      const pageIndicator = document.getElementById('page-indicator');
      if (pageIndicator && formattedImages.length > 0) {
        pageIndicator.textContent = `Showing wardrobe (${formattedImages.length} items)`;
      }
      
      console.log('✅ Wardrobe fallback complete - displayed', formattedImages.length, 'items');
      
    } catch (error) {
      console.error('❌ Error loading wardrobe fallback:', error);
      showEmptyPlaceholders('Unable to load wardrobe items');
    }
  }

  // Helper function to show empty placeholders with custom message
  function showEmptyPlaceholders(message = 'No images found on page') {
    const garmentPreview = document.getElementById('garment-preview');
    if (garmentPreview) {
      garmentPreview.style.display = 'grid';
      garmentPreview.innerHTML = `
        <div class="upload-placeholder" style="grid-column: span 2; text-align: center;">
          <span class="upload-text">${message}</span>
        </div>
        <div class="upload-placeholder">
          <span class="upload-text">Upload a garment to try on</span>
        </div>
        <div class="upload-placeholder">
          <span class="upload-text">Upload a garment to try on</span>
        </div>
      `;
    }
  }

  // Global variables for pagination
  let allExtractedImages = [];
  let currentImagePage = 0;
  const imagesPerPage = 4;

  // Global variables for wardrobe pagination
  let allWardrobeItems = [];
  let currentWardrobePage = 0;
  const wardrobeItemsPerPage = 4;

  // Function to handle try-on click from extracted images
  async function handleImageTryOn(imageSrc) {
    console.log('🎯 handleImageTryOn called with image:', imageSrc);
    
    // Detect garment type from current URL
    const garmentType = await detectGarmentTypeFromURL();
    console.log('🔍 Detected garment type:', garmentType);
    
    try {
      await performTryOn(imageSrc, garmentType);
      console.log('✅ Try-on completed successfully from extracted image');
    } catch (error) {
      console.error('❌ Try-on failed from extracted image:', error);
    }
  }

  // Handle checkbox change for garment selection
  function handleGarmentCheckboxChange(isChecked, imageSrc) {
    console.log(`📦 Checkbox ${isChecked ? 'checked' : 'unchecked'} for:`, imageSrc);
    
    if (isChecked) {
      // Add to selected garments if not already there
      if (!selectedGarments.some(g => g.src === imageSrc)) {
        selectedGarments.push({ src: imageSrc });
        console.log('✅ Added to selection. Total selected:', selectedGarments.length);
      }
    } else {
      // Remove from selected garments
      selectedGarments = selectedGarments.filter(g => g.src !== imageSrc);
      console.log('➖ Removed from selection. Total selected:', selectedGarments.length);
    }
    
    // Update the visual state of the garment item
    const garmentItems = document.querySelectorAll('.garment-item-tryon');
    garmentItems.forEach(item => {
      if (item.getAttribute('data-image-src') === imageSrc) {
        if (isChecked) {
          item.classList.add('selected');
        } else {
          item.classList.remove('selected');
        }
      }
    });
    
    // Note: With unified API, individual try-on button now handles multiple garments automatically
  }

  // REMOVED: handleMultiGarmentTryOn() - Multi-garment functionality now integrated into performTryOn()
  // The unified performTryOn() function automatically detects if multiple garments are selected
  // via checkboxes and sends them all to the unified /api/tryon-gemini endpoint

  // Function to detect garment type from current URL
  async function detectGarmentTypeFromURL() {
    try {
      // Get the current active tab URL
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const currentURL = tabs[0]?.url || '';
      const urlLower = currentURL.toLowerCase();
      
      // Define garment type categories (same as in checkBrandDomain)
      const garmentTypes = {
        upper: [
          'shirt', 'hemd', 't-shirt', 'tshirt', 
          'top', 'oberteil', 'blouse', 'bluse', 'jacket', 'jacke',
          'sweater', 'pullover', 'hoodie', 'kapuzenpullover', 'cardigan', 'strickjacke',
          'polo', 'poloshirt', 'tank', 'tanktop', 'vest', 'weste',
          'blazer', 'sakko', 'coat', 'mantel', 'sweatshirt', 'sweatshirt'
        ],
        lower: [
          'trouser', 'hose', 'pants', 'hose', 'jeans', 'jeans', 'shorts', 'shorts',
          'skirt', 'rock', 'leggings', 'leggings', 'chinos', 'chinos', 'slacks', 'stoffhose',
          'joggers', 'jogginghose', 'sweatpants', 'jogginghose', 'trackpants', 'trainingshose', 'capri', 'caprihose'
        ]
      };
      
      // Check upper garments first
      for (const garment of garmentTypes.upper) {
        if (urlLower.includes(garment.toLowerCase())) {
          return 'upper';
        }
      }
      
      // Check lower garments
      for (const garment of garmentTypes.lower) {
        if (urlLower.includes(garment.toLowerCase())) {
          return 'lower';
        }
      }
      
      // Default to upper if no specific type detected
      console.log('ℹ️ No specific garment type detected in URL, defaulting to upper');
      return 'upper';
      
    } catch (error) {
      console.error('❌ Error detecting garment type from URL:', error);
      return 'upper'; // Default fallback
    }
  }

  // Global try-on function that can be called from anywhere
  // Helper function to convert data URL to blob
  function dataURLToBlob(dataURL) {
    const parts = dataURL.split(',');
    const contentType = parts[0].match(/:(.*?);/)[1];
    const raw = window.atob(parts[1]);
    const rawLength = raw.length;
    const uInt8Array = new Uint8Array(rawLength);
    
    for (let i = 0; i < rawLength; ++i) {
      uInt8Array[i] = raw.charCodeAt(i);
    }
    
    return new Blob([uInt8Array], { type: contentType });
  }

  // Helper function to safely convert image data to blob
  async function safeImageToBlob(imageData) {
    console.log('🔄 Converting image to blob:', imageData ? imageData.substring(0, 100) + '...' : 'null');
    
    // Validate imageData
    if (!imageData) {
      throw new Error('Image data is null or undefined');
    }
    
    if (typeof imageData !== 'string') {
      throw new Error(`Image data must be a string, got ${typeof imageData}`);
    }
    
    if (imageData.startsWith('data:')) {
      // It's a data URL, convert directly to blob
      console.log('✅ Converting data URL to blob');
      return dataURLToBlob(imageData);
    } else {
      // It's a regular URL, we need to proxy it through our backend to avoid CORS
      console.log('🌐 Fetching external image through backend proxy...');
      try {
        // Use backend proxy to fetch external images and avoid CORS issues
        const proxyUrl = `${API_BASE_URL}/api/proxy-image?url=${encodeURIComponent(imageData)}`;
        const response = await fetch(proxyUrl);
        
        if (!response.ok) {
          throw new Error(`Proxy fetch failed: ${response.status} ${response.statusText}`);
        }
        
        const blob = await response.blob();
        console.log('✅ Successfully fetched image through proxy, blob size:', blob.size);
        return blob;
      } catch (error) {
        console.error('❌ Failed to fetch image through proxy:', error);
        
        // Fallback: try direct fetch (will likely fail due to CORS)
        try {
          console.log('⚠️ Attempting direct fetch as fallback...');
          const response = await fetch(imageData);
          return await response.blob();
        } catch (corsError) {
          console.error('❌ Direct fetch also failed (CORS):', corsError);
          throw new Error(`Cannot load external image: ${imageData}. CORS policy prevents direct access.`);
        }
      }
    }
  }

  // ===== WARDROBE FUNCTIONALITY =====
  // Helper function to convert blob to base64
  function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  }

  // Function to save garment to wardrobe
  async function saveToWardrobe(garmentImageData, garmentType, garmentUrl = null) {
    try {
      if (!currentUser || !currentUser.userID) {
        console.error('❌ No user logged in');
        return { success: false, message: 'Please sign in to save garments' };
      }

      // Generate unique garment ID
      const garmentId = `garment_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // Convert image data to blob if it's a data URL
      let imageBlob;
      if (garmentImageData.startsWith('data:')) {
        imageBlob = dataURLToBlob(garmentImageData);
      } else {
        const response = await fetch(garmentImageData);
        imageBlob = await response.blob();
      }

      // Convert blob to base64 for storage
      const imageBase64 = await blobToBase64(imageBlob);

      const wardrobeData = {
        user_id: currentUser.userID,
        garment_id: garmentId,
        garment_image: imageBase64,
        garment_type: garmentType,
        garment_url: garmentUrl,
        date_added: new Date().toISOString()
      };

      console.log(wardrobeData);

      // Save to backend database
      const response = await fetch(`${API_BASE_URL}/api/wardrobe/save`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(wardrobeData)
      });

      if (response.ok) {
        const result = await response.json();
        console.log('✅ Garment saved to wardrobe:', garmentId);
        
        // Add to local cache
        wardrobeItems.push(wardrobeData);
        console.log('✅ Item added to wardrobeItems cache. New count:', wardrobeItems.length);
        console.log('✅ Added item details:', {
          garment_id: wardrobeData.garment_id,
          user_id: wardrobeData.user_id,
          garment_image_preview: wardrobeData.garment_image.substring(0, 50) + '...'
        });
        
        return { success: true, garmentId: garmentId };
      } else {
        throw new Error(`Failed to save: ${response.status}`);
      }

    } catch (error) {
      console.error('❌ Error saving to wardrobe:', error);
      return { success: false, message: error.message };
    }
  }

  // Function to check if garment is already in wardrobe
  function isGarmentInWardrobe(garmentImageData) {
    // Simple check - in a real app, you might want to use image hashing
    const isInWardrobe = wardrobeItems.some(item => item.garment_image === garmentImageData);
    console.log('🔍 isGarmentInWardrobe check:', isInWardrobe, 'for', garmentImageData.substring(0, 50) + '...');
    console.log('🔍 Wardrobe items count:', wardrobeItems.length);
    return isInWardrobe;
  }

  // Function to get current display mode
  function getCurrentDisplayMode() {
    console.log('🔍 Current display mode:', currentDisplayMode);
    return currentDisplayMode;
  }

  // Function to check if currently showing wardrobe images
  function isShowingWardrobeImages() {
    return currentDisplayMode === 'wardrobe';
  }

  // Function to check if currently showing online images (page extracted or uploaded)
  function isShowingOnlineImages() {
    return currentDisplayMode === 'online';
  }

  // Function to remove garment from wardrobe
  async function removeFromWardrobe(garmentImageData) {
    try {
      console.log('🗑️ removeFromWardrobe called with:', garmentImageData.substring(0, 50) + '...');
      console.log('🔍 Current user:', currentUser);
      console.log('🔍 Wardrobe items count:', wardrobeItems.length);
      
      if (!currentUser || !currentUser.userID) {
        console.error('❌ No user logged in');
        return { success: false, message: 'Please sign in to remove garments' };
      }

      // Find the garment in local cache
      console.log('🔍 Searching for garment in wardrobe items...');
      const garmentIndex = wardrobeItems.findIndex(item => {
        console.log('🔍 Comparing:', item.garment_image.substring(0, 50) + '... vs', garmentImageData.substring(0, 50) + '...');
        return item.garment_image === garmentImageData;
      });
      
      console.log('🔍 Garment index found:', garmentIndex);
      
      if (garmentIndex === -1) {
        console.error('❌ Garment not found in wardrobe cache');
        console.log('🔍 Available wardrobe items:');
        wardrobeItems.forEach((item, index) => {
          console.log(`  ${index}: ${item.garment_id} - ${item.garment_image.substring(0, 50)}...`);
        });
        return { success: false, message: 'Garment not found in wardrobe' };
      }

      const garmentToRemove = wardrobeItems[garmentIndex];
      console.log('🗑️ Removing garment from wardrobe:', garmentToRemove.garment_id);

      // Remove from backend database
      const response = await fetch(`${API_BASE_URL}/api/wardrobe/remove`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: currentUser.userID,
          garment_id: garmentToRemove.garment_id
        })
      });

      if (response.ok) {
        const result = await response.json();
        console.log('✅ Garment removed from wardrobe database:', garmentToRemove.garment_id);
        
        // Remove from local cache
        wardrobeItems.splice(garmentIndex, 1);
        
        return { success: true, garmentId: garmentToRemove.garment_id };
      } else {
        const errorData = await response.json();
        throw new Error(`Failed to remove: ${response.status} - ${errorData.error || 'Unknown error'}`);
      }

    } catch (error) {
      console.error('❌ Error removing from wardrobe:', error);
      return { success: false, message: error.message };
    }
  }

  // Function to handle favorite button click
  async function handleFavoriteClick(event, garmentImageData, garmentType, garmentUrl = null) {
    event.stopPropagation(); // Prevent triggering try-on
    
    // Get the favorite button - use currentTarget first, then target as fallback
    const favoriteBtn = event.currentTarget || event.target.closest('.favorite-btn');
    
    if (!favoriteBtn) {
      console.error('❌ Could not find favorite button element');
      return;
    }
    
    const heartIcon = favoriteBtn.querySelector('.heart-icon');
    const garmentItem = favoriteBtn.closest('.garment-item-tryon');
    
    if (!heartIcon) {
      console.error('❌ Could not find heart icon element');
      return;
    }
    
    // Show loading state
    heartIcon.textContent = '⏳';
    favoriteBtn.disabled = true;

    try {
      console.log('🎯 handleFavoriteClick - Button state check:', {
        hasFavoritedClass: favoriteBtn.classList.contains('favorited'),
        buttonClasses: favoriteBtn.className,
        heartIconText: heartIcon.textContent,
        isInWardrobe: isGarmentInWardrobe(garmentImageData)
      });
      
      if (favoriteBtn.classList.contains('favorited')) {
        console.log('💔 Attempting to remove from wardrobe...');
        // Remove from wardrobe
        const result = await removeFromWardrobe(garmentImageData);
        
        if (result.success) {
          favoriteBtn.classList.remove('favorited');
          garmentItem.classList.remove('favorited');
          heartIcon.textContent = '♡';
          console.log('💔 Removed from wardrobe successfully');
          
          // Show success feedback
          showFavoriteRemoveSuccess();
        } else {
          heartIcon.textContent = '♥'; // Keep as favorited if removal failed
          console.error('Failed to remove:', result.message);
          // Show error message to user
          showFavoriteError(result.message);
        }
      } else {
        // Add to wardrobe
        const result = await saveToWardrobe(garmentImageData, garmentType, garmentUrl);
        
        if (result.success) {
          favoriteBtn.classList.add('favorited');
          garmentItem.classList.add('favorited');
          heartIcon.textContent = '♥';
          console.log('💖 Added to wardrobe');
          
          // Show success feedback
          showFavoriteSuccess();
        } else {
          heartIcon.textContent = '♡';
          console.error('Failed to save:', result.message);
          // Show error message to user
          showFavoriteError(result.message);
        }
      }
    } catch (error) {
      heartIcon.textContent = '♡';
      console.error('❌ Favorite action failed:', error);
      showFavoriteError('Failed to save garment');
    } finally {
      favoriteBtn.disabled = false;
    }
  }

  // Feedback functions
  function showFavoriteSuccess() {
    console.log('✅ Garment saved to your wardrobe!');
    // You can implement a toast notification here
  }

  function showFavoriteRemoveSuccess() {
    console.log('✅ Garment removed from your wardrobe!');
    // You can implement a toast notification here
  }

  function showFavoriteError(message) {
    console.error('❌ Error:', message);
    // You can implement error notification here
  }

  // Function to load user's wardrobe from backend
  async function loadUserWardrobe() {
    try {
      if (!currentUser || !currentUser.userID) return;
      
      const response = await fetch(`${API_BASE_URL}/api/wardrobe/user/${currentUser.userID}`);
      if (response.ok) {
        wardrobeItems = await response.json();
        console.log('👗 Loaded wardrobe items:', wardrobeItems.length);
        
        // ✨ NEW: Auto-display wardrobe if on non-brand page
        // Check if this is NOT a brand page after wardrobe loads
        if (!useGarmentCheckbox && wardrobeItems.length > 0) {
          console.log('📦 Non-brand page + wardrobe loaded → Auto-displaying wardrobe items');
          // Small delay to ensure UI is ready
          setTimeout(() => {
            loadWardrobeAsFallback();
          }, 100);
        }
      }
    } catch (error) {
      console.error('❌ Error loading wardrobe:', error);
    }
  }

  // Function to display wardrobe items
  function displayWardrobeItems() {
    const garmentPreview = document.getElementById('garment-preview');
    const garmentNavigation = document.getElementById('garment-navigation');
    
    if (!garmentPreview) return;
    
    // Set display mode flag to wardrobe
    currentDisplayMode = 'wardrobe';
    console.log('🔄 Display mode set to:', currentDisplayMode);
    
    console.log('👗 Displaying wardrobe items:', wardrobeItems.length);
    
    // Store all wardrobe items for pagination
    allWardrobeItems = [...wardrobeItems];
    currentWardrobePage = 0;
    
    // Render the first page of wardrobe items
    renderWardrobePage();
    
    console.log('✅ Wardrobe items display initialized with pagination');
  }

  // Function to toggle between wardrobe and page garments
  function toggleGarmentSource() {
    const toggleBtn = document.getElementById('garment-source-toggle');
    const toggleText = document.getElementById('toggle-text');
    
    console.log('🔄 toggleGarmentSource elements found:', {
      toggleBtn: !!toggleBtn,
      toggleText: !!toggleText
    });
    
    if (!toggleBtn || !toggleText) {
      console.error('❌ Required toggle elements not found');
      return;
    }
    
    console.log('🔄 toggleGarmentSource called - current source:', currentGarmentSource);
    
    if (currentGarmentSource === 'page') {
      // Switch to wardrobe
      console.log('🌐➡️👗 Switching from page to wardrobe');
      currentGarmentSource = 'wardrobe';
      isShowingWardrobe = true;
      toggleText.textContent = 'Show Garments on Page';
      displayWardrobeItems();
      console.log('👗 Switched to wardrobe view');
    } else {
      // Switch to page garments
      console.log('👗➡️🌐 Switching from wardrobe to page');
      currentGarmentSource = 'page';
      isShowingWardrobe = false;
      toggleText.textContent = 'Show Garments in Wardrobe';
      
      // ALWAYS force fresh extraction when switching back to page view
      console.log('� Forcing fresh extraction when switching to page view');
      if (useGarmentCheckbox) {
        // Clear cache and extract fresh images
        allExtractedImages = [];
        currentImagePage = 0;
        extractGarmentsFromPage();
      } else {
        // Show empty upload placeholders for non-brand pages
        console.log('⚠️ Not a brand page, showing upload placeholders');
        const garmentPreview = document.getElementById('garment-preview');
        if (garmentPreview) {
          garmentPreview.innerHTML = `
            <div class="upload-placeholder">
              <span class="upload-text">Upload a garment to try on</span>
            </div>
            <div class="upload-placeholder">
              <span class="upload-text">Upload a garment to try on</span>
            </div>
            <div class="upload-placeholder">
              <span class="upload-text">Upload a garment to try on</span>
            </div>
            <div class="upload-placeholder">
              <span class="upload-text">Upload a garment to try on</span>
            </div>
          `;
        }
      }
      console.log('🌐 Switched to page view');
    }
  }

  // Function to update toggle button state based on user and brand page status
  function updateToggleButtonState() {
    const toggleBtn = document.getElementById('garment-source-toggle');
    const toggleText = document.getElementById('toggle-text');
    
    console.log('🔄 updateToggleButtonState called - useGarmentCheckbox:', useGarmentCheckbox, 'currentUser:', !!currentUser, 'currentGarmentSource:', currentGarmentSource);
    
    if (!toggleBtn || !toggleText) {
      console.log('⚠️ Toggle button elements not found');
      return;
    }
    
    // Only show toggle button if on a brand page with garments
    if (!useGarmentCheckbox) {
      // Not a brand page - hide toggle button
      console.log('🙈 Hiding toggle button - not a brand page');
      toggleBtn.style.display = 'none';
      return;
    } else {
      console.log('👁️ Showing toggle button - brand page detected');
      toggleBtn.style.display = 'inline-flex';
    }
    
    if (!currentUser || !currentUser.userID) {
      // Guest user or not signed in - disable wardrobe functionality
      console.log('🚫 Disabling wardrobe functionality - no signed in user');
      toggleBtn.disabled = true;
      toggleBtn.style.opacity = '0.5';
      toggleText.textContent = 'Sign in for Wardrobe';
      toggleBtn.title = 'Sign in to access your wardrobe';
    } else {
      // Signed in user - enable wardrobe functionality
      console.log('✅ Enabling wardrobe functionality - user signed in');
      toggleBtn.disabled = false;
      toggleBtn.style.opacity = '1';
      toggleBtn.title = 'Switch between page garments and your wardrobe';
      
      if (currentGarmentSource === 'wardrobe') {
        console.log('👗➡️🌐 Setting toggle to show page garments');
        toggleText.textContent = 'Show Garments on Page';
      } else {
        console.log('🌐➡️👗 Setting toggle to show wardrobe garments');
        toggleText.textContent = 'Show Garments in Wardrobe';  
      }
    }
  }

  async function performTryOn(garmentImageData, garmentType) {
    console.log(`🎯 performTryOn function called globally!`);
    
    // Check if multiple garments are selected via checkboxes
    const isMultiGarment = selectedGarments && selectedGarments.length > 0;
    const garmentCount = isMultiGarment ? selectedGarments.length : 1;
    
    console.log(`🎯 Starting try-on with ${garmentCount} garment(s)`);
    console.log('👔 Multi-garment mode:', isMultiGarment);
    console.log('🤖 Selected AI Model at start of performTryOn:', selectedAIModel);
    console.log('📸 Garment image data:', garmentImageData ? 'Present' : 'Missing');
    
    const tryonResult = document.getElementById('tryon-result');
    console.log('🔍 tryonResult element exists:', !!tryonResult);
    
    if (!tryonResult) {
      console.error('❌ tryonResult element not found');
      return;
    }
    
    // Get processed avatar from storage
    return new Promise((resolve, reject) => {
      console.log('🔍 Fetching avatar from Chrome storage...');
      
      chrome.storage.local.get(['avatarBgRemovedImg', 'avatarImg', 'avatarDataUrl'], async function(result) {
        console.log('🔍 Storage fetch result:', {
          hasAvatarBgRemovedImg: !!result.avatarBgRemovedImg,
          hasAvatarImg: !!result.avatarImg,
          hasAvatarDataUrl: !!result.avatarDataUrl,
          avatarBgRemovedImgLength: result.avatarBgRemovedImg ? result.avatarBgRemovedImg.length : 0,
          avatarImgLength: result.avatarImg ? result.avatarImg.length : 0,
          avatarDataUrlLength: result.avatarDataUrl ? result.avatarDataUrl.length : 0
        });
        
        const avatarData = result.avatarBgRemovedImg || result.avatarDataUrl || result.avatarImg;
        
        console.log('🔍 Final avatarData selected:', avatarData ? `${avatarData.length} chars` : 'NULL');
        
        if (!avatarData) {
          console.error('❌ No avatar found in storage!');
          console.error('❌ Checked keys: avatarBgRemovedImg, avatarDataUrl, avatarImg');
          console.error('❌ All were empty or undefined');
          tryonResult.innerHTML = '📷 Please upload your photo first';
          showTryonResult();
          reject('No avatar uploaded');
          return;
        }
        
        console.log('✅ Avatar data found in storage, proceeding with try-on');
        
        // Validate garment data (either single garment or multiple selected garments)
        if (!garmentImageData && !isMultiGarment) {
          console.error('❌ No garment image data provided');
          tryonResult.innerHTML = '👕 Please select a garment';
          showTryonResult();
          reject('No garment selected');
          return;
        }
        
        console.log(`✅ Avatar and ${garmentCount} garment(s) present, starting try-on process`);
        
        // Create close button element instead of inline onclick
        const processingCloseBtn = document.createElement('button');
        processingCloseBtn.className = 'tryon-close-btn';
        processingCloseBtn.innerHTML = '&times;';
        processingCloseBtn.addEventListener('click', hideTryonResult);
        
        const processingText = document.createElement('span');
        processingText.className = 'tryon-processing-text';
        processingText.textContent = 'Creating Your Perfect Look...';
        
        tryonResult.innerHTML = '';
        tryonResult.appendChild(processingCloseBtn);
        tryonResult.appendChild(processingText);
        showTryonResult();
        
        try {
          // Always use unified Gemini API for try-ons
          const formData = new FormData();
          
          // Use processed avatar image  
          const avatarBlob = await safeImageToBlob(avatarData);
          formData.append('avatar_image', avatarBlob, 'avatar.png');
          
          // Handle single vs multiple garments
          if (isMultiGarment) {
            // MULTI-GARMENT MODE: Add all selected garments
            console.log(`👔 Multi-garment mode: Processing ${selectedGarments.length} garments`);
            
            for (let i = 0; i < selectedGarments.length; i++) {
              const garment = selectedGarments[i];
              console.log(`🔄 Processing garment ${i + 1}:`, garment.src);
              
              const garmentBlob = await safeImageToBlob(garment.src);
              console.log(`✅ Garment ${i + 1} blob created:`, garmentBlob.size, 'bytes');
              formData.append(`garment_image_${i + 1}`, garmentBlob, `garment_${i + 1}.png`);
              
              // Detect garment type for each garment
              const detectedType = await detectGarmentTypeFromURL(garment.src);
              console.log(`🏷️ Garment ${i + 1} type detected:`, detectedType);
              formData.append(`garment_type_${i + 1}`, detectedType);
            }
          } else {
            // SINGLE-GARMENT MODE: Process the provided garment
            console.log('👕 Single-garment mode: Processing 1 garment');
            
            // Try to remove background from garment, but continue if it fails
            let garmentBgRemovedBlob;
            try {
              const garmentBlob = await safeImageToBlob(garmentImageData);
              const garmentForm = new FormData();
              garmentForm.append('file', garmentBlob, 'garment.png');
              const garmentBgResp = await fetch(`${API_BASE_URL}/api/remove-bg`, {
                method: 'POST',
                body: garmentForm,
              });
              if (garmentBgResp.ok) {
                garmentBgRemovedBlob = await garmentBgResp.blob();
                console.log('✅ Garment background removed successfully');
              } else {
                throw new Error(`Background removal failed: ${garmentBgResp.status}`);
              }
            } catch (bgError) {
              console.warn('⚠️ Background removal failed, using original garment:', bgError.message);
              // Use original garment if background removal fails
              garmentBgRemovedBlob = await safeImageToBlob(garmentImageData);
            }
            
            formData.append('garment_image', garmentBgRemovedBlob, 'garment.png');
            formData.append('garment_type', garmentType === 'upper' ? 'top' : garmentType === 'lower' ? 'bottom' : 'top');
            formData.append('style_prompt', 'realistic virtual try-on with natural lighting');
          }
          
          // Add selected AI model to FormData
          formData.append('ai_model', selectedAIModel);
          console.log(`🤖 Selected AI model being sent: ${selectedAIModel}`);
          
          // Use unified Gemini API for virtual try-on
          const apiUrl = `${API_BASE_URL}/api/tryon-gemini`;
          
          console.log(`Sending try-on request to unified Gemini API with ${garmentCount} garment(s)`);
          console.log('🔗 API URL being used:', apiUrl);
          console.log('📋 FormData contents:', [...formData.entries()].map(([key, value]) => [key, value instanceof Blob ? `${value.type} blob (${value.size} bytes)` : value]));
          
          const response = await fetch(apiUrl, {
            method: 'POST',
            body: formData,
          });
          
          if (!response.ok) {
            tryonResult.innerHTML = '❌ Try-on failed';
            reject('Try-on API failed');
            return;
          }
          
          const tryonBlob = await response.blob();
          const url = URL.createObjectURL(tryonBlob);

          if (!formData.has('transparent_background')) {
            console.log('🔄 Removing background from try-on result...');
            
            // Convert blob to form data for background removal
            const bgRemovalForm = new FormData();
            bgRemovalForm.append('file', tryonBlob, 'tryon-result.png');
            
            const bgRemovalResp = await fetch(`${API_BASE_URL}/api/remove-bg`, {
              method: 'POST',
              body: bgRemovalForm,
            });
            
            if (bgRemovalResp.ok) {
              const transparentBlob = await bgRemovalResp.blob();
              const transparentUrl = URL.createObjectURL(transparentBlob);
              
              const resultCloseBtn = document.createElement('button');
              resultCloseBtn.className = 'tryon-close-btn';
              resultCloseBtn.innerHTML = '&times;';
              resultCloseBtn.addEventListener('click', hideTryonResult);
              
              const resultImg = document.createElement('img');
              resultImg.src = transparentUrl;
              resultImg.alt = 'Try-On Result';
              resultImg.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px;';
              
              tryonResult.innerHTML = '';
              tryonResult.appendChild(resultCloseBtn);
              tryonResult.appendChild(resultImg);
              console.log('✅ Background removed from try-on result');
              
              // Clear selected garments after successful try-on
              if (isMultiGarment) {
                console.log('🧹 Clearing selected garments array');
                selectedGarments = [];
                // Update UI to reflect cleared selection
                document.querySelectorAll('.garment-item-tryon.selected').forEach(item => {
                  item.classList.remove('selected');
                });
                document.querySelectorAll('.garment-checkbox:checked').forEach(checkbox => {
                  checkbox.checked = false;
                });
              }
              
              resolve();
              return;
            }
          }

          // Fallback: Show result with checkered background to indicate transparency
          const fallbackCloseBtn = document.createElement('button');
          fallbackCloseBtn.className = 'tryon-close-btn';
          fallbackCloseBtn.innerHTML = '&times;';
          fallbackCloseBtn.addEventListener('click', hideTryonResult);
          
          const resultImg = document.createElement('img');
          resultImg.src = url;
          resultImg.alt = 'Try-On Result';
          resultImg.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px;';
          
          tryonResult.innerHTML = '';
          tryonResult.appendChild(fallbackCloseBtn);
          tryonResult.appendChild(resultImg);
          console.log('✅ Try-on completed successfully');
          
          // Clear selected garments after successful try-on
          if (isMultiGarment) {
            console.log('🧹 Clearing selected garments array');
            selectedGarments = [];
            // Update UI to reflect cleared selection
            document.querySelectorAll('.garment-item-tryon.selected').forEach(item => {
              item.classList.remove('selected');
            });
            document.querySelectorAll('.garment-checkbox:checked').forEach(checkbox => {
              checkbox.checked = false;
            });
          }
          
          resolve();
          
        } catch (error) {
          console.error('Try-on error:', error.message || error);
          
          // Better error handling with specific messages
          let errorMessage = '❌ Try-on failed';
          
          if (error.message && error.message.includes('CORS policy')) {
            errorMessage = '🚫 Cannot access external image due to browser security policy. Please try uploading the image directly.';
          } else if (error.message && error.message.includes('ERR_CONNECTION_TIMED_OUT')) {
            errorMessage = `🔌 Server connection timed out. Please check if the backend server at ${API_BASE_URL} is running and accessible.`;
          } else if (error.message && error.message.includes('Failed to fetch')) {
            errorMessage = `🔌 Cannot connect to try-on server. Please verify the server is running at ${API_BASE_URL}.`;
          } else if (error.message && error.message.includes('Proxy fetch failed')) {
            errorMessage = '🌐 Failed to load external image. The image source may not be accessible.';
          } else if (error.message) {
            errorMessage = `❌ Try-on failed: ${error.message}`;
          }
          
          const errorCloseBtn = document.createElement('button');
          errorCloseBtn.className = 'tryon-close-btn';
          errorCloseBtn.innerHTML = '&times;';
          errorCloseBtn.addEventListener('click', hideTryonResult);
          
          const errorText = document.createElement('div');
          errorText.innerHTML = errorMessage;
          errorText.style.cssText = 'color: white; padding: 16px; text-align: center; background: rgba(0,0,0,0.8); border-radius: 8px; margin: 20px; font-size: 14px; line-height: 1.4;';
          
          tryonResult.innerHTML = '';
          tryonResult.appendChild(errorCloseBtn);
          tryonResult.appendChild(errorText);
          
          reject(error);
        }
      });
    });
  }

  // Helper functions that need to be global
  function showTryonResult() {
    const tryonResult = document.getElementById('tryon-result');
    const tryonBody = document.querySelector('.tryon-body');
    if (tryonResult) {
      tryonResult.style.display = 'block';
    }
    if (tryonBody) {
      tryonBody.style.display = 'flex';
    }
  }

  function hideTryonResult() {
    const tryonResult = document.getElementById('tryon-result');
    const tryonBody = document.querySelector('.tryon-body');
    
    // Clean up any blob URLs in the try-on result
    if (tryonResult) {
      const images = tryonResult.querySelectorAll('img');
      images.forEach(img => {
        if (img.src && img.src.startsWith('blob:')) {
          URL.revokeObjectURL(img.src);
        }
      });
      tryonResult.style.display = 'none';
    }
    if (tryonBody) {
      tryonBody.style.display = 'none';
    }
  }

  // Function to display images with pagination
  function displayImagesInPlaceholders(images) {
    console.log('🖼️ displayImagesInPlaceholders called with:', images.length, 'images');
    
    // Set display mode flag to online
    currentDisplayMode = 'online';
    console.log('🔄 Display mode set to:', currentDisplayMode);
    
    const garmentPreview = document.getElementById('garment-preview');
    console.log('🎯 garmentPreview element:', garmentPreview);
    
    if (!garmentPreview) {
      console.error('❌ garment-preview element not found!');
      return;
    }
    
    // Check if this is a wardrobe fallback call to prevent infinite loop
    const isWardrobeFallback = images.some(img => img.isWardrobeFallback);
    
    // Filter out transparent/placeholder images and take valid ones
    const validImages = images.filter(img => 
      img && img.src && 
      !img.src.includes('transparent-background.png') &&
      !img.src.includes('placeholder') &&
      (img.isWardrobeFallback || (img.width > 50 && img.height > 50)) // Allow wardrobe items through even without size check
    );
    
    console.log('🔍 Filtered valid images:', validImages.length, 'from', images.length, 'total');
    
    // ✨ ENHANCED: If no valid images found from URL or page, fallback to database wardrobe
    // But only if this isn't already a wardrobe fallback call
    if (validImages.length === 0 && !isWardrobeFallback) {
      console.log('📦 No valid images from URL/page - loading wardrobe items as fallback...');
      loadWardrobeAsFallback();
      return;
    } else if (validImages.length === 0 && isWardrobeFallback) {
      console.log('⚠️ Wardrobe fallback also returned no items - showing empty state');
      showEmptyPlaceholders('No items available. Upload garments or add to wardrobe!');
      return;
    }
    
    // Store all images for pagination
    allExtractedImages = validImages;
    currentImagePage = 0;
    
    // Render the current page
    renderImagePage();
    
    // Update toggle button state now that we have extracted garments
    if (validImages.length > 0) {
      setTimeout(() => {
        updateToggleButtonState();
      }, 100);
    }
  }

  // Function to render a specific page of images
  function renderImagePage() {
    const garmentPreview = document.getElementById('garment-preview');
    const garmentNavigation = document.getElementById('garment-navigation');
    const pageIndicator = document.getElementById('page-indicator');
    const prevBtn = document.getElementById('prev-images-btn');
    const nextBtn = document.getElementById('next-images-btn');
    
    if (!garmentPreview) return;
    
    // Make sure garment preview is visible
    garmentPreview.style.display = 'grid';
    
    const totalPages = Math.max(1, Math.ceil(allExtractedImages.length / imagesPerPage));
    const startIndex = currentImagePage * imagesPerPage;
    const endIndex = Math.min(startIndex + imagesPerPage, allExtractedImages.length);
    const currentImages = allExtractedImages.slice(startIndex, endIndex);
    
    console.log(`📋 Rendering page ${currentImagePage + 1}/${totalPages}, showing images ${startIndex + 1}-${Math.max(1, endIndex)}`);
    
    // Update navigation visibility and state
    if (garmentNavigation && totalPages > 1 && allExtractedImages.length > 0) {
      garmentNavigation.style.display = 'flex';
      
      // Update page indicator
      if (pageIndicator) {
        if (allExtractedImages.length > 0) {
          pageIndicator.textContent = `${currentImagePage + 1} / ${totalPages} (${allExtractedImages.length} total)`;
        } else {
          pageIndicator.textContent = 'No images found';
        }
      }
      
      // Update button states
      if (prevBtn) {
        prevBtn.disabled = currentImagePage === 0;
      }
      
      if (nextBtn) {
        nextBtn.disabled = currentImagePage >= totalPages - 1;
      }
    } else if (garmentNavigation) {
      garmentNavigation.style.display = 'none';
    }
    
    // Build image grid
    let gridHtml = '';
    for (let i = 0; i < imagesPerPage; i++) {
      if (i < currentImages.length) {
        const imgSrc = currentImages[i].src;
        const imageNumber = startIndex + i + 1;
        const isInWardrobe = isGarmentInWardrobe(imgSrc);
        console.log(`🖼️ Adding image ${imageNumber}:`, imgSrc);
        
        const isSelected = selectedGarments.some(g => g.src === imgSrc);
        
        gridHtml += `
          <div class="upload-placeholder garment-item-tryon ${isInWardrobe ? 'favorited' : ''} ${isSelected ? 'selected' : ''}" style="position: relative; background: #f0f0f0; cursor: pointer;" data-image-src="${imgSrc}">
            <img src="${imgSrc}" 
                 alt="Garment ${imageNumber}" 
                 style="width: 100%; height: 100%; object-fit: cover; border-radius: 15px;" 
                 onerror="console.error('❌ Failed to load image:', this.src); this.style.display='none'; this.nextElementSibling.style.display='flex';"
                 onload="console.log('✅ Image loaded successfully:', this.src);" />
            <span class="upload-text" style="display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(255,0,0,0.8); color: white; padding: 4px; border-radius: 4px; font-size: 10px;">Failed</span>
            
            <!-- Checkbox for Multi-Selection -->
            <div class="garment-checkbox-container" style="position: absolute; top: 8px; left: 8px; z-index: 10;">
              <input type="checkbox" class="garment-checkbox" ${isSelected ? 'checked' : ''} 
                     style="width: 20px; height: 20px; cursor: pointer; accent-color: #4CAF50;" 
                     data-garment-src="${imgSrc}" />
            </div>
            
            <!-- Favorite Button -->
            <button class="favorite-btn ${isInWardrobe ? 'favorited' : ''}" type="button">
              <span class="heart-icon">${isInWardrobe ? '♥' : '♡'}</span>
            </button>
            
            <!-- Image Number Badge -->
            <div style="position: absolute; bottom: 2px; right: 2px; background: rgba(0,0,0,0.7); color: white; padding: 2px 4px; border-radius: 2px; font-size: 10px;">
              ${imageNumber}
            </div>
            
            <!-- Try-on Hover Badge -->
            <div class="tryon-hover-badge" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; opacity: 0; transition: opacity 0.3s ease; pointer-events: none;">
              Try On
            </div>
            
          </div>
        `;
      } else {
        gridHtml += `
          <div class="upload-placeholder">
            <span class="upload-text">Empty</span>
          </div>
        `;
      }
    }
    
    // Set only the grid content
    garmentPreview.innerHTML = gridHtml;
    
    // Add event listeners for try-on functionality, checkboxes, and favorite buttons
    const tryonItems = garmentPreview.querySelectorAll('.garment-item-tryon');
    tryonItems.forEach((item, index) => {
      const actualIndex = startIndex + index;
      if (actualIndex < allExtractedImages.length) {
        const imgSrc = allExtractedImages[actualIndex].src;
        
        // Add try-on click listener to the image
        const img = item.querySelector('img');
        if (img) {
          img.addEventListener('click', async () => {
            console.log('🎯 Try-on clicked for image:', imgSrc);
            await handleImageTryOn(imgSrc);
          });
        }
        
        // Add checkbox change listener
        const checkbox = item.querySelector('.garment-checkbox');
        if (checkbox) {
          checkbox.addEventListener('change', (e) => {
            e.stopPropagation(); // Prevent triggering try-on
            handleGarmentCheckboxChange(e.target.checked, imgSrc);
          });
        }
        
        // Favorite button handling is now done via delegated event listener
        // No need for direct event listeners here
      }
    });
    
    // Update multi-garment try-on button visibility
    updateMultiTryOnButton();
    
    console.log('✅ Image page rendered successfully with', tryonItems.length, 'try-on items');
    
    // Force a reflow to ensure images are displayed
    garmentPreview.offsetHeight;
    console.log('🔄 Forced reflow completed');
  }

  // Function to render a specific page of wardrobe items
  function renderWardrobePage() {
    const garmentPreview = document.getElementById('garment-preview');
    const garmentNavigation = document.getElementById('garment-navigation');
    const pageIndicator = document.getElementById('page-indicator');
    const prevBtn = document.getElementById('prev-images-btn');
    const nextBtn = document.getElementById('next-images-btn');
    
    if (!garmentPreview) return;
    
    // Make sure garment preview is visible
    garmentPreview.style.display = 'grid';
    
    const totalPages = Math.ceil(allWardrobeItems.length / wardrobeItemsPerPage);
    const startIndex = currentWardrobePage * wardrobeItemsPerPage;
    const endIndex = Math.min(startIndex + wardrobeItemsPerPage, allWardrobeItems.length);
    const currentItems = allWardrobeItems.slice(startIndex, endIndex);
    
    console.log(`👗 Rendering wardrobe page ${currentWardrobePage + 1}/${totalPages}, showing items ${startIndex + 1}-${endIndex}`);
    
    // Update navigation visibility and state
    if (garmentNavigation && totalPages > 1) {
      garmentNavigation.style.display = 'flex';
      
      // Update page indicator
      if (pageIndicator) {
        pageIndicator.textContent = `${currentWardrobePage + 1} / ${totalPages} (${allWardrobeItems.length} wardrobe items)`;
      }
      
      // Update button states
      if (prevBtn) {
        prevBtn.disabled = currentWardrobePage === 0;
      }
      
      if (nextBtn) {
        nextBtn.disabled = currentWardrobePage >= totalPages - 1;
      }
    } else if (garmentNavigation) {
      garmentNavigation.style.display = 'none';
    }
    
    // Build wardrobe item grid using unified garment item structure
    let gridHtml = '';
    for (let i = 0; i < wardrobeItemsPerPage; i++) {
      if (i < currentItems.length) {
        const item = currentItems[i];
        const itemNumber = startIndex + i + 1;
        
        // Use the unified garment item HTML generator for wardrobe items
        gridHtml += createGarmentItemHTML({
          src: item.garment_image,
          title: item.garment_type.toUpperCase(),
          price: '', // Wardrobe items don't have price
          store: 'Wardrobe',
          isFavorited: true, // All wardrobe items are favorited by definition
          additionalClasses: 'wardrobe-item',
          source: 'wardrobe',
          itemNumber: itemNumber,
          wardrobeId: item.id
        });
      } else {
        gridHtml += `
          <div class="upload-placeholder">
            <span class="upload-text">No more wardrobe items</span>
          </div>
        `;
      }
    }
    
    // Set the grid content
    garmentPreview.innerHTML = gridHtml;
    
    // Add event listeners for wardrobe items
    const wardrobeItemsElements = garmentPreview.querySelectorAll('[data-wardrobe-item]');
    wardrobeItemsElements.forEach(element => {
      const itemId = element.dataset.wardrobeItem;
      const wardrobeItem = allWardrobeItems.find(item => item.id.toString() === itemId);
      
      if (wardrobeItem) {
        // Add try-on click listener to the image
        const img = element.querySelector('img');
        if (img) {
          img.addEventListener('click', async (e) => {
            // Don't trigger if clicking on favorite button
            if (e.target.classList.contains('favorite-btn') || 
                e.target.classList.contains('heart-icon')) {
              return;
            }
            
            console.log('🎯 Try-on clicked for wardrobe item:', wardrobeItem.garment_id);
            await performTryOn(wardrobeItem.garment_image, wardrobeItem.garment_type);
          });
        }
        
        // Favorite button handling is now done via delegated event listener
        // No need for direct event listeners here
      }
    });
    
    console.log('✅ Wardrobe page rendered successfully with', wardrobeItemsElements.length, 'wardrobe items');
    
    // Force a reflow to ensure items are displayed
    garmentPreview.offsetHeight;
    console.log('🔄 Forced reflow completed');
  }

  // Check if user is already signed in
  chrome.storage.local.get(['userSignedIn', 'userEmail', 'userId', 'userProfile', 'isGuest'], function(result) {
    if (result.userSignedIn) {
      // Set current user for wardrobe functionality (only for non-guest users)
      if (!result.isGuest && result.userId) {
        currentUser = {
          userID: result.userId,
          email: result.userEmail,
          profile: result.userProfile
        };
        console.log('👤 Existing user loaded for wardrobe:', currentUser);
        
        // Load user's wardrobe items
        loadUserWardrobe();
      } else {
        console.log('👤 Guest user - no wardrobe access');
        currentUser = null;
      }
      
      showMainApp();
    } else {
      showSignInPage();
    }
  });

  // Sign In Button Handler
  console.log('🔧 [LOGIN] Attaching event listener to signinBtn:', signinBtn);
  
  if (!signinBtn) {
    console.error('❌ [LOGIN] signinBtn element not found! Cannot attach event listener.');
  } else {
    console.log('✅ [LOGIN] signinBtn found, attaching click event listener');
  }
  
  signinBtn.addEventListener('click', async function() {
    console.log('🔐 [LOGIN] Sign In button clicked!');
    console.log('📧 [LOGIN] Email field value:', signinEmail?.value);
    console.log('🔑 [LOGIN] Password field exists:', !!signinPassword);
    
    const email = signinEmail.value.trim();
    const password = signinPassword.value.trim();

    if (!email || !password) {
      signinBtn.innerHTML = '⚠️ Please fill all fields';
      setTimeout(() => {
        signinBtn.innerHTML = '🔐 Sign In';
      }, 2000);
      return;
    }

    signinBtn.innerHTML = 'Signing In ...';
    signinBtn.disabled = true;

    try {
      console.log('🌐 [LOGIN] Calling login API...');
      console.log('🌐 [LOGIN] API URL:', `${API_BASE_URL}/api/login`);
      console.log('📤 [LOGIN] Sending credentials:', { email, password: '***' });
      
      // Call the login API
      const response = await fetch(`${API_BASE_URL}/api/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email,
          password: password
        })
      });
      
      console.log('📥 [LOGIN] Response received:', response.status, response.statusText);

      const result = await response.json();

      if (result.success) {
        console.log('✅ Login successful:', result.user_data);
        
        // Store user session with complete user data
        const userData = {
          userSignedIn: true,
          userEmail: email,
          userId: result.user_data.userid,
          userProfile: {
            firstname: result.user_data.first_name,
            lastname: result.user_data.last_name,
            age: result.user_data.age,
            gender: result.user_data.gender,
            weight: result.user_data.weight,
            height: result.user_data.height,
            physique: result.user_data.physique
          },
          signInTime: Date.now()
        };

        chrome.storage.local.set(userData);

        // Set current user for wardrobe functionality
        currentUser = {
          userID: result.user_data.userid,
          email: email,
          profile: userData.userProfile
        };
        console.log('👤 User signed in for wardrobe:', currentUser);

        signinBtn.innerHTML = 'Loading avatar...';
        
        // Load avatar from database if it exists
        await loadAvatarAfterSignIn(result.user_data.userid);

        // Load user's wardrobe items
        await loadUserWardrobe();

        signinBtn.innerHTML = 'Success!';
        setTimeout(() => {
          showMainApp();
        }, 500);

      } else {
        console.error('❌ Login failed:', result.error);
        signinBtn.innerHTML = `❌ ${result.error}`;
        signinBtn.disabled = false;
        setTimeout(() => {
          signinBtn.innerHTML = '🔐 Sign In';
        }, 2000);
      }

    } catch (error) {
      console.error('❌ Login error:', error);
      signinBtn.innerHTML = 'Connection failed';
      signinBtn.disabled = false;
      setTimeout(() => {
        signinBtn.innerHTML = '🔐 Sign In';
      }, 2000);
    }
  });

  // Guest Button Handler
  guestBtn.addEventListener('click', function() {
    chrome.storage.local.set({ 
      userSignedIn: true, 
      userEmail: 'guest@enable.com',
      isGuest: true,
      signInTime: Date.now()
    });
    
    // Set guest user but disable wardrobe functionality
    currentUser = null; // Guests don't have wardrobe access
    
    showMainApp();
  });

  // Garment Source Toggle Button Handler
  const garmentSourceToggle = document.getElementById('garment-source-toggle');
  console.log('🔍 Toggle button found:', !!garmentSourceToggle);
  
  if (garmentSourceToggle) {
    garmentSourceToggle.addEventListener('click', function() {
      console.log('🎯 Toggle button clicked! Current state:', {
        useGarmentCheckbox,
        currentUser: !!currentUser,
        currentUserID: currentUser?.userID,
        currentGarmentSource,
        wardrobeItemsLength: wardrobeItems.length
      });
      
      // Only show toggle on brand pages
      if (!useGarmentCheckbox) {
        console.log('⚠️ Toggle only available on brand pages - useGarmentCheckbox is false');
        alert('Toggle only available on brand pages with garments');
        return;
      }
      
      // Only allow wardrobe toggle if user is signed in
      if (!currentUser || !currentUser.userID) {
        console.log('⚠️ Please sign in to access wardrobe - currentUser:', currentUser);
        alert('Please sign in to access your wardrobe');
        return;
      }
      
      console.log('✅ All checks passed, proceeding with toggle');
      
      if (currentGarmentSource === 'page') {
        // Switch to wardrobe - load wardrobe items if not loaded
        console.log('🌐➡️👗 Switching to wardrobe, wardrobeItems.length:', wardrobeItems.length);
        if (wardrobeItems.length === 0) {
          console.log('📥 Loading wardrobe items first...');
          loadUserWardrobe().then(() => {
            console.log('✅ Wardrobe loaded, calling toggleGarmentSource');
            toggleGarmentSource();
          });
        } else {
          console.log('✅ Wardrobe already loaded, calling toggleGarmentSource');
          toggleGarmentSource();
        }
      } else {
        // Switch back to page garments
        console.log('👗➡️🌐 Switching to page garments');
        toggleGarmentSource();
      }
    });
  } else {
    console.error('❌ Toggle button not found in DOM!');
  }

  // AI Model Selection Dropdown Handler
  const aiModelSelect = document.getElementById('ai-model-select');
  console.log('🤖 AI Model selector found:', !!aiModelSelect);
  
  if (aiModelSelect) {
    aiModelSelect.addEventListener('change', function() {
      selectedAIModel = this.value;
      console.log('🤖 AI Model selected:', selectedAIModel);
      
      // Visual feedback for model selection
      if (selectedAIModel === 'gemini') {
        this.style.borderColor = '#4285F4'; // Google blue
        this.style.backgroundColor = 'rgba(66, 133, 244, 0.1)';
      } else {
        this.style.borderColor = '#003500';
        this.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
      }
    });
    
    // Set initial value
    selectedAIModel = aiModelSelect.value;
  } else {
    console.error('❌ AI Model selector not found in DOM!');
  }

  // Enter key handler for sign-in
  signinPassword.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      signinBtn.click();
    }
  });

  // Show account creation page
  if (createAccountLink) {
    createAccountLink.addEventListener('click', function(e) {
      e.preventDefault();
      showAccountCreationPage();
    });
  }

  // Back to signin page
  if (backToSigninLink) {
    backToSigninLink.addEventListener('click', function(e) {
      e.preventDefault();
      showSignInPage();
    });
  }

  // Handle account creation
  if (createAccountBtn) {
    createAccountBtn.addEventListener('click', function(e) {
      e.preventDefault();
      handleAccountCreation();
    });
  }

  async function handleAccountCreation() {
    console.log('Account creation submitted');
    
    // Get form values
    const email = createEmail.value.trim();
    const firstname = createFirstname.value.trim();
    const lastname = createLastname.value.trim();
    const password = createPassword.value;
    const age = createAge.value;
    const gender = createGender.value;
    const weight = createWeight.value;
    const height = createHeight.value;
    const physique = document.querySelector('input[name="physique"]:checked')?.value;
    
    // Validate required fields
    if (!email || !firstname || !lastname || !password || !age || !gender || !weight || !height || !physique) {
      alert('Please fill in all required fields');
      return;
    }
    
    // Show loading state
    createAccountBtn.innerHTML = 'Creating Account...';
    createAccountBtn.disabled = true;
    
    try {
      // Prepare account data
      const accountData = {
        email: email,
        firstname: firstname,
        lastname: lastname,
        password: password,
        age: parseInt(age),
        gender: gender,
        weight: parseFloat(weight),
        height: parseFloat(height),
        physique: physique
      };
      
      console.log('Sending account data to API:', accountData);
      
      // Call the create account API
      const response = await fetch(`${API_BASE_URL}/api/create-account`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(accountData)
      });
      
      const result = await response.json();
      
      if (result.success) {
        console.log('Account created successfully:', result);
        
        // Store user data in Chrome storage
        chrome.storage.local.set({
          userEmail: result.user_data.email,
          userId: result.user_data.userid,
          userSignedIn: true,
          userProfile: {
            firstname: result.user_data.first_name,
            lastname: result.user_data.last_name,
            age: result.user_data.age,
            gender: result.user_data.gender,
            weight: result.user_data.weight,
            height: result.user_data.height,
            physique: result.user_data.physique
          },
          signInTime: Date.now()
        });
        
        alert('Account created successfully! Welcome to Enable Virtual Try-On.');
        
        // Show main app
        showMainApp();
        
      } else {
        console.error('Account creation failed:', result.error);
        alert(`Account creation failed: ${result.error}`);
      }
      
    } catch (error) {
      console.error('Account creation error:', error);
      alert('Account creation failed. Please check your connection and try again.');
    } finally {
      // Reset button state
      createAccountBtn.innerHTML = 'Create Account';
      createAccountBtn.disabled = false;
    }
  }

  async function saveAvatarToDatabase(imageData, userId) {
    try {
      console.log('💾 Saving avatar to database for user:', userId);
      
      // Convert data URL to base64
      const base64Data = imageData.split(',')[1];
      
      const response = await fetch(`${API_BASE_URL}/api/update-avatar`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          avatar_data: imageData
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        console.log('✅ Avatar saved to database successfully');
        return true;
      } else {
        console.error('❌ Failed to save avatar to database:', result.error);
        return false;
      }
      
    } catch (error) {
      console.error('❌ Error saving avatar to database:', error);
      return false;
    }
  }

  // Function to load avatar from database
  async function loadAvatarFromDatabase(userId) {
    try {
      console.log('📥 Loading avatar from database for user:', userId);
      
      const response = await fetch(`${API_BASE_URL}/api/get-avatar/${userId}`);
      
      if (response.ok) {
        const blob = await response.blob();
        const imageUrl = URL.createObjectURL(blob);
        console.log('✅ Avatar loaded from database successfully');
        return imageUrl;
      } else {
        console.log('ℹ️ No avatar found in database');
        return null;
      }
      
    } catch (error) {
      console.error('❌ Error loading avatar from database:', error);
      return null;
    }
  }

  // Function to load avatar after sign-in and set it in the UI
  async function loadAvatarAfterSignIn(userId) {
    try {
      console.log('🔄 Loading avatar after sign-in for user:', userId);
      
      const avatarUrl = await loadAvatarFromDatabase(userId);
      
      if (avatarUrl) {
        // Convert the blob URL to a data URL for storage
        const response = await fetch(avatarUrl);
        const blob = await response.blob();
        
        return new Promise((resolve) => {
          const reader = new FileReader();
          reader.onload = function(e) {
            const avatarDataUrl = e.target.result;
            
            // Store avatar in Chrome storage for immediate use
            chrome.storage.local.set({ 
              avatarDataUrl: avatarDataUrl 
            }, () => {
              console.log('✅ Avatar loaded and stored for sign-in');
              resolve(avatarDataUrl);
            });
          };
          reader.readAsDataURL(blob);
        });
      } else {
        console.log('ℹ️ No avatar found for user after sign-in');
        return null;
      }
      
    } catch (error) {
      console.error('❌ Error loading avatar after sign-in:', error);
      return null;
    }
  }


  // User Profile Page Event Handlers
  if (userBtn) {
    userBtn.addEventListener('click', function(e) {
      e.preventDefault();
      showUserProfilePage();
    });
  }

  if (backToMainLink) {
    backToMainLink.addEventListener('click', function(e) {
      e.preventDefault();
      showMainApp();
    });
  }

  if (editProfileBtn) {
    editProfileBtn.addEventListener('click', function(e) {
      e.preventDefault();
      enableProfileEditing();
    });
  }

  if (saveProfileBtn) {
    saveProfileBtn.addEventListener('click', function(e) {
      e.preventDefault();
      handleProfileUpdate();
    });
  }

  if (cancelEditBtn) {
    cancelEditBtn.addEventListener('click', function(e) {
      e.preventDefault();
      cancelProfileEditing();
    });
  }

  function showSignInPage() {
    signinPage.style.display = 'flex';
    mainApp.style.display = 'none';
    if (accountCreationPage) accountCreationPage.style.display = 'none';
    if (userProfilePage) userProfilePage.style.display = 'none';
  }

  function showAccountCreationPage() {
    console.log('Showing account creation page');
    signinPage.style.display = 'none';
    mainApp.style.display = 'none';
    if (userProfilePage) userProfilePage.style.display = 'none';
    accountCreationPage.style.display = 'flex';
  }

  function showUserProfilePage() {
    console.log('Showing user profile page');
    signinPage.style.display = 'none';
    mainApp.style.display = 'none';
    if (accountCreationPage) accountCreationPage.style.display = 'none';
    userProfilePage.style.display = 'flex';
    
    // Load user data when showing profile page
    loadUserProfile();
  }

    // ===== AVATAR FUNCTIONS =====
  function renderAvatarPreview(avatarImageSrc = null) {
    const avatarPreview = document.getElementById('avatar-preview');
    if (!avatarPreview) {
      console.log('avatarPreview element not found');
      return;
    }
    
    const overlayButtons = `
      <button id="avatar-upload-btn" class="avatar-upload-camera-overlay" style="background: none; border: none; padding: 0; cursor: pointer;">
        <img src="camera.png" alt="Avatar Upload" style="width: 100%; height: 100%; object-fit: contain;" />
      </button>`;
    
    if (avatarImageSrc) {
      avatarPreview.innerHTML = `<img src="${avatarImageSrc}" alt="Avatar" class="avatar-display-image" />${overlayButtons}`;
      avatarPreview.classList.add('has-avatar');
    } else {
      avatarPreview.innerHTML = overlayButtons;
      avatarPreview.classList.remove('has-avatar');
    }
  }

  // Helper function to compress image to reduce storage size
  async function compressImage(dataUrl, maxSizeKB = 500) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = function() {
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;
        
        // Reduce dimensions if image is too large
        const maxDimension = 800;
        if (width > maxDimension || height > maxDimension) {
          if (width > height) {
            height = (height / width) * maxDimension;
            width = maxDimension;
          } else {
            width = (width / height) * maxDimension;
            height = maxDimension;
          }
        }
        
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);
        
        // Try different quality levels to meet size requirement
        let quality = 0.9;
        let compressed = canvas.toDataURL('image/jpeg', quality);
        
        while (compressed.length > maxSizeKB * 1024 && quality > 0.1) {
          quality -= 0.1;
          compressed = canvas.toDataURL('image/jpeg', quality);
        }
        
        console.log(`📦 Compressed image: ${dataUrl.length} → ${compressed.length} bytes (${Math.round(compressed.length / 1024)}KB)`);
        resolve(compressed);
      };
      img.src = dataUrl;
    });
  }

  async function processAvatarUpload(imgData) {
    console.log('🔄 processAvatarUpload called');
    
    // Get avatarPreview element (it's inside initializeMainApp scope, so we fetch it here)
    const avatarPreview = document.getElementById('avatar-preview');
    
    // Show loading state with message (same style as try-on)
    if (avatarPreview) {
      avatarPreview.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; height: 100%; border-radius: 15px;">
          <span class="tryon-processing-text">Creating Your Digital Avatar Look...</span>
        </div>
      `;
    }
    
    // Don't store full base64 in storage initially - wait for processed version
    // This prevents quota exceeded errors
    console.log('⏳ Skipping initial storage to avoid quota issues');
    
    let avatarFile = imgData;
    
    try {
      // Remove background from avatar
      const avatarBlob = await fetch(imgData).then(res => res.blob());
      const avatarForm = new FormData();
      
      // Choose API endpoint based on selected AI model
      let bgRemovalEndpoint;
      let formFieldName;
      
      if (selectedAIModel === 'rembg') {
        bgRemovalEndpoint = `${API_BASE_URL}/api/remove-bg-rembg`;
        formFieldName = 'image';
        avatarForm.append('image', avatarBlob, 'avatar.png');
        console.log('🤖 Using Rembg model for background removal');
      } else if (selectedAIModel === 'gemini') {
        bgRemovalEndpoint = `${API_BASE_URL}/api/remove-person-bg`;
        formFieldName = 'image';
        avatarForm.append('image', avatarBlob, 'avatar.png');
        console.log('🤖 Using Gemini model for background removal');
      } else {
        bgRemovalEndpoint = `${API_BASE_URL}/api/remove-bg`;
        formFieldName = 'file';
        avatarForm.append('file', avatarBlob, 'avatar.png');
        console.log('🤖 Using Garmash model for background removal');
      }
      
      const avatarBgResp = await fetch(bgRemovalEndpoint, {
        method: 'POST',
        body: avatarForm,
      });
      
      if (!avatarBgResp.ok) {
        const errorText = await avatarBgResp.text();
        console.error(`❌ Background removal failed (${selectedAIModel}):`, errorText);
        renderAvatarPreview();
        if (avatarPreview) {
          const cameraOverlay = avatarPreview.querySelector('.avatar-upload-camera-overlay');
          if (cameraOverlay) {
            cameraOverlay.insertAdjacentHTML('beforebegin', `❌ Failed to process avatar with ${selectedAIModel}`);
          }
        }
        return;
      }
      
      const avatarBgRemovedBlob = await avatarBgResp.blob();
      const bgReader = new FileReader();
      
      bgReader.onloadend = async function() {
        const processedAvatarData = bgReader.result;
        
        // Wait a moment before showing the avatar
        await new Promise(resolve => setTimeout(resolve, 300));
        
        renderAvatarPreview(processedAvatarData);
        
        // Compress avatar before storing to avoid quota errors
        console.log('🗜️ Compressing avatar for storage...');
        const compressedAvatar = await compressImage(processedAvatarData, 400); // Max 400KB
        
        // Store compressed version in local storage
        await new Promise((resolve) => {
          chrome.storage.local.set({ 
            avatarDataUrl: compressedAvatar
          }, () => {
            if (chrome.runtime.lastError) {
              console.error('❌ Storage error:', chrome.runtime.lastError);
              console.log('⚠️ Will rely on database storage only.');
            } else {
              console.log('✅ Compressed avatar stored successfully');
            }
            resolve();
          });
        });
        
        avatarFile = processedAvatarData;
        
        console.log(`✅ Avatar background removed successfully using ${selectedAIModel}`);
        console.log('✅ avatarFile variable set, length:', processedAvatarData.length);
        
        // Verify storage immediately after setting
        chrome.storage.local.get(['avatarDataUrl'], (verifyResult) => {
          console.log('🔍 Verification - Avatar in storage:', {
            avatarDataUrl: verifyResult.avatarDataUrl ? verifyResult.avatarDataUrl.length : 'NOT SET (Will use database instead)'
          });
        });
        
        // Save processed avatar to database
        chrome.storage.local.get(['userId'], async function(result) {
          if (result.userId) {
            console.log('💾 Saving processed avatar to database');
            const saved = await saveAvatarToDatabase(processedAvatarData, result.userId);
            if (saved) {
              console.log('✅ Processed avatar saved to database and local storage updated');
            } else {
              console.error('❌ Failed to save avatar to database');
            }
          } else {
            console.log('ℹ️ No user logged in - avatar saved to local storage only');
          }
        });
      };
      
      bgReader.readAsDataURL(avatarBgRemovedBlob);
    } catch (error) {
      console.error(`Error processing avatar with ${selectedAIModel}:`, error.message || error);
      
      // Show error message in avatar preview
      if (avatarPreview) {
        avatarPreview.innerHTML = `
          <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); border-radius: 15px; color: white; padding: 20px; text-align: center;">
            <div style="font-size: 40px; margin-bottom: 15px;">❌</div>
            <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">Processing Failed</div>
            <div style="font-size: 12px; opacity: 0.9; margin-bottom: 10px;">Failed to process with ${selectedAIModel}</div>
            <div style="font-size: 10px; opacity: 0.8; line-height: 1.4;">Check your connection and try again</div>
            <button id="avatar-upload-btn" class="avatar-upload-camera-overlay" style="margin-top: 15px; background: white; color: #f5576c; padding: 8px 16px; border-radius: 8px; border: none; cursor: pointer; font-weight: 600; font-size: 12px;">
              Try Again
            </button>
          </div>
        `;
      }
    }
  }

  function initializeMainApp() {
    console.log('🚀 Initializing main app...');
    
    // ===== DOM ELEMENTS =====
    // URL and Use Garment logic
    const pageUrlInput = document.getElementById('page-url');
    
    // ===== VARIABLES =====
    // Avatar upload and persistence
    const avatarUpload = document.getElementById('avatar-upload');
    const avatarPreview = document.getElementById('avatar-preview');
    let avatarFile = null;
    let avatarBgRemovedBlob = null;

    // UI containers
    const tryonBody = document.querySelector('.tryon-body');
    const tryonResult = document.getElementById('tryon-result');
    const signoutBtn = document.getElementById('signout-btn');
    const refreshBtn = document.getElementById('refresh-btn');

    // Garment upload elements
    const upperGarmentBtn = document.getElementById('upper-garment-btn');
    const lowerGarmentBtn = document.getElementById('lower-garment-btn');
    const garmentUpload = document.getElementById('garment-upload');
    const garmentPreview = document.getElementById('garment-preview');

    // Navigation elements
    const prevImagesBtn = document.getElementById('prev-images-btn');
    const nextImagesBtn = document.getElementById('next-images-btn');

    let garmentImgData = null;
    let garmentBgRemovedBlob = null;
    let selectedGarmentType = 'upper'; // Default to upper garment
    let uploadedGarments = []; // Array to store multiple uploaded garments

    // Debug: Log which elements are missing
    if (!upperGarmentBtn) console.log('Warning: upper-garment-btn element not found');
    if (!lowerGarmentBtn) console.log('Warning: lower-garment-btn element not found');
    if (!garmentUpload) console.log('Warning: garment-upload element not found');
    if (!garmentPreview) console.log('Warning: garment-preview element not found');

    // ===== NAVIGATION EVENT LISTENERS =====
    if (prevImagesBtn) {
      prevImagesBtn.addEventListener('click', () => {
        console.log('🔙 Previous button clicked - currentDisplayMode:', getCurrentDisplayMode());
        
        if (getCurrentDisplayMode() === 'wardrobe') {
          // Handle wardrobe pagination
          if (currentWardrobePage > 0) {
            currentWardrobePage--;
            console.log('📖 Going to wardrobe page:', currentWardrobePage + 1);
            renderWardrobePage();
          }
        } else if (getCurrentDisplayMode() === 'explorer') {
          // Handle explorer results pagination
          if (currentImagePage > 0) {
            currentImagePage--;
            console.log('📖 Going to explorer results page:', currentImagePage + 1);
            renderExplorerResults();
          }
        } else {
          // Handle online images pagination
          if (currentImagePage > 0) {
            currentImagePage--;
            console.log('📖 Going to image page:', currentImagePage + 1);
            renderImagePage();
          }
        }
      });
    }

    if (nextImagesBtn) {
      nextImagesBtn.addEventListener('click', () => {
        console.log('▶️ Next button clicked - currentDisplayMode:', getCurrentDisplayMode());
        
        if (getCurrentDisplayMode() === 'wardrobe') {
          // Handle wardrobe pagination
          const totalPages = Math.ceil(allWardrobeItems.length / wardrobeItemsPerPage);
          if (currentWardrobePage < totalPages - 1) {
            currentWardrobePage++;
            console.log('📖 Going to wardrobe page:', currentWardrobePage + 1);
            renderWardrobePage();
          }
        } else if (getCurrentDisplayMode() === 'explorer') {
          // Handle explorer results pagination
          const totalPages = Math.ceil(allExtractedImages.length / imagesPerPage);
          if (currentImagePage < totalPages - 1) {
            currentImagePage++;
            console.log('📖 Going to explorer results page:', currentImagePage + 1);
            renderExplorerResults();
          }
        } else {
          // Handle online images pagination
          const totalPages = Math.ceil(allExtractedImages.length / imagesPerPage);
          if (currentImagePage < totalPages - 1) {
            currentImagePage++;
            console.log('📖 Going to image page:', currentImagePage + 1);
            renderImagePage();
          }
        }
      });
    }

  // ===== INITIALIZATION =====
  // Get current tab URL
  chrome.tabs && chrome.tabs.query && chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    if (tabs && tabs[0] && tabs[0].url && pageUrlInput) {
      pageUrlInput.value = tabs[0].url;
    }
  });

  // ===== NOTE: GARMENT EXTRACTION FUNCTIONS =====
  // extractGarmentsFromPage, executeDirectImageSearch, and displayImagesInPlaceholders
  // are now defined in global scope above for better accessibility and timing

  // Reset to default placeholders
  function resetPlaceholders() {
    const garmentPreview = document.getElementById('garment-preview');
    if (!garmentPreview) return;
    
    garmentPreview.innerHTML = `
      <div class="upload-placeholder">
        <span class="upload-text">Garment 1</span>
      </div>
      <div class="upload-placeholder">
        <span class="upload-text">Garment 2</span>
      </div>
      <div class="upload-placeholder">
        <span class="upload-text">Garment 3</span>
      </div>
      <div class="upload-placeholder">
        <span class="upload-text">Garment 4</span>
      </div>
    `;
  }

  // ===== EVENT DELEGATION SETUP =====
  if (!window.avatarEventDelegationSetup) {
    setupEventDelegation();
    window.avatarEventDelegationSetup = true;
  }

  function setupEventDelegation() {
    // Event delegation for dynamically created avatar upload button
    document.addEventListener('click', function(e) {
      // Check if the clicked element is the avatar upload button or contains it
      const avatarUploadBtn = e.target.id === 'avatar-upload-btn' ? e.target : e.target.closest('#avatar-upload-btn');
      
      if (avatarUploadBtn) {
        e.preventDefault();
        e.stopPropagation();
        console.log('Avatar upload button clicked!', e.target);
        
        if (avatarUpload) {
          avatarUpload.value = '';
          avatarUpload.click();
        } else {
          console.log('avatarUpload element not found');
        }
      }
    });
    
    // Add file input for direct avatar upload via camera button
    const cameraInput = document.createElement('input');
    cameraInput.type = 'file';
    cameraInput.accept = 'image/*';
    cameraInput.style.display = 'none';
    document.body.appendChild(cameraInput);
    
    cameraInput.addEventListener('change', async function(event) {
      const file = event.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = async function(e) {
          const imageData = e.target.result;
          
          // Store in local storage
          chrome.storage.local.set({ avatarImg: imageData });
          
          // Process the avatar upload
          await processAvatarUpload(imageData);
          
          // Save to database if user is logged in
          chrome.storage.local.get(['userId'], async function(result) {
            if (result.userId) {
              const saved = await saveAvatarToDatabase(imageData, result.userId);
              if (saved) {
                console.log('✅ Avatar synchronized with database from camera input');
              }
            }
          });
        };
        reader.readAsDataURL(file);
      }
    });
  }



  // ===== INITIALIZATION - LOAD STORED DATA =====
  // Always load avatar from database if user is logged in to ensure we have the latest version
  chrome.storage.local.get(['userId', 'avatarBgRemovedImg', 'avatarImg', 'avatarDataUrl'], async function(result) {
    console.log('🚀 INITIALIZATION: Loading avatar data');
    console.log('🔍 Initial storage state:', {
      userId: result.userId,
      hasAvatarBgRemovedImg: !!result.avatarBgRemovedImg,
      hasAvatarImg: !!result.avatarImg,
      hasAvatarDataUrl: !!result.avatarDataUrl
    });
    
    // If user is logged in, ALWAYS fetch the latest avatar from database
    if (result.userId) {
      console.log('🔄 User logged in - fetching latest avatar from database for user:', result.userId);
      try {
        const databaseAvatar = await loadAvatarFromDatabase(result.userId);
        if (databaseAvatar) {
          console.log('✅ Latest avatar loaded from database, converting to data URL');
          // Convert blob URL to data URL for consistency
          const response = await fetch(databaseAvatar);
          const blob = await response.blob();
          const reader = new FileReader();
          reader.onload = function(e) {
            const imageData = e.target.result;
            
            console.log('📦 Storing database avatar to local storage, length:', imageData.length);
            
            // Update ALL avatar storage keys to ensure consistency
            chrome.storage.local.set({ 
              avatarBgRemovedImg: imageData,
              avatarDataUrl: imageData,
              avatarImg: imageData
            }, () => {
              renderAvatarPreview(imageData);
              console.log('✅ Latest database avatar synchronized to local storage and displayed');
              
              // Verify it was stored
              chrome.storage.local.get(['avatarBgRemovedImg', 'avatarDataUrl', 'avatarImg'], (verifyResult) => {
                console.log('🔍 VERIFICATION after database load:', {
                  avatarBgRemovedImg: verifyResult.avatarBgRemovedImg ? verifyResult.avatarBgRemovedImg.length : 'NOT SET',
                  avatarDataUrl: verifyResult.avatarDataUrl ? verifyResult.avatarDataUrl.length : 'NOT SET',
                  avatarImg: verifyResult.avatarImg ? verifyResult.avatarImg.length : 'NOT SET'
                });
              });
            });
          };
          reader.readAsDataURL(blob);
        } else {
          console.log('ℹ️ No avatar found in database for this user');
          // If no database avatar, check local storage as fallback
          const avatarData = result.avatarDataUrl || result.avatarBgRemovedImg || result.avatarImg;
          if (avatarData) {
            console.log('✅ Using local storage avatar as fallback, length:', avatarData.length);
          } else {
            console.log('⚠️ No avatar in database OR local storage');
          }
          renderAvatarPreview(avatarData);
        }
      } catch (error) {
        console.error('❌ Error loading avatar from database:', error);
        // Fallback to local storage on error
        const avatarData = result.avatarDataUrl || result.avatarBgRemovedImg || result.avatarImg;
        if (avatarData) {
          console.log('✅ Using local storage avatar after database error, length:', avatarData.length);
        } else {
          console.log('⚠️ No avatar in local storage after database error');
        }
        renderAvatarPreview(avatarData);
      }
    } else {
      // No user logged in - use local storage avatar if available
      const avatarData = result.avatarDataUrl || result.avatarBgRemovedImg || result.avatarImg;
      console.log('👤 No user logged in, loading from local storage:', avatarData ? `found (${avatarData.length} chars)` : 'none');
      renderAvatarPreview(avatarData);
      // Sync to avatarDataUrl if not present
      if (avatarData && !result.avatarDataUrl) {
        console.log('🔄 Syncing avatar to avatarDataUrl key');
        chrome.storage.local.set({ avatarDataUrl: avatarData });
      }
    }
  });

  // Initialize garment preview and load stored garments
  chrome.storage.local.get(['uploadedGarments', 'garmentImg', 'garmentType'], function(result) {
    if (result.uploadedGarments && result.uploadedGarments.length > 0) {
      // Load multiple stored garments
      uploadedGarments = result.uploadedGarments;
      
      // Set the most recent garment as selected for try-on
      const mostRecent = uploadedGarments[uploadedGarments.length - 1];
      selectedGarmentType = mostRecent.garmentType;
      garmentImgData = mostRecent.imgData;
      
      // Display all garments
      displayUploadedGarments();
      
      // Auto-select the most recent garment
      setTimeout(() => {
        selectGarmentForTryOn(uploadedGarments.length - 1);
      }, 100);
      
      console.log(`Loaded ${uploadedGarments.length} stored garments`);
    } else if (result.garmentImg && result.garmentType) {
      // Backward compatibility - convert single garment to array format
      uploadedGarments = [{
        imgData: result.garmentImg,
        garmentType: result.garmentType,
        id: Date.now()
      }];
      selectedGarmentType = result.garmentType;
      garmentImgData = result.garmentImg;
      displayUploadedGarments();
      console.log('Converted single stored garment to new format');
    } else {
      // Show default placeholders
      if (garmentPreview) {
        renderGarmentPlaceholders('default');
      }
    }
  });

  // Avatar file input change handler
  if (avatarUpload) {
    avatarUpload.addEventListener('change', async function(e) {
      console.log('File input changed, files:', e.target.files.length);
      const file = e.target.files[0];
      if (file) {
        console.log('Processing file:', file.name);
        const reader = new FileReader();
        reader.onload = async function(evt) {
          console.log('File read complete, processing upload...');
          await processAvatarUpload(evt.target.result);
          
          // Also save avatar to database if user is logged in
          chrome.storage.local.get(['userId'], async function(result) {
            if (result.userId) {
              console.log('📁 Saving avatar to database for user:', result.userId);
              const saved = await saveAvatarToDatabase(evt.target.result, result.userId);
              if (saved) {
                console.log('✅ Avatar synchronized with database');
              } else {
                console.log('⚠️ Failed to save avatar to database, but local storage succeeded');
              }
            } else {
              console.log('ℹ️ No user ID found, avatar saved locally only');
            }
          });
        };
        reader.readAsDataURL(file);
      }
    });
  } else {
    console.log('Note: avatar-upload element not found');
  }


  // ===== GARMENT FUNCTIONS =====
  function processGarmentUpload(imgData, garmentType = 'upper') {
    console.log('Processing garment upload for type:', garmentType);
    
    // Check if we have space for more garments (max 4)
    if (uploadedGarments.length >= 4) {
      console.log('⚠️ Maximum 4 garments allowed. Replacing oldest garment.');
      uploadedGarments.shift(); // Remove the oldest garment
    }
    
    // Add new garment to the array
    const newGarment = {
      imgData: imgData,
      garmentType: garmentType,
      id: Date.now() // Unique identifier
    };
    
    uploadedGarments.push(newGarment);
    console.log(`✅ Added ${garmentType} garment. Total garments: ${uploadedGarments.length}`);
    
    // Update the most recent garment data for try-on functionality
    garmentImgData = imgData;
    selectedGarmentType = garmentType;
    
    // Display all uploaded garments in the preview grid
    displayUploadedGarments();
    
    // Store all garments data
    chrome.storage.local.set({ 
      uploadedGarments: uploadedGarments,
      garmentImg: imgData, // Keep the most recent for backward compatibility
      garmentType: garmentType
    });
    
    console.log('All garments processed and stored');
  }

  // Function to display all uploaded garments in the grid
  function displayUploadedGarments() {
    console.log('🎨 displayUploadedGarments called');
    console.log('📦 uploadedGarments array:', uploadedGarments);
    
    // Set display mode flag to online (uploaded garments are considered online content)
    currentDisplayMode = 'online';
    console.log('🔄 Display mode set to:', currentDisplayMode);
    
    console.log('🔍 garmentPreview element:', garmentPreview);
    
    if (!garmentPreview) {
      console.error('❌ Garment preview element not found');
      return;
    }
    
    // Make sure garment preview is visible
    garmentPreview.style.display = 'grid';
    
    let html = '';
    
    // Display uploaded garments using unified garment item structure
    for (let i = 0; i < 4; i++) {
      if (i < uploadedGarments.length) {
        const garment = uploadedGarments[i];
        const isInWardrobe = isGarmentInWardrobe(garment.imgData);
        
        // Use the unified garment item HTML generator
        html += createGarmentItemHTML({
          src: garment.imgData,
          alt: `${garment.garmentType} Garment`,
          title: garment.garmentType,
          type: garment.garmentType,
          isFavorited: isInWardrobe,
          source: 'uploaded',
          index: i,
          showRemoveButton: true,
          additionalClasses: 'uploaded-garment',
          extraData: {
            'garment-index': i
          }
        });
      } else {

      }
    }
    
    garmentPreview.innerHTML = html;
    
    // Add click handlers for garment selection and removal
    const garmentItems = garmentPreview.querySelectorAll('.uploaded-garment');
    const removeButtons = garmentPreview.querySelectorAll('.garment-remove-btn');
    
    console.log('🔗 Adding click handlers to', garmentItems.length, 'garment items');
    console.log('🗑️ Adding remove handlers to', removeButtons.length, 'remove buttons');
    
    // Add remove button handlers
    removeButtons.forEach(button => {
      button.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent triggering the garment selection
        const index = parseInt(button.dataset.removeIndex);
        console.log(`🗑️ Removing garment ${index + 1}`);
        removeGarment(index);
      });
    });
    
    // Add garment selection handlers
    garmentItems.forEach(item => {
      const index = parseInt(item.dataset.garmentIndex);
      const selectedGarment = uploadedGarments[index];
      
      // Favorite button handling is now done via delegated event listener
      // No need for direct event listeners here
      
      item.addEventListener('click', async (e) => {
        // Don't trigger if clicking on remove button or favorite button
        if (e.target.classList.contains('garment-remove-btn') || 
            e.target.classList.contains('favorite-btn') ||
            e.target.classList.contains('heart-icon')) {
          return;
        }
        
        console.log(`🎯 Clicked garment ${index + 1} - starting try-on`);
        
        // Select the garment and start try-on immediately
        garmentImgData = selectedGarment.imgData;
        selectedGarmentType = selectedGarment.garmentType;
        
        // Visual feedback - highlight selected garment
        garmentPreview.querySelectorAll('.uploaded-garment').forEach((item, i) => {
          if (i === index) {
            item.classList.add('selected');
          } else {
            item.classList.remove('selected');
          }
        });
        
        // Start try-on process
        console.log('🔥 About to call performTryOn with:', selectedGarment);
        console.log('🔍 performTryOn function exists:', typeof performTryOn);
        console.log('🔍 garmentImgData:', garmentImgData);
        console.log('🔍 selectedGarmentType:', selectedGarmentType);
        
        try {
          await performTryOn(selectedGarment.imgData, selectedGarment.garmentType);
          console.log('✅ performTryOn completed successfully');
        } catch (error) {
          console.error('❌ performTryOn failed:', error);
          // Show error in UI as well
          if (tryonResult) {
            tryonResult.innerHTML = `❌ Try-on failed: ${error.message || error}`;
            showTryonResult();
          }
        }
      });
    });
    
    console.log('✅ Displayed all uploaded garments in grid');
    console.log('🔍 Final check - garment items in DOM:');
    console.log(garmentPreview.querySelectorAll('.uploaded-garment'));
  }

  // Function to select a specific garment for try-on
  function selectGarmentForTryOn(index) {
    if (index >= 0 && index < uploadedGarments.length) {
      const selectedGarment = uploadedGarments[index];
      garmentImgData = selectedGarment.imgData;
      selectedGarmentType = selectedGarment.garmentType;
      
      // Visual feedback - highlight selected garment
      garmentPreview.querySelectorAll('.uploaded-garment').forEach((item, i) => {
        if (i === index) {
          item.classList.add('selected');
        } else {
          item.classList.remove('selected');
        }
      });
      
      console.log(`🎯 Selected garment ${index + 1} (${selectedGarment.garmentType}) for try-on`);
    }
  }

  // Function to clear all uploaded garments
  function clearAllGarments() {
    uploadedGarments = [];
    garmentImgData = null;
    selectedGarmentType = 'upper';
    
    // Clear storage
    chrome.storage.local.remove(['uploadedGarments', 'garmentImg', 'garmentType']);
    
    // Reset to default placeholders
    if (garmentPreview) {
      renderGarmentPlaceholders('default');
    }
    
    console.log('🗑️ All garments cleared');
  }

  // Function to remove a specific garment
  function removeGarment(index) {
    if (index >= 0 && index < uploadedGarments.length) {
      const removedGarment = uploadedGarments[index];
      console.log(`🗑️ Removing ${removedGarment.garmentType} garment at index ${index}`);
      
      // Remove from array
      uploadedGarments.splice(index, 1);
      
      // Update storage
      chrome.storage.local.set({ 
        uploadedGarments: uploadedGarments 
      });
      
      // If we removed the currently selected garment, reset selection
      if (garmentImgData === removedGarment.imgData) {
        if (uploadedGarments.length > 0) {
          // Select the first remaining garment
          const firstGarment = uploadedGarments[0];
          garmentImgData = firstGarment.imgData;
          selectedGarmentType = firstGarment.garmentType;
          console.log(`🎯 Switched to first remaining garment: ${firstGarment.garmentType}`);
        } else {
          // No garments left
          garmentImgData = null;
          selectedGarmentType = 'upper';
          console.log('📭 No garments remaining');
        }
      }
      
      // Refresh the display
      displayUploadedGarments();
      
      console.log(`✅ Garment removed. Remaining: ${uploadedGarments.length}`);
    } else {
      console.error(`❌ Invalid garment index: ${index}`);
    }
  }

  // Note: performTryOn function moved to global scope for accessibility

  function renderGarmentPlaceholders(state, data = null) {
    if (!garmentPreview) {
      console.log('garmentPreview element not found');
      return;
    }
    const placeholders = garmentPreview.querySelectorAll('.upload-placeholder');
    
    switch (state) {
      case 'loading':
        garmentPreview.innerHTML = `
          <div class="selected-garment-preview" style="width:100%;height:80px;background:#f5f5f5;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:10px;">
            <span style="color:#666;">⏳ Scanning page for garments...</span>
          </div>
          <div>
            <div class="upload-placeholder loading"><span class="upload-text">Loading...</span></div>
            <div class="upload-placeholder loading"><span class="upload-text">Loading...</span></div>
            <div class="upload-placeholder loading"><span class="upload-text">Loading...</span></div>
            <div class="upload-placeholder loading"><span class="upload-text">Loading...</span></div>
          </div>
        `;
        break;
        
      case 'images':
        const images = data || [];
        let placeholderHTML = `
          <div class="selected-garment-preview" style="width:100%;height:80px;background:#f5f5f5;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:10px;">
            <span style="color:#666;">👕 Select a garment below</span>
          </div>
          <div>
        `;
        
        for (let i = 0; i < 4; i++) {
          if (i < images.length) {
            const img = images[i];
            placeholderHTML += `
              <div class="upload-placeholder garment-item" data-src="${img.src}" style="cursor:pointer;position:relative;overflow:hidden;">
                <img src="${img.src}" alt="Garment ${i+1}" style="width:100%;height:100%;object-fit:cover;" />
                <div class="garment-overlay" style="position:absolute;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.3);opacity:0;transition:opacity 0.2s;display:flex;align-items:center;justify-content:center;color:white;font-size:12px;">
                  Click to select
                </div>
              </div>
            `;
          } else {
            placeholderHTML += `
              <div class="upload-placeholder">
                <span class="upload-text">-</span>
              </div>
            `;
          }
        }
        placeholderHTML += '</div>';
        garmentPreview.innerHTML = placeholderHTML;
        
        // Add click handlers for garment items
        garmentPreview.querySelectorAll('.garment-item').forEach(item => {
          item.addEventListener('click', () => {
            const src = item.dataset.src;
            if (src) {
              processGarmentUpload(src, selectedGarmentType); // Use the selected garment type
              // Add selected state
              garmentPreview.querySelectorAll('.garment-item').forEach(i => i.classList.remove('selected'));
              item.classList.add('selected');
            }
          });
          
          // Hover effects
          const overlay = item.querySelector('.garment-overlay');
          item.addEventListener('mouseenter', () => {
            if (overlay) overlay.style.opacity = '1';
          });
          item.addEventListener('mouseleave', () => {
            if (overlay) overlay.style.opacity = '0';
          });
        });
        break;
        
      case 'error':
        const errorMessage = typeof data === 'string' ? data : (data?.message || 'Error loading garments');
        garmentPreview.innerHTML = `
          <div class="selected-garment-preview" style="width:100%;height:80px;background:#fee;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:10px;">
            <span style="color:#c33;">❌ ${errorMessage}</span>
          </div>
          <div>
            <div class="upload-placeholder"><span class="upload-text">Error</span></div>
            <div class="upload-placeholder"><span class="upload-text">Error</span></div>
            <div class="upload-placeholder"><span class="upload-text">Error</span></div>
            <div class="upload-placeholder"><span class="upload-text">Error</span></div>
          </div>
        `;
        break;
        
      case 'empty':
        const emptyMessage = typeof data === 'string' ? data : (data?.message || 'No garments found');
        garmentPreview.innerHTML = `
          <div class="selected-garment-preview" style="width:100%;height:80px;background:#fef9e7;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:10px;">
            <span style="color:#856404;">👕 ${emptyMessage}</span>
          </div>
          <div>
            <div class="upload-placeholder"><span class="upload-text">Empty</span></div>
            <div class="upload-placeholder"><span class="upload-text">Empty</span></div>
            <div class="upload-placeholder"><span class="upload-text">Empty</span></div>
            <div class="upload-placeholder"><span class="upload-text">Empty</span></div>
          </div>
        `;
        break;
        
      case 'default':
      default:
        garmentPreview.innerHTML = `
          <div>
            <div class="upload-placeholder"><span class="upload-text">Garment</span></div>
            <div class="upload-placeholder"><span class="upload-text">Garment</span></div>
            <div class="upload-placeholder"><span class="upload-text">Garment</span></div>
            <div class="upload-placeholder"><span class="upload-text">Garment</span></div>
          </div>
        `;
        break;
    }
  }

  // ===== GARMENT EVENT HANDLERS =====
  // Upper garment button handler
  if (upperGarmentBtn) {
    upperGarmentBtn.addEventListener('click', function() {
      console.log('Upper garment button clicked');
      selectedGarmentType = 'upper';
      if (garmentUpload) {
        garmentUpload.value = '';
        garmentUpload.click();
      } else {
        console.error('garment-upload file input not found');
      }
    });
  }

  // Lower garment button handler
  if (lowerGarmentBtn) {
    lowerGarmentBtn.addEventListener('click', function() {
      console.log('Lower garment button clicked');
      selectedGarmentType = 'lower';
      if (garmentUpload) {
        garmentUpload.value = '';
        garmentUpload.click();
      } else {
        console.error('garment-upload file input not found');
      }
    });
  }

  // Garment file input handler
  if (garmentUpload) {
    garmentUpload.addEventListener('change', function(e) {
      console.log('Garment file selected, type:', selectedGarmentType);
      const file = e.target.files[0];
      if (file) {
        console.log('Processing garment file:', file.name, 'as', selectedGarmentType);
        const reader = new FileReader();
        reader.onload = function(evt) {
          processGarmentUpload(evt.target.result, selectedGarmentType);
        };
        reader.readAsDataURL(file);
      }
    });
  } else {
    console.log('Note: garment-upload file input not found');
  }


/* filepath: /Users/rhishikeshthakur/Enable/Software_Development/enable_because_future/chrome-extension/popup.js */
// Replace the UI CONTROL HANDLERS section around line 965-1001:

// ===== UI CONTROL HANDLERS =====  

  // Signout button logic
  if (signoutBtn) {
    signoutBtn.addEventListener('click', () => {
      if (confirm('Sign out and return to login?')) {
        console.log('User confirmed signout');
        
        // Clear all storage
        chrome.storage.local.clear();
        
        // Reset UI and return to sign-in
        showSignInPage();
        
        // Reset sign-in form
        if (signinEmail) signinEmail.value = '';
        if (signinPassword) signinPassword.value = '';
        if (signinBtn) {
          signinBtn.innerHTML = 'Sign In';
          signinBtn.disabled = false;
        }
        
        console.log('Signout completed successfully');
      } else {
        console.log('User cancelled signout');
      }
    });
  } else {
    console.log('Note: signout-btn element not found');
  }

  // Refresh button logic (if it exists separately)
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      console.log('🔄 Refresh button clicked - forcing fresh extraction and resetting session');
      
      if (confirm('Refresh page content? This will extract fresh images from the current page and clear uploaded images.')) {
        console.log('✅ User confirmed refresh');
        
        // Clear extracted images cache for fresh extraction
        allExtractedImages = [];
        currentImagePage = 0;
        
        // Reset garment data
        uploadedGarments = [];
        garmentImgData = null;
        garmentBgRemovedBlob = null;
        renderGarmentPlaceholders('default');
        
        // Reset try-on result
        if (tryonResult) {
          tryonResult.innerHTML = '';
          hideTryonResult();
        }
        
        if (tryonBody) {
          tryonBody.style.display = 'flex';
        }
        
        // Clear image storage but keep user session
        chrome.storage.local.remove([
          'avatarImg', 
          'avatarBgRemovedImg', 
          'uploadedGarments',
          'garmentImg',
          'garmentType'
        ]);
        
        // Force fresh brand check and extraction
        console.log('🔄 Starting fresh brand check and extraction...');
        initializeBrandCheck().then(() => {
          console.log('✅ Fresh extraction completed');
        });
        
        console.log('✅ Session refresh completed');
      } else {
        console.log('❌ User cancelled refresh');
      }
    });
  } else {
    console.log('Note: refresh-btn element not found');
  }

  // ===== CHAT INTERFACE FUNCTIONALITY =====
  const chatButton = document.getElementById('ai-chat-btn');
  const chatContainer = document.getElementById('ai-chat-interface'); // Changed from .ai-chat-container
  const chatMessages = document.querySelector('.chat-messages');
  const chatInput = document.querySelector('.chat-input');
  const sendButton = document.getElementById('send-chat-btn'); // Changed from .send-button

  // Debug: Log if chat elements are found
  console.log('🔍 Chat elements found:', {
    chatButton: !!chatButton,
    chatContainer: !!chatContainer,
    chatMessages: !!chatMessages,
    chatInput: !!chatInput,
    sendButton: !!sendButton
  });

  // Toggle chat interface visibility
  if (chatButton) {
    chatButton.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      if (chatContainer) {
        const isVisible = chatContainer.style.display !== 'none';
        if (isVisible) {
          chatContainer.style.display = 'none';
          chatButton.classList.remove('active');
          console.log('💬 Chat interface hidden');
        } else {
          chatContainer.style.display = 'block';
          chatButton.classList.add('active');
          // Reset conversation state for new session
          resetConversationState();
          hideViewResultsButton();
          console.log('💬 Chat interface shown - state reset');
          // Focus the input when showing chat
          if (chatInput) {
            setTimeout(() => chatInput.focus(), 100);
          }
        }
      }
    });
  }

  // Close chat button handler
  const closeChatBtn = document.getElementById('close-chat-btn');
  if (closeChatBtn) {
    closeChatBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      
      if (chatContainer) {
        chatContainer.style.display = 'none';
        chatButton.classList.remove('active');
        // Hide view results button when closing chat
        hideViewResultsButton();
        console.log('💬 Chat interface closed via close button');
      }
    });
  }

  // Send message functionality
  function sendChatMessage() {
    if (!chatInput || !chatMessages || !sendButton) {
      console.log('❌ Chat elements not found');
      return;
    }

    const message = chatInput.value.trim();
    if (!message) {
      return;
    }

    // Hide the view results button when starting a new search
    hideViewResultsButton();

    // Disable input and button while processing
    chatInput.disabled = true;
    sendButton.disabled = true;
    sendButton.textContent = 'Sending...';

    // Add user message to chat
    addChatMessage(message, 'user');
    chatInput.value = '';

    // Show loading indicator
    const loadingElement = addChatLoadingIndicator();

    // Send message to backend
    processChatMessage(message)
      .then(response => {
        // Remove loading indicator
        if (loadingElement && loadingElement.parentNode) {
          loadingElement.parentNode.removeChild(loadingElement);
        }
        
        // Add AI response
        addChatMessage(response, 'system');
      })
      .catch(error => {
        console.error('❌ Chat error:', error);
        
        // Remove loading indicator
        if (loadingElement && loadingElement.parentNode) {
          loadingElement.parentNode.removeChild(loadingElement);
        }
        
        // Show error message
        addChatMessage('Sorry, I encountered an error processing your request. Please try again.', 'system');
      })
      .finally(() => {
        // Re-enable input and button
        chatInput.disabled = false;
        sendButton.disabled = false;
        sendButton.textContent = 'Send';
        chatInput.focus();
      });
  }

  // Add message to chat interface
  function addChatMessage(message, type) {
    if (!chatMessages) return;

    const messageElement = document.createElement('div');
    messageElement.className = `chat-message ${type}`;
    messageElement.textContent = message;
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    console.log(`💬 Added ${type} message:`, message);
  }

  // Add loading indicator
  function addChatLoadingIndicator() {
    if (!chatMessages) return null;

    const loadingElement = document.createElement('div');
    loadingElement.className = 'chat-loading';
    loadingElement.innerHTML = `
      <span>🔍 Searching for garments...</span>
      <div class="dots">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
    `;
    
    chatMessages.appendChild(loadingElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return loadingElement;
  }

  // ==== SIMPLIFIED CHAT LOGIC ====
  
  let conversationState = 'initial'; // 'initial', 'awaiting_details', 'searching'
  let firstMessage = '';
  
  // Reset conversation state when chat is opened
  function resetConversationState() {
    conversationState = 'initial';
    firstMessage = '';
    console.log('💬 Chat conversation reset');
  }

  // Check for missing required parameters
  function analyzeGarmentQuery(message) {
    const lowerMessage = message.toLowerCase();
    console.log('🔍 Analyzing query for missing info:', message);
    
    const missing = [];
    
    // Garment type check
    const garmentTypes = ['shirt', 't-shirt', 'tshirt', 'pant', 'pants', 'jean', 'jeans', 'dress', 'jacket', 'coat', 'skirt', 'shoe', 'sweater', 'shoes', 'sneaker', 'boot', 'hoodie', 'sweater', 'top', 'bottom'];
    if (!garmentTypes.some(type => lowerMessage.includes(type))) {
      missing.push('garment type');
    }
    
    // Gender check
    const genders = ['men', 'women', 'male', 'female', 'unisex', 'boy', 'girl'];
    if (!genders.some(g => lowerMessage.includes(g))) {
      missing.push('gender');
    }
    
    // Size check  
    const sizes = ['small', 'medium', 'large', 'xs', 's', 'm', 'l', 'xl', 'xxl', 'size'];
    if (!sizes.some(s => lowerMessage.includes(s))) {
      missing.push('size');
    }
    
    // Style check
    const styles = ['casual', 'formal', 'sporty', 'sport', 'athletic', 'vintage', 'classic', 'modern'];
    if (!styles.some(st => lowerMessage.includes(st))) {
      missing.push('style');
    }
    
    // Fabric check
    const fabrics = ['cotton', 'polyester', 'wool', 'silk', 'linen', 'denim', 'leather'];
    if (!fabrics.some(f => lowerMessage.includes(f))) {
      missing.push('fabric');
    }
    
    // Brand check
    const brands = ['nike', 'adidas', 'zara', 'gucci', 'levi', 'h&m', 'gap', 'uniqlo'];
    if (!brands.some(b => lowerMessage.includes(b))) {
      missing.push('brand');
    }
    
    console.log('🔍 Missing parameters:', missing);
    return missing;
  }

  // Process chat message - TWO-STEP FLOW
  async function processChatMessage(message) {
    try {
      console.log(`💬 [${conversationState}] Processing message:`, message);
      
      if (conversationState === 'initial') {
        // STEP 1: Check first message for missing parameters
        const missing = analyzeGarmentQuery(message);
        
        if (missing.length > 0) {
          // Ask for missing details (only once)
          firstMessage = message;
          conversationState = 'awaiting_details';
          return `I need a few more details:\n\n${missing.map(m => `• ${m}`).join('\n')}\n\nPlease provide these details.`;
        } else {
          // All details present, go directly to search
          conversationState = 'searching';
          return await performSearch(message);
        }
      } else if (conversationState === 'awaiting_details') {
        // STEP 2: Combine messages and search (no more questions)
        const combinedQuery = `${firstMessage} ${message}`;
        conversationState = 'searching';
        return await performSearch(combinedQuery);
      } else {
        // After search, start fresh conversation
        resetConversationState();
        return await processChatMessage(message);
      }
      
    } catch (error) {
      console.error('❌ Chat processing error:', error);
      resetConversationState();
      return 'Sorry, I encountered an error. Please try again.';
    }
  }

  // Perform the actual search
  async function performSearch(query) {
    try {
      console.log(`🔍 Searching for: "${query}"`);
      
      const response = await fetch(`${API_BASE_URL}/api/unified-search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('🔍 Search response:', data);
      
      if (data.success && data.garment_images && data.garment_images.length > 0) {
        displayExplorerResults(data.garment_images, query);
        return `✅ Found ${data.garment_images.length} items! Click "View Results" to see them.`;
      } else {
        hideViewResultsButton();
        return "❌ No items found matching your search. Try different terms.";
      }
      
    } catch (error) {
      console.error('❌ Search failed:', error);
      hideViewResultsButton();
      return 'Sorry, the search service is unavailable. Please try again later.';
    }
  }

  // ==== END SIMPLIFIED CHAT LOGIC ====

  // Display explorer search results in garment preview
  function displayExplorerResults(garmentImages, originalQuery) {
    console.log('🖼️ Displaying explorer results:', garmentImages.length, 'items');
    
    if (!garmentPreview) {
      console.error('❌ Garment preview element not found');
      return;
    }
    
    // ✨ ENHANCED: If no search results found, fallback to database wardrobe
    if (!garmentImages || garmentImages.length === 0) {
      console.log('⚠️ No garment images from search - loading wardrobe as fallback');
      hideViewResultsButton();
      loadWardrobeAsFallback();
      return;
    }
    
    // Clear current display and set to explorer mode
    allExtractedImages = garmentImages.map((item, index) => ({
      src: item.src,
      title: item.title,
      price: item.price,
      store: item.store,
      url: item.url || item.src, // Use URL if available, fallback to image src
      query: originalQuery,
      isExplorerResult: true,
      index: index
    }));
    
    currentImagePage = 0;
    currentDisplayMode = 'explorer';
    
    // Make sure garment preview is visible
    garmentPreview.style.display = 'grid';
    
    // Render the explorer results
    renderExplorerResults();
    
    // Show the "View Results" button only if we have results
    showViewResultsButton(garmentImages.length);
    
    console.log('✅ Explorer results displayed in garment preview');
  }

  // Render explorer results with enhanced styling
  function renderExplorerResults() {
    if (!garmentPreview) return;
    
    const totalPages = Math.ceil(allExtractedImages.length / imagesPerPage);
    const startIndex = currentImagePage * imagesPerPage;
    const endIndex = Math.min(startIndex + imagesPerPage, allExtractedImages.length);
    const currentImages = allExtractedImages.slice(startIndex, endIndex);
    
    console.log(`🖼️ Rendering explorer page ${currentImagePage + 1}/${totalPages}, showing items ${startIndex + 1}-${endIndex}`);
    
    // Update navigation if it exists
    const garmentNavigation = document.getElementById('garment-navigation');
    const pageIndicator = document.getElementById('page-indicator');
    const prevBtn = document.getElementById('prev-images-btn');
    const nextBtn = document.getElementById('next-images-btn');
    
    if (garmentNavigation && totalPages > 1) {
      garmentNavigation.style.display = 'flex';
      if (pageIndicator) {
        pageIndicator.textContent = `${currentImagePage + 1} / ${totalPages} (${allExtractedImages.length} results found)`;
      }
      if (prevBtn) prevBtn.disabled = currentImagePage === 0;
      if (nextBtn) nextBtn.disabled = currentImagePage === totalPages - 1;
    } else if (garmentNavigation) {
      garmentNavigation.style.display = 'none';
    }
    
    // Build enhanced image grid using unified garment item structure
    let gridHtml = '';
    
    for (let i = 0; i < imagesPerPage; i++) {
      if (i < currentImages.length) {
        const img = currentImages[i];
        const isInWardrobe = false; // Explorer results are not in wardrobe initially
        
        // Use the unified garment item HTML generator
        gridHtml += createGarmentItemHTML({
          src: img.src,
          title: img.title,
          price: img.price,
          store: img.store,
          url: img.url,
          isFavorited: isInWardrobe,
          additionalClasses: 'explorer-item',
          source: 'explorer'
        });
      } else {
        gridHtml += `
          <div class="upload-placeholder explorer-placeholder">
            <span class="upload-text">-</span>
          </div>
        `;
      }
    }
    
    garmentPreview.innerHTML = gridHtml;
    
    // Add event listeners for explorer items
    const explorerItems = garmentPreview.querySelectorAll('.explorer-item');
    explorerItems.forEach((item, index) => {
      const globalIndex = startIndex + index;
      const imgData = allExtractedImages[globalIndex];
      
      // Try-on functionality
      item.addEventListener('click', async (e) => {
        // Don't trigger if clicking on favorite button
        if (e.target.classList.contains('favorite-btn') || 
            e.target.classList.contains('heart-icon')) {
          return;
        }
        
        console.log(`🎯 Clicked explorer item: ${imgData.title}`);
        
        try {
          // Determine garment type based on title/description
          const title = imgData.title.toLowerCase();
          let garmentType = 'upper'; // default
          
          if (title.includes('jean') || title.includes('pant') || title.includes('trouser') || 
              title.includes('short') || title.includes('skirt') || title.includes('bottom')) {
            garmentType = 'lower';
          }
          
          // Start try-on process
          await performTryOn(imgData.src, garmentType);
          console.log('✅ Explorer item try-on completed successfully');
          
        } catch (error) {
          console.error('❌ Explorer item try-on failed:', error);
          if (tryonResult) {
            tryonResult.innerHTML = `❌ Try-on failed: ${error.message || error}`;
            showTryonResult();
          }
        }
      });
      
      // Hover effects for explorer items
      item.addEventListener('mouseenter', () => {
        const hoverBadge = item.querySelector('.tryon-hover-badge');
        const img = item.querySelector('img');
        if (hoverBadge) hoverBadge.style.opacity = '1';
        if (img) img.style.transform = 'scale(1.05)';
      });
      
      item.addEventListener('mouseleave', () => {
        const hoverBadge = item.querySelector('.tryon-hover-badge');
        const img = item.querySelector('img');
        if (hoverBadge) hoverBadge.style.opacity = '0';
        if (img) img.style.transform = 'scale(1)';
      });
    });
    
    console.log('✅ Explorer results page rendered with', explorerItems.length, 'items');
  }

  // Send button click handler
  if (sendButton) {
    sendButton.addEventListener('click', sendChatMessage);
  }

  // Enter key handler for chat input
  if (chatInput) {
    chatInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
      }
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 80) + 'px';
    });
  }

  // Initialize chat - don't add welcome message since it's already in HTML
  if (chatMessages) {
    console.log('💬 Chat interface initialized - welcome message already in HTML');
  }

  // Debug Try-On Button Handler
  const debugTryonBtn = document.getElementById('debug-tryon-btn');
  if (debugTryonBtn) {
    debugTryonBtn.addEventListener('click', async () => {
      console.log('🧪 Debug try-on button clicked');
      // Create close button for debug state
      const debugCloseBtn = document.createElement('button');
      debugCloseBtn.className = 'tryon-close-btn';
      debugCloseBtn.innerHTML = '&times;';
      debugCloseBtn.addEventListener('click', hideTryonResult);
      
      const debugText = document.createElement('span');
      debugText.textContent = '🧪 Testing try-on API connection...';
      
      tryonResult.innerHTML = '';
      tryonResult.appendChild(debugCloseBtn);
      tryonResult.appendChild(debugText);
      showTryonResult();
      
      try {
        // Test API connectivity with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
        
        const testResponse = await fetch(`${API_BASE_URL}/api/tryon`, {
          method: 'OPTIONS',
          signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (testResponse.ok) {
          tryonResult.innerHTML = '✅ Try-on API is accessible! Server is running and ready.';
          console.log('✅ Try-on API connection successful');
          
          // Now test if we have garments to try on
          if (uploadedGarments.length > 0) {
            console.log('🎯 Found garments, testing try-on...');
            const testGarment = uploadedGarments[0];
            
            // Test with the first garment
            chrome.storage.local.get(['avatarBgRemovedImg'], async (result) => {
              if (result.avatarBgRemovedImg) {
                console.log('🧪 Testing performTryOn with actual data');
                await performTryOn(testGarment.imgData, testGarment.garmentType);
              } else {
                tryonResult.innerHTML = '⚠️ API accessible but no avatar uploaded. Upload an avatar first.';
              }
            });
          } else {
            tryonResult.innerHTML = '⚠️ API accessible but no garments uploaded. Upload a garment first.';
          }
        } else {
          tryonResult.innerHTML = `⚠️ Try-on API responded but returned status ${testResponse.status}. Server may be having issues.`;
        }
      } catch (error) {
        if (error.name === 'AbortError') {
          tryonResult.innerHTML = `⏱️ Connection timeout: Server at ${API_BASE_URL} is not responding. Please check if the backend server is running.`;
        } else if (error.message.includes('ERR_CONNECTION_REFUSED')) {
          tryonResult.innerHTML = `🚫 Connection refused: Server at ${API_BASE_URL} is not accepting connections. Please start the backend server.`;
        } else if (error.message.includes('ERR_CONNECTION_TIMED_OUT')) {
          tryonResult.innerHTML = `⏱️ Connection timed out: Cannot reach server at ${API_BASE_URL}. Check network connectivity.`;
        } else {
          tryonResult.innerHTML = `❌ Try-on API connection failed: ${error.message}`;
        }
        console.error('❌ Debug try-on error:', error);
      }
    });
  }

  // ===== TRY-ON FUNCTIONALITY =====
  // Try-On button logic (optional - may be commented out in HTML)
  const tryonBtn = document.getElementById('tryon-btn');

  if (tryonBtn) {
    tryonBtn.addEventListener('click', async () => {
      console.log('🎯 Try-on button clicked');
      
      if (!garmentImgData) {
        tryonResult.innerHTML = '👕 Please select a garment first';
        showTryonResult();
        return;
      }
      
      try {
        await performTryOn(garmentImgData, selectedGarmentType);
      } catch (error) {
        console.error('Try-on failed:', error);
      }
    });
  } // End of tryonBtn null check
  
  } // End of initializeMainApp function

  function showMainApp() {
    signinPage.style.display = 'none';
    if (accountCreationPage) accountCreationPage.style.display = 'none';
    if (userProfilePage) userProfilePage.style.display = 'none';
    mainApp.style.display = 'flex';
    
    // Ensure proper grid layout for garment preview
    ensureGridLayout();
    
    // Update toggle button state based on user status and brand page detection
    setTimeout(() => {
      updateToggleButtonState();
    }, 100);
    
    // Update user info in header and load avatar
    chrome.storage.local.get(['userEmail', 'isGuest', 'avatarDataUrl'], function(result) {
      const userEmailEl = document.getElementById('user-email');
      if (userEmailEl) {
        if (result.isGuest) {
          console.log("", result.isGuest)
          userEmailEl.textContent = 'Guest User';
        } else {
          userEmailEl.textContent = result.userEmail || 'User';
        }
      }
      
      // Load avatar if available in storage
      if (result.avatarDataUrl) {
        console.log('🖼️ Loading avatar from storage for main app');
        // We'll render the avatar after the main app is initialized
        setTimeout(() => {
          const avatarPreview = document.getElementById('avatar-preview');
          if (avatarPreview) {
            renderAvatarPreview(result.avatarDataUrl);
          }
        }, 100); // Small delay to ensure elements are rendered
      }
    });
    
    initializeMainApp();
    
    // Note: Garment extraction now happens immediately in initializeBrandCheck()
    // when checkBrandDomain() returns true, not here
  }

  // User Profile Management Functions
  async function loadUserProfile() {
    try {
      // Get current user email from storage
      chrome.storage.local.get(['userEmail', 'isGuest'], async function(result) {
        if (result.isGuest) {
          alert('Profile not available for guest users. Please sign in with an account.');
          showMainApp();
          return;
        }
        
        if (!result.userEmail) {
          alert('No user email found. Please sign in again.');
          showSignInPage();
          return;
        }

        console.log('📥 Loading user profile for:', result.userEmail);
        
        // Show loading state
        editProfileBtn.innerHTML = 'Loading...';
        editProfileBtn.disabled = true;

        // Call API to get user data by email
        const response = await fetch(`http://localhost:5000/api/get-user-data-by-email/${encodeURIComponent(result.userEmail)}`);
        const data = await response.json();

        if (data.success) {
          console.log('✅ User profile loaded successfully:', data.user_data);
          populateProfileForm(data.user_data);
        } else {
          console.error('❌ Failed to load user profile:', data.error);
          if (data.error === 'User not found') {
            alert('Profile not found. This may be because you signed in as a guest or your account was created before the profile system. Please create a new account or sign in with a valid account.');
          } else {
            alert(`Failed to load profile: ${data.error}`);
          }
          showMainApp();
        }

        // Reset loading state
        editProfileBtn.innerHTML = 'Edit Profile';
        editProfileBtn.disabled = false;
      });

    } catch (error) {
      console.error('❌ Error loading user profile:', error);
      alert('Error loading profile. Please try again.');
      showMainApp();
      
      // Reset loading state
      editProfileBtn.innerHTML = 'Edit Profile';
      editProfileBtn.disabled = false;
    }
  }

  function populateProfileForm(userData) {
    // Populate form fields with user data
    if (profileUserid) profileUserid.value = userData.userid || '';
    if (profileEmail) profileEmail.value = userData.email || '';
    if (profileFirstname) profileFirstname.value = userData.first_name || '';
    if (profileLastname) profileLastname.value = userData.last_name || '';
    if (profileAge) profileAge.value = userData.age || '';
    if (profileGender) profileGender.value = userData.gender || '';
    if (profileWeight) profileWeight.value = userData.weight || '';
    if (profileHeight) profileHeight.value = userData.height || '';

    // Set physique radio button
    if (userData.physique) {
      const physiqueRadio = document.querySelector(`input[name="profile-physique"][value="${userData.physique}"]`);
      if (physiqueRadio) {
        physiqueRadio.checked = true;
      }
    }

    // Make sure fields are in read-only mode initially
    setProfileFieldsReadOnly(true);
  }

  function enableProfileEditing() {
    console.log('📝 Enabling profile editing mode');
    
    // Enable form fields (except userid and email)
    setProfileFieldsReadOnly(false);
    
    // Show/hide buttons
    editProfileBtn.style.display = 'none';
    saveProfileBtn.style.display = 'inline-block';
    cancelEditBtn.style.display = 'inline-block';
  }

  function cancelProfileEditing() {
    console.log('❌ Cancelling profile editing');
    
    // Reload profile data to reset form
    loadUserProfile();
    
    // Show/hide buttons
    editProfileBtn.style.display = 'inline-block';
    saveProfileBtn.style.display = 'none';
    cancelEditBtn.style.display = 'none';
  }

  function setProfileFieldsReadOnly(readOnly) {
    // Set readonly attribute for input fields (keep userid and email always readonly)
    if (profileFirstname) profileFirstname.readOnly = readOnly;
    if (profileLastname) profileLastname.readOnly = readOnly;
    if (profileAge) profileAge.readOnly = readOnly;
    if (profileWeight) profileWeight.readOnly = readOnly;
    if (profileHeight) profileHeight.readOnly = readOnly;
    
    // Set disabled attribute for select and radio inputs
    if (profileGender) profileGender.disabled = readOnly;
    
    // Handle physique radio buttons
    const physiqueRadios = document.querySelectorAll('input[name="profile-physique"]');
    physiqueRadios.forEach(radio => {
      radio.disabled = readOnly;
    });
  }

  async function handleProfileUpdate() {
    try {
      console.log('💾 Saving profile changes');
      
      // Get form data
      const formData = {
        first_name: profileFirstname.value.trim(),
        last_name: profileLastname.value.trim(),
        age: parseInt(profileAge.value),
        gender: profileGender.value,
        weight: parseFloat(profileWeight.value),
        height: parseFloat(profileHeight.value),
        physique: document.querySelector('input[name="profile-physique"]:checked')?.value
      };

      // Validate required fields
      if (!formData.first_name || !formData.last_name || !formData.age || !formData.gender || 
          !formData.weight || !formData.height || !formData.physique) {
        alert('Please fill in all required fields');
        return;
      }

      // Show loading state
      saveProfileBtn.innerHTML = 'Saving...';
      saveProfileBtn.disabled = true;

      // Get userid from form
      const userid = profileUserid.value;

      // Call update API
      const response = await fetch(`http://localhost:5000/api/update-user-data/${userid}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      const result = await response.json();

      if (result.success) {
        console.log('✅ Profile updated successfully');
        alert('Profile updated successfully!');
        
        // Return to read-only mode
        setProfileFieldsReadOnly(true);
        editProfileBtn.style.display = 'inline-block';
        saveProfileBtn.style.display = 'none';
        cancelEditBtn.style.display = 'none';
        
      } else {
        console.error('❌ Failed to update profile:', result.error);
        alert(`Failed to update profile: ${result.error}`);
      }

    } catch (error) {
      console.error('❌ Error updating profile:', error);
      alert('Error updating profile. Please try again.');
    } finally {
      // Reset loading state
      saveProfileBtn.innerHTML = 'Save Changes';
      saveProfileBtn.disabled = false;
    }
  }

  // Utility functions to manage try-on result display and avatar visibility
  function showTryonResult() {
    const tryonResult = document.getElementById('tryon-result');
    if (tryonResult) {
      tryonResult.style.display = 'flex';
      // Add class to hide avatar
      const mainContainer = document.querySelector('.main-container');
      if (mainContainer) {
        mainContainer.classList.add('tryon-active');
      }
    }
  }

  function hideTryonResult() {
    const tryonResult = document.getElementById('tryon-result');
    if (tryonResult) {
      // Clean up any blob URLs in the try-on result
      const images = tryonResult.querySelectorAll('img');
      images.forEach(img => {
        if (img.src && img.src.startsWith('blob:')) {
          URL.revokeObjectURL(img.src);
        }
      });
      tryonResult.style.display = 'none';
      // Remove class to show avatar again
      const mainContainer = document.querySelector('.main-container');
      if (mainContainer) {
        mainContainer.classList.remove('tryon-active');
      }
    }
  }

  // ===== VIEW RESULTS BUTTON FUNCTIONALITY =====
  
  // Function to show the "View Results" button
  function showViewResultsButton(resultCount = null) {
    const viewResultsBtn = document.getElementById('view-results-btn');
    if (viewResultsBtn) {
      // Update button text if result count is provided
      if (resultCount !== null && resultCount > 0) {
        const btnText = viewResultsBtn.querySelector('.btn-text');
        if (btnText) {
          btnText.textContent = `View ${resultCount} Result${resultCount !== 1 ? 's' : ''}`;
        }
      }
      
      viewResultsBtn.style.display = 'flex';
      viewResultsBtn.classList.add('show');
      console.log('✅ View Results button shown', resultCount ? `with ${resultCount} results` : '');
    }
  }
  
  // Function to hide the "View Results" button
  function hideViewResultsButton() {
    const viewResultsBtn = document.getElementById('view-results-btn');
    if (viewResultsBtn) {
      viewResultsBtn.style.display = 'none';
      viewResultsBtn.classList.remove('show');
      console.log('✅ View Results button hidden');
    }
  }
  
  // Function to scroll to garment preview
  function scrollToGarmentPreview() {
    const garmentPreview = document.getElementById('garment-preview');
    const tryonBody = document.querySelector('.tryon-body');
    const chatInterface = document.getElementById('ai-chat-interface');
    
    if (garmentPreview && tryonBody && chatInterface) {
      // First, hide the chat interface
      chatInterface.style.display = 'none';
      
      // Show the tryon body (main interface)
      tryonBody.style.display = 'flex';
      
      // Ensure garment preview is visible
      garmentPreview.style.display = 'grid';
      
      // Scroll to the garment preview section
      setTimeout(() => {
        garmentPreview.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'start' 
        });
      }, 100);
      
      console.log('✅ Navigated to garment preview section');
    } else {
      console.error('❌ Could not find required elements for navigation');
    }
  }
  
  // Add event listener for the view results button
  const viewResultsBtn = document.getElementById('view-results-btn');
  if (viewResultsBtn) {
    viewResultsBtn.addEventListener('click', () => {
      console.log('🎯 View Results button clicked');
      scrollToGarmentPreview();
    });
  }

  // Add event listeners for upload placeholders to fix CSP violations
  function addUploadPlaceholderListeners() {
    const uploadPlaceholders = document.querySelectorAll('#garment-preview .upload-placeholder');
    uploadPlaceholders.forEach(placeholder => {
      placeholder.addEventListener('click', function() {
        alert('Upload garments first using the + buttons on the avatar!');
      });
    });
  }

  // Add listeners after a small delay to ensure DOM is fully loaded
  setTimeout(addUploadPlaceholderListeners, 100);

  // Add delegated event listener for favorite buttons and premium try-on
  document.addEventListener('click', async function(event) {
    console.log('🔍 Document click detected:', event.target.className || '(no class)', event.target.tagName);
    console.log('🔍 Element details:', {
      textContent: event.target.textContent,
      innerHTML: event.target.innerHTML,
      parentElement: event.target.parentElement?.className,
      parentTag: event.target.parentElement?.tagName
    });
    
    // Check if the clicked element is a premium try-on button
    const isPremiumBtn = event.target.classList.contains('premium-tryon-btn');
    const premiumBtn = event.target.closest('.premium-tryon-btn');
    const isPremiumText = event.target.classList.contains('premium-text');
    
    if (isPremiumBtn || premiumBtn || isPremiumText) {
      const actualPremiumBtn = isPremiumBtn ? event.target : premiumBtn;
      const url = actualPremiumBtn?.dataset?.url;
      
      if (url) {
        console.log('👑 Premium try-on clicked for URL:', url);
        event.stopPropagation();
        
        // Open the URL in a new tab
        try {
          window.open(url, '_blank', 'noopener,noreferrer');
          console.log('✅ Premium try-on link opened in new tab');
        } catch (error) {
          console.error('❌ Failed to open premium try-on link:', error);
          // Fallback: try to navigate directly
          window.location.href = url;
        }
      } else {
        console.warn('⚠️ No URL found for premium try-on button');
      }
      return;
    }
    
    // Check if the clicked element is a favorite button or heart icon
    const isHeartIcon = event.target.classList.contains('heart-icon');
    const isFavoriteBtn = event.target.classList.contains('favorite-btn');
    const favoriteBtn = event.target.closest('.favorite-btn');
    
    // Also check if this is a heart symbol inside a favorite button
    const isHeartSymbol = (event.target.textContent === '♥' || event.target.textContent === '♡') && 
                         event.target.tagName === 'SPAN';
    
    if (isHeartIcon || isFavoriteBtn || favoriteBtn || isHeartSymbol) {
      console.log('🎯 Favorite button clicked via delegation!', {
        isHeartIcon,
        isFavoriteBtn,
        hasFavoriteBtn: !!favoriteBtn,
        isHeartSymbol,
        targetClass: event.target.className,
        textContent: event.target.textContent
      });
      
      const actualFavoriteBtn = isFavoriteBtn ? event.target : favoriteBtn;
        
      if (!actualFavoriteBtn) {
        console.error('❌ Could not find favorite button');
        return;
      }
      
      event.stopPropagation();
      
      // Get the garment item container
      const garmentItem = actualFavoriteBtn.closest('.garment-item-tryon');
      if (!garmentItem) {
        console.error('❌ Could not find garment item container');
        return;
      }
      
      // Get the image source
      const img = garmentItem.querySelector('img');
      if (!img) {
        console.error('❌ Could not find image in garment item');
        return;
      }
      
      const imgSrc = img.src;
      const garmentType = await detectGarmentTypeFromURL();
      const garmentUrl = window.location.href;
      
      // Create a mock event object for handleFavoriteClick
      const mockEvent = {
        currentTarget: actualFavoriteBtn,
        target: event.target,
        stopPropagation: () => event.stopPropagation()
      };
      
      console.log('🔍 Calling handleFavoriteClick with delegated event');
      console.log('🔍 Parameters:', {
        imgSrc: imgSrc.substring(0, 50) + '...',
        garmentType,
        garmentUrl: garmentUrl.substring(0, 50) + '...'
      });
      
      await handleFavoriteClick(mockEvent, imgSrc, garmentType, garmentUrl);
    }
  });

  // Make functions globally available
  window.showTryonResult = showTryonResult;
  window.hideTryonResult = hideTryonResult;
});

// ============================================================================
// MEMORY MANAGEMENT
// ============================================================================
// Aggressive memory management for Chrome extension
let imageCache = new Map();
const MAX_CACHE_SIZE = 3; // Limit cached images to 3

// Clear image cache when it gets too large
function clearImageCache() {
  if (imageCache.size > MAX_CACHE_SIZE) {
    imageCache.clear();
  }
  
  // Clear blob URLs to free memory
  document.querySelectorAll('img').forEach(img => {
    if (img.src && img.src.startsWith('blob:')) {
      // Only revoke if the image is not currently visible
      const rect = img.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) {
        URL.revokeObjectURL(img.src);
      }
    }
  });
  
  // Force garbage collection if available
  if (window.gc) {
    window.gc();
  }
  
  // Clear any unused form data
  window.FormData = class extends FormData {
    constructor(...args) {
      super(...args);
      setTimeout(() => this.delete, 5000); // Clear after 5 seconds
    }
  };
}

// Clear memory every 3 seconds instead of 10
setInterval(clearImageCache, 3000);

// Clear on page visibility change
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    clearImageCache();
  }
});
