// content-script.js
(function() {
  console.log('Content script loaded on:', window.location.href);
  
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
    console.log('Content script received message:', msg);
    if (msg && msg.type === 'GET_IMAGES_ON_PAGE') {
      const images = getImagesOnPage();
      console.log('Found images:', images.length, images);
      sendResponse({ images: images });
      return true; // Keep message channel open for async response
    }
  });
})();
