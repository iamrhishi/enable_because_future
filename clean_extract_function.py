def extract_garment_images_from_results(results):
    """Process and filter search results to extract valid garment images"""
    garment_images = []
    
    for result in results:
        try:
            img_url = result.get('image_url')
            if not img_url:
                continue
            
            # Filter out non-clothing related images
            title = result.get('title', '').lower()
            if any(keyword in title for keyword in ['clothing', 'shirt', 'dress', 'jean', 'pant', 'jacket', 'coat', 'sweater', 'blouse', 'skirt', 'fashion', 'wear', 'apparel']):
                garment_images.append({
                    'src': img_url,
                    'title': result.get('title', 'Fashion Item'),
                    'price': result.get('price'),
                    'store': result.get('store'),
                    'url': img_url  # For compatibility with existing code
                })
                
        except Exception as e:
            print(f"❌ Error processing result: {e}")
            continue
    
    print(f"🔍 Extracted {len(garment_images)} valid garment images from {len(results)} results")
    return garment_images