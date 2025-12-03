// content-script.js
(function() {
  // Prevent multiple injections
  if (window.enableExtractorLoaded) {
    console.log('Content script already loaded, skipping...');
    return;
  }
  window.enableExtractorLoaded = true;
  
  console.log('🔄 Fresh content script loaded on:', window.location.href);
  
  function getImagesOnPage() {
    console.log('🔍 getImagesOnPage called - starting fresh scan...');
    
    // If the page is a direct image (jpg/png/webp/gif/svg), return that
    const imageExt = /\.(jpe?g|png|webp|gif|svg)$/i;
    if (imageExt.test(window.location.pathname)) {
      console.log('📸 Direct image page detected');
      return [{
        src: window.location.href,
        width: window.innerWidth,
        height: window.innerHeight,
        type: 'direct-image'
      }];
    }

    // Enhanced filter function to identify likely garment images
    function isLikelyGarment(img, element) {
      // Size filters - garment images are usually reasonably sized
      if (img.width < 100 || img.height < 100) return false;
      if (img.width > 3000 || img.height > 3000) return false;

      // URL/alt text keywords that suggest clothing/garments
      const garmentKeywords = [
        'shirt', 'dress', 'pants', 'jeans', 'jacket', 'coat', 'sweater', 
        'hoodie', 'blouse', 'skirt', 'shorts', 'top', 'bottom', 'clothing',
        'apparel', 'fashion', 'wear', 'garment', 'outfit', 'style',
        'product', 'item', 'cloth', 'tshirt', 't-shirt', 'polo', 'cardigan',
        'blazer', 'vest', 'tank', 'pullover', 'sweatshirt', 'trouser',
        'chinos', 'leggings', 'joggers'
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
        const parentElement = element.parentElement;
        const parentClass = parentElement ? (parentElement.className || '').toLowerCase() : '';
        
        const productClasses = ['product', 'item', 'clothing', 'apparel', 'garment', 'gallery', 'thumbnail', 'hero'];
        const hasProductClass = productClasses.some(keyword =>
          className.includes(keyword) || elementId.includes(keyword) || parentClass.includes(keyword)
        );
        
        if (hasProductClass) return true;
      }

      // Exclude common non-garment images
      const excludeKeywords = ['logo', 'icon', 'banner', 'header', 'footer', 'nav', 'menu', 'ad', 'advertisement', 'avatar', 'profile'];
      const hasExcludeKeyword = excludeKeywords.some(keyword => 
        imgSrc.includes(keyword) || imgAlt.includes(keyword)
      );

      if (hasExcludeKeyword) return false;
      
      // Accept images with garment keywords or reasonably sized product images
      return hasGarmentKeyword || (img.width >= 200 && img.height >= 200);
    }

    // Collect <img> elements with garment filtering
    console.log('🔍 Scanning <img> elements...');
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

    console.log('📸 Found', imgTags.length, 'img elements');

    // Collect background images from visible elements with garment filtering
    console.log('🔍 Scanning background images...');
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

    console.log('🖼️ Found', bgImgs.length, 'background images');

    // Sort by size (larger images first) and limit results
    const allImages = [...imgTags, ...bgImgs]
      .sort((a, b) => (b.width * b.height) - (a.width * a.height))
      .slice(0, 12); // Limit to 12 images

    console.log('✅ Total filtered images:', allImages.length);
    return allImages;
  }

  // Remove any existing listeners before adding new ones
  if (chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
      console.log('📨 Content script received message:', msg);
      if (msg && msg.type === 'GET_IMAGES_ON_PAGE') {
        const images = getImagesOnPage();
        console.log('📤 Sending back', images.length, 'images:', images);
        sendResponse({ images: images });
        return true; // Keep message channel open for async response
      }
    });
  }
  
  console.log('✅ Content script setup complete');
})();
