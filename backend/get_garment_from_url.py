from flask import Flask, request, jsonify
import requests
import base64
from bs4 import BeautifulSoup
from urllib.parse import urlparse

app = Flask(__name__)

@app.route('/api/get-garment-from-url')
def get_garment_from_url():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return jsonify({'error': 'Failed to fetch page'}), 400
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Try to find the largest image on the page (as a garment proxy)
        images = soup.find_all('img')
        max_area = 0
        garment_img_url = None
        for img in images:
            src = img.get('src')
            if not src:
                continue
            width = int(img.get('width') or 0)
            height = int(img.get('height') or 0)
            area = width * height
            if area > max_area:
                max_area = area
                garment_img_url = src
        if not garment_img_url:
            return jsonify({'error': 'No image found'}), 404
        # Handle relative URLs
        if garment_img_url.startswith('//'):
            garment_img_url = 'https:' + garment_img_url
        elif garment_img_url.startswith('/'):
            parsed = urlparse(url)
            garment_img_url = f"{parsed.scheme}://{parsed.netloc}{garment_img_url}"
        img_resp = requests.get(garment_img_url, timeout=5)
        if img_resp.status_code != 200:
            return jsonify({'error': 'Failed to fetch image'}), 400
        img_b64 = base64.b64encode(img_resp.content).decode('utf-8')
        return jsonify({'image_base64': img_b64})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
