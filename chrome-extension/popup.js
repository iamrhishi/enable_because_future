document.addEventListener('DOMContentLoaded', function() {
        // Function to fetch avatar from backend and update Chrome storage
        async function fetchAndStoreAvatar() {
          chrome.storage.local.get(['jwtToken', 'userID'], async function(result) {
            const jwtToken = result.jwtToken;
            const userID = result.userID;
            if (!jwtToken || !userID) return;
            try {
              // Use the new /api/avatar/<userid> endpoint to get the avatar file directly
              const response = await fetch(`${API_BASE_URL}/api/avatar/${userID}`, {
                method: 'GET'
              });
              if (response.ok) {
                // Get the blob and convert to data URL
                const blob = await response.blob();
                const reader = new FileReader();
                reader.onloadend = function() {
                  const avatarDataUrl = reader.result;
                  chrome.storage.local.set({ avatarDataUrl });
                  renderAvatarPreview(avatarDataUrl);
                };
                reader.readAsDataURL(blob);
              } else {
                // Fallback: try to get avatar_url from the authenticated endpoint
                const authResponse = await fetch(`${API_BASE_URL}/api/users/avatar`, {
                  method: 'GET',
                  headers: { 'Authorization': `Bearer ${jwtToken}` }
                });
                if (authResponse.ok) {
                  const result = await authResponse.json();
                  if (result.success && result.data && result.data.avatar_url) {
                    chrome.storage.local.set({ avatarDataUrl: result.data.avatar_url });
                    renderAvatarPreview(result.data.avatar_url);
                  } else {
                    chrome.storage.local.set({ avatarDataUrl: null });
                    renderAvatarPreview(null);
                  }
                } else {
                  chrome.storage.local.set({ avatarDataUrl: null });
                  renderAvatarPreview(null);
                }
              }
            } catch (error) {
              console.error('Failed to fetch avatar:', error);
              chrome.storage.local.set({ avatarDataUrl: null });
              renderAvatarPreview(null);
            }
          });
        }
      const menuBar = document.getElementById('bottom-menu-bar');

      function showSignInPage() {
        signinPage.style.display = 'flex';
        if (accountCreationPage) accountCreationPage.style.display = 'none';
        if (userProfilePage) userProfilePage.style.display = 'none';
        if (wardrobePage) wardrobePage.style.display = 'none';
        mainApp.style.display = 'none';
        if (menuBar) menuBar.style.display = 'none';
      }

      function showAccountCreationPage() {
        signinPage.style.display = 'none';
        if (accountCreationPage) accountCreationPage.style.display = 'flex';
        if (userProfilePage) userProfilePage.style.display = 'none';
        if (wardrobePage) wardrobePage.style.display = 'none';
        mainApp.style.display = 'none';
        if (menuBar) menuBar.style.display = 'none';
      }

      function showMainApp() {
        signinPage.style.display = 'none';
        if (accountCreationPage) accountCreationPage.style.display = 'none';
        if (userProfilePage) userProfilePage.style.display = 'none';
        if (wardrobePage) wardrobePage.style.display = 'none';
        mainApp.style.display = 'flex';
        if (menuBar) menuBar.style.display = 'flex';
        // ...existing code...
        updateToggleButtonState();
        // ...existing code...
        fetchAndStoreAvatar();
        initializeMainApp();
      }

      function showWardrobePage() {
        // Hide all other pages
        signinPage.style.display = 'none';
        if (accountCreationPage) accountCreationPage.style.display = 'none';
        if (userProfilePage) userProfilePage.style.display = 'none';
        if (mainApp) mainApp.style.display = 'none';
        const savedPage = document.getElementById('saved-page');
        if (savedPage) savedPage.style.display = 'none';
        
        // Show wardrobe page and header
        if (wardrobePage) wardrobePage.style.display = 'flex';
        if (menuBar) menuBar.style.display = 'flex';
        const extensionHeader = document.querySelector('.extension-header');
        if (extensionHeader) extensionHeader.style.display = 'flex';
        loadWardrobeItems();
      }
    // Avatar upload elements
    const avatarUploadInput = document.getElementById('avatar-upload');
    const avatarPreview = document.getElementById('avatar-preview');
    const avatarCameraBtn = document.createElement('button');
    avatarCameraBtn.className = 'avatar-upload-camera';
    avatarCameraBtn.innerHTML = '<img src="camera.png" alt="Upload Avatar" />';
    avatarPreview.appendChild(avatarCameraBtn);

    // Handle camera button click
    avatarCameraBtn.addEventListener('click', () => {
      avatarUploadInput.click();
    });

    // Handle avatar file selection
    avatarUploadInput.addEventListener('change', async (event) => {
      const file = event.target.files[0];
      if (!file) return;
      // Show loading state
      avatarCameraBtn.disabled = true;
      avatarCameraBtn.innerHTML = 'Uploading...';

      // Prepare form data for backend
      const formData = new FormData();
      formData.append('user_id', currentUser?.userID || '');
      formData.append('avatar', file);

      // Retrieve JWT token from chrome storage
      chrome.storage.local.get(['jwtToken'], async function(tokenResult) {
        const jwtToken = tokenResult.jwtToken;
        try {
          // Call avatar creation API (adjust endpoint as per backend)
          const response = await fetch(`${API_BASE_URL}/api/save-avatar`, {
            method: 'POST',
            body: formData,
            headers: jwtToken ? { 'Authorization': `Bearer ${jwtToken}` } : undefined
          });
          if (!response.ok) throw new Error('Avatar upload failed');
          const result = await response.json();
          // Show avatar image on home screen
          if (result.success && result.data && result.data.avatar_url) {
            avatarPreview.innerHTML = `<img src="${result.data.avatar_url}" class="avatar-display-image" alt="Avatar" />`;
            // Store new avatar URL in Chrome storage for immediate display
            chrome.storage.local.set({ avatarDataUrl: result.data.avatar_url });
          } else {
            avatarPreview.innerHTML = '<span>Avatar upload failed</span>';
          }
        } catch (error) {
          avatarPreview.innerHTML = '<span>Avatar upload failed</span>';
          console.error('Avatar upload error:', error);
        } finally {
          avatarCameraBtn.disabled = false;
          avatarCameraBtn.innerHTML = '<img src="camera.png" alt="Upload Avatar" />';
        }
      });
    });
  // ===== BACKEND URL CONFIGURATION =====
  // Use dev branch backend
  const API_BASE_URL = 'http://localhost:8000'; // Ensure this matches backend port
  // const API_BASE_URL = 'http://34.32.121.88:5001';


  // ===== GLOBAL VARIABLES =====
  // Wardrobe functionality
  let currentUser = null; // Will store user info after sign-in
  let wardrobeItems = []; // Cache for wardrobe items

  // Garment source toggle
  let currentGarmentSource = 'online'; // 'online' or 'wardrobe'
  let isShowingWardrobe = false;

  // ===== LAYERED TRY-ON STATE =====
  let currentWorkingAvatar = null; // Original avatar (base64) or try-on result blob
  let originalAvatarBase64 = null; // Store original for reset
  let appliedGarments = []; // Track applied garments: [{type, src}]
  let tryOnCount = 0; // 0, 1, or 2 (max 2 layers)
  let firstGarmentType = null; // 'upper' or 'lower'
  let tryOnInProgress = false; // Prevent multiple simultaneous try-ons

  // ===== BACKGROUND THEME STATE =====
  let currentBackground = 'image'; // 'image', 'white', or 'blue'

  // ===== TRY-ON PERSISTENCE FUNCTIONS =====
  // Save try-on state to Chrome storage
  function saveTryOnState(resultDataUrl) {
    const state = {
      currentWorkingAvatar,
      originalAvatarBase64,
      appliedGarments,
      tryOnCount,
      firstGarmentType,
      resultDataUrl
    };
    chrome.storage.local.set({ tryOnState: state });
    console.log('💾 Try-on state saved to storage:', { tryOnCount, appliedCount: appliedGarments.length });
  }

  // Restore try-on state from Chrome storage
  function restoreTryOnState() {
    chrome.storage.local.get('tryOnState', function(result) {
      if (result.tryOnState) {
        const state = result.tryOnState;
        currentWorkingAvatar = state.currentWorkingAvatar;
        originalAvatarBase64 = state.originalAvatarBase64;
        appliedGarments = state.appliedGarments || [];
        tryOnCount = state.tryOnCount || 0;
        firstGarmentType = state.firstGarmentType;
        
        console.log('📂 Try-on state restored from storage:', { tryOnCount, appliedCount: appliedGarments.length });
        
        // Display the saved result if it exists
        if (state.resultDataUrl && tryOnCount > 0) {
          displayPersistedTryOnResult(state.resultDataUrl);
        }
      }
    });
  }

  // Display the persisted try-on result
  function displayPersistedTryOnResult(resultDataUrl) {
    const tryonResult = document.getElementById('tryon-result');
    if (!tryonResult) return;
    
    console.log('📸 displayPersistedTryOnResult called');
    
    // Create wrapper for image
    const imgWrapper = document.createElement('div');
    imgWrapper.style.cssText = 'position: relative; width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;';
    
    const resultImg = document.createElement('img');
    resultImg.src = resultDataUrl;
    resultImg.alt = 'Try-On Result';
    resultImg.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px;';
    
    // Create save button
    const saveBtn = document.createElement('button');
    saveBtn.className = 'tryon-save-btn';
    saveBtn.innerHTML = '❤️';
    saveBtn.title = 'Save to Database';
    saveBtn.style.cssText = 'position: absolute; top: 50px; right: 12px; width: 32px; height: 32px; background: rgba(255, 255, 255, 0.9); border: none; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 18px; z-index: 1002; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);';
    saveBtn.addEventListener('click', async () => {
      console.log('❤️ Heart button clicked');
      saveBtn.disabled = true;
      saveBtn.style.opacity = '0.6';
      const success = await saveResultToDatabase(resultDataUrl);
      if (success) {
        saveBtn.innerHTML = '❤️';
        saveBtn.classList.add('saved-success');
        console.log('✅ Try-on saved successfully');
        setTimeout(() => {
          saveBtn.disabled = false;
          saveBtn.style.opacity = '1';
          saveBtn.innerHTML = '❤️';
          saveBtn.classList.remove('saved-success');
        }, 2000);
      } else {
        saveBtn.disabled = false;
        saveBtn.style.opacity = '1';
        saveBtn.innerHTML = '❤️';
        console.log('❌ Failed to save try-on');
        alert('Failed to save. Please try again.');
      }
    });
    saveBtn.addEventListener('mouseover', function() {
      this.style.background = 'rgba(255, 255, 255, 1)';
      this.style.transform = 'scale(1.1)';
      this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.2)';
    });
    saveBtn.addEventListener('mouseout', function() {
      this.style.background = 'rgba(255, 255, 255, 0.9)';
      this.style.transform = 'scale(1)';
      this.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.15)';
    });
    
    // Create button container for vertical stacking
    const buttonContainer = document.createElement('div');
    buttonContainer.style.cssText = 'position: absolute; top: 0; right: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1001;';
    buttonContainer.appendChild(saveBtn);
    
    // Give buttons pointer events
    saveBtn.style.pointerEvents = 'auto';
    
    imgWrapper.appendChild(resultImg);
    imgWrapper.appendChild(buttonContainer);
    
    tryonResult.innerHTML = '';
    tryonResult.appendChild(imgWrapper);
    
    console.log('🖼️ Buttons appended, close:', resultCloseBtn, 'heart:', saveBtn);
    
    // Show the layered UI with buttons
    showLayeredTryOnUI();
    showTryonResult();
    
    console.log('🖼️ Persisted try-on result displayed');
  }

  // Reset try-on state variables
  function resetTryOnState() {
    currentWorkingAvatar = null;
    appliedGarments = [];
    tryOnCount = 0;
    firstGarmentType = null;
  }

  // ===== SAVED TRY-ONS DATABASE FUNCTIONS =====
  
  // Save try-on result to both browser storage and backend database
  async function saveResultToDatabase(resultDataUrl) {
    try {
      // Get JWT token from storage
      const storageResult = await new Promise((resolve) => {
        chrome.storage.local.get('jwtToken', resolve);
      });
      
      const jwtToken = storageResult.jwtToken;
      if (!jwtToken) {
        console.warn('⚠️ No JWT token found, skipping database save');
        return false;
      }

      // Prepare payload
      const payload = {
        result_image: resultDataUrl,
        applied_garments: appliedGarments,
        try_on_count: tryOnCount,
        original_avatar: originalAvatarBase64
      };

      // Call backend API
      const response = await fetch(`${API_BASE_URL}/api/tryon-results`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${jwtToken}`
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        console.error('❌ Failed to save try-on result to database:', response.status);
        return false;
      }

      const data = await response.json();
      console.log('✅ Try-on result saved to database with ID:', data.data?.id);
      return true;
    } catch (error) {
      console.error('❌ Error saving to database:', error);
      return false;
    }
  }

  // Fetch all saved try-ons for current user
  async function fetchSavedTryOns() {
    try {
      const storageResult = await new Promise((resolve) => {
        chrome.storage.local.get('jwtToken', resolve);
      });
      
      const jwtToken = storageResult.jwtToken;
      if (!jwtToken) {
        console.warn('⚠️ No JWT token found');
        return [];
      }

      const response = await fetch(`${API_BASE_URL}/api/tryon-results`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${jwtToken}`
        }
      });

      if (!response.ok) {
        console.error('❌ Failed to fetch saved try-ons:', response.status);
        return [];
      }

      const data = await response.json();
      console.log('✅ Fetched saved try-ons:', data.data?.length || 0);
      return data.data || [];
    } catch (error) {
      console.error('❌ Error fetching saved try-ons:', error);
      return [];
    }
  }

  // Get details of a specific saved try-on
  async function fetchSavedTryOnDetails(resultId) {
    try {
      const storageResult = await new Promise((resolve) => {
        chrome.storage.local.get('jwtToken', resolve);
      });
      
      const jwtToken = storageResult.jwtToken;
      if (!jwtToken) return null;

      const response = await fetch(`${API_BASE_URL}/api/tryon-results/${resultId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${jwtToken}`
        }
      });

      if (!response.ok) {
        console.error('❌ Failed to fetch details for result:', resultId);
        return null;
      }

      const data = await response.json();
      return data.data || null;
    } catch (error) {
      console.error('❌ Error fetching try-on details:', error);
      return null;
    }
  }

  // Delete a saved try-on
  async function deleteSavedTryOn(resultId) {
    try {
      const storageResult = await new Promise((resolve) => {
        chrome.storage.local.get('jwtToken', resolve);
      });
      
      const jwtToken = storageResult.jwtToken;
      if (!jwtToken) return false;

      const response = await fetch(`${API_BASE_URL}/api/tryon-results/${resultId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${jwtToken}`
        }
      });

      if (!response.ok) {
        console.error('❌ Failed to delete try-on:', resultId);
        return false;
      }

      console.log('✅ Try-on deleted successfully:', resultId);
      return true;
    } catch (error) {
      console.error('❌ Error deleting try-on:', error);
      return false;
    }
  }

  // Display saved try-ons in the saved page
  async function displaySavedTryOns() {
    const savedList = document.getElementById('saved-results-list');
    if (!savedList) return;

    // Show loading state
    savedList.innerHTML = '<div class="saved-empty-state"><p>Loading...</p></div>';

    // Fetch saved try-ons
    const results = await fetchSavedTryOns();

    if (!results || results.length === 0) {
      savedList.innerHTML = `
        <div class="saved-empty-state">
          <p>No saved try-ons yet</p>
          <p class="saved-empty-hint">Try-ons you save will appear here</p>
        </div>
      `;
      return;
    }

    // Build list HTML
    savedList.innerHTML = '';
    results.forEach((result) => {
      const item = document.createElement('div');
      item.className = 'saved-result-item';
      
      // Format date
      const date = new Date(result.created_at);
      const timeStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      // Parse applied_garments if it's JSON string
      let garmentsText = '';
      if (typeof result.applied_garments === 'string') {
        try {
          const garments = JSON.parse(result.applied_garments);
          garmentsText = garments.map(g => `${g.type} (${g.id})`).join(', ');
        } catch (e) {
          garmentsText = result.applied_garments;
        }
      } else if (Array.isArray(result.applied_garments)) {
        garmentsText = result.applied_garments.map(g => `${g.type} (${g.id})`).join(', ');
      }

      item.innerHTML = `
        <img src="${result.result_image}" alt="Try-on result" class="saved-result-thumbnail" />
        <div class="saved-result-info">
          <div class="saved-result-details">
            <div class="saved-result-count">Layers: ${result.try_on_count}/2</div>
            <div class="saved-result-garments">${garmentsText || 'No details'}</div>
            <div class="saved-result-time">${timeStr}</div>
          </div>
        </div>
        <div class="saved-result-actions">
          <button class="saved-result-btn load-btn" data-result-id="${result.id}">Load</button>
          <button class="saved-result-btn delete-btn" data-result-id="${result.id}">Delete</button>
        </div>
      `;

      // Load button handler
      const loadBtn = item.querySelector('.load-btn');
      loadBtn.addEventListener('click', async () => {
        await loadSavedTryOn(result.id);
      });

      // Delete button handler
      const deleteBtn = item.querySelector('.delete-btn');
      deleteBtn.addEventListener('click', async () => {
        if (confirm('Delete this saved try-on?')) {
          const success = await deleteSavedTryOn(result.id);
          if (success) {
            displaySavedTryOns(); // Refresh the list
          }
        }
      });

      savedList.appendChild(item);
    });
  }

  // Load a saved try-on and display it
  async function loadSavedTryOn(resultId) {
    const details = await fetchSavedTryOnDetails(resultId);
    if (!details) {
      alert('Failed to load try-on details');
      return;
    }

    // Restore state from saved try-on
    currentWorkingAvatar = details.result_image;
    originalAvatarBase64 = details.original_avatar;
    appliedGarments = details.applied_garments || [];
    tryOnCount = details.try_on_count || 0;
    firstGarmentType = appliedGarments.length > 0 ? appliedGarments[0].type : null;

    console.log('📂 Loaded saved try-on:', { tryOnCount, appliedCount: appliedGarments.length });

    // Switch to main app
    showMainApp();

    // Display the result
    setTimeout(() => {
      displayPersistedTryOnResult(details.result_image);
    }, 200);
  }

  // Signout button - handles all signout buttons (main app, wardrobe, saved page)
  document.addEventListener('click', (e) => {
    const isSignoutBtn = e.target.id === 'signout-btn' || e.target.closest('#signout-btn') ||
                         e.target.id === 'signout-btn-saved' || e.target.closest('#signout-btn-saved');
    
    if (isSignoutBtn) {
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
    }
  });

  // Refresh button - handles all refresh buttons (main app, wardrobe, saved page)
  document.addEventListener('click', (e) => {
    const isRefreshBtn = e.target.id === 'refresh-btn' || e.target.closest('#refresh-btn') ||
                         e.target.id === 'refresh-btn-saved' || e.target.closest('#refresh-btn-saved');
    
    if (isRefreshBtn) {
      console.log('Refresh button clicked - reloading saved try-ons');
      
      // Get current page
      const savedPage = document.getElementById('saved-page');
      if (savedPage && savedPage.style.display !== 'none') {
        // Reload saved page
        displaySavedTryOns();
      } else {
        // Original refresh logic for main app
        console.log('Refresh button clicked - resetting current session');
        
        if (confirm('Reset current session? This will clear uploaded images but keep you signed in.')) {
          console.log('User confirmed refresh');
          
          // Reset garment data
          uploadedGarments = [];
          garmentImgData = null;
          
          // Reset try-on result if it exists
          const tryonResult = document.getElementById('tryon-result');
          if (tryonResult) {
            tryonResult.innerHTML = '';
          }
          
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
      }
    }
  });

  // Background theme button - handles all background theme buttons
  document.addEventListener('click', (e) => {
    const isBgThemeBtn = e.target.id === 'bg-theme-btn' || e.target.closest('#bg-theme-btn') ||
                         e.target.id === 'bg-theme-btn-saved' || e.target.closest('#bg-theme-btn-saved');
    
    if (isBgThemeBtn) {
      console.log('Background theme button clicked - cycling background');
      cycleBackgroundTheme();
    }
  });

  // Function to cycle through background themes
  function cycleBackgroundTheme() {
    const themes = ['image', 'white', 'blue'];
    const currentIndex = themes.indexOf(currentBackground);
    const nextIndex = (currentIndex + 1) % themes.length;
    setBackground(themes[nextIndex]);
    console.log(`🎨 Cycled to background: ${themes[nextIndex]}`);
  }
  function showBackgroundThemeModal() {
    return new Promise((resolve) => {
      // Modal function removed - now cycles directly on button click
      resolve();
    });
  }


  // Function to set background
  function setBackground(theme) {
    currentBackground = theme;
    chrome.storage.local.set({ backgroundTheme: theme });
    console.log('🎨 Background set to:', theme);

    const mainApp = document.getElementById('main-app');
    const wardrobePage = document.getElementById('wardrobe-page');

    if (theme === 'image') {
      if (mainApp) mainApp.style.background = 'url("Hintegrund Dressing Room cut 1.png") center/cover no-repeat fixed';
      if (wardrobePage) wardrobePage.style.background = 'url("Hintegrund Dressing Room cut 1.png") center/cover no-repeat fixed';
    } else if (theme === 'white') {
      if (mainApp) mainApp.style.background = '#ffffff fixed';
      if (wardrobePage) wardrobePage.style.background = '#ffffff fixed';
    } else if (theme === 'blue') {
      if (mainApp) mainApp.style.background = '#A2B5B8 fixed';
      if (wardrobePage) wardrobePage.style.background = '#A2B5B8 fixed';
    }
  }

  // Load saved background theme on startup
  chrome.storage.local.get('backgroundTheme', function(result) {
    const theme = result.backgroundTheme || 'image';
    setBackground(theme);
  });

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

  // Account Creation Form Fields (NEW MODEL)
  const createEmail = document.getElementById('create-email');
  const createFirstname = document.getElementById('create-firstname');
  const createLastname = document.getElementById('create-lastname');
  const createGender = document.getElementById('create-gender');
  const createBirthdate = document.getElementById('create-birthdate');
  const createStreetNo = document.getElementById('create-streetno');
  const createCity = document.getElementById('create-city');
  const createPostalCode = document.getElementById('create-postalcode');
  const createPassword = document.getElementById('create-password');
  const createConfirmPassword = document.getElementById('create-confirm-password');

  // User Profile Page Elements
  const userProfilePage = document.getElementById('user-profile-page');
  const userBtn = document.getElementById('user-btn');
  const backToMainLink = document.getElementById('back-to-main');
  const editProfileBtn = document.getElementById('edit-profile-btn');
  const saveProfileBtn = document.getElementById('save-profile-btn');
  const cancelEditBtn = document.getElementById('cancel-edit-btn');

  // User Profile Form Fields
  const profileEmail = document.getElementById('profile-email');
  const profileFirstname = document.getElementById('profile-firstname');
  const profileLastname = document.getElementById('profile-lastname');
  const profileGender = document.getElementById('profile-gender');
  const profileBirthday = document.getElementById('profile-birthday');
  const profileStreet = document.getElementById('profile-street');
  const profileCity = document.getElementById('profile-city');
  const profilePostalCode = document.getElementById('profile-postal-code');
  
  // Body Measurements Fields
  const profileHeight = document.getElementById('profile-height');
  const profileWeight = document.getElementById('profile-weight');
  const profileShoulderCircumference = document.getElementById('profile-shoulder-circumference');
  const profileArmLength = document.getElementById('profile-arm-length');
  const profileBicepsCircumference = document.getElementById('profile-biceps-circumference');
  const profileBreastCircumference = document.getElementById('profile-breast-circumference');
  const profileUnderBreastCircumference = document.getElementById('profile-under-breast-circumference');
  const profileCollarboneToBellyButtonLength = document.getElementById('profile-collarbone-to-belly-button-length');
  const profileWaistCircumference = document.getElementById('profile-waist-circumference');
  const profileHipCircumference = document.getElementById('profile-hip-circumference');
  const profileUpperThighCircumference = document.getElementById('profile-upper-thigh-circumference');
  const profileNeckCircumference = document.getElementById('profile-neck-circumference');
  const profileWaistToCrotchFrontLength = document.getElementById('profile-waist-to-crotch-front-length');
  const profileWaistToCrotchBackLength = document.getElementById('profile-waist-to-crotch-back-length');
  const profileInnerLegLength = document.getElementById('profile-inner-leg-length');
  const profileFootLength = document.getElementById('profile-foot-length');
  const profileFootWidth = document.getElementById('profile-foot-width');

  // Wardrobe Page Elements
  const wardrobePage = document.getElementById('wardrobe-page');
  const wardrobeSearchInput = document.getElementById('wardrobe-search');
  const wardrobeTabs = document.querySelectorAll('.wardrobe-tab');
  const wardrobeTabContents = document.querySelectorAll('.wardrobe-tab-content');
  const upperGarmentsGrid = document.getElementById('upper-garments-grid');
  const lowerGarmentsGrid = document.getElementById('lower-garments-grid');
  const upperEmptyState = document.getElementById('upper-empty-state');
  const lowerEmptyState = document.getElementById('lower-empty-state');

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

  async function handleImageTryOn(imageSrc) {
    console.log('🎯 handleImageTryOn called with image:', imageSrc.substring(0, 100) + (imageSrc.length > 100 ? '...' : ''));
    console.log('   Full URL length:', imageSrc.length, 'characters');
    
    // Detect garment type from current URL
    const garmentType = await detectGarmentTypeFromURL();
    console.log('🔍 Detected garment type:', garmentType);
    
    try {
      console.log('📤 Calling performTryOn with:', {
        imageSrc: imageSrc.substring(0, 100) + (imageSrc.length > 100 ? '...' : ''),
        garmentType: garmentType
      });
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
    return new Promise((resolve, reject) => {
      try {
        if (!currentUser || !currentUser.userID) {
          console.error('❌ No user logged in');
          resolve({ success: false, message: 'Please sign in to save garments' });
          return;
        }

        // Get JWT token from chrome storage (same as avatar retrieval)
        chrome.storage.local.get(['jwtToken'], async function(tokenResult) {
          const jwtToken = tokenResult.jwtToken;
          
          if (!jwtToken) {
            console.error('❌ No JWT token found in storage');
            resolve({ success: false, message: 'Authentication token not found' });
            return;
          }

          try {
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
              date_added: new Date().toISOString()
            };

            // Only include garment_url if it's provided
            if (garmentUrl) {
              wardrobeData.garment_url = garmentUrl;
            }

            // Save to backend database using the new /save-extracted endpoint
            console.log('🔐 JWT Token retrieved from chrome storage:', jwtToken?.substring(0, 20) + '...');
            console.log('🔐 Sending wardrobe request to /api/wardrobe/save-extracted with Authorization header');
            
            const response = await fetch(`${API_BASE_URL}/api/wardrobe/save-extracted`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${jwtToken}`
              },
              body: JSON.stringify({
                garment_image: garmentImageData,
                garment_type: garmentType,
                garment_id: garmentId
              })
            });

            if (response.ok) {
              const result = await response.json();
              console.log('✅ Garment saved to wardrobe:', garmentId);
              
              // Add to local cache
              wardrobeItems.push(wardrobeData);
              
              resolve({ success: true, garmentId: garmentId });
            } else {
              throw new Error(`Failed to save: ${response.status}`);
            }

          } catch (error) {
            console.error('❌ Error saving to wardrobe:', error);
            resolve({ success: false, message: error.message });
          }
        });

      } catch (error) {
        console.error('❌ Error in saveToWardrobe:', error);
        resolve({ success: false, message: error.message });
      }
    });
  }

  // Function to check if garment is already in wardrobe
  function isGarmentInWardrobe(garmentImageData) {
    // Simple check - in a real app, you might want to use image hashing
    return wardrobeItems.some(item => item.garment_image === garmentImageData);
  }

  // Function to handle favorite button click
  async function handleFavoriteClick(event, garmentImageData, garmentType, garmentUrl = null) {
    event.stopPropagation(); // Prevent triggering try-on
    
    // Find the favorite button - it might be the currentTarget or a parent
    let favoriteBtn = event.currentTarget;
    if (!favoriteBtn || favoriteBtn.tagName !== 'BUTTON') {
      favoriteBtn = event.target.closest('.favorite-btn');
    }
    
    if (!favoriteBtn) {
      console.error('❌ Could not find favorite button');
      return;
    }
    
    const heartIcon = favoriteBtn.querySelector('.heart-icon');
    const garmentItem = favoriteBtn.closest('.garment-item-tryon');
    
    // Show loading state on image
    if (heartIcon) {
      heartIcon.style.opacity = '0.5';
    }
    favoriteBtn.disabled = true;

    try {
      if (favoriteBtn.classList.contains('favorited')) {
        // Remove from wardrobe
        favoriteBtn.classList.remove('favorited');
        if (garmentItem) garmentItem.classList.remove('favorited');
        if (heartIcon) heartIcon.style.filter = 'grayscale(100%)';
        console.log('💔 Removed from wardrobe');
      } else {
        // Add to wardrobe
        const result = await saveToWardrobe(garmentImageData, garmentType, garmentUrl);
        
        if (result.success) {
          favoriteBtn.classList.add('favorited');
          if (garmentItem) garmentItem.classList.add('favorited');
          if (heartIcon) heartIcon.style.filter = 'none';
          console.log('💖 Added to wardrobe');
          
          // Show success feedback
          showFavoriteSuccess();
        } else {
          if (heartIcon) heartIcon.style.filter = 'grayscale(100%)';
          console.error('Failed to save:', result.message);
          // Show error message to user
          showFavoriteError(result.message);
        }
      }
    } catch (error) {
      if (heartIcon) heartIcon.style.filter = 'grayscale(100%)';
      console.error('❌ Favorite action failed:', error);
      showFavoriteError('Failed to save garment');
    } finally {
      // Remove loading state
      if (heartIcon) {
        heartIcon.style.opacity = '1';
      }
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
      
      const response = await fetch(`http://localhost:8000/api/wardrobe/user/${currentUser.userID}`);
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
              <img src="love.png" alt="In wardrobe" class="heart-icon" style="width: 24px; height: 24px; object-fit: contain;" />
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
              Try On
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

  // ===== LAYERED TRY-ON VALIDATION & HELPER FUNCTIONS =====
  
  // Validate garment combination for layered try-ons
  function validateLayeredCombination(currentGarmentType, newGarmentType) {
    console.log('🔍 Validating combination:', {
      appliedCount: appliedGarments.length,
      firstType: firstGarmentType,
      currentType: currentGarmentType,
      newType: newGarmentType
    });
    
    // Check max layers (2 try-ons = 2 layers)
    if (tryOnCount >= 2) {
      return {
        valid: false,
        message: '⚠️ Maximum 2 layers reached. Reset to try different combinations.'
      };
    }
    
    // First try-on - always allowed
    if (tryOnCount === 0) {
      return { valid: true };
    }
    
    // Second try-on - check combination rules
    if (tryOnCount === 1) {
      // Rule 1: Cannot try two bottoms (lower + lower)
      if (firstGarmentType === 'lower' && newGarmentType === 'lower') {
        return {
          valid: false,
          message: '❌ Cannot try on 2 bottoms. Allowed: Upper+Upper or Upper+Bottom'
        };
      }
      
      // Allowed combinations:
      // - upper + upper ✅
      // - upper + lower ✅
      // - lower + upper ✅
      
      return { valid: true };
    }
    
    return { valid: false, message: 'Unknown state' };
  }
  
  // Show layered try-on UI (Reset button, Applied garments, Try Another button)
  function showLayeredTryOnUI() {
    const tryonResult = document.getElementById('tryon-result');
    if (!tryonResult) return;
    
    // Add applied garments info above result
    // Update header with layer count display (only X/2 format)
    let layerCount = document.getElementById('layer-count-display');
    if (!layerCount) {
      layerCount = document.createElement('span');
      layerCount.id = 'layer-count-display';
      layerCount.style.cssText = `
        margin-left: 12px;
        color: #333;
        font-size: 12px;
        font-weight: 600;
      `;
      const headerLeft = document.querySelector('.header-left');
      if (headerLeft) {
        headerLeft.appendChild(layerCount);
        console.log('✅ Layer count display added to .header-left');
      } else {
        // Fallback: add to tryon-result parent
        const tryonResultParent = document.getElementById('tryon-result')?.parentElement;
        if (tryonResultParent) {
          tryonResultParent.insertBefore(layerCount, document.getElementById('tryon-result'));
          console.log('⚠️ Layer count display added to result parent (fallback)');
        }
      }
    }
    if (layerCount) {
      layerCount.textContent = `${tryOnCount}/2`;
      layerCount.style.display = 'block';
      console.log('📊 Layer count updated:', `${tryOnCount}/2`);
    }
    
    // Remove the old applied-garments-info div from result area if it exists
    const oldAppliedInfo = document.getElementById('applied-garments-info');
    if (oldAppliedInfo) {
      oldAppliedInfo.remove();
      console.log('🗑️ Removed old applied info div');
    }
    
    // Show buttons only after first try-on
    if (tryOnCount >= 1) {
      const buttonContainer = document.getElementById('layered-tryon-buttons');
      if (!buttonContainer) {
        const btnDiv = document.createElement('div');
        btnDiv.id = 'layered-tryon-buttons';
        btnDiv.style.cssText = `
          display: flex;
          gap: 8px;
          margin-top: 12px;
          justify-content: center;
        `;
        tryonResult.parentElement.appendChild(btnDiv);
      }
      
      const btnDiv = document.getElementById('layered-tryon-buttons');
      btnDiv.innerHTML = '';
      
      // Reset button
      const resetBtn = document.createElement('button');
      resetBtn.style.cssText = `
        padding: 8px 12px;
        background: #ff6b6b;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        font-weight: 600;
      `;
      
      // Add refresh icon
      const resetIcon = document.createElement('img');
      resetIcon.src = 'refresh.png';
      resetIcon.alt = 'Reset';
      resetIcon.style.cssText = 'width: 16px; height: 16px; object-fit: contain;';
      resetBtn.appendChild(resetIcon);
      
      // Add text
      const resetText = document.createElement('span');
      resetText.textContent = 'Reset Avatar';
      resetBtn.appendChild(resetText);
      
      resetBtn.addEventListener('click', resetToOriginalAvatar);
      btnDiv.appendChild(resetBtn);
      console.log('✅ Reset button created with refresh icon');
      
      // Try Another button (only if not at max)
      if (tryOnCount < 2) {
        const tryAnotherBtn = document.createElement('button');
        tryAnotherBtn.textContent = '+ Try Another';
        tryAnotherBtn.style.cssText = `
          padding: 8px 16px;
          background: #4CAF50;
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-size: 12px;
          font-weight: 600;
        `;
        tryAnotherBtn.addEventListener('click', () => {
          // Scroll back to garment selection
          const garmentPreview = document.getElementById('garment-preview');
          if (garmentPreview) {
            garmentPreview.scrollIntoView({ behavior: 'smooth' });
          }
        });
        btnDiv.appendChild(tryAnotherBtn);
      } else {
        // At max - show disabled state
        const maxReachedBtn = document.createElement('button');
        maxReachedBtn.textContent = '✓ 2 Layers Applied';
        maxReachedBtn.style.cssText = `
          padding: 8px 16px;
          background: #ccc;
          color: #666;
          border: none;
          border-radius: 6px;
          cursor: not-allowed;
          font-size: 12px;
          font-weight: 600;
        `;
        maxReachedBtn.disabled = true;
        btnDiv.appendChild(maxReachedBtn);
      }
    }
  }
  
  // Reset to original avatar
  async function resetToOriginalAvatar() {
    console.log('↻ Resetting to original avatar');
    
    // Clear persisted try-on state
    chrome.storage.local.remove('tryOnState');
    
    // Reset state
    currentWorkingAvatar = null;
    appliedGarments = [];
    tryOnCount = 0;
    firstGarmentType = null;
    
    // Reload original avatar
    if (originalAvatarBase64) {
      currentWorkingAvatar = originalAvatarBase64;
      console.log('✅ Reset to original avatar');
    }
    
    // Hide layered try-on UI
    const appliedInfo = document.getElementById('applied-garments-info');
    if (appliedInfo) appliedInfo.remove();
    
    // Hide layer count badge from header
    // Hide layer count display from header
    const layerCountDisplay = document.getElementById('layer-count-display');
    if (layerCountDisplay) layerCountDisplay.style.display = 'none';
    
    const buttonContainer = document.getElementById('layered-tryon-buttons');
    if (buttonContainer) buttonContainer.remove();
    
    // Hide garment info button and container
    const garmentInfoBtn = document.getElementById('garment-info-btn');
    if (garmentInfoBtn) {
      garmentInfoBtn.style.display = 'none';
    }
    
    const garmentInfoContainer = document.getElementById('garment-info-container');
    if (garmentInfoContainer) {
      garmentInfoContainer.style.display = 'none';
    }
    
    // Show original avatar in result
    const tryonResult = document.getElementById('tryon-result');
    if (tryonResult && originalAvatarBase64) {
      const closeBtn = document.createElement('button');
      closeBtn.className = 'tryon-close-btn';
      closeBtn.innerHTML = '&times;';
      closeBtn.addEventListener('click', hideTryonResult);
      
      const img = document.createElement('img');
      img.src = originalAvatarBase64;
      img.alt = 'Original Avatar';
      img.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px;';
      
      tryonResult.innerHTML = '';
      tryonResult.appendChild(closeBtn);
      tryonResult.appendChild(img);
      showTryonResult();
    }
  }
  
  // Show error message for invalid combination
  function showCombinationError(message) {
    console.log('❌ Combination error:', message);
    
    const tryonResult = document.getElementById('tryon-result');
    if (!tryonResult) return;
    
    const closeBtn = document.createElement('button');
    closeBtn.className = 'tryon-close-btn';
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', hideTryonResult);
    
    const errorDiv = document.createElement('div');
    errorDiv.style.cssText = `
      background: #ffebee;
      border: 2px solid #ff6b6b;
      color: #c62828;
      padding: 16px;
      border-radius: 8px;
      text-align: center;
      font-weight: 600;
      font-size: 14px;
    `;
    errorDiv.textContent = message;
    
    tryonResult.innerHTML = '';
    tryonResult.appendChild(closeBtn);
    tryonResult.appendChild(errorDiv);
    showTryonResult();
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

  // ===== GARMENT TYPE SELECTION MODAL FOR 2ND LAYER =====
  // Show modal to manually select garment type for second try-on
  function showGarmentTypeSelectionModal() {
    return new Promise((resolve) => {
      // Create modal container
      const modal = document.createElement('div');
      modal.id = 'garment-type-selection-modal';
      modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        backdrop-filter: blur(2px);
      `;

      // Create modal content
      const modalContent = document.createElement('div');
      modalContent.style.cssText = `
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 32px;
        border-radius: 16px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.5) inset;
        text-align: center;
        max-width: 340px;
        animation: modalSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
        border: 1px solid rgba(255, 255, 255, 0.8);
      `;

      // Header icon
      const headerIcon = document.createElement('div');
      headerIcon.style.cssText = `
        font-size: 36px;
        margin-bottom: 12px;
      `;
      headerIcon.textContent = '';

      // Title
      const title = document.createElement('h3');
      title.textContent = 'Choose Your Second Layer';
      title.style.cssText = `
        margin: 0 0 8px 0;
        font-size: 20px;
        font-weight: 700;
        color: #1a1a1a;
        letter-spacing: -0.5px;
      `;

      // Subtitle
      const subtitle = document.createElement('p');
      subtitle.textContent = `Layer 2 of 2 • Already applied: ${firstGarmentType.toUpperCase()}`;
      subtitle.style.cssText = `
        margin: 0 0 24px 0;
        font-size: 12px;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 500;
      `;

      // Buttons container
      const buttonsContainer = document.createElement('div');
      buttonsContainer.style.cssText = `
        display: flex;
        gap: 12px;
        justify-content: center;
        margin-top: 24px;
      `;

      // Upper button
      const upperBtn = document.createElement('button');
      upperBtn.textContent = 'Upper';
      upperBtn.style.cssText = `
        flex: 1;
        padding: 16px 12px;
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        color: white;
        border: none;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3);
      `;
      upperBtn.addEventListener('mouseenter', () => {
        upperBtn.style.transform = 'translateY(-3px)';
        upperBtn.style.boxShadow = '0 8px 20px rgba(76, 175, 80, 0.4)';
      });
      upperBtn.addEventListener('mouseleave', () => {
        upperBtn.style.transform = 'translateY(0)';
        upperBtn.style.boxShadow = '0 4px 12px rgba(76, 175, 80, 0.3)';
      });
      upperBtn.addEventListener('click', () => {
        console.log('User selected: upper');
        modal.remove();
        resolve('upper');
      });

      // Lower button
      const lowerBtn = document.createElement('button');
      lowerBtn.textContent = 'Lower';
      lowerBtn.style.cssText = `
        flex: 1;
        padding: 16px 12px;
        background: linear-gradient(135deg, #2196F3 0%, #1976d2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        box-shadow: 0 4px 12px rgba(33, 150, 243, 0.3);
      `;

      // Disable lower button if first garment was lower
      if (firstGarmentType === 'lower') {
        lowerBtn.disabled = true;
        lowerBtn.style.background = '#d0d0d0';
        lowerBtn.style.cursor = 'not-allowed';
        lowerBtn.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1)';
        lowerBtn.title = 'Cannot combine 2 bottoms';
        
        const disabledOverlay = document.createElement('div');
        disabledOverlay.style.cssText = `
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(255, 255, 255, 0.5);
          border-radius: 12px;
          pointer-events: none;
        `;
        disabledOverlay.textContent = '';
        lowerBtn.style.position = 'relative';
        lowerBtn.appendChild(disabledOverlay);
        
        const disabledText = document.createElement('div');
        disabledText.style.cssText = `
          font-size: 10px;
          color: #999;
          margin-top: 6px;
          font-weight: 500;
        `;
        disabledText.textContent = 'Cannot use 2 bottoms';
        
        const lowerWrapper = document.createElement('div');
        lowerWrapper.appendChild(lowerBtn);
        lowerWrapper.appendChild(disabledText);
        buttonsContainer.appendChild(lowerWrapper);
      } else {
        lowerBtn.addEventListener('mouseenter', () => {
          lowerBtn.style.transform = 'translateY(-3px)';
          lowerBtn.style.boxShadow = '0 8px 20px rgba(33, 150, 243, 0.4)';
        });
        lowerBtn.addEventListener('mouseleave', () => {
          lowerBtn.style.transform = 'translateY(0)';
          lowerBtn.style.boxShadow = '0 4px 12px rgba(33, 150, 243, 0.3)';
        });
        lowerBtn.addEventListener('click', () => {
          console.log('👖 User selected: lower');
          modal.remove();
          resolve('lower');
        });
        buttonsContainer.appendChild(lowerBtn);
      }

      buttonsContainer.insertBefore(upperBtn, buttonsContainer.firstChild);

      // Fit Analysis button
      const fitAnalysisBtn = document.createElement('button');
      fitAnalysisBtn.textContent = 'Fit Analysis';
      fitAnalysisBtn.style.cssText = `
        width: 100%;
        padding: 14px 16px;
        background: #ffffff;
        color: #2c3e50;
        border: 1.5px solid #e0e0e0;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
        margin-top: 16px;
      `;
      fitAnalysisBtn.addEventListener('mouseenter', () => {
        fitAnalysisBtn.style.background = '#f8f9fa';
        fitAnalysisBtn.style.borderColor = '#9e9e9e';
        fitAnalysisBtn.style.transform = 'translateY(-2px)';
        fitAnalysisBtn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
      });
      fitAnalysisBtn.addEventListener('mouseleave', () => {
        fitAnalysisBtn.style.background = '#ffffff';
        fitAnalysisBtn.style.borderColor = '#e0e0e0';
        fitAnalysisBtn.style.transform = 'translateY(0)';
        fitAnalysisBtn.style.boxShadow = 'none';
      });
      fitAnalysisBtn.addEventListener('click', () => {
        console.log('Fit Analysis clicked');
        modal.remove();
        resolve('fit-analysis');
      });

      // Close on background click
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          console.log('Modal closed by background click');
          modal.remove();
          resolve(null); // User closed without selecting
        }
      });

      // Add styles for animations
      const style = document.createElement('style');
      style.textContent = `
        @keyframes modalSlideIn {
          from {
            opacity: 0;
            transform: scale(0.85) translateY(-20px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }
        
        #garment-type-selection-modal button:active {
          transform: scale(0.98) !important;
        }
      `;
      document.head.appendChild(style);

      // Assemble modal
      modalContent.appendChild(headerIcon);
      modalContent.appendChild(title);
      modalContent.appendChild(subtitle);
      modalContent.appendChild(buttonsContainer);
      modalContent.appendChild(fitAnalysisBtn);
      modal.appendChild(modalContent);
      document.body.appendChild(modal);

      console.log('📋 Garment type selection modal shown');
    });
  }

  // Main try-on function with layered support
  async function performTryOn(garmentImageData, garmentType) {
    console.log(`🎯 performTryOn called with ${garmentType} garment`);
    console.log('📊 Current state:', { tryOnCount, firstGarmentType, appliedGarments });
    
    // Prevent multiple simultaneous try-ons
    if (tryOnInProgress) {
      console.log('⏳ Try-on already in progress');
      return;
    }
    
    const tryonResult = document.getElementById('tryon-result');
    if (!tryonResult) {
      console.error('❌ tryonResult element not found');
      return;
    }
    
    // ===== FOR SECOND TRY-ON: SHOW MODAL TO SELECT GARMENT TYPE =====
    let finalGarmentType = garmentType;
    if (tryOnCount === 1) {
      console.log('🎯 Second try-on - asking user to manually select garment type');
      const selectedType = await showGarmentTypeSelectionModal();
      
      if (!selectedType) {
        console.log('⚠️ User cancelled garment type selection');
        return; // User closed modal without selecting
      }
      
      // Handle Fit Analysis selection
      if (selectedType === 'fit-analysis') {
        console.log('📊 Fit Analysis selected - implementing fit analysis feature');
        // TODO: Implement fit analysis functionality here
        // This could show garment sizing comparison, recommendations, etc.
        return;
      }
      
      finalGarmentType = selectedType; // Use user's manual selection instead of auto-detected
      console.log('✅ User selected garment type:', finalGarmentType);
    }
    
    // ===== VALIDATION FOR LAYERED TRY-ONS =====
    if (tryOnCount > 0) {
      // Not the first try-on - validate combination
      const validation = validateLayeredCombination(firstGarmentType, finalGarmentType);
      if (!validation.valid) {
        showCombinationError(validation.message);
        return;
      }
    }
    
    // Get processed avatar from storage
    return new Promise((resolve, reject) => {
      chrome.storage.local.get(['avatarBgRemovedImg', 'avatarImg'], async function(result) {
        // Determine which avatar to use
        let avatarDataToUse;
        if (tryOnCount === 0) {
          // First try-on - use original avatar and store it
          avatarDataToUse = result.avatarBgRemovedImg || result.avatarImg;
          if (avatarDataToUse && !originalAvatarBase64) {
            originalAvatarBase64 = avatarDataToUse;
            currentWorkingAvatar = avatarDataToUse;
            console.log('💾 Stored original avatar for reset');
          }
        } else {
          // Subsequent try-on - use previous result or original
          avatarDataToUse = currentWorkingAvatar || (result.avatarBgRemovedImg || result.avatarImg);
        }
        
        if (!avatarDataToUse) {
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
        
        // Show processing state
        tryOnInProgress = true;
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
        
        let avatarBlob = null;
        let garmentBlob = null;
        try {
          // Convert avatar and garment images to blobs
          console.log('🔄 Converting avatar to blob...');
          avatarBlob = await safeImageToBlob(avatarDataToUse);
          console.log('✅ Avatar blob created:', { size: avatarBlob.size, type: avatarBlob.type });
          
          console.log('🔄 Converting garment image to blob...');
          garmentBlob = await safeImageToBlob(garmentImageData);
          console.log('✅ Garment blob created:', { size: garmentBlob.size, type: garmentBlob.type });

          // Validate blobs
          if (!avatarBlob || avatarBlob.size === 0) {
            tryonResult.innerHTML = '❌ Invalid avatar image data.';
            showTryonResult();
            tryOnInProgress = false;
            reject('Invalid avatar image');
            return;
          }
          if (!garmentBlob || garmentBlob.size === 0) {
            console.error('❌ Garment blob is empty');
            tryonResult.innerHTML = '❌ Invalid garment image data.';
            showTryonResult();
            tryOnInProgress = false;
            reject('Invalid garment image');
            return;
          }

          // Call try-on API
          const formData = new FormData();
          formData.append('avatar_image', avatarBlob, 'avatar.png');
          formData.append('garment_image', garmentBlob, 'garment.png');
          formData.append('cloth_type', finalGarmentType);
          formData.append('num_inference_steps', 50);
          
          console.log('📦 Sending try-on request...');

          // Retrieve JWT token
          let jwtToken = null;
          await new Promise(resolve => {
            chrome.storage.local.get(['jwtToken'], function(tokenResult) {
              jwtToken = tokenResult.jwtToken;
              resolve();
            });
          });

          const response = await fetch('http://127.0.0.1:8000/api/tryon-gemini', {
            method: 'POST',
            body: formData,
            headers: jwtToken ? { 'Authorization': `Bearer ${jwtToken}` } : undefined
          });
          console.log('📥 API Response status:', response.status);
          
          if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ Try-on API failed:', response.status);
            tryonResult.innerHTML = `❌ Try-on failed (${response.status})`;
            tryOnInProgress = false;
            reject('Try-on API failed');
            return;
          }
          
          // Handle image response
          const tryonBlob = await response.blob();
          console.log('✅ Received try-on result blob:', { size: tryonBlob.size });
          
          // Convert blob to data URL for storage and reuse
          const reader = new FileReader();
          reader.onload = async function(e) {
            const resultDataUrl = e.target.result;
            
            // ===== UPDATE LAYERED TRY-ON STATE =====
            if (tryOnCount === 0) {
              firstGarmentType = finalGarmentType;
            }
            appliedGarments.push({ type: finalGarmentType, src: garmentImageData });
            tryOnCount++;
            currentWorkingAvatar = resultDataUrl; // Store result for next layer
            
            console.log('✅ Try-on #' + tryOnCount + ' completed');
            console.log('   Applied so far:', appliedGarments.map(g => g.type).join(' + '));

            // Display result image
            const resultImg = document.createElement('img');
            resultImg.src = resultDataUrl;
            resultImg.alt = 'Try-On Result';
            resultImg.style.cssText = 'max-width: 100%; height: auto; border-radius: 8px;';
            
            tryonResult.innerHTML = '';
            tryonResult.appendChild(resultImg);
            
            // Save try-on state to persist across popup closures
            saveTryOnState(resultDataUrl);
            
            // Show layered try-on UI
            showLayeredTryOnUI();
            
            tryOnInProgress = false;
            resolve();
          };
          
          reader.onerror = function(error) {
            console.error('Error reading result blob:', error);
            tryonResult.innerHTML = '❌ Failed to process result';
            tryOnInProgress = false;
            reject(error);
          };
          
          reader.readAsDataURL(tryonBlob);
          
        } catch (error) {
          console.error('Try-on error:', error.message);
          if (error.message && error.message.includes('Failed to fetch')) {
            tryonResult.innerHTML = '🔌 Cannot connect to try-on server.';
          } else {
            tryonResult.innerHTML = `❌ Try-on failed: ${error.message || 'Unknown error'}`;
          }
          tryOnInProgress = false;
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
              <img src="love.png" alt="Add to wardrobe" class="heart-icon" style="width: 24px; height: 24px; object-fit: contain; filter: ${isInWardrobe ? 'none' : 'grayscale(100%)'};" />
            </button>
            
            <!-- Image Number Badge -->
            <div style="position: absolute; bottom: 2px; right: 2px; background: rgba(0,0,0,0.7); color: white; padding: 2px 4px; border-radius: 2px; font-size: 10px;">
              ${imageNumber}
            </div>
            
            <!-- Try-on Hover Badge -->
            <div class="tryon-hover-badge" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); color: white; padding: 8px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; opacity: 0; transition: opacity 0.3s ease; pointer-events: none;">
              Try On
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
    console.log(`📌 Attaching event listeners to ${tryonItems.length} garment items`);
    tryonItems.forEach((item, index) => {
      const actualIndex = startIndex + index;
      if (actualIndex < allExtractedImages.length) {
        const imgSrc = allExtractedImages[actualIndex].src;
        console.log(`📎 Item ${index + 1} (actual ${actualIndex + 1}): ${imgSrc.substring(0, 80)}...`);
        
        // Add try-on click listener to the image
        const img = item.querySelector('img');
        if (img) {
          img.addEventListener('click', async () => {
            console.log('👕 Try-on clicked for image:', imgSrc.substring(0, 100) + (imgSrc.length > 100 ? '...' : ''));
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
          profile: result.userProfile,
          jwtToken: result.jwtToken
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

      const result = await response.json();

      console.log('📦 Raw response object:', result);
      console.log('📦 response.status:', response.status);
      console.log('📦 response.ok:', response.ok);

      if (result.success) {
        console.log('✅ Login successful:', result.data.user);
        console.log('� Full login response:', JSON.stringify(result, null, 2));
        console.log('🔐 Token from result.data.token:', result.data.token);
        console.log('🔐 Token from result.token:', result.token);
        console.log('🔐 All keys in result.data:', Object.keys(result.data));

        // Store user session with complete user data and JWT token
        const userData = {
          userSignedIn: true,
          userEmail: email,
          userId: result.data.user.userid,
          userID: result.data.user.userid,  // Also store as userID for avatar endpoint
          userProfile: {
            firstname: result.data.user.first_name,
            lastname: result.data.user.last_name,
            age: result.data.user.age,
            gender: result.data.user.gender,
            weight: result.data.user.weight,
            height: result.data.user.height,
            physique: result.data.user.physique
          },
          signInTime: Date.now(),
          jwtToken: result.data.token || ''
        };

        console.log('💾 Storing JWT token:', userData.jwtToken);
        chrome.storage.local.set(userData);

        // Set current user for wardrobe functionality
        currentUser = {
          userID: result.data.user.userid,
          email: email,
          profile: userData.userProfile,
          jwtToken: userData.jwtToken
        };
        console.log('👤 User signed in for wardrobe:', currentUser);
        console.log('✅ currentUser.jwtToken set to:', currentUser.jwtToken);

        signinBtn.innerHTML = 'Loading avatar...';

        // Load avatar from database if it exists
        await loadAvatarAfterSignIn(result.data.user.userid);

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
    createAccountBtn.addEventListener('click', async function(e) {
      e.preventDefault();
      handleAccountCreation();
    });
  }

  // Account Creation Handler (NEW MODEL)
  createAccountBtn.addEventListener('click', async function() {
    const email = createEmail.value;
    const firstname = createFirstname.value;
    const lastname = createLastname.value;
    const gender = createGender.value;
    const birthdate = document.getElementById('create-birthdate').value;
    const streetNo = document.getElementById('create-streetno').value;
    const city = document.getElementById('create-city').value;
    const postalCode = document.getElementById('create-postalcode').value;
    const password = createPassword.value;
    const confirmPassword = document.getElementById('create-confirm-password').value;

    // Remove all other fields from the model
    try {
      const userData = {
        email,
        first_name: firstname,
        last_name: lastname,
        gender,
        birthdate,
        street_no: streetNo,
        city,
        postal_code: postalCode,
        password,
        confirm_password: confirmPassword
      };
      // Update API call to match new model
      const response = await fetch(`${API_BASE_URL}/api/create-account`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData)
      });
      const result = await response.json();
      if (result.success) {
        alert('Account created successfully! Please sign in.');
        accountCreationPage.style.display = 'none';
        signinPage.style.display = 'block';
      } else {
        alert('Account creation failed: ' + (result.message || 'Unknown error'));
      }
    } catch (error) {
      alert('Account creation error: ' + error.message);
    }
  });

  async function saveAvatarToDatabase(imageData, userId) {
    try {
      console.log('💾 Saving avatar to database for user:', userId);
      
      // Convert data URL to base64
      const base64Data = imageData.split(',')[1];
      
      const response = await fetch('http://localhost:8000/api/update-avatar', {
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
      
      // Use the new /api/avatar/<userid> endpoint that looks up the actual filename from the database
      const response = await fetch(`${API_BASE_URL}/api/avatar/${userId}`);
      
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

  // ===== WARDROBE PAGE INITIALIZATION =====
  // Menu wardrobe button handler
  const menuWardrobeBtn = document.getElementById('menu-wardrobe');
  if (menuWardrobeBtn) {
    menuWardrobeBtn.addEventListener('click', function(e) {
      e.preventDefault();
      showWardrobePage();
      // Mark button as active
      document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));
      menuWardrobeBtn.classList.add('active');
    });
  }

  // Menu home button handler
  const menuHomeBtn = document.getElementById('menu-home');
  if (menuHomeBtn) {
    menuHomeBtn.addEventListener('click', function(e) {
      e.preventDefault();
      showMainApp();
      // Mark button as active
      document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));
      menuHomeBtn.classList.add('active');
    });
  }

  // Menu saved button handler
  const menuBookmarkBtn = document.getElementById('menu-bookmark');
  if (menuBookmarkBtn) {
    menuBookmarkBtn.addEventListener('click', function(e) {
      e.preventDefault();
      showSavedPage();
      // Mark button as active
      document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));
      menuBookmarkBtn.classList.add('active');
    });
  }

  // Show saved page function
  function showSavedPage() {
    // Hide all other pages
    signinPage.style.display = 'none';
    if (accountCreationPage) accountCreationPage.style.display = 'none';
    if (userProfilePage) userProfilePage.style.display = 'none';
    if (wardrobePage) wardrobePage.style.display = 'none';
    if (mainApp) mainApp.style.display = 'none';
    
    // Show saved page and header
    const savedPage = document.getElementById('saved-page');
    if (savedPage) {
      savedPage.style.display = 'flex';
      // Load and display saved try-ons
      displaySavedTryOns();
    }
    if (menuBar) menuBar.style.display = 'flex';
    const extensionHeader = document.querySelector('.extension-header');
    if (extensionHeader) extensionHeader.style.display = 'flex';
  }

  // Wardrobe tab handlers
  wardrobeTabs.forEach(tab => {
    tab.addEventListener('click', function(e) {
      e.preventDefault();
      const tabName = this.getAttribute('data-tab');
      
      // Remove active class from all tabs and contents
      wardrobeTabs.forEach(t => t.classList.remove('active'));
      wardrobeTabContents.forEach(content => content.classList.remove('active'));
      
      // Add active class to clicked tab and corresponding content
      this.classList.add('active');
      const tabId = tabName === 'upper' ? 'upper-garments-tab' : 'lower-garments-tab';
      const tabContent = document.getElementById(tabId);
      if (tabContent) tabContent.classList.add('active');
      
      // Filter displayed items based on tab
      filterWardrobeByType(tabName);
    });
  });

  // Wardrobe search handler
  if (wardrobeSearchInput) {
    wardrobeSearchInput.addEventListener('input', function(e) {
      const searchTerm = e.target.value.toLowerCase();
      filterWardrobeBySearch(searchTerm);
    });
  }

  // Function to load wardrobe items from backend
  async function loadWardrobeItems() {
    try {
      if (!currentUser || !currentUser.userID) {
        console.log('❌ No user logged in');
        upperEmptyState.style.display = 'flex';
        lowerEmptyState.style.display = 'flex';
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/wardrobe/items`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${currentUser.jwtToken || ''}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        wardrobeItems = result.data || [];
        console.log('✅ Loaded wardrobe items:', wardrobeItems.length);
        renderWardrobeItems();
      } else {
        console.error('Failed to load wardrobe items:', response.status);
        upperEmptyState.style.display = 'flex';
        lowerEmptyState.style.display = 'flex';
      }
    } catch (error) {
      console.error('❌ Error loading wardrobe:', error);
      upperEmptyState.style.display = 'flex';
      lowerEmptyState.style.display = 'flex';
    }
  }

  // Function to render wardrobe items in grids
  function renderWardrobeItems() {
    const upperItems = wardrobeItems.filter(item => item.garment_type === 'upper');
    const lowerItems = wardrobeItems.filter(item => item.garment_type === 'lower');

    // Clear existing items
    upperGarmentsGrid.innerHTML = '';
    lowerGarmentsGrid.innerHTML = '';

    // Render upper garments
    if (upperItems.length === 0) {
      upperEmptyState.style.display = 'flex';
    } else {
      upperEmptyState.style.display = 'none';
      upperItems.forEach(item => {
        const garmentElement = createWardrobeGarmentElement(item);
        upperGarmentsGrid.appendChild(garmentElement);
      });
    }

    // Render lower garments
    if (lowerItems.length === 0) {
      lowerEmptyState.style.display = 'flex';
    } else {
      lowerEmptyState.style.display = 'none';
      lowerItems.forEach(item => {
        const garmentElement = createWardrobeGarmentElement(item);
        lowerGarmentsGrid.appendChild(garmentElement);
      });
    }
  }

  // Function to create a wardrobe garment element
  function createWardrobeGarmentElement(item) {
    const div = document.createElement('div');
    div.className = 'garment-item-wardrobe';
    div.dataset.id = item.garment_id;
    div.dataset.type = item.garment_type;

    const img = document.createElement('img');
    img.src = item.garment_image || item.garment_url;
    img.alt = 'Garment';

    const removeBtn = document.createElement('button');
    removeBtn.className = 'remove-btn';
    removeBtn.innerHTML = '×';
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      removeGarmentFromWardrobe(item.garment_id);
    });

    const useBtn = document.createElement('button');
    useBtn.className = 'use-btn';
    useBtn.textContent = 'Use';
    useBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      useGarmentFromWardrobe(item);
    });

    div.appendChild(img);
    div.appendChild(removeBtn);
    div.appendChild(useBtn);

    return div;
  }

  // Function to filter wardrobe by garment type
  function filterWardrobeByType(type) {
    const upperGrid = upperGarmentsGrid.querySelectorAll('.garment-item-wardrobe');
    const lowerGrid = lowerGarmentsGrid.querySelectorAll('.garment-item-wardrobe');

    if (type === 'upper') {
      upperGrid.forEach(item => item.style.display = 'flex');
      lowerGrid.forEach(item => item.style.display = 'none');
    } else {
      upperGrid.forEach(item => item.style.display = 'none');
      lowerGrid.forEach(item => item.style.display = 'flex');
    }
  }

  // Function to filter wardrobe by search term
  function filterWardrobeBySearch(searchTerm) {
    const allItems = document.querySelectorAll('.garment-item-wardrobe');
    allItems.forEach(item => {
      // For now, show all items if search is empty, otherwise could implement image-based filtering
      if (searchTerm === '') {
        item.style.display = 'flex';
      } else {
        // This is a placeholder - in a real app you'd search by metadata
        item.style.display = 'flex';
      }
    });
  }

  // Function to remove garment from wardrobe
  async function removeGarmentFromWardrobe(garmentId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/wardrobe/delete/${garmentId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${currentUser.jwtToken || ''}`
        }
      });

      if (response.ok) {
        console.log('✅ Garment removed from wardrobe');
        wardrobeItems = wardrobeItems.filter(item => item.garment_id !== garmentId);
        renderWardrobeItems();
      } else {
        console.error('Failed to remove garment:', response.status);
      }
    } catch (error) {
      console.error('❌ Error removing garment:', error);
    }
  }

  // Function to use garment from wardrobe (load it into try-on)
  function useGarmentFromWardrobe(item) {
    console.log('Using garment from wardrobe:', item);
    // Load the garment for try-on
    garmentImgData = item.garment_image || item.garment_url;
    selectedGarmentType = item.garment_type;
    
    // Show in garment section
    const garmentPreview = document.getElementById('garment-preview');
    if (garmentPreview) {
      garmentPreview.innerHTML = '';
      const img = document.createElement('img');
      img.src = garmentImgData;
      img.alt = 'Selected Garment';
      garmentPreview.appendChild(img);
    }

    // Go back to main app
    showMainApp();
    document.querySelectorAll('.menu-btn').forEach(btn => btn.classList.remove('active'));
    const menuHomeBtn = document.getElementById('menu-home');
    if (menuHomeBtn) menuHomeBtn.classList.add('active');
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
    if (wardrobePage) wardrobePage.style.display = 'none';
    const savedPage = document.getElementById('saved-page');
    if (savedPage) savedPage.style.display = 'none';
    if (menuBar) menuBar.style.display = 'none';
    
    // Hide header on signin
    const extensionHeader = document.querySelector('.extension-header');
    if (extensionHeader) extensionHeader.style.display = 'none';
  }

  function showAccountCreationPage() {
    console.log('Showing account creation page');
    signinPage.style.display = 'none';
    mainApp.style.display = 'none';
    if (userProfilePage) userProfilePage.style.display = 'none';
    if (wardrobePage) wardrobePage.style.display = 'none';
    const savedPage = document.getElementById('saved-page');
    if (savedPage) savedPage.style.display = 'none';
    accountCreationPage.style.display = 'flex';
    if (menuBar) menuBar.style.display = 'none';
    
    // Hide header on account creation
    const extensionHeader = document.querySelector('.extension-header');
    if (extensionHeader) extensionHeader.style.display = 'none';
  }

  function showUserProfilePage() {
    console.log('Showing user profile page');
    signinPage.style.display = 'none';
    mainApp.style.display = 'none';
    if (accountCreationPage) accountCreationPage.style.display = 'none';
    if (wardrobePage) wardrobePage.style.display = 'none';
    const savedPage = document.getElementById('saved-page');
    if (savedPage) savedPage.style.display = 'none';
    userProfilePage.style.display = 'flex';
    
    // Hide header on profile page
    const extensionHeader = document.querySelector('.extension-header');
    if (extensionHeader) extensionHeader.style.display = 'none';
    if (menuBar) menuBar.style.display = 'none';
    
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
      
      const avatarBgResp = await fetch('http://localhost:8000/api/remove-bg', {
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
    const saveTryonBtn = document.getElementById('save-tryon-btn');
    
    // Add event listener to save button
    if (saveTryonBtn) {
      saveTryonBtn.addEventListener('click', async () => {
        console.log('❤️ Save try-on button clicked');
        
        // Check if there's a current try-on result
        if (!currentWorkingAvatar || !appliedGarments || appliedGarments.length === 0) {
          alert('Please complete a try-on first before saving.');
          return;
        }
        
        // Get the result image
        const resultImg = document.querySelector('#tryon-result img');
        if (!resultImg || !resultImg.src) {
          alert('No try-on result to save.');
          return;
        }
        
        saveTryonBtn.disabled = true;
        const heartIcon = saveTryonBtn.querySelector('.heart-icon');
        if (heartIcon) heartIcon.style.opacity = '0.5';
        
        const success = await saveResultToDatabase(resultImg.src);
        
        if (success) {
          if (heartIcon) {
            heartIcon.style.filter = 'none';
            saveTryonBtn.classList.add('favorited');
          }
          console.log('✅ Try-on saved successfully');
          setTimeout(() => {
            saveTryonBtn.disabled = false;
            if (heartIcon) heartIcon.style.opacity = '1';
          }, 2000);
        } else {
          saveTryonBtn.disabled = false;
          if (heartIcon) heartIcon.style.opacity = '1';
          console.log('❌ Failed to save try-on');
          alert('Failed to save. Please try again.');
        }
      });
    }
    
    // ===== VARIABLES =====
    // Avatar upload and persistence
    const avatarUpload = document.getElementById('avatar-upload');
    const avatarPreview = document.getElementById('avatar-preview');
    let avatarFile = null;
    let avatarBgRemovedBlob = null;

    // UI containers
    const tryonBody = document.querySelector('.tryon-body');
    const tryonResult = document.getElementById('tryon-result');

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
        reader.onload = async function(evt) {
          const imageData = evt.target.result;
          
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
            } else {
              console.log('ℹ️ No user ID found, avatar saved locally only');
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
              <img src="love.png" alt="Add to wardrobe" class="heart-icon" style="width: 24px; height: 24px; object-fit: contain; filter: ${isInWardrobe ? 'none' : 'grayscale(100%)'}; " />
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
              Try On
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

  // Signout button logic - use event delegation to handle both signout buttons
  document.addEventListener('click', (e) => {
    if (e.target.id === 'signout-btn' || e.target.closest('#signout-btn')) {
      const signoutBtn = e.target.id === 'signout-btn' ? e.target : e.target.closest('#signout-btn');
      
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
    }
  });

  // Refresh button logic - use event delegation to handle both refresh buttons
  document.addEventListener('click', (e) => {
    if (e.target.id === 'refresh-btn' || e.target.closest('#refresh-btn')) {
      console.log('Refresh button clicked - resetting current session');
      
      if (confirm('Reset current session? This will clear uploaded images but keep you signed in.')) {
        console.log('User confirmed refresh');
        
        // Reset avatar data
        // renderAvatarPreview();
        clearAllGarments();
        
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
    }
  });

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
        
        const testResponse = await fetch('http://localhost:8000/api/tryon', {
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
          tryonResult.innerHTML = '⏱️ Connection timeout: Server at localhost:8000 is not responding. Please check if the backend server is running.';
        } else if (error.message.includes('ERR_CONNECTION_REFUSED')) {
          tryonResult.innerHTML = '🚫 Connection refused: Server at localhost:8000 is not accepting connections. Please start the backend server.';
        } else if (error.message.includes('ERR_CONNECTION_TIMED_OUT')) {
          tryonResult.innerHTML = '⏱️ Connection timed out: Cannot reach server at localhost:8000. Check network connectivity.';
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
    // Hide all other pages
    signinPage.style.display = 'none';
    if (accountCreationPage) accountCreationPage.style.display = 'none';
    if (userProfilePage) userProfilePage.style.display = 'none';
    if (wardrobePage) wardrobePage.style.display = 'none';
    const savedPage = document.getElementById('saved-page');
    if (savedPage) savedPage.style.display = 'none';
    
    // Show main app and header
    mainApp.style.display = 'flex';
    if (menuBar) menuBar.style.display = 'flex';
    const extensionHeader = document.querySelector('.extension-header');
    if (extensionHeader) extensionHeader.style.display = 'flex';
    
    // Restore previous try-on state if it exists
    restoreTryOnState();
    
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
      // Get current user email and JWT token from storage
      chrome.storage.local.get(['userEmail', 'isGuest', 'jwtToken'], async function(result) {
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

        if (!result.jwtToken) {
          alert('You are not authenticated. Please sign in again.');
          showSignInPage();
          editProfileBtn.innerHTML = 'Edit Profile';
          editProfileBtn.disabled = false;
          return;
        }

        try {
          // Fetch user data using JWT authentication
          const userResponse = await fetch('http://localhost:8000/api/users/profile', {
            method: 'GET',
            headers: {
              'Authorization': `Bearer ${result.jwtToken}`,
              'Content-Type': 'application/json'
            }
          });

          if (!userResponse.ok) {
            throw new Error(`Failed to load user data: ${userResponse.status}`);
          }

          const userData = await userResponse.json();

          if (!userData.success) {
            throw new Error(userData.error || 'Failed to load user data');
          }

          // Fetch body measurements if JWT token available
          let bodyMeasurementsData = null;
          try {
            const measResponse = await fetch('http://localhost:8000/api/body-measurements', {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${result.jwtToken}`,
                'Content-Type': 'application/json'
              }
            });
            
            if (measResponse.ok) {
              const measData = await measResponse.json();
              if (measData.success) {
                bodyMeasurementsData = measData.data;
                console.log('✅ Body measurements loaded:', bodyMeasurementsData);
              }
            } else if (measResponse.status === 404) {
              // No measurements exist yet - this is fine
              console.log('ℹ️ No body measurements found yet for this user');
            } else {
              console.warn('⚠️ Unexpected response loading body measurements:', measResponse.status);
            }
          } catch (measError) {
            console.warn('⚠️ Could not load body measurements:', measError);
            // Don't fail the whole profile load if measurements fail
          }

          console.log('✅ User profile loaded successfully:', userData.data);
          populateProfileForm(userData.data, bodyMeasurementsData);
        } catch (error) {
          console.error('❌ Failed to load user profile:', error);
          alert(`Failed to load profile: ${error.message}`);
          showMainApp();
        } finally {
          // Reset loading state
          editProfileBtn.innerHTML = 'Edit Profile';
          editProfileBtn.disabled = false;
        }
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

  function populateProfileForm(userData, bodyMeasurementsData) {
    // Populate user profile form fields
    if (profileEmail) profileEmail.value = userData.email || '';
    if (profileFirstname) profileFirstname.value = userData.first_name || '';
    if (profileLastname) profileLastname.value = userData.last_name || '';
    if (profileGender) profileGender.value = userData.gender || '';
    if (profileBirthday) profileBirthday.value = userData.birthday || '';
    if (profileStreet) profileStreet.value = userData.street || '';
    if (profileCity) profileCity.value = userData.city || '';
    if (profilePostalCode) profilePostalCode.value = userData.postal_code || '';

    // Populate body measurements if available
    if (bodyMeasurementsData) {
      if (profileHeight) profileHeight.value = bodyMeasurementsData.height || '';
      if (profileWeight) profileWeight.value = bodyMeasurementsData.weight || '';
      if (profileShoulderCircumference) profileShoulderCircumference.value = bodyMeasurementsData.shoulder_circumference || '';
      if (profileArmLength) profileArmLength.value = bodyMeasurementsData.arm_length || '';
      if (profileBicepsCircumference) profileBicepsCircumference.value = bodyMeasurementsData.biceps_circumference || '';
      if (profileBreastCircumference) profileBreastCircumference.value = bodyMeasurementsData.breast_circumference || '';
      if (profileUnderBreastCircumference) profileUnderBreastCircumference.value = bodyMeasurementsData.under_breast_circumference || '';
      if (profileCollarboneToBellyButtonLength) profileCollarboneToBellyButtonLength.value = bodyMeasurementsData.collarbone_to_belly_button_length || '';
      if (profileWaistCircumference) profileWaistCircumference.value = bodyMeasurementsData.waist_circumference || '';
      if (profileHipCircumference) profileHipCircumference.value = bodyMeasurementsData.hip_circumference || '';
      if (profileUpperThighCircumference) profileUpperThighCircumference.value = bodyMeasurementsData.upper_thigh_circumference || '';
      if (profileNeckCircumference) profileNeckCircumference.value = bodyMeasurementsData.neck_circumference || '';
      if (profileWaistToCrotchFrontLength) profileWaistToCrotchFrontLength.value = bodyMeasurementsData.waist_to_crotch_front_length || '';
      if (profileWaistToCrotchBackLength) profileWaistToCrotchBackLength.value = bodyMeasurementsData.waist_to_crotch_back_length || '';
      if (profileInnerLegLength) profileInnerLegLength.value = bodyMeasurementsData.inner_leg_length || '';
      if (profileFootLength) profileFootLength.value = bodyMeasurementsData.foot_length || '';
      if (profileFootWidth) profileFootWidth.value = bodyMeasurementsData.foot_width || '';
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
    // Set readonly attribute for input fields (keep email always readonly)
    // User profile fields
    if (profileFirstname) profileFirstname.readOnly = readOnly;
    if (profileLastname) profileLastname.readOnly = readOnly;
    if (profileBirthday) profileBirthday.readOnly = readOnly;
    if (profileStreet) profileStreet.readOnly = readOnly;
    if (profileCity) profileCity.readOnly = readOnly;
    if (profilePostalCode) profilePostalCode.readOnly = readOnly;
    
    // Body measurements fields
    if (profileHeight) profileHeight.readOnly = readOnly;
    if (profileWeight) profileWeight.readOnly = readOnly;
    if (profileShoulderCircumference) profileShoulderCircumference.readOnly = readOnly;
    if (profileArmLength) profileArmLength.readOnly = readOnly;
    if (profileBicepsCircumference) profileBicepsCircumference.readOnly = readOnly;
    if (profileBreastCircumference) profileBreastCircumference.readOnly = readOnly;
    if (profileUnderBreastCircumference) profileUnderBreastCircumference.readOnly = readOnly;
    if (profileCollarboneToBellyButtonLength) profileCollarboneToBellyButtonLength.readOnly = readOnly;
    if (profileWaistCircumference) profileWaistCircumference.readOnly = readOnly;
    if (profileHipCircumference) profileHipCircumference.readOnly = readOnly;
    if (profileUpperThighCircumference) profileUpperThighCircumference.readOnly = readOnly;
    if (profileNeckCircumference) profileNeckCircumference.readOnly = readOnly;
    if (profileWaistToCrotchFrontLength) profileWaistToCrotchFrontLength.readOnly = readOnly;
    if (profileWaistToCrotchBackLength) profileWaistToCrotchBackLength.readOnly = readOnly;
    if (profileInnerLegLength) profileInnerLegLength.readOnly = readOnly;
    if (profileFootLength) profileFootLength.readOnly = readOnly;
    if (profileFootWidth) profileFootWidth.readOnly = readOnly;
    
    // Set disabled attribute for select inputs
    if (profileGender) profileGender.disabled = readOnly;
  }

  async function handleProfileUpdate() {
    try {
      console.log('💾 Saving profile changes');
      
      // Get user profile form data (only fields in cleaned users table)
      const userData = {
        first_name: profileFirstname.value.trim(),
        last_name: profileLastname.value.trim(),
        gender: profileGender.value,
        birthday: profileBirthday.value,
        street: profileStreet.value.trim(),
        city: profileCity.value.trim(),
        postal_code: profilePostalCode.value.trim()
      };

      // Validate required fields
      if (!userData.first_name || !userData.last_name || !userData.gender) {
        alert('Please fill in all required profile fields');
        return;
      }

      // Get body measurements form data
      const bodyMeasurementsData = {
        height: profileHeight.value ? parseFloat(profileHeight.value) : null,
        weight: profileWeight.value ? parseFloat(profileWeight.value) : null,
        shoulder_circumference: profileShoulderCircumference.value ? parseFloat(profileShoulderCircumference.value) : null,
        arm_length: profileArmLength.value ? parseFloat(profileArmLength.value) : null,
        biceps_circumference: profileBicepsCircumference.value ? parseFloat(profileBicepsCircumference.value) : null,
        breast_circumference: profileBreastCircumference.value ? parseFloat(profileBreastCircumference.value) : null,
        under_breast_circumference: profileUnderBreastCircumference.value ? parseFloat(profileUnderBreastCircumference.value) : null,
        collarbone_to_belly_button_length: profileCollarboneToBellyButtonLength.value ? parseFloat(profileCollarboneToBellyButtonLength.value) : null,
        waist_circumference: profileWaistCircumference.value ? parseFloat(profileWaistCircumference.value) : null,
        hip_circumference: profileHipCircumference.value ? parseFloat(profileHipCircumference.value) : null,
        upper_thigh_circumference: profileUpperThighCircumference.value ? parseFloat(profileUpperThighCircumference.value) : null,
        neck_circumference: profileNeckCircumference.value ? parseFloat(profileNeckCircumference.value) : null,
        waist_to_crotch_front_length: profileWaistToCrotchFrontLength.value ? parseFloat(profileWaistToCrotchFrontLength.value) : null,
        waist_to_crotch_back_length: profileWaistToCrotchBackLength.value ? parseFloat(profileWaistToCrotchBackLength.value) : null,
        inner_leg_length: profileInnerLegLength.value ? parseFloat(profileInnerLegLength.value) : null,
        foot_length: profileFootLength.value ? parseFloat(profileFootLength.value) : null,
        foot_width: profileFootWidth.value ? parseFloat(profileFootWidth.value) : null
      };

      // Show loading state
      saveProfileBtn.innerHTML = 'Saving...';
      saveProfileBtn.disabled = true;

      // Get JWT token for API call
      let jwtToken = null;
      await new Promise((resolve) => {
        chrome.storage.local.get('jwtToken', (result) => {
          jwtToken = result.jwtToken;
          resolve();
        });
      });

      if (!jwtToken) {
        alert('You are not authenticated. Please sign in again.');
        saveProfileBtn.innerHTML = 'Save Changes';
        saveProfileBtn.disabled = false;
        return;
      }

      let updateSuccess = true;
      let errorMessage = '';

      // Call user profile update API using JWT
      try {
        console.log('📤 Sending user profile data:', userData);
        const userResponse = await fetch('http://localhost:8000/api/users/profile', {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${jwtToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(userData)
        });

        const userResult = await userResponse.json();

        if (!userResult.success) {
          updateSuccess = false;
          errorMessage = userResult.error || 'Failed to update user profile';
          console.error('❌ Failed to update user profile:', errorMessage);
        } else {
          console.log('✅ User profile updated successfully');
        }
      } catch (error) {
        updateSuccess = false;
        errorMessage = `User profile update error: ${error.message}`;
        console.error('❌ Error updating user profile:', error);
      }

      // Call body measurements update API if JWT available
      if (jwtToken && updateSuccess) {
        try {
          console.log('📤 Sending body measurements data:', bodyMeasurementsData);
          console.log('📝 Update success status:', updateSuccess);
          const measResponse = await fetch('http://localhost:8000/api/body-measurements', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${jwtToken}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(bodyMeasurementsData)
          });

          const measResult = await measResponse.json();

          if (!measResult.success) {
            console.warn('⚠️ Warning: Body measurements update failed:', measResult.error);
            // Don't fail the whole update if body measurements update fails
          } else {
            console.log('✅ Body measurements updated successfully');
          }
        } catch (error) {
          console.warn('⚠️ Warning: Error updating body measurements:', error);
          // Don't fail the whole update if body measurements update fails
        }
      }

      if (updateSuccess) {
        console.log('✅ Profile updated successfully');
        alert('Profile updated successfully!');
        
        // Return to read-only mode
        setProfileFieldsReadOnly(true);
        editProfileBtn.style.display = 'inline-block';
        saveProfileBtn.style.display = 'none';
        cancelEditBtn.style.display = 'none';
        
        // Reload profile to ensure data is synchronized
        loadUserProfile();
      } else {
        alert(`Failed to update profile: ${errorMessage}`);
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
      // Show garment info button
      const garmentInfoBtn = document.getElementById('garment-info-btn');
      if (garmentInfoBtn) {
        garmentInfoBtn.style.display = 'block';
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
      // Hide garment info button
      const garmentInfoBtn = document.getElementById('garment-info-btn');
      if (garmentInfoBtn) {
        garmentInfoBtn.style.display = 'none';
      }
      // Hide info container if it exists
      const garmentInfoContainer = document.getElementById('garment-info-container');
      if (garmentInfoContainer) {
        garmentInfoContainer.style.display = 'none';
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

  // ===== GARMENT API FUNCTIONALITY =====
  // Garment API configuration
  const GARMENT_API_BASE_URL = 'https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1';
  const GARMENT_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNjamR4eGdvYWhmc3hubHRoeG1tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1MTE0MTUsImV4cCI6MjA5MTA4NzQxNX0.nS0QYp-_ubvp9uwvQhS1ElLVVeMAbgKxAXWeG0jRayw';

  // Get current tab URL
  async function getCurrentTabUrl() {
    return new Promise((resolve, reject) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length === 0) {
          reject(new Error('No active tab found'));
        } else {
          resolve(tabs[0].url);
        }
      });
    });
  }

  // Fetch garment data from Garment API
  async function getGarmentFromAPI(url) {
    try {
      const encodedUrl = encodeURIComponent(url);
      const apiUrl = `${GARMENT_API_BASE_URL}/get-garment?url=${encodedUrl}`;
      
      console.log('🔗 Fetching garment from API:', apiUrl);
      
      const response = await fetch(apiUrl, {
        method: 'GET',
        headers: {
          'apikey': GARMENT_API_KEY,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `API returned status ${response.status}`);
      }

      const garmentData = await response.json();
      console.log('✅ Garment data received:', garmentData);
      return garmentData;
    } catch (error) {
      console.error('❌ Error fetching garment:', error);
      throw error;
    }
  }

  // Determine garment type (upper or lower) from category
  function determinGarmentType(garmentData) {
    const category = (garmentData.category || '').toLowerCase();
    const subcategory = (garmentData.subcategory || '').toLowerCase();
    
    // Lower garments
    const lowerCategories = ['pants', 'jeans', 'skirt', 'shorts', 'trouser', 'leggings', 'bottom', 'lower'];
    const lowerSubcategories = ['pants', 'jeans', 'skirt', 'shorts', 'trouser', 'leggings', 'bottom'];
    
    if (lowerCategories.includes(category) || lowerSubcategories.includes(subcategory)) {
      return 'lower';
    }
    
    // Default to upper
    return 'upper';
  }
  
  // Call fit analysis API
  async function callFitAnalysisAPI(garmentType, garmentMeasurements, garmentSize) {
    // Get auth token (stored as jwtToken in extension)
    const token = await new Promise(resolve => {
      chrome.storage.local.get('jwtToken', result => {
        resolve(result.jwtToken);
      });
    });
    
    if (!token) {
      throw new Error('Authentication token not found. Please sign in first.');
    }
    
    // Get server URL
    const serverUrl = await new Promise(resolve => {
      chrome.storage.local.get('serverUrl', result => {
        resolve(result.serverUrl || 'http://localhost:8000');
      });
    });
    
    const apiUrl = `${serverUrl}/api/fit-analysis`;
    
    const payload = {
      garment_type: garmentType,
      garment_measurements: garmentMeasurements,
      garment_size: garmentSize
    };
    
    console.log('📤 Calling FIT API:', apiUrl, payload);
    
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || `FIT API returned status ${response.status}`);
    }
    
    const fitResult = await response.json();
    console.log('✅ FIT Analysis result:', fitResult);
    return fitResult;
  }
  
  // Display fit analysis results with body visualization
  function displayFitAnalysisResults(fitResult, garmentName, selectedSize) {
    // Create or get modal container
    let modal = document.getElementById('fit-analysis-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'fit-analysis-modal';
      document.body.appendChild(modal);
    }
    
    // Determine overall color based on fit status
    let overallFitColor;
    if (fitResult.overall_fit === 'body fit') {
      overallFitColor = '#4CAF50';  // Green - perfect
    } else if (fitResult.overall_fit === 'good fit') {
      overallFitColor = '#4CAF50';  // Green - good
    } else if (fitResult.overall_fit === 'loose fit') {
      overallFitColor = '#FF9800';  // Orange - loose
    } else {  // tight
      overallFitColor = '#ff6b6b';  // Red - tight
    }
    
    // Color mapping for individual measurements
    const statusColorMap = {
      'body fit': { text: '#2E7D32', bg: '#E8F5E9', border: '#4CAF50' },  // Green
      'good fit': { text: '#558B2F', bg: '#E8F5E9', border: '#7CB342' },  // Light green
      'loose fit': { text: '#E65100', bg: '#FFE0B2', border: '#FF9800' },  // Orange
      'tight': { text: '#C62828', bg: '#FFEBEE', border: '#ff6b6b' }       // Red
    };
    
    // Get color for a specific fit status
    const getStatusColor = (status) => {
      return statusColorMap[status] || { text: '#666', bg: '#f5f5f5', border: '#999' };
    };
    
    // Group measurements by body part for visual positioning
    const bodyPartMap = {
      'breast_width': { label: 'Chest', y: '35%', color: '#ff6b6b' },
      'arm_width': { label: 'Arms', y: '40%', color: '#ff9800' },
      'shirt_length': { label: 'Length', y: '75%', color: '#2196F3' },
      'arm_length': { label: 'Sleeve', y: '45%', color: '#ff9800' },
      'shoulder_width': { label: 'Shoulder', y: '25%', color: '#4CAF50' },
      'waist': { label: 'Waist', y: '52%', color: '#ff6b6b' },
      'hip': { label: 'Hips', y: '62%', color: '#ff6b6b' },
      'leg_length': { label: 'Inseam', y: '85%', color: '#2196F3' },
      'front_rise': { label: 'Rise', y: '58%', color: '#ff9800' },
      'inseam': { label: 'Inseam', y: '85%', color: '#2196F3' },
      'thigh': { label: 'Thigh', y: '68%', color: '#ff9800' }
    };
    
    // Map measurements to positions and colors
    const mappedMeasurements = (fitResult.measurements || []).map(m => {
      const bodyPart = bodyPartMap[m.metric] || { label: m.metric.replace(/_/g, ' '), y: '50%', color: '#666' };
      const statusColor = getStatusColor(m.fit_status);
      return {
        ...m,
        ...bodyPart,
        statusColor
      };
    });
    
    const statusCounts = {
      body_fit: fitResult.body_fit_count || 0,
      good_fit: fitResult.good_fits || 0,
      loose_fit: fitResult.loose_fit_count || 0,
      tight: fitResult.tight_count || 0
    };
    
    // Create body outline SVG
    const bodySVG = `
      <svg viewBox="0 0 100 200" style="width: 100%; max-width: 150px; height: auto;">
        <!-- Head -->
        <circle cx="50" cy="25" r="12" fill="none" stroke="#333" stroke-width="2"/>
        <!-- Neck -->
        <rect x="48" y="37" width="4" height="6" fill="#333"/>
        <!-- Chest -->
        <path d="M 48 43 L 35 65 L 35 85 L 65 85 L 65 65 L 52 43 Z" fill="none" stroke="#333" stroke-width="2"/>
        <!-- Arms -->
        <line x1="35" y1="50" x2="15" y2="65" stroke="#333" stroke-width="2"/>
        <line x1="65" y1="50" x2="85" y2="65" stroke="#333" stroke-width="2"/>
        <!-- Waist/Hips -->
        <ellipse cx="50" cy="95" rx="18" ry="12" fill="none" stroke="#333" stroke-width="2"/>
        <!-- Legs -->
        <line x1="42" y1="107" x2="40" y2="180" stroke="#333" stroke-width="2"/>
        <line x1="58" y1="107" x2="60" y2="180" stroke="#333" stroke-width="2"/>
        <!-- Feet -->
        <line x1="35" y1="180" x2="45" y2="180" stroke="#333" stroke-width="2"/>
        <line x1="55" y1="180" x2="65" y2="180" stroke="#333" stroke-width="2"/>
      </svg>
    `;
    
    // Build detailed measurements list
    const measurementsList = mappedMeasurements.map(m => `
      <div style="
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 8px;
        padding: 8px;
        margin-bottom: 6px;
        background: ${m.statusColor.bg};
        border-left: 3px solid ${m.statusColor.border};
        border-radius: 4px;
        font-size: 12px;
      ">
        <span style="font-weight: 600; color: ${m.statusColor.text}; min-width: 80px;">${m.metric.replace(/_/g, ' ')}</span>
        <span style="color: #666;">
          Body: <strong>${m.body_value}</strong> cm | 
          Garment: <strong>${m.garment_value}</strong> cm
        </span>
      </div>
    `).join('');
    
    modal.innerHTML = `
      <div style="
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
      " id="fit-modal-overlay">
        <div style="
          background: white;
          border-radius: 12px;
          padding: 24px;
          max-width: 900px;
          max-height: 85vh;
          overflow-y: auto;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
        ">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
            <h2 style="margin: 0; font-size: 22px; color: #333; font-weight: 700;">Fit Analysis: ${garmentName}</h2>
            <button id="fit-modal-close" style="
              background: none;
              border: none;
              font-size: 28px;
              cursor: pointer;
              color: #999;
              padding: 0;
              width: 32px;
              height: 32px;
              display: flex;
              align-items: center;
              justify-content: center;
            ">&times;</button>
          </div>
          
          <!-- Overall Assessment Badge -->
          <div style="
            background: ${overallFitColor}15;
            border: 2px solid ${overallFitColor};
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 24px;
            text-align: center;
          ">
            <div style="font-size: 12px; color: #999; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Overall Assessment</div>
            <div style="font-size: 28px; font-weight: 700; color: ${overallFitColor}; margin-bottom: 8px;">
              ${fitResult.overall_fit.toUpperCase()}
            </div>
            <div style="font-size: 13px; color: #666;">
              Size ${selectedSize} | ${statusCounts.body_fit} perfect, ${statusCounts.good_fit} good, ${statusCounts.loose_fit} loose, ${statusCounts.tight} tight
            </div>
          </div>
          
          <!-- Main Fit Visualization -->
          <div style="
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
            align-items: flex-start;
          ">
            <!-- Left: User Size Info -->
            <div style="
              background: #f5f5f5;
              border-radius: 8px;
              padding: 16px;
              text-align: center;
            ">
              <div style="font-size: 12px; color: #999; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Your Measurements</div>
              <div style="font-size: 32px; font-weight: 700; color: #4CAF50; margin-bottom: 8px;">
                ${fitResult.measurements && fitResult.measurements[0] ? fitResult.measurements[0].body_value : '--'}
              </div>
              <div style="font-size: 12px; color: #333; margin-bottom: 12px; font-weight: 500;">Reference</div>
              <div style="
                font-size: 11px;
                color: #666;
                padding-top: 12px;
                border-top: 1px solid #ddd;
                line-height: 1.6;
              ">
                Your body measurements on file
              </div>
            </div>
            
            <!-- Center: Body Outline -->
            <div style="
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
            ">
              <div style="margin-bottom: 12px;">${bodySVG}</div>
              <div style="
                font-size: 11px;
                color: #999;
                text-align: center;
                padding-top: 8px;
              ">Fit Analysis</div>
            </div>
            
            <!-- Right: Size Info -->
            <div style="
              background: #f5f5f5;
              border-radius: 8px;
              padding: 16px;
              text-align: center;
            ">
              <div style="font-size: 12px; color: #999; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Garment Size ${selectedSize}</div>
              <div style="font-size: 32px; font-weight: 700; color: #2196F3; margin-bottom: 8px;">
                ${fitResult.measurements && fitResult.measurements[0] ? fitResult.measurements[0].garment_value : '--'}
              </div>
              <div style="font-size: 12px; color: #333; margin-bottom: 12px; font-weight: 500;">Specification</div>
              <div style="
                font-size: 11px;
                color: #666;
                padding-top: 12px;
                border-top: 1px solid #ddd;
                line-height: 1.6;
              ">
                Size ${selectedSize} garment measurements
              </div>
            </div>
          </div>
          
          <!-- Detailed Measurements -->
          <div style="margin-bottom: 24px;">
            <h3 style="margin: 0 0 12px 0; font-size: 14px; color: #333; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600;">Measurement Details</h3>
            <div style="
              background: #fafafa;
              border-radius: 8px;
              padding: 12px;
              max-height: 200px;
              overflow-y: auto;
            ">
              ${measurementsList}
            </div>
          </div>
          
          <!-- Legend -->
          <div style="
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 20px;
            font-size: 12px;
          ">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="width: 16px; height: 16px; background: #4CAF50; border-radius: 3px;"></div>
              <span style="color: #666;">Body Fit (Perfect)</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="width: 16px; height: 16px; background: #7CB342; border-radius: 3px;"></div>
              <span style="color: #666;">Good Fit</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="width: 16px; height: 16px; background: #FF9800; border-radius: 3px;"></div>
              <span style="color: #666;">Loose Fit</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="width: 16px; height: 16px; background: #ff6b6b; border-radius: 3px;"></div>
              <span style="color: #666;">Tight</span>
            </div>
          </div>
          
          <button id="fit-modal-close-btn" style="
            width: 100%;
            padding: 14px 16px;
            background: ${overallFitColor};
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
          ">Close</button>
        </div>
      </div>
    `;
    
    modal.style.display = 'block';
    
    // Close button handlers
    const closeBtn = document.getElementById('fit-modal-close');
    const closeBtnAlt = document.getElementById('fit-modal-close-btn');
    const overlay = document.getElementById('fit-modal-overlay');
    
    const closeModal = () => {
      modal.style.display = 'none';
    };
    
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (closeBtnAlt) closeBtnAlt.addEventListener('click', closeModal);
    if (overlay) overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });
    
    // Add hover effect to close button
    if (closeBtn) {
      closeBtn.addEventListener('mouseenter', () => {
        closeBtn.style.color = '#333';
      });
      closeBtn.addEventListener('mouseleave', () => {
        closeBtn.style.color = '#999';
      });
    }
    
    console.log('🎨 FIT Analysis results displayed with body visualization');
  }

  // Display garment information
  function displayGarmentInfo(garmentData) {
    // Create a container for garment info if it doesn't exist
    let garmentInfoContainer = document.getElementById('garment-info-container');
    if (!garmentInfoContainer) {
      garmentInfoContainer = document.createElement('div');
      garmentInfoContainer.id = 'garment-info-container';
      garmentInfoContainer.style.cssText = `
        padding: 20px;
        background: #ffffff;
        border-radius: 12px;
        margin: 16px 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        border: 1px solid #f0f0f0;
        max-height: 500px;
        overflow-y: auto;
      `;
      
      // Insert after the main app or at the beginning of the visible area
      const mainApp = document.getElementById('main-app');
      if (mainApp) {
        mainApp.insertAdjacentElement('afterbegin', garmentInfoContainer);
      }
    }

    // Extract garment information
    const measurementsBySize = garmentData.measurements_by_size || {};
    const hasMeasurements = Object.keys(measurementsBySize).length > 0;
    
    // Build measurements HTML organized by size
    const measurementsHtml = hasMeasurements ? Object.entries(measurementsBySize).map(([size, measurements]) => `
      <div style="margin-bottom: 16px;">
        <div style="font-weight: 600; color: #1a1a1a; margin-bottom: 8px; padding-bottom: 8px; border-bottom: 2px solid #e0e0e0; font-size: 13px;">Size ${size}</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
          ${Object.entries(measurements).map(([measType, value]) => `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 6px 0; font-size: 12px;">
              <span style="color: #666;">${measType.replace(/_/g, ' ')}</span>
              <span style="color: #333; font-weight: 500;">${value} cm</span>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('') : '';

    // Build HTML for garment info with elegant styling
    const html = `
      <div style="margin-bottom: 20px;">
        <h3 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #1a1a1a; letter-spacing: -0.3px;">
          ${garmentData.name || 'Garment'}
        </h3>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
        <div>
          <div style="margin-bottom: 12px;">
            <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;">SKU</span>
            <span style="font-size: 14px; color: #333;">${garmentData.sku || 'N/A'}</span>
          </div>
          <div>
            <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;">Brand</span>
            <span style="font-size: 14px; color: #333;">${garmentData.brand_partners?.brand_name || 'Unknown'}</span>
          </div>
        </div>
        <div>
          <div style="margin-bottom: 12px;">
            <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;">Category</span>
            <span style="font-size: 14px; color: #333; text-transform: capitalize;">${garmentData.category || 'N/A'} ${garmentData.subcategory ? '— ' + garmentData.subcategory : ''}</span>
          </div>
          <div>
            <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;">Color</span>
            <span style="font-size: 14px; color: #333;">${garmentData.color || 'N/A'}</span>
          </div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #f0f0f0;">
        <div>
          <div style="margin-bottom: 12px;">
            <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;">Fit Type</span>
            <span style="font-size: 14px; color: #333; text-transform: capitalize;">${garmentData.fit_type || 'N/A'}</span>
          </div>
        </div>
        <div>
          <div>
            <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; font-weight: 600;">Material Stretch</span>
            <span style="font-size: 14px; color: #333; text-transform: capitalize;">${garmentData.material_stretch || 'N/A'}</span>
          </div>
        </div>
      </div>

      <div style="margin-bottom: 20px;">
        <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600;">Sizes Available</span>
        <span style="font-size: 14px; color: #333;">${garmentData.size_label || 'N/A'}</span>
      </div>

      <div style="margin-bottom: 20px;">
        <span style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; font-weight: 600;">Measurements</span>
        <div style="background: #fafafa; border-radius: 8px; padding: 12px; border: 1px solid #f0f0f0;">
          ${measurementsHtml || '<span style="color: #999; font-size: 13px;">No measurements available</span>'}
        </div>
      </div>

      <div style="margin-bottom: 20px; display: ${hasMeasurements ? 'block' : 'none'};">
        <label style="display: block; font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600;">Select Size</label>
        <select id="garment-size-selector" style="
          width: 100%;
          padding: 10px 12px;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          font-size: 14px;
          background: white;
          color: #333;
          cursor: pointer;
        ">
          <option value="">-- Choose a size --</option>
          ${Object.keys(measurementsBySize).map(size => `<option value="${size}">${size}</option>`).join('')}
        </select>
      </div>

      <button id="garment-fit-analysis-btn" style="
        width: 100%;
        padding: 14px 16px;
        background: #4CAF50;
        color: white;
        border: none;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        box-shadow: 0 2px 8px rgba(76, 175, 80, 0.2);
        ${!hasMeasurements ? 'background: #cccccc; cursor: not-allowed;' : ''}
      " ${!hasMeasurements ? 'disabled' : ''}>Fit Analysis</button>
    `;

    garmentInfoContainer.innerHTML = html;
    garmentInfoContainer.style.display = 'block';

    // Add event listener for Fit Analysis button
    const fitAnalysisBtn = document.getElementById('garment-fit-analysis-btn');
    const sizeSelector = document.getElementById('garment-size-selector');
    
    if (fitAnalysisBtn) {
      fitAnalysisBtn.addEventListener('mouseenter', () => {
        if (!fitAnalysisBtn.disabled) {
          fitAnalysisBtn.style.background = '#45a049';
          fitAnalysisBtn.style.transform = 'translateY(-2px)';
          fitAnalysisBtn.style.boxShadow = '0 4px 12px rgba(76, 175, 80, 0.3)';
        }
      });
      fitAnalysisBtn.addEventListener('mouseleave', () => {
        if (!fitAnalysisBtn.disabled) {
          fitAnalysisBtn.style.background = '#4CAF50';
          fitAnalysisBtn.style.transform = 'translateY(0)';
          fitAnalysisBtn.style.boxShadow = '0 2px 8px rgba(76, 175, 80, 0.2)';
        }
      });
      fitAnalysisBtn.addEventListener('click', async () => {
        console.log('📊 Fit Analysis clicked for garment:', garmentData.name);
        
        // Validate size selection
        if (!sizeSelector || !sizeSelector.value) {
          alert('Please select a size first');
          return;
        }
        
        const selectedSize = sizeSelector.value;
        const measurements = measurementsBySize[selectedSize];
        
        if (!measurements) {
          alert('Measurements not available for selected size');
          return;
        }
        
        try {
          // Determine garment type from category
          const garmentType = determinGarmentType(garmentData);
          
          console.log('📤 Starting fit analysis:', {
            garmentName: garmentData.name,
            selectedSize,
            garmentType,
            measurements
          });
          
          // Call fit analysis API
          const fitResult = await callFitAnalysisAPI(garmentType, measurements, selectedSize);
          
          // Display fit analysis results
          displayFitAnalysisResults(fitResult, garmentData.name, selectedSize);
          
        } catch (error) {
          console.error('❌ Fit analysis error:', error);
          alert('Error analyzing fit: ' + error.message);
        }
      });
      
      // Enable/disable button based on size selection
      if (sizeSelector) {
        sizeSelector.addEventListener('change', () => {
          fitAnalysisBtn.disabled = !sizeSelector.value;
          fitAnalysisBtn.style.background = sizeSelector.value ? '#4CAF50' : '#cccccc';
          fitAnalysisBtn.style.cursor = sizeSelector.value ? 'pointer' : 'not-allowed';
        });
      }
    }

    console.log('🖼️ Garment info displayed');
  }

  // Fetch and display garment from current URL
  window.fetchGarmentFromCurrentUrl = async function() {
    const fetchBtn = document.getElementById('fetch-garment-btn');
    if (fetchBtn) {
      fetchBtn.disabled = true;
      fetchBtn.innerHTML = 'Loading...';
    }

    try {
      const currentUrl = await getCurrentTabUrl();
      console.log('📍 Current URL:', currentUrl);

      const garmentData = await getGarmentFromAPI(currentUrl);
      displayGarmentInfo(garmentData);

      if (fetchBtn) {
        fetchBtn.innerHTML = '✓ Garment Loaded';
        setTimeout(() => {
          fetchBtn.innerHTML = 'Load Garment Info';
          fetchBtn.disabled = false;
        }, 2000);
      }
    } catch (error) {
      console.error('Error:', error);
      alert(`Failed to fetch garment: ${error.message}`);
      if (fetchBtn) {
        fetchBtn.innerHTML = 'Load Garment Info';
        fetchBtn.disabled = false;
      }
    }
  };

  // Fetch garment info and display
  window.toggleGarmentInfo = async function() {
    const garmentInfoContainer = document.getElementById('garment-info-container');
    
    // If already showing, just toggle visibility
    if (garmentInfoContainer && garmentInfoContainer.style.display !== 'none') {
      garmentInfoContainer.style.display = garmentInfoContainer.style.display === 'none' ? 'block' : 'none';
      return;
    }
    
    // Otherwise, fetch the garment info
    const garmentInfoBtn = document.getElementById('garment-info-btn');
    if (garmentInfoBtn) {
      garmentInfoBtn.disabled = true;
      garmentInfoBtn.style.opacity = '0.6';
    }

    try {
      const currentUrl = await getCurrentTabUrl();
      console.log('📍 Current URL:', currentUrl);

      const garmentData = await getGarmentFromAPI(currentUrl);
      displayGarmentInfo(garmentData);

      if (garmentInfoBtn) {
        garmentInfoBtn.style.opacity = '1';
        garmentInfoBtn.disabled = false;
      }
    } catch (error) {
      console.error('Error:', error);
      // Remove the info container on error
      const infoContainer = document.getElementById('garment-info-container');
      if (infoContainer) {
        infoContainer.remove();
      }
      
      if (garmentInfoBtn) {
        garmentInfoBtn.style.opacity = '1';
        garmentInfoBtn.disabled = false;
      }
    }
  };

  // Make functions globally available
  window.showTryonResult = showTryonResult;
  window.hideTryonResult = hideTryonResult;

  // Add event listener for garment info button
  const garmentInfoBtn = document.getElementById('garment-info-btn');
  if (garmentInfoBtn) {
    garmentInfoBtn.addEventListener('click', window.toggleGarmentInfo);
  }
});
