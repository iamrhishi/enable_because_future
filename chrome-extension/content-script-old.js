// content-script.js
(function() {
  console.log('Content script loaded on:', window.location.href);

  // ===== GARMENT API CONFIGURATION =====
  const GARMENT_API_BASE_URL = 'https://ccjdxxgoahfsxnlthxmm.supabase.co/functions/v1';
  const GARMENT_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNjamR4eGdvYWhmc3hubHRoeG1tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzU1MTE0MTUsImV4cCI6MjA5MTA4NzQxNX0.nS0QYp-_ubvp9uwvQhS1ElLVVeMAbgKxAXWeG0jRayw';

  // ===== INJECT STYLES FOR INFO BUTTON AND MODAL =====
  function injectStyles() {
    const styleId = 'enable-garment-info-styles';
    if (document.getElementById(styleId)) return; // Already injected

    const styles = document.createElement('style');
    styles.id = styleId;
    styles.textContent = `
      .enable-info-btn {
        position: fixed;
        top: 50%;
        right: 20px;
        transform: translateY(-50%);
        width: 56px;
        height: 56px;
        background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        border: 3px solid white;
        border-radius: 50%;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 28px;
        z-index: 999999;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
        transition: all 0.3s ease;
        font-weight: bold;
        color: white;
      }

      .enable-info-btn:hover {
        background: linear-gradient(135deg, #45a049 0%, #3d8b40 100%);
        transform: translateY(-50%) scale(1.15);
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35);
      }

      .enable-info-btn:active {
        transform: translateY(-50%) scale(0.9);
      }

      .enable-garment-modal {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.6);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10001;
        animation: fadeIn 0.2s ease-out;
      }

      @keyframes fadeIn {
        from {
          opacity: 0;
        }
        to {
          opacity: 1;
        }
      }

      .enable-garment-modal-content {
        background: white;
        border-radius: 12px;
        padding: 24px;
        max-width: 500px;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        position: relative;
        animation: slideUp 0.3s ease-out;
      }

      @keyframes slideUp {
        from {
          opacity: 0;
          transform: translateY(20px);
        }
        to {
          opacity: 1;
          transform: translateY(0);
        }
      }

      .enable-modal-close {
        position: absolute;
        top: 12px;
        right: 12px;
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: #666;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: all 0.2s ease;
      }

      .enable-modal-close:hover {
        background: #f0f0f0;
        color: #333;
      }

      .enable-garment-info {
        margin-top: 8px;
      }

      .enable-garment-info h2 {
        margin: 0 0 16px 0;
        font-size: 20px;
        color: #333;
        padding-right: 28px;
      }

      .enable-garment-info-section {
        margin-bottom: 16px;
        padding-bottom: 12px;
        border-bottom: 1px solid #eee;
      }

      .enable-garment-info-section:last-child {
        border-bottom: none;
      }

      .enable-garment-label {
        font-weight: 600;
        color: #666;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
      }

      .enable-garment-value {
        color: #333;
        font-size: 14px;
      }

      .enable-measurements-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
      }

      .enable-measurement-item {
        background: #f5f5f5;
        padding: 8px;
        border-radius: 6px;
      }

      .enable-measurement-type {
        font-size: 11px;
        font-weight: 600;
        color: #999;
        text-transform: capitalize;
        margin-bottom: 2px;
      }

      .enable-measurement-value {
        font-size: 16px;
        font-weight: 700;
        color: #333;
      }

      .enable-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 32px;
        color: #666;
      }

      .enable-error {
        background: #fee;
        color: #c33;
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid #c33;
      }
    `;
    document.head.appendChild(styles);
  }

  // ===== FETCH GARMENT DATA FROM API =====
  async function fetchGarmentInfo(url) {
    try {
      const encodedUrl = encodeURIComponent(url);
      const apiUrl = `${GARMENT_API_BASE_URL}/get-garment?url=${encodedUrl}`;
      
      console.log('🔗 [Enable] Fetching garment from API:', apiUrl);
      
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
      console.log('✅ [Enable] Garment data received:', garmentData);
      return garmentData;
    } catch (error) {
      console.error('❌ [Enable] Error fetching garment:', error);
      throw error;
    }
  }

  // ===== DISPLAY GARMENT INFO IN MODAL =====
  function displayGarmentModal(garmentData) {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.className = 'enable-garment-modal';

    // Create modal content
    const content = document.createElement('div');
    content.className = 'enable-garment-modal-content';

    // Close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'enable-modal-close';
    closeBtn.innerHTML = '×';
    closeBtn.addEventListener('click', () => modal.remove());

    // Garment info container
    const infoDiv = document.createElement('div');
    infoDiv.className = 'enable-garment-info';

    // Title
    const title = document.createElement('h2');
    title.textContent = garmentData.name || 'Garment';
    infoDiv.appendChild(title);

    // Basic info
    const basicSection = document.createElement('div');
    basicSection.className = 'enable-garment-info-section';

    const addInfoRow = (label, value) => {
      if (!value) return;
      const row = document.createElement('div');
      row.innerHTML = `
        <div class="enable-garment-label">${label}</div>
        <div class="enable-garment-value">${value}</div>
      `;
      basicSection.appendChild(row);
    };

    addInfoRow('Brand', garmentData.brand_partners?.brand_name || 'N/A');
    addInfoRow('Category', `${garmentData.category || 'N/A'} - ${garmentData.subcategory || 'N/A'}`);
    addInfoRow('Fit Type', garmentData.fit_type || 'N/A');
    addInfoRow('Material Stretch', garmentData.material_stretch || 'N/A');
    addInfoRow('Color', garmentData.color || 'N/A');
    addInfoRow('SKU', garmentData.sku || 'N/A');
    addInfoRow('Sizes Available', garmentData.size_label || 'N/A');

    infoDiv.appendChild(basicSection);

    // Measurements section
    const measurements = garmentData.garment_measurements || [];
    if (measurements.length > 0) {
      const measSection = document.createElement('div');
      measSection.className = 'enable-garment-info-section';

      const measLabel = document.createElement('div');
      measLabel.className = 'enable-garment-label';
      measLabel.textContent = 'Measurements';
      measSection.appendChild(measLabel);

      const measGrid = document.createElement('div');
      measGrid.className = 'enable-measurements-grid';

      measurements.forEach(m => {
        const item = document.createElement('div');
        item.className = 'enable-measurement-item';
        item.innerHTML = `
          <div class="enable-measurement-type">${m.measurement_type.replace(/_/g, ' ')}</div>
          <div class="enable-measurement-value">${m.value_cm} cm</div>
        `;
        measGrid.appendChild(item);
      });

      measSection.appendChild(measGrid);
      infoDiv.appendChild(measSection);
    }

    content.appendChild(closeBtn);
    content.appendChild(infoDiv);
    modal.appendChild(content);

    // Close on overlay click
    modal.addEventListener('click', (e) => {
      if (e.target === modal) modal.remove();
    });

    document.body.appendChild(modal);
  }

  // ===== CREATE AND INJECT INFO BUTTON =====
  function createInfoButton() {
    if (document.querySelector('.enable-info-btn')) {
      console.log('✅ [Enable] Info button already exists');
      return;
    }

    console.log('🔘 [Enable] Creating info button...');
    
    const btn = document.createElement('button');
    btn.className = 'enable-info-btn';
    btn.innerHTML = 'ⓘ';
    btn.title = 'View Garment Information';

    btn.addEventListener('click', async () => {
      console.log('🔘 [Enable] Info button clicked');
      btn.disabled = true;
      btn.innerHTML = '⏳';

      try {
        const garmentData = await fetchGarmentInfo(window.location.href);
        displayGarmentModal(garmentData);
        btn.innerHTML = '✓';
        setTimeout(() => {
          btn.innerHTML = 'ⓘ';
          btn.disabled = false;
        }, 1000);
      } catch (error) {
        console.error('❌ [Enable] Error:', error);
        
        // Show error in modal
        const modal = document.createElement('div');
        modal.className = 'enable-garment-modal';
        const content = document.createElement('div');
        content.className = 'enable-garment-modal-content';
        
        const closeBtn = document.createElement('button');
        closeBtn.className = 'enable-modal-close';
        closeBtn.innerHTML = '×';
        closeBtn.addEventListener('click', () => modal.remove());
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'enable-error';
        errorDiv.innerHTML = `<strong>Error:</strong> Failed to load garment info. ${error.message}`;
        
        content.appendChild(closeBtn);
        content.appendChild(errorDiv);
        modal.appendChild(content);
        
        modal.addEventListener('click', (e) => {
          if (e.target === modal) modal.remove();
        });
        
        document.body.appendChild(modal);
        
        btn.innerHTML = '❌';
        setTimeout(() => {
          btn.innerHTML = 'ⓘ';
          btn.disabled = false;
        }, 1500);
      }
    });

    document.body.appendChild(btn);
    console.log('✅ [Enable] Info button created and added to DOM');
  }
        
        // Show error in modal
        const modal = document.createElement('div');
        modal.className = 'enable-garment-modal';
        const content = document.createElement('div');
        content.className = 'enable-garment-modal-content';
        
        const closeBtn = document.createElement('button');
        closeBtn.className = 'enable-modal-close';
        closeBtn.innerHTML = '×';
        closeBtn.addEventListener('click', () => modal.remove());
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'enable-error';
        errorDiv.innerHTML = `<strong>Error:</strong> Failed to load garment info. ${error.message}`;
        
        content.appendChild(closeBtn);
        content.appendChild(errorDiv);
        modal.appendChild(content);
        
        modal.addEventListener('click', (e) => {
          if (e.target === modal) modal.remove();
        });
        
        document.body.appendChild(modal);
        
        btn.innerHTML = '❌';
        setTimeout(() => {
          btn.innerHTML = 'ⓘ';
          btn.disabled = false;
        }, 1500);
      }
    });

    document.body.appendChild(btn);
  }

  // ===== INITIALIZE ON PAGE LOAD =====
  function initializeGarmentInfo() {
    injectStyles();
    createInfoButton();
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeGarmentInfo);
  } else {
    initializeGarmentInfo();
  }
  
  function getImagesOnPage() {
    console.log('getImagesOnPage called');
    // If the page is a direct image (jpg/png/webp/gif/svg), return that
    const imageExt = /\.(jpe?g|png|webp|gif|svg)$/i;
    if (imageExt.test(window.location.pathname)) {
      return [{
        src: window.location.href,
        width: window.innerWidth,
        height: window.innerHeight,
        type: 'direct-image'
      }];
    }

    // Filter function to identify likely garment images
    function isLikelyGarment(img, element) {
      // Size filters - garment images are usually reasonably sized
      if (img.width < 100 || img.height < 100) return false;
      if (img.width > 2000 || img.height > 2000) return false;

      // URL/alt text keywords that suggest clothing/garments
      const garmentKeywords = [
        'shirt', 'dress', 'pants', 'jeans', 'jacket', 'coat', 'sweater', 
        'hoodie', 'blouse', 'skirt', 'shorts', 'top', 'bottom', 'clothing',
        'apparel', 'fashion', 'wear', 'garment', 'outfit', 'style',
        'product', 'item', 'cloth'
      ];

      const imgSrc = img.src.toLowerCase();
      const imgAlt = (img.alt || '').toLowerCase();
      const hasGarmentKeyword = garmentKeywords.some(keyword => 
        imgSrc.includes(keyword) || imgAlt.includes(keyword)
      );

      // Class/ID detection for product images
      if (element) {
        const className = (element.className || '').toLowerCase();
        const elementId = (element.id || '').toLowerCase();
        const hasProductClass = ['product', 'item', 'clothing', 'apparel', 'garment'].some(keyword =>
          className.includes(keyword) || elementId.includes(keyword)
        );
        
        if (hasProductClass) return true;
      }

      // Exclude common non-garment images
      const excludeKeywords = ['logo', 'icon', 'banner', 'header', 'footer', 'nav', 'menu', 'ad', 'advertisement'];
      const hasExcludeKeyword = excludeKeywords.some(keyword => 
        imgSrc.includes(keyword) || imgAlt.includes(keyword)
      );

      if (hasExcludeKeyword) return false;
      
      return hasGarmentKeyword || (img.width >= 200 && img.height >= 200);
    }

    // Collect <img> elements with garment filtering
    const imgTags = Array.from(document.images)
      .map(img => ({
        src: img.src,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
        alt: img.alt,
        type: 'img',
        element: img
      }))
      .filter(img => img.src && isLikelyGarment(img, img.element));

    // Collect background images from visible elements with garment filtering
    const bgImgs = [];
    const allEls = document.querySelectorAll('*');
    allEls.forEach(el => {
      const style = window.getComputedStyle(el);
      const bg = style.getPropertyValue('background-image');
      if (bg && bg !== 'none' && bg.startsWith('url(')) {
        const url = bg.replace(/^url\(["']?/, '').replace(/["']?\)$/, '');
        // Only add if not already in imgTags and passes garment filter
        if (url && !imgTags.some(img => img.src === url) && !bgImgs.some(img => img.src === url)) {
          const rect = el.getBoundingClientRect();
          const imgData = {
            src: url,
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            type: 'background-image',
            element: el
          };
          
          if (isLikelyGarment(imgData, el)) {
            bgImgs.push(imgData);
          }
        }
      }
    });

    // Sort by size (larger images first) and limit results
    const allImages = [...imgTags, ...bgImgs]
      .sort((a, b) => (b.width * b.height) - (a.width * a.height))
      .slice(0, 12); // Limit to 12 images

    return allImages;
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    console.log('📨 Content script received message:', msg);
    if (msg && msg.type === 'GET_IMAGES_ON_PAGE') {
      const images = getImagesOnPage();
      console.log('✅ Content script found', images.length, 'garment images');
      images.forEach((img, idx) => {
        console.log(`   Image ${idx + 1}:`, {
          src: img.src.substring(0, 100) + (img.src.length > 100 ? '...' : ''),
          width: img.width,
          height: img.height,
          type: img.type,
          alt: img.alt
        });
      });
      sendResponse({ images: images });
      return true;
    }
  });
})();
