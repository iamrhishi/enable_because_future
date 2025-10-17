document.addEventListener('DOMContentLoaded', function() {
  
  // Page Navigation Elements
  const signinPage = document.getElementById('signin-page');
  const signupPage = document.getElementById('signup-page');
  const mainPage = document.getElementById('main-page');
  
  // Navigation Buttons
  const gotoSignupBtn = document.getElementById('goto-signup');
  const gotoSigninBtn = document.getElementById('goto-signin');
  const logoutBtn = document.getElementById('logout-btn');
  
  // Form Elements
  const signinForm = document.getElementById('signin-form');
  const signupForm = document.getElementById('signup-form');
  const signinBtn = document.getElementById('signin-btn');
  const signupBtn = document.getElementById('signup-btn');
  
  // Main Interface Variables
  let avatarFile = null;
  let avatarBgRemovedBlob = null;
  let garmentBgRemovedBlob = null;
  
  // Check if user is already logged in
  const isLoggedIn = localStorage.getItem('isLoggedIn') === 'true';
  
  // Initialize page based on login status
  if (isLoggedIn) {
    showMainPage();
  } else {
    showSigninPage();
  }
  
  // Page Navigation Functions
  function showPage(pageToShow) {
    [signinPage, signupPage, mainPage].forEach(page => {
      page.classList.remove('active');
    });
    pageToShow.classList.add('active');
  }
  
  function showSigninPage() {
    showPage(signinPage);
  }
  
  function showSignupPage() {
    showPage(signupPage);
  }
  
  function showMainPage() {
    showPage(mainPage);
    if (!mainInterfaceInitialized) {
      initializeMainInterface();
      mainInterfaceInitialized = true;
    }
  }
  
  let mainInterfaceInitialized = false;
  
  // Navigation Event Listeners
  if (gotoSignupBtn) gotoSignupBtn.addEventListener('click', showSignupPage);
  if (gotoSigninBtn) gotoSigninBtn.addEventListener('click', showSigninPage);
  if (logoutBtn) logoutBtn.addEventListener('click', function() {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userName');
    showSigninPage();
  });
  
  // Form Validation Functions
  function validateEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }
  
  function validatePassword(password) {
    return password.length >= 6;
  }
  
  function showError(inputId, message) {
    const input = document.getElementById(inputId);
    const errorElement = document.getElementById(inputId + '-error');
    if (input && errorElement) {
      input.classList.add('error');
      errorElement.textContent = message;
    }
  }
  
  function clearError(inputId) {
    const input = document.getElementById(inputId);
    const errorElement = document.getElementById(inputId + '-error');
    if (input && errorElement) {
      input.classList.remove('error');
      errorElement.textContent = '';
    }
  }
  
  function showSuccess(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
      input.classList.add('success');
    }
  }
  
  function setButtonLoading(button, isLoading) {
    if (!button) return;
    
    const btnText = button.querySelector('.btn-text');
    const btnSpinner = button.querySelector('.btn-spinner');
    
    if (isLoading) {
      if (btnText) btnText.style.display = 'none';
      if (btnSpinner) btnSpinner.style.display = 'block';
      button.disabled = true;
    } else {
      if (btnText) btnText.style.display = 'block';
      if (btnSpinner) btnSpinner.style.display = 'none';
      button.disabled = false;
    }
  }
  
  // Sign In Form Handling
  if (signinForm) {
    signinForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const email = document.getElementById('signin-email').value.trim();
      const password = document.getElementById('signin-password').value;
      
      // Clear previous errors
      clearError('signin-email');
      clearError('signin-password');
      
      let hasErrors = false;
      
      // Validate email
      if (!email) {
        showError('signin-email', 'Email is required');
        hasErrors = true;
      } else if (!validateEmail(email)) {
        showError('signin-email', 'Please enter a valid email');
        hasErrors = true;
      } else {
        showSuccess('signin-email');
      }
      
      // Validate password
      if (!password) {
        showError('signin-password', 'Password is required');
        hasErrors = true;
      } else if (!validatePassword(password)) {
        showError('signin-password', 'Password must be at least 6 characters');
        hasErrors = true;
      } else {
        showSuccess('signin-password');
      }
      
      if (hasErrors) return;
      
      // Simulate API call
      setButtonLoading(signinBtn, true);
      
      setTimeout(() => {
        // For demo purposes, accept any valid email/password
        localStorage.setItem('isLoggedIn', 'true');
        localStorage.setItem('userEmail', email);
        setButtonLoading(signinBtn, false);
        showMainPage();
      }, 1500);
    });
  }
  
  // Sign Up Form Handling  
  if (signupForm) {
    signupForm.addEventListener('submit', function(e) {
      e.preventDefault();
      
      const name = document.getElementById('signup-name').value.trim();
      const email = document.getElementById('signup-email').value.trim();
      const password = document.getElementById('signup-password').value;
      const confirmPassword = document.getElementById('signup-confirm-password').value;
      
      // Clear previous errors
      clearError('signup-name');
      clearError('signup-email');
      clearError('signup-password');
      clearError('signup-confirm');
      
      let hasErrors = false;
      
      // Validate name
      if (!name) {
        showError('signup-name', 'Full name is required');
        hasErrors = true;
      } else if (name.length < 2) {
        showError('signup-name', 'Name must be at least 2 characters');
        hasErrors = true;
      } else {
        showSuccess('signup-name');
      }
      
      // Validate email
      if (!email) {
        showError('signup-email', 'Email is required');
        hasErrors = true;
      } else if (!validateEmail(email)) {
        showError('signup-email', 'Please enter a valid email');
        hasErrors = true;
      } else {
        showSuccess('signup-email');
      }
      
      // Validate password
      if (!password) {
        showError('signup-password', 'Password is required');
        hasErrors = true;
      } else if (!validatePassword(password)) {
        showError('signup-password', 'Password must be at least 6 characters');
        hasErrors = true;
      } else {
        showSuccess('signup-password');
      }
      
      // Validate confirm password
      if (!confirmPassword) {
        showError('signup-confirm', 'Please confirm your password');
        hasErrors = true;
      } else if (password !== confirmPassword) {
        showError('signup-confirm', 'Passwords do not match');
        hasErrors = true;
      } else {
        showSuccess('signup-confirm');
      }
      
      if (hasErrors) return;
      
      // Simulate API call
      setButtonLoading(signupBtn, true);
      
      setTimeout(() => {
        localStorage.setItem('isLoggedIn', 'true');
        localStorage.setItem('userEmail', email);
        localStorage.setItem('userName', name);
        setButtonLoading(signupBtn, false);
        showMainPage();
      }, 2000);
    });
  }
  
  // Initialize Main Interface
  function initializeMainInterface() {
    // Get current tab URL
    if (chrome.tabs && chrome.tabs.query) {
      chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        if (tabs && tabs[0] && tabs[0].url) {
          const pageUrlInput = document.getElementById('page-url');
          if (pageUrlInput) {
            pageUrlInput.value = tabs[0].url;
          }
        }
      });
    }
    
    // Initialize main interface event listeners
    setupMainInterfaceListeners();
  }
  
  function setupMainInterfaceListeners() {
    // Main interface elements
    const avatarUpload = document.getElementById('avatar-upload');
    const avatarUploadBtn = document.getElementById('avatar-upload-btn');
    const avatarPreview = document.getElementById('avatar-preview');
    const garmentUpload = document.getElementById('garment-upload'); 
    const garmentUploadBtn = document.getElementById('garment-upload-btn');
    const garmentPreview = document.getElementById('garment-preview');
    const tryonBtn = document.getElementById('tryon-btn');
    const refreshBtn = document.getElementById('refresh-btn');
    const useGarmentCheckbox = document.getElementById('use-garment-checkbox');
    
    // Avatar upload functionality
    if (avatarUploadBtn && avatarUpload) {
      avatarUploadBtn.addEventListener('click', () => avatarUpload.click());
      
      avatarUpload.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
          avatarFile = file;
          const reader = new FileReader();
          reader.onload = function(e) {
            avatarPreview.innerHTML = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;">`;
          };
          reader.readAsDataURL(file);
        }
      });
    }
    
    // Garment upload functionality
    if (garmentUploadBtn && garmentUpload) {
      garmentUploadBtn.addEventListener('click', () => garmentUpload.click());
      
      garmentUpload.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = function(e) {
            garmentPreview.innerHTML = `<img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;">`;
          };
          reader.readAsDataURL(file);
        }
      });
    }
    
    // Try-on functionality
    if (tryonBtn) {
      tryonBtn.addEventListener('click', function() {
        if (!avatarFile) {
          alert('Please upload an avatar image first');
          return;
        }
        
        setButtonLoading(tryonBtn, true);
        
        // Simulate try-on process
        setTimeout(() => {
          setButtonLoading(tryonBtn, false);
          alert('Try-on completed! (This is a demo)');
        }, 3000);
      });
    }
    
    // Refresh functionality
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function() {
        location.reload();
      });
    }
    
    // Use garment from page functionality
    if (useGarmentCheckbox) {
      useGarmentCheckbox.addEventListener('change', function() {
        if (this.checked) {
          // Disable manual garment upload
          if (garmentUploadBtn) garmentUploadBtn.disabled = true;
          
          // Try to extract garment from current page
          if (chrome.tabs && chrome.tabs.query) {
            chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
              if (tabs && tabs[0] && tabs[0].id) {
                chrome.tabs.sendMessage(tabs[0].id, {type: 'GET_IMAGES_ON_PAGE'}, function(response) {
                  if (response && response.images && response.images.length > 0) {
                    // For demo, just show the first image found
                    const firstImage = response.images[0];
                    garmentPreview.innerHTML = `<img src="${firstImage.src}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px;">`;
                  }
                });
              }
            });
          }
        } else {
          // Re-enable manual garment upload
          if (garmentUploadBtn) garmentUploadBtn.disabled = false;
        }
      });
    }
  }
  
});
