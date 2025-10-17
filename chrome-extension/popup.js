document.addEventListener('DOMContentLoaded', function() {

  // ===== GLOBAL VARIABLES =====
  // Wardrobe functionality
  let currentUser = null; // Will store user info after sign-in
  let wardrobeItems = []; // Cache for wardrobe items

  // Garment source toggle
  let currentGarmentSource = 'online'; // 'online' or 'wardrobe'
  let isShowingWardrobe = false;

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
        console.log('🎯 Brand page detected - triggering garment extraction NOW');
        // Wait a brief moment for DOM to be ready, then extract garments
        setTimeout(() => {
          extractGarmentsFromPage();
        }, 100);
      }
    } catch (error) {
      console.error('❌ Initial brand domain check failed:', error);
      useGarmentCheckbox = false;
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
          'polo', 'poloshirt', 'tank', 'tanktop', 'vest', 'weste',
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
    
    console.log('🔍 Extracting garments from page...');
    
    try {
      // Get the current active tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      console.log('Active tab:', tab.url, 'ID:', tab.id);
      
      // Send message to content script
      chrome.tabs.sendMessage(tab.id, { type: 'GET_IMAGES_ON_PAGE' }, (response) => {
        if (chrome.runtime.lastError) {
          console.error('Content script error:', chrome.runtime.lastError.message || chrome.runtime.lastError);
          console.log('Attempting to inject content script...');
          
          // Try to inject content script manually
          chrome.scripting.executeScript({
            target: { tabId: tab.id },
            files: ['content-script.js']
          }, () => {
            if (chrome.runtime.lastError) {
              console.error('Failed to inject content script:', chrome.runtime.lastError.message);
              console.log('Trying direct image search as final fallback...');
              executeDirectImageSearch(tab.id);
              return;
            }
            
            // Try sending message again after injection
            setTimeout(() => {
              chrome.tabs.sendMessage(tab.id, { type: 'GET_IMAGES_ON_PAGE' }, (response) => {
                if (chrome.runtime.lastError) {
                  console.error('Still no response after injection:', chrome.runtime.lastError.message);
                  console.log('Falling back to direct image search...');
                  executeDirectImageSearch(tab.id);
                  return;
                }
                console.log('📨 Got images after injection - Raw response:', response);
                
                // Handle different response formats
                let images = [];
                if (Array.isArray(response)) {
                  images = response;
                } else if (response?.images && Array.isArray(response.images)) {
                  images = response.images;
                } else if (response && typeof response === 'object') {
                  images = Object.values(response).filter(item => item && item.src);
                }
                
                console.log('🎯 Final images after injection:', images);
                displayImagesInPlaceholders(images);
              });
            }, 100);
          });
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
        
        console.log('🎯 Final images to display:', images);
        displayImagesInPlaceholders(images);
      });
      
    } catch (error) {
      console.error('Error extracting garments from page:', error.message || error);
    }
  }

  // Fallback function to search for images directly via script injection
  function executeDirectImageSearch(tabId) {
    chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: function() {
        const images = Array.from(document.images)
          .filter(img => img.src && img.naturalWidth > 100 && img.naturalHeight > 100)
          .slice(0, 4)
          .map(img => ({
            src: img.src,
            width: img.naturalWidth,
            height: img.naturalHeight,
            alt: img.alt || '',
            type: 'img'
          }));
        return images;
      }
    }, (results) => {
      if (chrome.runtime.lastError) {
        console.error('Direct script execution failed:', chrome.runtime.lastError.message);
        displayImagesInPlaceholders([]);
        return;
      }
      
      const images = results?.[0]?.result || [];
      console.log('Got images via direct execution:', images);
      displayImagesInPlaceholders(images);
    });
  }

  // Global variables for pagination
  let allExtractedImages = [];
  let currentImagePage = 0;
  const imagesPerPage = 4;

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
    if (imageData.startsWith('data:')) {
      // It's a data URL, convert directly to blob
      return dataURLToBlob(imageData);
    } else {
      // It's a regular URL, fetch it
      return await fetch(imageData).then(res => res.blob());
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

      // Save to backend database
      const response = await fetch('http://localhost:5000/api/wardrobe/save', {
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
    return wardrobeItems.some(item => item.garment_image === garmentImageData);
  }

  // Function to handle favorite button click
  async function handleFavoriteClick(event, garmentImageData, garmentType, garmentUrl = null) {
    event.stopPropagation(); // Prevent triggering try-on
    
    const favoriteBtn = event.currentTarget;
    const heartIcon = favoriteBtn.querySelector('.heart-icon');
    const garmentItem = favoriteBtn.closest('.garment-item-tryon');
    
    // Show loading state
    heartIcon.textContent = '⏳';
    favoriteBtn.disabled = true;

    try {
      if (favoriteBtn.classList.contains('favorited')) {
        // Remove from wardrobe (implement removeFromWardrobe function if needed)
        favoriteBtn.classList.remove('favorited');
        garmentItem.classList.remove('favorited');
        heartIcon.textContent = '🤍';
        console.log('💔 Removed from wardrobe');
      } else {
        // Add to wardrobe
        const result = await saveToWardrobe(garmentImageData, garmentType, garmentUrl);
        
        if (result.success) {
          favoriteBtn.classList.add('favorited');
          garmentItem.classList.add('favorited');
          heartIcon.textContent = '❤️';
          console.log('💖 Added to wardrobe');
          
          // Show success feedback
          showFavoriteSuccess();
        } else {
          heartIcon.textContent = '🤍';
          console.error('Failed to save:', result.message);
          // Show error message to user
          showFavoriteError(result.message);
        }
      }
    } catch (error) {
      heartIcon.textContent = '🤍';
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

  function showFavoriteError(message) {
    console.error('❌ Error:', message);
    // You can implement error notification here
  }

  // Function to load user's wardrobe from backend
  async function loadUserWardrobe() {
    try {
      if (!currentUser || !currentUser.userID) return;
      
      const response = await fetch(`http://localhost:5000/api/wardrobe/user/${currentUser.userID}`);
      if (response.ok) {
        wardrobeItems = await response.json();
        console.log('👗 Loaded wardrobe items:', wardrobeItems.length);
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
    
    console.log('👗 Displaying wardrobe items:', wardrobeItems.length);
    
    // Hide navigation for wardrobe view
    if (garmentNavigation) {
      garmentNavigation.style.display = 'none';
    }
    
    // Make sure garment preview is visible
    garmentPreview.style.display = 'grid';
    
    let html = '';
    
    // Display wardrobe items in a 2x2 grid
    for (let i = 0; i < 4; i++) {
      if (i < wardrobeItems.length) {
        const item = wardrobeItems[i];
        html += `
          <div class="upload-placeholder garment-item-tryon favorited" style="position: relative; background: #f0f0f0; cursor: pointer;" data-wardrobe-item="${item.id}">
            <img src="${item.garment_image}" 
                 alt="Wardrobe ${item.garment_type}" 
                 style="width: 100%; height: 100%; object-fit: cover; border-radius: 15px;" />
            
            <!-- Favorite Button (already favorited) -->
            <button class="favorite-btn favorited" type="button" disabled>
              <span class="heart-icon">❤️</span>
            </button>
            
            <!-- Garment Type Badge -->
            <div class="garment-type-badge">
              ${item.garment_type.toUpperCase()}
            </div>
            
            <!-- Wardrobe Item Number -->
            <div style="position: absolute; bottom: 2px; right: 2px; background: rgba(0,0,0,0.7); color: white; padding: 2px 4px; border-radius: 2px; font-size: 10px;">
              ${i + 1}
            </div>
            
            <!-- Try-on Hover Badge -->
            <div class="tryon-hover-badge" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; opacity: 0; transition: opacity 0.3s ease; pointer-events: none;">
              👕 Try On
            </div>
            
            <!-- Wardrobe Badge -->
            <div style="position: absolute; top: 2px; left: 2px; background: rgba(231, 76, 60, 0.9); color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px; font-weight: 600;">
              Wardrobe
            </div>
          </div>
        `;
      } else {
        html += `
          <div class="upload-placeholder">
            <span class="upload-text">No more wardrobe items</span>
          </div>
        `;
      }
    }
    
    garmentPreview.innerHTML = html;
    
    // Add event listeners for wardrobe items
    const wardrobeItemsElements = garmentPreview.querySelectorAll('[data-wardrobe-item]');
    wardrobeItemsElements.forEach(element => {
      const itemId = element.dataset.wardrobeItem;
      const wardrobeItem = wardrobeItems.find(item => item.id.toString() === itemId);
      
      if (wardrobeItem) {
        element.addEventListener('click', async () => {
          console.log('🎯 Try-on clicked for wardrobe item:', wardrobeItem.garment_id);
          await performTryOn(wardrobeItem.garment_image, wardrobeItem.garment_type);
        });
      }
    });
    
    console.log('✅ Wardrobe items displayed successfully');
  }

  // Function to toggle between wardrobe and online garments
  function toggleGarmentSource() {
    const toggleBtn = document.getElementById('garment-source-toggle');
    const toggleText = document.getElementById('toggle-text');
    const toggleIcon = document.getElementById('toggle-icon');
    
    if (!toggleBtn || !toggleText || !toggleIcon) return;
    
    if (currentGarmentSource === 'online') {
      // Switch to wardrobe
      currentGarmentSource = 'wardrobe';
      isShowingWardrobe = true;
      toggleText.textContent = 'Switch to Online';
      toggleIcon.textContent = '🌐';
      displayWardrobeItems();
      console.log('👗 Switched to wardrobe view');
    } else {
      // Switch to online
      currentGarmentSource = 'online';
      isShowingWardrobe = false;
      toggleText.textContent = 'Switch to Wardrobe';
      toggleIcon.textContent = '👗';
      
      // Show either uploaded garments or extracted images based on what's available
      if (uploadedGarments && uploadedGarments.length > 0) {
        displayUploadedGarments();
      } else if (allExtractedImages && allExtractedImages.length > 0) {
        renderImagePage();
      } else {
        // Show empty upload placeholders
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
      console.log('🌐 Switched to online view');
    }
  }

  // Function to update toggle button state based on user and wardrobe status
  function updateToggleButtonState() {
    const toggleBtn = document.getElementById('garment-source-toggle');
    const toggleText = document.getElementById('toggle-text');
    const toggleIcon = document.getElementById('toggle-icon');
    
    if (!toggleBtn || !toggleText || !toggleIcon) return;
    
    if (!currentUser || !currentUser.userID) {
      // Guest user or not signed in - disable wardrobe functionality
      toggleBtn.disabled = true;
      toggleBtn.style.opacity = '0.5';
      toggleText.textContent = 'Sign in for Wardrobe';
      toggleIcon.textContent = '🔒';
      toggleBtn.title = 'Sign in to access your wardrobe';
    } else {
      // Signed in user - enable wardrobe functionality
      toggleBtn.disabled = false;
      toggleBtn.style.opacity = '1';
      toggleBtn.title = 'Switch between online garments and your wardrobe';
      
      if (currentGarmentSource === 'wardrobe') {
        toggleText.textContent = 'Switch to Online';
        toggleIcon.textContent = '🌐';
      } else {
        toggleText.textContent = 'Switch to Wardrobe';
        toggleIcon.textContent = '👗';
      }
    }
  }

  async function performTryOn(garmentImageData, garmentType) {
    console.log(`🎯 performTryOn function called globally!`);
    console.log(`🎯 Starting try-on with ${garmentType} garment`);
    console.log('📸 Garment image data:', garmentImageData ? 'Present' : 'Missing');
    
    const tryonResult = document.getElementById('tryon-result');
    console.log('🔍 tryonResult element exists:', !!tryonResult);
    
    if (!tryonResult) {
      console.error('❌ tryonResult element not found');
      return;
    }
    
    // Get processed avatar from storage
    return new Promise((resolve, reject) => {
      chrome.storage.local.get(['avatarBgRemovedImg', 'avatarImg'], async function(result) {
        const avatarData = result.avatarBgRemovedImg || result.avatarImg;
        
        if (!avatarData) {
          tryonResult.innerHTML = '📷 Please upload your photo first';
          showTryonResult();
          reject('No avatar uploaded');
          return;
        }
        
        if (!garmentImageData) {
          tryonResult.innerHTML = '👕 Please select a garment';
          showTryonResult();
          reject('No garment selected');
          return;
        }
        
        // Create close button element instead of inline onclick
        const processingCloseBtn = document.createElement('button');
        processingCloseBtn.className = 'tryon-close-btn';
        processingCloseBtn.innerHTML = '&times;';
        processingCloseBtn.addEventListener('click', hideTryonResult);
        
        const processingText = document.createElement('span');
        processingText.textContent = ' Processing your try-on...';
        processingText.style.cssText = 'background: #666; color: white; padding: 8px 12px; border-radius: 6px; font-size: 14px; font-weight: 500;';
        
        tryonResult.innerHTML = '';
        tryonResult.appendChild(processingCloseBtn);
        tryonResult.appendChild(processingText);
        showTryonResult();
        
        try {
          // Try to remove background from garment, but continue if it fails
          let garmentBgRemovedBlob;
          try {
            const garmentBlob = await safeImageToBlob(garmentImageData);
            const garmentForm = new FormData();
            garmentForm.append('file', garmentBlob, 'garment.png');
            const garmentBgResp = await fetch('http://192.168.178.48:5000/api/remove-bg', {
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
          
          // Call try-on API
          const formData = new FormData();
          // Use processed avatar image  
          const avatarBlob = await safeImageToBlob(avatarData);
          formData.append('person_image', avatarBlob, 'avatar.png');
          formData.append('cloth_image', garmentBgRemovedBlob, 'garment.png');
          formData.append('cloth_type', garmentType); // Use the garment type (upper/lower)
          formData.append('num_inference_steps',50);
          
          console.log('Sending try-on request with garment type:', garmentType);
          
          const response = await fetch('http://localhost:5000/api/tryon', {
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
            
            const bgRemovalResp = await fetch('http://localhost:5000/api/remove-bg', {
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
          resolve();
          
        } catch (error) {
          console.error('Try-on error:', error.message || error);
          if (error.message && error.message.includes('ERR_CONNECTION_TIMED_OUT')) {
            tryonResult.innerHTML = '🔌 Server connection timed out. Please check if the backend server at localhost:5000 is running and accessible.';
          } else if (error.message && error.message.includes('Failed to fetch')) {
            tryonResult.innerHTML = '🔌 Cannot connect to try-on server. Please verify the server is running at localhost:5000.';
          } else {
            tryonResult.innerHTML = `❌ Try-on failed: ${error.message || 'Unknown error'}`;
          }
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
    if (tryonResult) {
      tryonResult.style.display = 'none';
    }
    if (tryonBody) {
      tryonBody.style.display = 'none';
    }
  }

  // Function to display images with pagination
  function displayImagesInPlaceholders(images) {
    console.log('🖼️ displayImagesInPlaceholders called with:', images.length, 'images');
    
    const garmentPreview = document.getElementById('garment-preview');
    console.log('🎯 garmentPreview element:', garmentPreview);
    
    if (!garmentPreview) {
      console.error('❌ garment-preview element not found!');
      return;
    }
    
    // Filter out transparent/placeholder images and take valid ones
    const validImages = images.filter(img => 
      img && img.src && 
      !img.src.includes('transparent-background.png') &&
      !img.src.includes('placeholder') &&
      img.width > 50 && img.height > 50
    );
    
    console.log('🔍 Filtered valid images:', validImages.length, 'from', images.length, 'total');
    
    // Store all images for pagination
    allExtractedImages = validImages;
    currentImagePage = 0;
    
    // Render the current page
    renderImagePage();
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
    garmentPreview.style.display = 'block';
    
    const totalPages = Math.ceil(allExtractedImages.length / imagesPerPage);
    const startIndex = currentImagePage * imagesPerPage;
    const endIndex = Math.min(startIndex + imagesPerPage, allExtractedImages.length);
    const currentImages = allExtractedImages.slice(startIndex, endIndex);
    
    console.log(`📋 Rendering page ${currentImagePage + 1}/${totalPages}, showing images ${startIndex + 1}-${endIndex}`);
    
    // Update navigation visibility and state
    if (garmentNavigation && totalPages > 1) {
      garmentNavigation.style.display = 'flex';
      
      // Update page indicator
      if (pageIndicator) {
        pageIndicator.textContent = `${currentImagePage + 1} / ${totalPages} (${allExtractedImages.length} total)`;
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
    let gridHtml = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px;">';
    for (let i = 0; i < imagesPerPage; i++) {
      if (i < currentImages.length) {
        const imgSrc = currentImages[i].src;
        const imageNumber = startIndex + i + 1;
        const isInWardrobe = isGarmentInWardrobe(imgSrc);
        console.log(`🖼️ Adding image ${imageNumber}:`, imgSrc);
        
        gridHtml += `
          <div class="upload-placeholder garment-item-tryon ${isInWardrobe ? 'favorited' : ''}" style="position: relative; background: #f0f0f0; cursor: pointer;" data-image-src="${imgSrc}">
            <img src="${imgSrc}" 
                 alt="Garment ${imageNumber}" 
                 style="width: 100%; height: 100%; object-fit: cover; border-radius: 15px;" 
                 onerror="console.error('❌ Failed to load image:', this.src); this.style.display='none'; this.nextElementSibling.style.display='flex';"
                 onload="console.log('✅ Image loaded successfully:', this.src);" />
            <span class="upload-text" style="display: none; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(255,0,0,0.8); color: white; padding: 4px; border-radius: 4px; font-size: 10px;">Failed</span>
            
            <!-- Favorite Button -->
            <button class="favorite-btn ${isInWardrobe ? 'favorited' : ''}" type="button">
              <span class="heart-icon">${isInWardrobe ? '❤️' : '🤍'}</span>
            </button>
            
            <!-- Image Number Badge -->
            <div style="position: absolute; bottom: 2px; right: 2px; background: rgba(0,0,0,0.7); color: white; padding: 2px 4px; border-radius: 2px; font-size: 10px;">
              ${imageNumber}
            </div>
            
            <!-- Try-on Hover Badge -->
            <div class="tryon-hover-badge" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; opacity: 0; transition: opacity 0.3s ease; pointer-events: none;">
              👕 Try On
            </div>
            
            <!-- Favorite Status -->
            <div class="favorite-status">In Wardrobe</div>
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
    gridHtml += '</div>';
    
    // Set only the grid content
    garmentPreview.innerHTML = gridHtml;
    
    // Add event listeners for try-on functionality and favorite buttons
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
        
        // Add favorite button listener
        const favoriteBtn = item.querySelector('.favorite-btn');
        if (favoriteBtn) {
          favoriteBtn.addEventListener('click', async (event) => {
            const garmentType = await detectGarmentTypeFromURL();
            await handleFavoriteClick(event, imgSrc, garmentType, window.location.href);
          });
        }
      }
    });
    
    console.log('✅ Image page rendered successfully with', tryonItems.length, 'try-on items');
    
    // Force a reflow to ensure images are displayed
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
  signinBtn.addEventListener('click', async function() {
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
      // Call the login API
      const response = await fetch('http://localhost:5000/api/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email: email,
          password: password
        })
      });

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
  if (garmentSourceToggle) {
    garmentSourceToggle.addEventListener('click', function() {
      // Only allow toggle if user is signed in and has wardrobe items
      if (!currentUser || !currentUser.userID) {
        console.log('⚠️ Please sign in to access wardrobe');
        // You could show a notification here
        return;
      }
      
      if (currentGarmentSource === 'wardrobe' || wardrobeItems.length === 0) {
        // Load wardrobe if switching to wardrobe mode and items not loaded
        if (currentGarmentSource === 'online' && wardrobeItems.length === 0) {
          loadUserWardrobe().then(() => {
            if (wardrobeItems.length > 0) {
              toggleGarmentSource();
            } else {
              console.log('ℹ️ No wardrobe items found');
              // You could show a notification here
            }
          });
        } else {
          toggleGarmentSource();
        }
      } else {
        toggleGarmentSource();
      }
    });
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
      const response = await fetch('http://localhost:5000/api/create-account', {
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
      
      const response = await fetch('http://localhost:5000/api/update-avatar', {
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
      
      const response = await fetch(`http://localhost:5000/api/get-avatar/${userId}`);
      
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

  async function processAvatarUpload(imgData) {
    console.log('processAvatarUpload called');
    chrome.storage.local.set({ avatarImg: imgData });
    avatarFile = imgData;
    
    try {
      // Remove background from avatar
      const avatarBlob = await fetch(imgData).then(res => res.blob());
      const avatarForm = new FormData();
      avatarForm.append('file', avatarBlob, 'avatar.png');
      
      const avatarBgResp = await fetch('http://localhost:5000/api/remove-bg', {
        method: 'POST',
        body: avatarForm,
      });
      
      if (!avatarBgResp.ok) {
        renderAvatarPreview();
        if (avatarPreview) {
          const cameraOverlay = avatarPreview.querySelector('.avatar-upload-camera-overlay');
          if (cameraOverlay) {
            cameraOverlay.insertAdjacentHTML('beforebegin', '❌ Failed to process avatar');
          }
        }
        return;
      }
      
      const avatarBgRemovedBlob = await avatarBgResp.blob();
      const bgReader = new FileReader();
      
      bgReader.onloadend = async function() {
        renderAvatarPreview(bgReader.result);
        chrome.storage.local.set({ avatarBgRemovedImg: bgReader.result });
        avatarFile = bgReader.result;
        
        // Save processed avatar to database
        chrome.storage.local.get(['userId'], async function(result) {
          if (result.userId) {
            console.log('💾 Saving processed avatar to database');
            const saved = await saveAvatarToDatabase(bgReader.result, result.userId);
            if (saved) {
              console.log('✅ Processed avatar saved to database');
            }
          }
        });
      };
      
      bgReader.readAsDataURL(avatarBgRemovedBlob);
    } catch (error) {
      console.error('Error processing avatar:', error.message || error);
      renderAvatarPreview();
      if (avatarPreview) {
        const cameraOverlay = avatarPreview.querySelector('.avatar-upload-camera-overlay');
        if (cameraOverlay) {
          cameraOverlay.insertAdjacentHTML('beforebegin', '❌ Failed to process avatar');
        }
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
        if (currentImagePage > 0) {
          currentImagePage--;
          renderImagePage();
        }
      });
    }

    if (nextImagesBtn) {
      nextImagesBtn.addEventListener('click', () => {
        const totalPages = Math.ceil(allExtractedImages.length / imagesPerPage);
        if (currentImagePage < totalPages - 1) {
          currentImagePage++;
          renderImagePage();
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
  // Load avatar from database if user is logged in, otherwise load from local storage
  chrome.storage.local.get(['userId', 'avatarBgRemovedImg', 'avatarImg', 'avatarDataUrl'], async function(result) {
    // Check if we have avatar data from sign-in first
    if (result.avatarDataUrl) {
      console.log('🖼️ Loading avatar from sign-in data');
      renderAvatarPreview(result.avatarDataUrl);
      // Also store it in the legacy key for consistency
      chrome.storage.local.set({ avatarBgRemovedImg: result.avatarDataUrl });
    } else if (result.userId && !result.avatarBgRemovedImg && !result.avatarImg) {
      console.log('🔄 No local avatar found, trying to load from database for user:', result.userId);
      // Try to load avatar from database
      const databaseAvatar = await loadAvatarFromDatabase(result.userId);
      if (databaseAvatar) {
        console.log('✅ Avatar loaded from database, converting to data URL');
        // Convert blob URL to data URL for consistency
        try {
          const response = await fetch(databaseAvatar);
          const blob = await response.blob();
          const reader = new FileReader();
          reader.onload = function(e) {
            const imageData = e.target.result;
            chrome.storage.local.set({ 
              avatarBgRemovedImg: imageData,
              avatarDataUrl: imageData 
            });
            renderAvatarPreview(imageData);
            console.log('✅ Database avatar synchronized to local storage');
          };
          reader.readAsDataURL(blob);
        } catch (error) {
          console.error('❌ Error converting database avatar:', error);
          renderAvatarPreview();
        }
      } else {
        console.log('ℹ️ No avatar found in database');
        renderAvatarPreview();
      }
    } else {
      // Use local storage avatar if available
      const avatarData = result.avatarBgRemovedImg || result.avatarImg;
      console.log('Loading stored avatar data:', avatarData ? 'found locally' : 'none');
      renderAvatarPreview(avatarData);
      // Sync to avatarDataUrl if not present
      if (avatarData && !result.avatarDataUrl) {
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
    console.log('🔍 garmentPreview element:', garmentPreview);
    
    if (!garmentPreview) {
      console.error('❌ Garment preview element not found');
      return;
    }
    
    // Make sure garment preview is visible
    garmentPreview.style.display = 'grid';
    
    let html = '';
    
    // Display uploaded garments in order
    for (let i = 0; i < 4; i++) {
      if (i < uploadedGarments.length) {
        const garment = uploadedGarments[i];
        const isInWardrobe = isGarmentInWardrobe(garment.imgData);
        html += `
          <div class="upload-placeholder uploaded-garment garment-item-tryon ${isInWardrobe ? 'favorited' : ''}" data-garment-index="${i}" style="position: relative; cursor: pointer;">
            <img src="${garment.imgData}" alt="${garment.garmentType} Garment" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;" />
            
            <!-- Favorite Button -->
            <button class="favorite-btn ${isInWardrobe ? 'favorited' : ''}" type="button">
              <span class="heart-icon">${isInWardrobe ? '❤️' : '🤍'}</span>
            </button>
            
            <button class="garment-remove-btn" data-remove-index="${i}" title="Remove garment">
              ×
            </button>
            <div class="garment-type-badge">
              ${garment.garmentType}
            </div>
            <div class="garment-number-badge">
              ${i + 1}
            </div>
            <div class="tryon-hover-badge" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; opacity: 0; transition: opacity 0.3s ease; pointer-events: none;">
              👕 Try On
            </div>
            
            <!-- Favorite Status -->
            <div class="favorite-status">In Wardrobe</div>
          </div>
        `;
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
      
      // Add favorite button listener
      const favoriteBtn = item.querySelector('.favorite-btn');
      if (favoriteBtn) {
        favoriteBtn.addEventListener('click', (event) => {
          handleFavoriteClick(event, selectedGarment.imgData, selectedGarment.garmentType, null);
        });
      }
      
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
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
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
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
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
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
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
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
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
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;">
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
      console.log('Refresh button clicked - resetting current session');
      
      if (confirm('Reset current session? This will clear uploaded images but keep you signed in.')) {
        console.log('User confirmed refresh');
        
        // Reset avatar data
        // renderAvatarPreview();
        // avatarFile = null;
        // avatarBgRemovedBlob = null;
        
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
        
        // Reset useGarmentCheckbox variable
        useGarmentCheckbox = false;
        
        // Clear image storage but keep user session
        chrome.storage.local.remove([
          'avatarImg', 
          'avatarBgRemovedImg', 
          'uploadedGarments',
          'garmentImg',
          'garmentType'
        ]);
        
        console.log('Session refresh completed');
      } else {
        console.log('User cancelled refresh');
      }
    });
  } else {
    console.log('Note: refresh-btn element not found');
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
        
        const testResponse = await fetch('http://localhost:5000/api/tryon', {
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
          tryonResult.innerHTML = '⏱️ Connection timeout: Server at localhost:5000 is not responding. Please check if the backend server is running.';
        } else if (error.message.includes('ERR_CONNECTION_REFUSED')) {
          tryonResult.innerHTML = '🚫 Connection refused: Server at localhost:5000 is not accepting connections. Please start the backend server.';
        } else if (error.message.includes('ERR_CONNECTION_TIMED_OUT')) {
          tryonResult.innerHTML = '⏱️ Connection timed out: Cannot reach server at localhost:5000. Check network connectivity.';
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
    
    // Update toggle button state based on user status
    updateToggleButtonState();
    
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
      tryonResult.style.display = 'none';
      // Remove class to show avatar again
      const mainContainer = document.querySelector('.main-container');
      if (mainContainer) {
        mainContainer.classList.remove('tryon-active');
      }
    }
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

  // Make functions globally available
  window.showTryonResult = showTryonResult;
  window.hideTryonResult = hideTryonResult;
});
