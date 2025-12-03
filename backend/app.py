from flask import Flask, jsonify, request, Response, send_file, make_response
import mysql.connector
import requests
from requests.auth import HTTPBasicAuth
from flask_cors import CORS
import os
import io
import numpy as np
# import cv2  # Commented out temporarily due to installation issue
from io import BytesIO
from werkzeug.utils import secure_filename
import base64
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import hashlib
import uuid
import re
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from google import genai
from PIL import Image
import time
import traceback
from googleapiclient.discovery import build
from rembg import remove
# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Gemini AI (includes Nano Banana image generation capabilities)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
# Note: Using google.genai client instead of google.generativeai

# Configure Google Custom Search API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CSE_ID = os.getenv('GOOGLE_CSE_ID')

MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', 'root')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'hello_db')


db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'root',  # Add your MySQL password here if you have one
    'database': 'hello_db',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci',
    'autocommit': True
}

WARDROBE_FOLDER = "../frontend/public/images/wardrobe"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Proxy endpoint for background removal
@app.route('/api/remove-bg', methods=['POST'])
def remove_bg():
    api_url = "https://api.becausefuture.tech/bg-service/api/remove"
    api_username = 'becausefuture'  # TODO: Replace with your API username
    api_password = 'becausefuture!2025'  # TODO: Replace with your API password
    if 'file' not in request.files:
        return {'error': 'No file uploaded'}, 400
    file = request.files['file']
    files = {'file': (file.filename, file.stream, file.mimetype)}
    try:
        resp = requests.post(
            api_url,
            files=files,
            auth=(api_username, api_password),
            headers={"Accept":"image/png"},
            timeout=60
        )
        if resp.status_code == 200:
            return Response(resp.content, mimetype='image/png')
        else:
            return resp.json(), resp.status_code
    except Exception as e:
        return {'error': str(e)}, 500


@app.route('/api/remove-person-bg', methods=['POST'])
def remove_person_bg():
    try:
        # Validate API key
        if not GEMINI_API_KEY:
            print("[REMOVE-PERSON-BG][ERROR] Gemini API key not configured")
            return jsonify({
                "message": "Gemini API key not configured",
                "code": "MISSING_API_KEY",
                "statusCode": 500
            }), 500

        # Get uploaded file
        if 'image' not in request.files:
            print("[REMOVE-PERSON-BG][ERROR] No image file provided")
            return jsonify({
                "message": "No image file provided",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400

        image_file = request.files['image']
        
        # Validate file type
        if not image_file.filename:
            return jsonify({
                "message": "No filename provided",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400
        
        file_ext = image_file.filename.rsplit('.', 1)[-1].lower()
        if file_ext not in ['png', 'jpg', 'jpeg']:
            return jsonify({
                "message": "Invalid file type. Only PNG and JPEG are accepted",
                "code": "INVALID_FILE_TYPE",
                "statusCode": 400
            }), 400

        print(f"[REMOVE-PERSON-BG][FILE] Received: {image_file.filename}, type: {file_ext}")

        # Load and resize image to reduce token usage (max 1024px on longest side)
        try:
            image_file.seek(0)
            original_pil = Image.open(image_file).convert("RGB")
            
            # Resize image to reduce token consumption
            max_dimension = 1024
            if max(original_pil.size) > max_dimension:
                ratio = max_dimension / max(original_pil.size)
                new_size = tuple(int(dim * ratio) for dim in original_pil.size)
                original_pil = original_pil.resize(new_size, Image.Resampling.LANCZOS)
                print(f"[REMOVE-PERSON-BG][IMAGE] Resized to {original_pil.size} for efficiency")
            else:
                print(f"[REMOVE-PERSON-BG][IMAGE] Original size {original_pil.size}")
                
        except Exception as img_err:
            print(f"[REMOVE-PERSON-BG][ERROR] Image loading failed: {img_err}")
            return jsonify({
                "message": f"Image processing failed: {str(img_err)}",
                "code": "IMAGE_ERROR",
                "statusCode": 400
            }), 400

        # Convert PIL image to bytes
        def pil_to_bytes(img: Image.Image, fmt="PNG"):
            buf = BytesIO()
            img.save(buf, format=fmt, optimize=True)
            buf.seek(0)
            return buf.read()

        image_bytes = pil_to_bytes(original_pil, fmt="PNG")
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')

        # Initialize Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        model_name = "gemini-2.5-flash-image"

        # Concise, token-efficient prompt
        removal_prompt = (
            "Remove background from this image. Keep ONLY the person with transparent background.\n\n"
            "REQUIREMENTS:\n"
            "1. PRESERVE: Exact person (face, body, pose, clothing, accessories) - NO changes\n"
            "2. REMOVE: All background (walls, floor, objects) - 100% transparent (alpha=0)\n"
            "3. EDGES: Smooth, clean edges with no halos; preserve hair details\n"
            "4. OUTPUT: PNG with transparent RGBA background, full-body visible\n\n"
            "Do NOT alter person appearance, pose, or crop image. This is for 2D avatar creation."
        )

        print(f"[REMOVE-PERSON-BG][GEMINI] Using model {model_name}, prompt: {len(removal_prompt)} chars")

        # Call Gemini API with retry logic
        max_retries = 3
        backoff = 1.0
        generation_response = None

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[REMOVE-PERSON-BG][GEMINI] Attempt {attempt}")
                
                contents = [
                    {"parts": [{"text": removal_prompt}]},
                    {"parts": [{"inline_data": {"mime_type": "image/png", "data": image_b64}}]}
                ]
                
                generation_response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                
                print("[REMOVE-PERSON-BG][GEMINI] Response received")
                break
                
            except Exception as ex:
                print(f"[REMOVE-PERSON-BG][ERROR] Attempt {attempt} failed: {ex}")
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    print(f"[REMOVE-PERSON-BG][ERROR] All retries failed")
                    return jsonify({
                        "message": f"Background removal failed: {str(ex)}",
                        "code": "GENERATION_ERROR",
                        "statusCode": 500
                    }), 500

        if generation_response is None:
            return jsonify({
                "message": "Background removal failed - no response from AI",
                "code": "GENERATION_ERROR",
                "statusCode": 500
            }), 500

        # Extract image data from response
        parts = getattr(generation_response, "parts", None)
        if parts:
            for i, part in enumerate(parts):
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    image_data = inline.data
                    mime_type = getattr(inline, "mime_type", "image/png")
                    
                    print(f"[REMOVE-PERSON-BG][GEMINI-RAW] Received image, size={len(image_data)} bytes")
                    
                    # POST-PROCESS: Remove checkered/white background and create true transparency
                    try:
                        print("[REMOVE-PERSON-BG][POST-PROCESS] Starting background removal...")
                        
                        # Load image from bytes
                        result_image = Image.open(BytesIO(image_data))
                        
                        # Convert to RGBA if not already
                        if result_image.mode != 'RGBA':
                            result_image = result_image.convert('RGBA')
                            print(f"[REMOVE-PERSON-BG][POST-PROCESS] Converted to RGBA mode")
                        
                        # Convert to numpy array for processing
                        data = np.array(result_image)
                        
                        # Extract RGBA channels
                        r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
                        
                        # Create masks for background removal
                        # 1. White/very light pixels (R, G, B all > 240)
                        white_mask = (r > 240) & (g > 240) & (b > 240)
                        
                        # 2. Light gray pixels (checkered pattern - RGB between 200-240)
                        gray_mask = (r > 200) & (r < 240) & (g > 200) & (g < 240) & (b > 200) & (b < 240)
                        
                        # 3. Very light pixels (RGB > 235) - catch near-white
                        near_white_mask = (r > 235) & (g > 235) & (b > 235)
                        
                        # Combine all background masks
                        background_mask = white_mask | gray_mask | near_white_mask
                        
                        # Set background pixels to fully transparent
                        data[background_mask, 3] = 0
                        
                        # Advanced: Remove pixels similar to detected background color
                        if np.any(background_mask):
                            bg_pixels = data[background_mask]
                            if len(bg_pixels) > 100:  # Need sufficient samples
                                # Calculate average background color
                                avg_r = float(np.mean(bg_pixels[:,0]))
                                avg_g = float(np.mean(bg_pixels[:,1]))
                                avg_b = float(np.mean(bg_pixels[:,2]))
                                
                                print(f"[REMOVE-PERSON-BG][POST-PROCESS] Detected background color: RGB({avg_r:.0f}, {avg_g:.0f}, {avg_b:.0f})")
                                
                                # Find pixels within 40 units of background color (Euclidean distance)
                                color_diff = np.sqrt(
                                    (r.astype(float) - avg_r)**2 + 
                                    (g.astype(float) - avg_g)**2 + 
                                    (b.astype(float) - avg_b)**2
                                )
                                similar_bg_mask = color_diff < 40
                                data[similar_bg_mask, 3] = 0
                                
                                # Soften edges: Make near-background pixels semi-transparent
                                edge_mask = (color_diff >= 40) & (color_diff < 80)
                                if np.any(edge_mask):
                                    # Gradually fade alpha based on distance from background
                                    alpha_fade = ((color_diff[edge_mask] - 40) / 40 * 255).astype(np.uint8)
                                    data[edge_mask, 3] = np.minimum(data[edge_mask, 3], alpha_fade)
                        
                        # Count transparent pixels for verification
                        transparent_count = np.sum(data[:,:,3] == 0)
                        total_pixels = data.shape[0] * data.shape[1]
                        transparency_percent = (transparent_count / total_pixels) * 100
                        
                        print(f"[REMOVE-PERSON-BG][POST-PROCESS] Transparency: {transparency_percent:.1f}% ({transparent_count}/{total_pixels} pixels)")
                        
                        # Convert back to PIL Image
                        result_image = Image.fromarray(data, 'RGBA')
                        
                        # Save to bytes with PNG format (preserves transparency)
                        output_buffer = BytesIO()
                        result_image.save(output_buffer, format='PNG', optimize=True)
                        output_buffer.seek(0)
                        processed_image_data = output_buffer.read()
                        
                        print(f"[REMOVE-PERSON-BG][POST-PROCESS] ✅ Complete! Output size: {len(processed_image_data)} bytes")
                        
                        # Use processed image
                        image_data = processed_image_data
                        
                    except Exception as post_error:
                        print(f"[REMOVE-PERSON-BG][POST-PROCESS] ⚠️ Warning: Post-processing failed: {post_error}")
                        print(f"[REMOVE-PERSON-BG][POST-PROCESS] Using original Gemini output without post-processing")
                        # Continue with original image_data
                    
                    print(f"[REMOVE-PERSON-BG][SUCCESS] Returning image, size={len(image_data)} bytes")
                    
                    resp = make_response(send_file(
                        BytesIO(image_data),
                        mimetype='image/png',
                        as_attachment=False,
                        download_name='person_no_bg.png'
                    ))
                    resp.headers['X-AI-Model'] = model_name
                    resp.headers['X-Processing-Method'] = 'gemini-with-transparency-postprocess'
                    resp.status_code = 200
                    return resp

        # Check candidates structure
        candidates = getattr(generation_response, "candidates", None)
        if candidates:
            for ci, cand in enumerate(candidates):
                maybe_parts = getattr(cand, "parts", None) or getattr(cand, "output", None)
                if maybe_parts:
                    for part in maybe_parts:
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            image_data = inline.data
                            mime_type = getattr(inline, "mime_type", "image/png")
                            
                            print(f"[REMOVE-PERSON-BG][GEMINI-RAW] Received image from candidates, size={len(image_data)} bytes")
                            
                            # POST-PROCESS: Remove checkered/white background and create true transparency
                            try:
                                print("[REMOVE-PERSON-BG][POST-PROCESS] Starting background removal...")
                                
                                # Load image from bytes
                                result_image = Image.open(BytesIO(image_data))
                                
                                # Convert to RGBA if not already
                                if result_image.mode != 'RGBA':
                                    result_image = result_image.convert('RGBA')
                                    print(f"[REMOVE-PERSON-BG][POST-PROCESS] Converted to RGBA mode")
                                
                                # Convert to numpy array for processing
                                data = np.array(result_image)
                                
                                # Extract RGBA channels
                                r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
                                
                                # Create masks for background removal
                                # 1. White/very light pixels (R, G, B all > 240)
                                white_mask = (r > 240) & (g > 240) & (b > 240)
                                
                                # 2. Light gray pixels (checkered pattern - RGB between 200-240)
                                gray_mask = (r > 200) & (r < 240) & (g > 200) & (g < 240) & (b > 200) & (b < 240)
                                
                                # 3. Very light pixels (RGB > 235) - catch near-white
                                near_white_mask = (r > 235) & (g > 235) & (b > 235)
                                
                                # Combine all background masks
                                background_mask = white_mask | gray_mask | near_white_mask
                                
                                # Set background pixels to fully transparent
                                data[background_mask, 3] = 0
                                
                                # Advanced: Remove pixels similar to detected background color
                                if np.any(background_mask):
                                    bg_pixels = data[background_mask]
                                    if len(bg_pixels) > 100:  # Need sufficient samples
                                        # Calculate average background color
                                        avg_r = float(np.mean(bg_pixels[:,0]))
                                        avg_g = float(np.mean(bg_pixels[:,1]))
                                        avg_b = float(np.mean(bg_pixels[:,2]))
                                        
                                        print(f"[REMOVE-PERSON-BG][POST-PROCESS] Detected background color: RGB({avg_r:.0f}, {avg_g:.0f}, {avg_b:.0f})")
                                        
                                        # Find pixels within 40 units of background color (Euclidean distance)
                                        color_diff = np.sqrt(
                                            (r.astype(float) - avg_r)**2 + 
                                            (g.astype(float) - avg_g)**2 + 
                                            (b.astype(float) - avg_b)**2
                                        )
                                        similar_bg_mask = color_diff < 40
                                        data[similar_bg_mask, 3] = 0
                                        
                                        # Soften edges: Make near-background pixels semi-transparent
                                        edge_mask = (color_diff >= 40) & (color_diff < 80)
                                        if np.any(edge_mask):
                                            # Gradually fade alpha based on distance from background
                                            alpha_fade = ((color_diff[edge_mask] - 40) / 40 * 255).astype(np.uint8)
                                            data[edge_mask, 3] = np.minimum(data[edge_mask, 3], alpha_fade)
                                
                                # Count transparent pixels for verification
                                transparent_count = np.sum(data[:,:,3] == 0)
                                total_pixels = data.shape[0] * data.shape[1]
                                transparency_percent = (transparent_count / total_pixels) * 100
                                
                                print(f"[REMOVE-PERSON-BG][POST-PROCESS] Transparency: {transparency_percent:.1f}% ({transparent_count}/{total_pixels} pixels)")
                                
                                # Convert back to PIL Image
                                result_image = Image.fromarray(data, 'RGBA')
                                
                                # Save to bytes with PNG format (preserves transparency)
                                output_buffer = BytesIO()
                                result_image.save(output_buffer, format='PNG', optimize=True)
                                output_buffer.seek(0)
                                processed_image_data = output_buffer.read()
                                
                                print(f"[REMOVE-PERSON-BG][POST-PROCESS] ✅ Complete! Output size: {len(processed_image_data)} bytes")
                                
                                # Use processed image
                                image_data = processed_image_data
                                
                            except Exception as post_error:
                                print(f"[REMOVE-PERSON-BG][POST-PROCESS] ⚠️ Warning: Post-processing failed: {post_error}")
                                print(f"[REMOVE-PERSON-BG][POST-PROCESS] Using original Gemini output without post-processing")
                                # Continue with original image_data
                            
                            resp = make_response(send_file(
                                BytesIO(image_data),
                                mimetype='image/png',
                                as_attachment=False,
                                download_name='person_no_bg.png'
                            ))
                            resp.headers['X-AI-Model'] = model_name
                            resp.headers['X-Processing-Method'] = 'gemini-with-transparency-postprocess'
                            resp.status_code = 200
                            return resp

        # No image data found
        print("[REMOVE-PERSON-BG][ERROR] No image data in response")
        return jsonify({
            "message": "Background removal failed - no image generated",
            "code": "NO_IMAGE_DATA",
            "statusCode": 500
        }), 500

    except ValueError as ve:
        print(f"[REMOVE-PERSON-BG][ERROR] ValueError: {ve}")
        return jsonify({
            "message": "Request was blocked or returned no valid content",
            "code": "CONTENT_BLOCKED",
            "statusCode": 400,
            "details": str(ve)
        }), 400

    except Exception as e:
        print(f"[REMOVE-PERSON-BG][ERROR] Unexpected error: {e}")
        print(traceback.format_exc())
        return jsonify({
            "message": f"Background removal failed: {str(e)}",
            "code": "SERVER_ERROR",
            "statusCode": 500
        }), 500


@app.route('/api/remove-bg-rembg', methods=['POST'])
def remove_bg_rembg():
    """
    Remove background from image using rembg library
    Input: Image file (PNG, JPG, JPEG, WEBP)
    Output: PNG image with transparent background
    """
    print("[REMOVE-BG-REMBG][START] API call initiated")
    try:
        # Get uploaded file
        if 'image' not in request.files:
            print("[REMOVE-BG-REMBG][ERROR] No image file provided")
            return jsonify({
                "message": "No image file provided",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400

        image_file = request.files['image']
        
        # Validate file type
        if not image_file.filename:
            return jsonify({
                "message": "No filename provided",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400
        
        file_ext = image_file.filename.rsplit('.', 1)[-1].lower()
        if file_ext not in ['png', 'jpg', 'jpeg', 'webp']:
            return jsonify({
                "message": "Invalid file type. Only PNG, JPG, JPEG, and WEBP are accepted",
                "code": "INVALID_FILE_TYPE",
                "statusCode": 400
            }), 400

        print(f"[REMOVE-BG-REMBG][FILE] Received file: {image_file.filename}, type: {file_ext}")

        # Load image using PIL - preserve maximum quality
        try:
            image_file.seek(0)
            input_image = Image.open(image_file)
            original_size = input_image.size
            original_mode = input_image.mode
            print(f"[REMOVE-BG-REMBG][IMAGE] Loaded size={original_size}, mode={original_mode}")
            
            # Convert to RGB if needed (rembg works best with RGB)
            # But preserve original mode info for quality decisions
            if input_image.mode not in ('RGB', 'RGBA'):
                input_image = input_image.convert('RGB')
                print(f"[REMOVE-BG-REMBG][IMAGE] Converted {original_mode} to RGB for processing")
                
        except Exception as img_err:
            print(f"[REMOVE-BG-REMBG][ERROR] Image loading failed: {img_err}")
            return jsonify({
                "message": f"Image processing failed: {str(img_err)}",
                "code": "IMAGE_ERROR",
                "statusCode": 400
            }), 400

        # Remove background using rembg with HIGH QUALITY settings
        try:
            print("[REMOVE-BG-REMBG][PROCESSING] Removing background with high-quality settings...")
            
            # Use rembg with quality-focused parameters
            # alpha_matting=True provides better edge quality
            # alpha_matting_foreground_threshold and background_threshold fine-tune the mask
            output_image = remove(
                input_image,
                alpha_matting=True,              # Enable alpha matting for smoother edges
                alpha_matting_foreground_threshold=240,  # Fine-tune foreground detection
                alpha_matting_background_threshold=10,   # Fine-tune background detection
                alpha_matting_erode_size=10,     # Erosion size for matting
                post_process_mask=True           # Enable post-processing for cleaner results
            )
            
            print(f"[REMOVE-BG-REMBG][PROCESSING] Background removed, output size={output_image.size}, mode={output_image.mode}")
            
        except ImportError:
            print("[REMOVE-BG-REMBG][ERROR] rembg library not installed")
            return jsonify({
                "message": "Background removal library not installed. Please install: pip install rembg",
                "code": "LIBRARY_MISSING",
                "statusCode": 500
            }), 500
        except TypeError as type_err:
            # If alpha_matting parameters not supported, fall back to basic mode
            print(f"[REMOVE-BG-REMBG][WARNING] Advanced parameters not supported, using basic mode: {type_err}")
            try:
                output_image = remove(input_image)
                print(f"[REMOVE-BG-REMBG][PROCESSING] Background removed (basic mode), output size={output_image.size}")
            except Exception as fallback_err:
                print(f"[REMOVE-BG-REMBG][ERROR] Background removal failed: {fallback_err}")
                return jsonify({
                    "message": f"Background removal failed: {str(fallback_err)}",
                    "code": "PROCESSING_ERROR",
                    "statusCode": 500
                }), 500
        except Exception as rembg_err:
            print(f"[REMOVE-BG-REMBG][ERROR] Background removal failed: {rembg_err}")
            return jsonify({
                "message": f"Background removal failed: {str(rembg_err)}",
                "code": "PROCESSING_ERROR",
                "statusCode": 500
            }), 500

        # POST-PROCESSING: Enhance edge quality and remove artifacts
        try:
            print("[REMOVE-BG-REMBG][POST-PROCESS] Enhancing output quality...")
            
            # Ensure output is RGBA
            if output_image.mode != 'RGBA':
                output_image = output_image.convert('RGBA')
            
            # Convert to numpy for advanced processing
            img_array = np.array(output_image)
            
            # Extract alpha channel
            alpha = img_array[:, :, 3]
            
            # Clean up semi-transparent pixels for sharper edges
            # Pixels with very low alpha (< 10) should be fully transparent
            alpha[alpha < 10] = 0
            
            # Pixels with very high alpha (> 245) should be fully opaque
            alpha[alpha > 245] = 255
            
            # Update alpha channel
            img_array[:, :, 3] = alpha
            
            # Convert back to PIL Image
            output_image = Image.fromarray(img_array, 'RGBA')
            
            # Calculate transparency statistics
            transparent_pixels = np.sum(alpha == 0)
            total_pixels = alpha.size
            transparency_percent = (transparent_pixels / total_pixels) * 100
            
            print(f"[REMOVE-BG-REMBG][POST-PROCESS] Enhanced! Transparency: {transparency_percent:.1f}%")
            
        except Exception as post_err:
            print(f"[REMOVE-BG-REMBG][POST-PROCESS] Warning: Post-processing failed, using original output: {post_err}")
            # Continue with original rembg output

        # Convert to bytes for response with MAXIMUM QUALITY settings
        output_buffer = BytesIO()
        output_image.save(
            output_buffer, 
            format='PNG',
            compress_level=6,  # PNG compression (0-9, 6 is good balance of quality/size)
            optimize=False     # Disable optimize to prevent quality loss
        )
        output_buffer.seek(0)
        image_data = output_buffer.read()
        
        print(f"[REMOVE-BG-REMBG][SUCCESS] Returning image, size={len(image_data)} bytes")
        
        # Return PNG image with transparency
        resp = make_response(send_file(
            BytesIO(image_data),
            mimetype='image/png',
            as_attachment=False,
            download_name='no_bg.png'
        ))
        resp.headers['X-Processing-Method'] = 'rembg'
        resp.headers['X-Output-Format'] = 'PNG'
        resp.status_code = 200
        return resp

    except Exception as e:
        print(f"[REMOVE-BG-REMBG][ERROR] Unexpected error: {e}")
        print(traceback.format_exc())
        return jsonify({
            "message": f"Background removal failed: {str(e)}",
            "code": "SERVER_ERROR",
            "statusCode": 500
        }), 500


@app.route('/api/proxy-image', methods=['GET'])
def proxy_image():
    """Proxy endpoint to fetch external images and avoid CORS issues"""
    try:
        image_url = request.args.get('url')
        
        if not image_url:
            return {'error': 'No image URL provided'}, 400
        
        print(f"🌐 Proxying image request for: {image_url}")
        
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Fetch the external image
        response = requests.get(image_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Get the content type from the response
        content_type = response.headers.get('content-type', 'image/jpeg')
        
        print(f"✅ Successfully proxied image, content-type: {content_type}, size: {len(response.content)} bytes")
        
        # Return the image with proper CORS headers
        return Response(
            response.content,
            mimetype=content_type,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Cache-Control': 'public, max-age=3600'  # Cache for 1 hour
            }
        )
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch image: {str(e)}")
        return {'error': f'Failed to fetch image: {str(e)}'}, 500
    except Exception as e:
        print(f"❌ Proxy error: {str(e)}")
        return {'error': f'Proxy error: {str(e)}'}, 500


# Proxy endpoint for remove.bg (temporarily disabled due to cv2 issues)
# @app.route('/api/remove-bg-alt', methods=['POST'])
def remove_bg_alt_disabled():
    api_url = 'https://api.remove.bg/v1.0/removebg'
    api_key = 'NmxgViaSgd1K2ahiJzqdeQzK'
    if 'file' not in request.files:
        return {'error': 'No file uploaded'}, 400
    file = request.files['file']
    files = {'image_file': (file.filename, file.stream, file.mimetype)}
    data = {'size': 'auto'}
    headers = {'X-Api-Key': api_key}
    try:
        resp = requests.post(api_url, files=files, data=data, headers=headers, timeout=60)
        if resp.status_code == requests.codes.ok:
            # Post-process: crop to main object (non-transparent area)
            image_bytes = resp.content
            image_array = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(image_array, cv2.IMREAD_UNCHANGED)
            if img is not None and img.shape[2] == 4:
                # Find non-transparent pixels
                alpha = img[:,:,3]
                coords = cv2.findNonZero((alpha > 0).astype(np.uint8))
                if coords is not None:
                    x, y, w, h = cv2.boundingRect(coords)
                    cropped = img[y:y+h, x:x+w]
                    # Encode back to PNG
                    _, buf = cv2.imencode('.png', cropped)
                    return Response(buf.tobytes(), mimetype='image/png')
            # Fallback: return original if crop fails
            return Response(image_bytes, mimetype='image/png')
        else:
            return {'error': resp.text}, resp.status_code
    except Exception as e:
        return {'error': str(e)}, 500
    

# --- Try-On API Proxy ---
@app.route('/api/tryon', methods=['POST'])
def tryon():

    api_username = 'becausefuture'  
    api_password = 'becausefuture!2025' 

    try:
        # Get files and form data
        person_image = request.files.get('person_image')
        cloth_image = request.files.get('cloth_image')
        cloth_type = request.form.get('cloth_type')
        num_inference_steps = request.form.get('num_inference_steps')

        if not person_image or not cloth_image or not cloth_type:
            return jsonify({"message": "Missing required fields", "code": "INVALID_INPUT", "statusCode": 400}), 400

        files = {
            'person_image': (person_image.filename, person_image.stream, person_image.mimetype),
            'cloth_image': (cloth_image.filename, cloth_image.stream, cloth_image.mimetype)
        }

        data = {'cloth_type': cloth_type}
        
        if num_inference_steps:
            data['num_inference_steps'] = num_inference_steps        
        
        print(data)

        # Forward to the actual try-on API (replace URL and auth as needed)
        api_url = 'https://api.becausefuture.tech/mixer-service/tryon'
        headers = {"Accept":"image/png"}
        
        resp = requests.post(api_url, files=files, auth=(api_username, api_password), data=data, headers=headers, timeout=120)

        if resp.status_code == 200 and resp.headers.get('Content-Type', '').startswith('image/'):
            return send_file(BytesIO(resp.content), mimetype=resp.headers['Content-Type'])
        else:
            print(f"[TRYON][ERROR] Try-on API error: {resp.text}")
                # Try to return JSON if possible, else return raw text
            try:
                return jsonify(resp.json()), resp.status_code
            except Exception:
                return Response(resp.text, status=resp.status_code, mimetype='text/plain')

    except Exception as e:
        return jsonify({"message": str(e), "code": "SERVER_ERROR", "statusCode": 500}), 500

@app.route('/api/tryon-gemini', methods=['POST'])
def tryon_gemini():
    """
    Virtual try-on API using Gemini 2.5 Flash Image (Nano Banana) for direct image generation
    
    ENHANCED: Now supports multiple images of the SAME garment for improved accuracy
    
    Input formats:
    1. Single image (legacy): avatar_image, garment_image, garment_type
    2. Multiple views: avatar_image, garment_image_1, garment_image_2, garment_image_3, ..., garment_type
    
    Multiple images allow the AI to see front, back, side, and detail views for better accuracy.
    """
    print("[TRYON-GEMINI][START] API call initiated")
    try:
        print(f"[TRYON-GEMINI][REQUEST] Content-Type: {request.content_type}")
        print(f"[TRYON-GEMINI][REQUEST] Files: {list(request.files.keys())}")
        print(f"[TRYON-GEMINI][REQUEST] Form data: {dict(request.form)}")

        if not GEMINI_API_KEY:
            print("[TRYON-GEMINI][ERROR] Gemini API key not configured")
            return jsonify({
                "message": "Gemini API key not configured",
                "code": "MISSING_API_KEY",
                "statusCode": 500
            }), 500

        print(f"[TRYON-GEMINI][CONFIG] Gemini API key configured: {GEMINI_API_KEY[:10]}...")

        avatar_file = request.files.get('avatar_image')
        if not avatar_file:
            print("[TRYON-GEMINI][ERROR] Missing avatar_image")
            return jsonify({
                "message": "Missing required file: avatar_image",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400

        # NEW: Support multiple images of the SAME garment for better accuracy
        garment_files = []
        
        # Try numbered format first (garment_image_1, garment_image_2, ...)
        idx = 1
        while True:
            garment_file = request.files.get(f'garment_image_{idx}')
            if garment_file:
                garment_files.append(garment_file)
                print(f"[TRYON-GEMINI][FILES] Found garment_image_{idx}: {garment_file.filename}")
                idx += 1
            else:
                break
        
        # Fallback to single garment_image
        if not garment_files:
            garment_file = request.files.get('garment_image')
            if garment_file:
                garment_files.append(garment_file)
                print(f"[TRYON-GEMINI][FILES] Found single garment_image: {garment_file.filename}")
        
        if not garment_files:
            print("[TRYON-GEMINI][ERROR] No garment images provided")
            return jsonify({
                "message": "Missing required file: garment_image or garment_image_1, garment_image_2, etc.",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400

        print(f"[TRYON-GEMINI][FILES] Avatar: {avatar_file.filename}, Garment images: {len(garment_files)}")

        garment_type = request.form.get('garment_type', 'top')
        style_prompt = request.form.get('style_prompt', 'realistic virtual try-on')

        # Load and normalize images
        try:
            avatar_file.seek(0)
            avatar_pil = Image.open(avatar_file).convert("RGB")
            print(f"[TRYON-GEMINI][IMAGES] Avatar loaded size={avatar_pil.size}, mode={avatar_pil.mode}")

            # Load all garment images
            garment_pils = []
            for idx, garment_file in enumerate(garment_files):
                garment_file.seek(0)
                garment_pil = Image.open(garment_file).convert("RGBA")  # keep alpha if garment has transparency
                garment_pils.append(garment_pil)
                print(f"[TRYON-GEMINI][IMAGES] Garment image {idx+1} loaded size={garment_pil.size}, mode={garment_pil.mode}")
        except Exception as img_err:
            print(f"[TRYON-GEMINI][ERROR] Image processing failed: {img_err}")
            return jsonify({
                "message": f"Image processing failed: {str(img_err)}",
                "code": "IMAGE_ERROR",
                "statusCode": 400
            }), 400

        # Convert PIL images to bytes in memory (PNG recommended to preserve alpha)
        def pil_to_bytes(img: Image.Image, fmt="PNG"):
            buf = BytesIO()
            img.save(buf, format=fmt)
            buf.seek(0)
            return buf.read()

        avatar_bytes = pil_to_bytes(avatar_pil, fmt="PNG")
        avatar_b64 = base64.b64encode(avatar_bytes).decode('utf-8')
        
        # Convert all garment images to base64
        garment_b64_list = []
        for garment_pil in garment_pils:
            garment_bytes = pil_to_bytes(garment_pil, fmt="PNG")
            garment_b64 = base64.b64encode(garment_bytes).decode('utf-8')
            garment_b64_list.append(garment_b64)

        # Use genai.Client properly and call the image model name 'gemini-2.5-flash-image'
        client = genai.Client(api_key=GEMINI_API_KEY)
        model_name = "gemini-2.5-flash-image"

        # Prepare prompt - Enhanced for detail preservation and multiple views
        num_garment_images = len(garment_b64_list)
        
        if num_garment_images > 1:
            reference_context = (
                f"📷 REFERENCE IMAGES PROVIDED: {num_garment_images} images of the SAME garment showing different views.\n"
                f"Use ALL {num_garment_images} reference images to:\n"
                f"- Understand the complete 3D structure from all angles (front, back, side views)\n"
                f"- Capture design details visible only in specific views (back pockets, side seams, hood details, etc.)\n"
                f"- Ensure accurate color by cross-referencing multiple views\n"
                f"- Identify fabric texture, material properties, and construction details\n"
                f"- Understand how the garment drapes and fits in reality\n\n"
            )
        else:
            reference_context = ""
        
        generation_prompt = (
            f"🚨 CRITICAL INSTRUCTION: This is a VIRTUAL TRY-ON task. You MUST keep the person from the FIRST image (avatar) 100% unchanged.\n"
            f"Your ONLY job is to add the garment onto this existing person. DO NOT create a new person.\n\n"
            
            f"📸 IMAGE ORDER:\n"
            f"- Image 1: AVATAR (the person to dress - keep this person exactly as-is)\n"
            f"- Image{'s' if num_garment_images > 1 else ''} {', '.join([str(i) for i in range(2, num_garment_images + 2)])}: GARMENT reference image{'s' if num_garment_images > 1 else ''} (extract garment design only)\n\n"
            
            f"{reference_context}"
            
            f"⛔ ABSOLUTE PROHIBITIONS - NEVER DO THESE:\n"
            f"1. DO NOT replace the avatar person with a different person\n"
            f"2. DO NOT use the person/model from the garment reference images\n"
            f"3. DO NOT change the avatar's face, body, pose, or appearance in ANY way\n"
            f"4. DO NOT change the background or lighting from the avatar image\n"
            f"5. DO NOT create a composite of the avatar and garment model\n\n"
            
            f"✅ WHAT YOU MUST DO:\n\n"
            f"1. AVATAR PRESERVATION (100% UNCHANGED):\n"
            f"Keep these EXACTLY as shown in the AVATAR image (image 1):\n"
            f"- EXACT same face, eyes, nose, mouth, facial expression\n"
            f"- EXACT same hair style, color, and position\n"
            f"- EXACT same skin tone and complexion\n"
            f"- EXACT same body pose, hand position, arm position\n"
            f"- EXACT same body proportions and build\n"
            f"- EXACT same background, floor, walls, environment\n"
            f"- EXACT same lighting direction, color, and intensity\n"
            f"- EXACT same camera angle and perspective\n\n"
            
            f"2. GARMENT EXTRACTION (from reference images):\n"
            f"{'Analyze ALL garment reference images to extract: ' if num_garment_images > 1 else 'From the garment reference image, extract only: '}\n"
            f"Extract ONLY the {garment_type} design - ignore the person wearing it.\n"
        )

        # Add specific requirements based on garment type
        # This logic is excellent and has been preserved.
        if garment_type.lower() in ['top', 'shirt', 'blouse', 'jacket', 'sweater', 'hoodie', 't-shirt', 'tank top']:
            generation_prompt += (
                f"- NECK STYLING: Preserve exact neckline (round/V-neck/collar/turtleneck).\n"
                f"- SLEEVE DETAILS: Maintain exact sleeve length (short/long/3-quarter) and style.\n"
                f"- COLLAR DETAILS: Keep exact collar type, shape, and positioning.\n"
                f"- BUTTON/ZIPPER DETAILS: Preserve all buttons, zippers, and fasteners in exact positions.\n"
                f"- POCKET DETAILS: Maintain all pockets, flaps, and positioning.\n"
                f"- PATTERN/PRINT: Keep exact colors, patterns, logos, and graphic designs.\n"
                f"- FABRIC TEXTURE: Preserve material appearance (cotton/denim/silk/knit texture).\n"
                f"- HEM DETAILS: Maintain exact bottom hemline and any decorative elements.\n"
            )
        elif garment_type.lower() in ['pants', 'jeans', 'shorts', 'skirt', 'dress', 'trousers']:
            generation_prompt += (
                f"- WAISTLINE: Preserve exact waist height (high/low/mid-rise) and waistband details.\n"
                f"- LEG SHAPE: Maintain exact fit style (skinny/straight/wide-leg/bootcut).\n"
                f"- LENGTH: Keep exact garment length (ankle/cropped/full-length/knee-length).\n"
                f"- POCKET DETAILS: Preserve all pockets, stitching, and positioning.\n"
                f"- SEAM DETAILS: Maintain all visible seams, side stripes, and decorative stitching.\n"
                f"- BUTTON/ZIPPER: Keep exact fly style, button placement, and closure details.\n"
                f"- PATTERN/PRINT: Preserve exact colors, patterns, distressing, or fading.\n"
                f"- FABRIC TEXTURE: Maintain material appearance (denim/cotton/leather texture).\n"
                f"- HEM DETAILS: Keep exact bottom hem style (cuffed/raw/finished).\n"
                f"- BELT LOOPS: Preserve belt loops, belt details, or waistband styling.\n"
            )
        else:
            # Fallback for generic garments
            generation_prompt += (
                f"- DESIGN DETAILS: Preserve ALL design elements, embellishments, and features.\n"
                f"- COLOR/PATTERN: Keep exact colors, patterns, prints, and graphic elements.\n"
                f"- FABRIC TEXTURE: Maintain exact material appearance and texture.\n"
                f"- CLOSURE DETAILS: Preserve all buttons, zippers, ties, or fastening methods.\n"
            )

        generation_prompt += (
            f"\n3. GARMENT ADAPTATION (Apply to extracted garment):\n"
            f"Take the extracted {garment_type} design and adapt it to fit the AVATAR's body:\n"
            f"- **DRAPING:** Warp the garment to fit the avatar's body contours and pose\n"
            f"- **WRINKLES:** Add natural wrinkles based on avatar's pose and fabric type\n"
            f"- **SHADOWS:** Apply shadows that match the avatar's lighting\n"
            f"- **OCCLUSION:** Layer garment behind avatar's hands/arms if they're in front\n"
            f"- **STYLING:** If garment shows styling (rolled sleeves, open collar), apply to garment on avatar\n\n"
            
            f"🎯 FINAL OUTPUT SPECIFICATION:\n"
            f"You MUST generate an image that is:\n"
            f"✓ The EXACT avatar person (image 1) - same face, same body, same pose, same background\n"
            f"✓ With the {garment_type} design (from garment images) now fitted onto them\n"
            f"✓ The garment looks realistically worn, not pasted on\n\n"
            
            f"❌ YOUR OUTPUT MUST NOT BE:\n"
            f"✗ A different person\n"
            f"✗ The model from the garment reference images\n"
            f"✗ A blend/composite of avatar and garment model\n"
            f"✗ A changed/modified version of the avatar\n\n"
            
            f"🔴 FINAL REMINDER: Use the avatar person from image 1. Extract only the garment design from the other images. "
            f"DO NOT replace the avatar with anyone else."
        )

        print(f"[TRYON-GEMINI][GEMINI] Using model {model_name}; prompt length={len(generation_prompt)}")
        print(f"[TRYON-GEMINI][GEMINI] Processing {num_garment_images} garment reference image(s)")

        # Call the API with retry logic
        max_retries = 3
        backoff = 1.0
        last_exc = None
        generation_response = None

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[TRYON-GEMINI][GEMINI] generate_content attempt {attempt}")
                
                # Format content properly for google.genai API - include ALL garment images
                contents = [
                    {"parts": [{"text": generation_prompt}]},
                    {"parts": [{"inline_data": {"mime_type": "image/png", "data": avatar_b64}}]}
                ]
                
                # Add all garment reference images
                for idx, garment_b64 in enumerate(garment_b64_list):
                    contents.append({"parts": [{"inline_data": {"mime_type": "image/png", "data": garment_b64}}]})
                    print(f"[TRYON-GEMINI][GEMINI] Added garment reference image {idx+1} to contents")
                
                print(f"[TRYON-GEMINI][GEMINI] Sending {len(contents)} total items to model (1 avatar + {num_garment_images} garment images)")
                
                generation_response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    # optionally add other kwargs like temperature, max_output_tokens if supported
                )
                print("[TRYON-GEMINI][GEMINI] generation_response received")
                break
            except Exception as ex:
                last_exc = ex
                print(f"[TRYON-GEMINI][ERROR] generation attempt {attempt} failed: {ex}")
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    print(f"[TRYON-GEMINI][ERROR] all retries failed")
                    print(traceback.format_exc())

        if generation_response is None:
            return jsonify({
                "message": f"Gemini generation failed: {str(last_exc)}",
                "code": "GENERATION_ERROR",
                "statusCode": 500
            }), 500

        print(f"[TRYON-GEMINI][DEBUG] Response dir: {dir(generation_response)}")

        # Some SDKs return .parts, others return .candidates[].output or similar.
        # Try to guard against several common shapes.

        # 1) Check parts (inline image data)
        parts = getattr(generation_response, "parts", None)
        if parts:
            for i, part in enumerate(parts):
                print(f"[TRYON-GEMINI][RESPONSE] part {i} type: {type(part)}")
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    image_data = inline.data
                    mime_type = getattr(inline, "mime_type", "image/png")
                    print(f"[TRYON-GEMINI][SUCCESS] returning image part {i} mime={mime_type} size={len(image_data)}")
                    resp = make_response(send_file(BytesIO(image_data), mimetype=mime_type, as_attachment=False))
                    resp.headers['X-AI-Model'] = model_name
                    resp.headers['X-Generation-Method'] = 'direct-tryon-multi-view' if num_garment_images > 1 else 'direct-tryon'
                    resp.headers['X-Reference-Images'] = str(num_garment_images)
                    resp.status_code = 200
                    return resp

        # 2) Some SDKs return candidates with .output or parts nested inside candidates
        candidates = getattr(generation_response, "candidates", None)
        if candidates:
            for ci, cand in enumerate(candidates):
                print(f"[TRYON-GEMINI][DEBUG] candidate {ci} attrs: {dir(cand)}")
                # try to find inline data inside candidate
                maybe_parts = getattr(cand, "parts", None) or getattr(cand, "output", None)
                if maybe_parts:
                    for part in maybe_parts:
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            image_data = inline.data
                            mime_type = getattr(inline, "mime_type", "image/png")
                            resp = make_response(send_file(BytesIO(image_data), mimetype=mime_type, as_attachment=False))
                            resp.headers['X-AI-Model'] = model_name
                            resp.headers['X-Generation-Method'] = 'direct-tryon-multi-view' if num_garment_images > 1 else 'direct-tryon'
                            resp.headers['X-Reference-Images'] = str(num_garment_images)
                            resp.status_code = 200
                            return resp

                # fallback: candidate might have base64 or text
                text = getattr(cand, "text", None) or getattr(cand, "content", None)
                if text:
                    print(f"[TRYON-GEMINI][INFO] candidate text: {text[:200]}")

        # If still nothing, print helpful debug info and return error
        print("[TRYON-GEMINI][ERROR] No image data found in the response")
        print("[TRYON-GEMINI][ERROR] Full response repr:")
        try:
            print(repr(generation_response)[:2000])
        except Exception:
            pass

        return jsonify({
            "message": "Gemini Nano Banana failed to generate virtual try-on image",
            "code": "GENERATION_FAILED",
            "statusCode": 500,
            "details": "No image data returned from Gemini model - possibly blocked or model returned text only"
        }), 500

    except ValueError as ve:
        print(f"[TRYON-GEMINI][ERROR] ValueError: {ve}")
        return jsonify({
            "message": "Gemini request was blocked or returned no valid content",
            "code": "CONTENT_BLOCKED",
            "statusCode": 400,
            "details": str(ve)
        }), 400

    except Exception as e:
        print(f"[TRYON-GEMINI][ERROR] Unexpected error: {e}")
        print(traceback.format_exc())
        return jsonify({
            "message": f"Gemini Nano Banana virtual try-on failed: {str(e)}",
            "code": "SERVER_ERROR",
            "statusCode": 500
        }), 500

@app.route('/api/tryon-gemini-multi', methods=['POST'])
def tryon_gemini_multi():
    """
    Multi-garment virtual try-on API using Gemini 2.5 Flash Image
    Supports trying on multiple garments simultaneously with multiple images per garment for improved accuracy
    
    Input format:
    - avatar_image: Single avatar image
    - garment_1_image_1, garment_1_image_2, ... : Multiple views of garment 1 (front, back, side, detail)
    - garment_2_image_1, garment_2_image_2, ... : Multiple views of garment 2
    - garment_1_type, garment_2_type, ... : Types for each garment
    
    Legacy format still supported:
    - garment_image_1, garment_image_2 (single image per garment)
    """
    print("[TRYON-GEMINI-MULTI][START] API call initiated")
    try:
        print(f"[TRYON-GEMINI-MULTI][REQUEST] Content-Type: {request.content_type}")
        print(f"[TRYON-GEMINI-MULTI][REQUEST] Files: {list(request.files.keys())}")
        print(f"[TRYON-GEMINI-MULTI][REQUEST] Form data: {dict(request.form)}")

        if not GEMINI_API_KEY:
            print("[TRYON-GEMINI-MULTI][ERROR] Gemini API key not configured")
            return jsonify({
                "message": "Gemini API key not configured",
                "code": "MISSING_API_KEY",
                "statusCode": 500
            }), 500

        print(f"[TRYON-GEMINI-MULTI][CONFIG] Gemini API key configured: {GEMINI_API_KEY[:10]}...")

        # Get avatar image
        avatar_file = request.files.get('avatar_image')
        if not avatar_file:
            print("[TRYON-GEMINI-MULTI][ERROR] Missing avatar_image")
            return jsonify({
                "message": "Missing required file: avatar_image",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400

        # NEW: Support multiple images per garment for improved accuracy
        # Structure: garment_files_by_garment = [[img1, img2, img3], [img1, img2], ...]
        garment_files_by_garment = []  # List of lists - each inner list contains multiple images of same garment
        garment_types = []
        
        # Try new multi-image format first (garment_1_image_1, garment_1_image_2, ...)
        garment_idx = 1
        while True:
            garment_images = []
            image_idx = 1
            
            # Collect all images for this garment
            while True:
                garment_file = request.files.get(f'garment_{garment_idx}_image_{image_idx}')
                if garment_file:
                    garment_images.append(garment_file)
                    print(f"[TRYON-GEMINI-MULTI][FILES] Found garment_{garment_idx}_image_{image_idx}: {garment_file.filename}")
                    image_idx += 1
                else:
                    break
            
            # If we found images for this garment, add to collection
            if garment_images:
                garment_files_by_garment.append(garment_images)
                garment_type = request.form.get(f'garment_{garment_idx}_type', f'garment_{garment_idx}')
                garment_types.append(garment_type)
                print(f"[TRYON-GEMINI-MULTI][FILES] Garment {garment_idx}: {len(garment_images)} image(s), type: {garment_type}")
                garment_idx += 1
            else:
                break
        
        # FALLBACK: Try legacy single-image format (garment_image_1, garment_image_2, ...)
        if not garment_files_by_garment:
            print("[TRYON-GEMINI-MULTI][LEGACY] Trying legacy single-image format")
            i = 1
            while True:
                garment_file = request.files.get(f'garment_image_{i}')
                if garment_file:
                    garment_files_by_garment.append([garment_file])  # Wrap in list for consistency
                    garment_type = request.form.get(f'garment_type_{i}', f'garment_{i}')
                    garment_types.append(garment_type)
                    print(f"[TRYON-GEMINI-MULTI][LEGACY] Found garment_{i}: {garment_file.filename}, type: {garment_type}")
                    i += 1
                else:
                    break
        
        # FALLBACK 2: Try array format
        if not garment_files_by_garment:
            garment_files = request.files.getlist('garment_images')
            if garment_files:
                print(f"[TRYON-GEMINI-MULTI][LEGACY] Found {len(garment_files)} garments in array format")
                garment_files_by_garment = [[f] for f in garment_files]  # Wrap each in list
                
                garment_types_str = request.form.get('garment_types', '')
                if garment_types_str:
                    garment_types = [t.strip() for t in garment_types_str.split(',')]
                else:
                    garment_types = [f'garment_{i+1}' for i in range(len(garment_files))]

        if not garment_files_by_garment:
            print("[TRYON-GEMINI-MULTI][ERROR] No garment images provided")
            return jsonify({
                "message": "At least one garment image is required (use garment_1_image_1, garment_1_image_2, etc.)",
                "code": "INVALID_INPUT",
                "statusCode": 400
            }), 400

        total_garment_count = len(garment_files_by_garment)
        total_image_count = sum(len(images) for images in garment_files_by_garment)
        
        print(f"[TRYON-GEMINI-MULTI][FILES] Avatar: {avatar_file.filename}")
        print(f"[TRYON-GEMINI-MULTI][FILES] Processing {total_garment_count} garment(s) with {total_image_count} total image(s)")

        # Load and normalize avatar image
        try:
            avatar_file.seek(0)
            avatar_pil = Image.open(avatar_file).convert("RGB")
            print(f"[TRYON-GEMINI-MULTI][IMAGES] Avatar loaded size={avatar_pil.size}, mode={avatar_pil.mode}")
        except Exception as img_err:
            print(f"[TRYON-GEMINI-MULTI][ERROR] Avatar image processing failed: {img_err}")
            return jsonify({
                "message": f"Failed to process avatar image: {str(img_err)}",
                "code": "IMAGE_PROCESSING_ERROR",
                "statusCode": 400
            }), 400

        # Load and normalize garment images (now supporting multiple images per garment)
        garment_pils_by_garment = []  # List of lists - each inner list contains PIL images of same garment
        
        for garment_idx, garment_files in enumerate(garment_files_by_garment):
            garment_pils = []
            for img_idx, garment_file in enumerate(garment_files):
                try:
                    garment_file.seek(0)
                    garment_pil = Image.open(garment_file).convert("RGBA")
                    garment_pils.append(garment_pil)
                    print(f"[TRYON-GEMINI-MULTI][IMAGES] Garment {garment_idx+1}, Image {img_idx+1} loaded size={garment_pil.size}, mode={garment_pil.mode}")
                except Exception as img_err:
                    print(f"[TRYON-GEMINI-MULTI][ERROR] Garment {garment_idx+1}, Image {img_idx+1} processing failed: {img_err}")
                    return jsonify({
                        "message": f"Failed to process garment {garment_idx+1}, image {img_idx+1}: {str(img_err)}",
                        "code": "IMAGE_PROCESSING_ERROR",
                        "statusCode": 400
                    }), 400
            
            garment_pils_by_garment.append(garment_pils)

        # Convert PIL images to bytes
        def pil_to_bytes(img: Image.Image, fmt="PNG"):
            buf = BytesIO()
            img.save(buf, format=fmt)
            buf.seek(0)
            return buf.read()

        avatar_bytes = pil_to_bytes(avatar_pil, fmt="PNG")
        avatar_b64 = base64.b64encode(avatar_bytes).decode('utf-8')

        # Convert all garment images to base64 (grouped by garment)
        garment_b64_by_garment = []
        for garment_pils in garment_pils_by_garment:
            garment_b64_list = []
            for garment_pil in garment_pils:
                garment_bytes = pil_to_bytes(garment_pil, fmt="PNG")
                garment_b64 = base64.b64encode(garment_bytes).decode('utf-8')
                garment_b64_list.append(garment_b64)
            garment_b64_by_garment.append(garment_b64_list)

        # Initialize Gemini client
        client = genai.Client(api_key=GEMINI_API_KEY)
        model_name = "gemini-2.5-flash-image"

        # Build garment descriptions for prompt (with image counts)
        garment_descriptions = []
        for idx, (garment_type, garment_images) in enumerate(zip(garment_types, garment_b64_by_garment)):
            img_count = len(garment_images)
            if img_count > 1:
                garment_descriptions.append(f"Garment {idx+1} ({garment_type}) - {img_count} reference images showing different views")
            else:
                garment_descriptions.append(f"Garment {idx+1} ({garment_type})")
        
        garments_list_str = ", ".join(garment_descriptions)
        
        # Prepare multi-garment prompt (enhanced for multiple reference images)
        generation_prompt = (
            f"🚨 CRITICAL INSTRUCTION: This is a MULTI-GARMENT VIRTUAL TRY-ON task. You MUST keep the person from the FIRST image (avatar) 100% unchanged.\n"
            f"Your ONLY job is to add {total_garment_count} garments onto this existing person. DO NOT create a new person.\n\n"
            
            f"� IMAGE ORDER:\n"
            f"- Image 1: AVATAR (the person to dress - keep this person exactly as-is)\n"
            f"- Images 2-{total_image_count + 1}: GARMENT reference images (extract garment designs only)\n"
            f"  {garments_list_str}\n\n"
            
            f"⛔ ABSOLUTE PROHIBITIONS - NEVER DO THESE:\n"
            f"1. DO NOT replace the avatar person with a different person\n"
            f"2. DO NOT use any person/model from the garment reference images\n"
            f"3. DO NOT change the avatar's face, body, pose, or appearance in ANY way\n"
            f"4. DO NOT change the background or lighting from the avatar image\n"
            f"5. DO NOT create a composite of the avatar and any garment model\n\n"
            
            f"✅ WHAT YOU MUST DO:\n\n"
            f"1. AVATAR PRESERVATION (100% UNCHANGED):\n"
            f"Keep these EXACTLY as shown in the AVATAR image (image 1):\n"
            f"- EXACT same face, eyes, nose, mouth, facial expression\n"
            f"- EXACT same hair style, color, and position\n"
            f"- EXACT same skin tone and complexion\n"
            f"- EXACT same body pose, hand position, arm position\n"
            f"- EXACT same body proportions and build\n"
            f"- EXACT same background, floor, walls, environment\n"
            f"- EXACT same lighting direction, color, and intensity\n"
            f"- EXACT same camera angle and perspective\n\n"
            
            f"2. GARMENT EXTRACTION (from reference images):\n"
            f"Analyze ALL {total_image_count} garment reference images to extract garment designs - ignore the people wearing them.\n"
            f"For each garment, extract:\n"
            f"- Design details (colors, patterns, logos, buttons, pockets, etc.)\n"
            f"- Front, back, and side design elements\n"
            f"- Fabric texture and material properties\n"
            f"- 3D structure from multiple angles\n\n"
            
            f"3. GARMENT COORDINATION:\n"
            f"Layer the {total_garment_count} garments correctly:\n"
            f"- Layer properly (top over bottom, jacket over shirt)\n"
            f"- Position each garment appropriately on body\n"
            f"- Maintain realistic proportions between garments\n\n"
            
            f"4. GARMENT ADAPTATION (Apply to extracted garments):\n"
            f"Take the extracted garment designs and adapt them to fit the AVATAR's body:\n"
            f"- **DRAPING:** Warp each garment to fit the avatar's body contours and pose\n"
            f"- **WRINKLES:** Add natural wrinkles based on avatar's pose and fabric type\n"
            f"- **SHADOWS:** Apply shadows that match the avatar's lighting\n"
            f"- **OCCLUSION:** Layer garments behind avatar's hands/arms if they're in front\n"
            f"- **STYLING:** If garments show styling (rolled sleeves, long sleeves on hands, raised collar, open collar, short length trousers, long and bell bottom trousers, etc. consider all of these fitting shown in the images provided and change it.), apply to garments on avatar\n"
            f"- **INTERACTION:** Show realistic interaction between garments\n\n"
            
            f"🎯 FINAL OUTPUT SPECIFICATION:\n"
            f"You MUST generate an image that is:\n"
            f"✓ The EXACT avatar person (image 1) - same face, same body, same pose, same background\n"
            f"✓ With ALL {total_garment_count} garment designs (from garment images) now fitted onto them\n"
            f"✓ The garments look realistically worn, not pasted on\n"
            f"✓ All garments work together as a cohesive outfit\n\n"
            
            f"❌ YOUR OUTPUT MUST NOT BE:\n"
            f"✗ A different person\n"
            f"✗ Any model from the garment reference images\n"
            f"✗ A blend/composite of avatar and any garment model\n"
            f"✗ A changed/modified version of the avatar\n\n"
            
            f"🔴 FINAL REMINDER: Use the avatar person from image 1. Extract only the garment designs from the other images. "
            f"DO NOT replace the avatar with anyone else. Use ALL {total_image_count} reference images to extract complete garment details."
        )

        print(f"[TRYON-GEMINI-MULTI][GEMINI] Using model {model_name}; prompt length={len(generation_prompt)}")
        print(f"[TRYON-GEMINI-MULTI][GEMINI] Processing {total_garment_count} garment(s) with {total_image_count} total reference images")

        # Build contents with avatar + all garment images (grouped by garment for better context)
        contents = [
            {"parts": [{"text": generation_prompt}]},
            {"parts": [{"inline_data": {"mime_type": "image/png", "data": avatar_b64}}]}
        ]
        
        # Add all images for each garment (multiple images per garment for improved accuracy)
        for garment_idx, garment_b64_list in enumerate(garment_b64_by_garment):
            for img_idx, garment_b64 in enumerate(garment_b64_list):
                contents.append({
                    "parts": [{"inline_data": {"mime_type": "image/png", "data": garment_b64}}]
                })
                print(f"[TRYON-GEMINI-MULTI][GEMINI] Added garment {garment_idx+1}, image {img_idx+1} to contents")
        
        print(f"[TRYON-GEMINI-MULTI][GEMINI] Sending {len(contents)} total items to model (1 avatar + {total_image_count} garment images across {total_garment_count} garments)")

        # Call the API with retry logic
        max_retries = 3
        backoff = 1.0
        generation_response = None

        for attempt in range(1, max_retries + 1):
            try:
                print(f"[TRYON-GEMINI-MULTI][GEMINI] Attempt {attempt}")
                
                generation_response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                
                print("[TRYON-GEMINI-MULTI][GEMINI] Response received")
                break
                
            except Exception as ex:
                print(f"[TRYON-GEMINI-MULTI][ERROR] Attempt {attempt} failed: {ex}")
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    print(f"[TRYON-GEMINI-MULTI][ERROR] All retries failed")
                    return jsonify({
                        "message": f"Multi-garment try-on failed: {str(ex)}",
                        "code": "GENERATION_ERROR",
                        "statusCode": 500
                    }), 500

        if generation_response is None:
            return jsonify({
                "message": "Multi-garment try-on failed - no response from AI",
                "code": "GENERATION_ERROR",
                "statusCode": 500
            }), 500

        print(f"[TRYON-GEMINI-MULTI][DEBUG] Response dir: {dir(generation_response)}")

        # Extract image data from response (check parts first)
        parts = getattr(generation_response, "parts", None)
        if parts:
            for i, part in enumerate(parts):
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    image_data = inline.data
                    
                    print(f"[TRYON-GEMINI-MULTI][SUCCESS] Got multi-garment try-on image, size={len(image_data)} bytes")
                    
                    # Apply background removal post-processing
                    try:
                        print("[TRYON-GEMINI-MULTI][POST-PROCESS] Removing background...")
                        result_image = Image.open(BytesIO(image_data))
                        
                        # Convert to RGBA if not already
                        if result_image.mode != 'RGBA':
                            result_image = result_image.convert('RGBA')
                            print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Converted to RGBA mode")
                        
                        # Convert to numpy array for processing
                        data = np.array(result_image)
                        
                        # Extract RGBA channels
                        r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
                        
                        # Create masks for background removal
                        # 1. White/very light pixels (R, G, B all > 240)
                        white_mask = (r > 240) & (g > 240) & (b > 240)
                        
                        # 2. Light gray pixels (checkered pattern - RGB between 200-240)
                        gray_mask = (r > 200) & (r < 240) & (g > 200) & (g < 240) & (b > 200) & (b < 240)
                        
                        # 3. Very light pixels (RGB > 235) - catch near-white
                        near_white_mask = (r > 235) & (g > 235) & (b > 235)
                        
                        # 4. Black/very dark pixels (R, G, B all < 15)
                        black_mask = (r < 15) & (g < 15) & (b < 15)
                        
                        # 5. Near-black pixels (R, G, B all < 30) - catch dark gray
                        near_black_mask = (r < 30) & (g < 30) & (b < 30)
                        
                        # Combine all background masks
                        background_mask = white_mask | gray_mask | near_white_mask | black_mask | near_black_mask
                        
                        # Set background pixels to fully transparent
                        data[background_mask, 3] = 0
                        
                        # Advanced: Remove pixels similar to detected background color
                        if np.any(background_mask):
                            bg_pixels = data[background_mask]
                            if len(bg_pixels) > 100:  # Need sufficient samples
                                # Calculate average background color
                                avg_r = float(np.mean(bg_pixels[:,0]))
                                avg_g = float(np.mean(bg_pixels[:,1]))
                                avg_b = float(np.mean(bg_pixels[:,2]))
                                
                                print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Detected background color: RGB({avg_r:.0f}, {avg_g:.0f}, {avg_b:.0f})")
                                
                                # Find pixels within 40 units of background color (Euclidean distance)
                                color_diff = np.sqrt(
                                    (r.astype(float) - avg_r)**2 + 
                                    (g.astype(float) - avg_g)**2 + 
                                    (b.astype(float) - avg_b)**2
                                )
                                similar_bg_mask = color_diff < 40
                                data[similar_bg_mask, 3] = 0
                                
                                # Soften edges: Make near-background pixels semi-transparent
                                edge_mask = (color_diff >= 40) & (color_diff < 80)
                                if np.any(edge_mask):
                                    # Gradually fade alpha based on distance from background
                                    alpha_fade = ((color_diff[edge_mask] - 40) / 40 * 255).astype(np.uint8)
                                    data[edge_mask, 3] = np.minimum(data[edge_mask, 3], alpha_fade)
                        
                        # Count transparent pixels for verification
                        transparent_count = np.sum(data[:,:,3] == 0)
                        total_pixels = data.shape[0] * data.shape[1]
                        transparency_percent = (transparent_count / total_pixels) * 100
                        
                        print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Transparency: {transparency_percent:.1f}% ({transparent_count}/{total_pixels} pixels)")
                        
                        # Convert back to PIL Image
                        result_image = Image.fromarray(data, 'RGBA')
                        
                        # Save to bytes with PNG format (preserves transparency)
                        output_buffer = BytesIO()
                        result_image.save(output_buffer, format='PNG', optimize=True)
                        output_buffer.seek(0)
                        processed_image_data = output_buffer.read()
                        
                        print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] ✅ Complete! Output size: {len(processed_image_data)} bytes")
                        
                        # Use processed image instead of original
                        image_data = processed_image_data
                        
                    except Exception as post_err:
                        print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Warning: Background removal failed: {post_err}")
                        # Continue with original image if post-processing fails
                    
                    resp = make_response(send_file(
                        BytesIO(image_data),
                        mimetype='image/png',
                        as_attachment=False,
                        download_name='tryon_multi_garment.png'
                    ))
                    resp.headers['X-AI-Model'] = model_name
                    resp.headers['X-Processing-Method'] = 'multi-garment-tryon-enhanced'
                    resp.headers['X-Garment-Count'] = str(total_garment_count)
                    resp.headers['X-Total-Reference-Images'] = str(total_image_count)
                    resp.status_code = 200
                    return resp

        # Check candidates structure
        candidates = getattr(generation_response, "candidates", None)
        if candidates:
            for ci, cand in enumerate(candidates):
                maybe_parts = getattr(cand, "parts", None) or getattr(cand, "output", None)
                if maybe_parts:
                    for part in maybe_parts:
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            image_data = inline.data
                            
                            print(f"[TRYON-GEMINI-MULTI][SUCCESS] Got multi-garment try-on image from candidates, size={len(image_data)} bytes")
                            
                            # Apply background removal post-processing
                            try:
                                print("[TRYON-GEMINI-MULTI][POST-PROCESS] Removing background...")
                                result_image = Image.open(BytesIO(image_data))
                                
                                # Convert to RGBA if not already
                                if result_image.mode != 'RGBA':
                                    result_image = result_image.convert('RGBA')
                                    print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Converted to RGBA mode")
                                
                                # Convert to numpy array for processing
                                data = np.array(result_image)
                                
                                # Extract RGBA channels
                                r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
                                
                                # Create masks for background removal
                                # 1. White/very light pixels (R, G, B all > 240)
                                white_mask = (r > 240) & (g > 240) & (b > 240)
                                
                                # 2. Light gray pixels (checkered pattern - RGB between 200-240)
                                gray_mask = (r > 200) & (r < 240) & (g > 200) & (g < 240) & (b > 200) & (b < 240)
                                
                                # 3. Very light pixels (RGB > 235) - catch near-white
                                near_white_mask = (r > 235) & (g > 235) & (b > 235)
                                
                                # 4. Black/very dark pixels (R, G, B all < 15)
                                black_mask = (r < 15) & (g < 15) & (b < 15)
                                
                                # 5. Near-black pixels (R, G, B all < 30) - catch dark gray
                                near_black_mask = (r < 30) & (g < 30) & (b < 30)
                                
                                # Combine all background masks
                                background_mask = white_mask | gray_mask | near_white_mask | black_mask | near_black_mask
                                
                                # Set background pixels to fully transparent
                                data[background_mask, 3] = 0
                                
                                # Advanced: Remove pixels similar to detected background color
                                if np.any(background_mask):
                                    bg_pixels = data[background_mask]
                                    if len(bg_pixels) > 100:  # Need sufficient samples
                                        # Calculate average background color
                                        avg_r = float(np.mean(bg_pixels[:,0]))
                                        avg_g = float(np.mean(bg_pixels[:,1]))
                                        avg_b = float(np.mean(bg_pixels[:,2]))
                                        
                                        print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Detected background color: RGB({avg_r:.0f}, {avg_g:.0f}, {avg_b:.0f})")
                                        
                                        # Find pixels within 40 units of background color (Euclidean distance)
                                        color_diff = np.sqrt(
                                            (r.astype(float) - avg_r)**2 + 
                                            (g.astype(float) - avg_g)**2 + 
                                            (b.astype(float) - avg_b)**2
                                        )
                                        similar_bg_mask = color_diff < 40
                                        data[similar_bg_mask, 3] = 0
                                        
                                        # Soften edges: Make near-background pixels semi-transparent
                                        edge_mask = (color_diff >= 40) & (color_diff < 80)
                                        if np.any(edge_mask):
                                            # Gradually fade alpha based on distance from background
                                            alpha_fade = ((color_diff[edge_mask] - 40) / 40 * 255).astype(np.uint8)
                                            data[edge_mask, 3] = np.minimum(data[edge_mask, 3], alpha_fade)
                                
                                # Count transparent pixels for verification
                                transparent_count = np.sum(data[:,:,3] == 0)
                                total_pixels = data.shape[0] * data.shape[1]
                                transparency_percent = (transparent_count / total_pixels) * 100
                                
                                print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Transparency: {transparency_percent:.1f}% ({transparent_count}/{total_pixels} pixels)")
                                
                                # Convert back to PIL Image
                                result_image = Image.fromarray(data, 'RGBA')
                                
                                # Save to bytes with PNG format (preserves transparency)
                                output_buffer = BytesIO()
                                result_image.save(output_buffer, format='PNG', optimize=True)
                                output_buffer.seek(0)
                                processed_image_data = output_buffer.read()
                                
                                print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] ✅ Complete! Output size: {len(processed_image_data)} bytes")
                                
                                # Use processed image instead of original
                                image_data = processed_image_data
                                
                            except Exception as post_err:
                                print(f"[TRYON-GEMINI-MULTI][POST-PROCESS] Warning: Background removal failed: {post_err}")
                                # Continue with original image if post-processing fails
                            
                            resp = make_response(send_file(
                                BytesIO(image_data),
                                mimetype='image/png',
                                as_attachment=False,
                                download_name='tryon_multi_garment.png'
                            ))
                            resp.headers['X-AI-Model'] = model_name
                            resp.headers['X-Processing-Method'] = 'multi-garment-tryon-enhanced'
                            resp.headers['X-Garment-Count'] = str(total_garment_count)
                            resp.headers['X-Total-Reference-Images'] = str(total_image_count)
                            resp.status_code = 200
                            return resp

        # No image data found
        print("[TRYON-GEMINI-MULTI][ERROR] No image data found in the response")
        print("[TRYON-GEMINI-MULTI][ERROR] Full response repr:")
        try:
            print(repr(generation_response)[:2000])
        except Exception:
            pass

        return jsonify({
            "message": "Multi-garment try-on failed - no image generated",
            "code": "GENERATION_FAILED",
            "statusCode": 500,
            "details": "No image data returned from Gemini model - possibly blocked or model returned text only"
        }), 500

    except ValueError as ve:
        print(f"[TRYON-GEMINI-MULTI][ERROR] ValueError: {ve}")
        return jsonify({
            "message": "Gemini request was blocked or returned no valid content",
            "code": "CONTENT_BLOCKED",
            "statusCode": 400,
            "details": str(ve)
        }), 400

    except Exception as e:
        print(f"[TRYON-GEMINI-MULTI][ERROR] Unexpected error: {e}")
        print(traceback.format_exc())
        return jsonify({
            "message": f"Multi-garment virtual try-on failed: {str(e)}",
            "code": "SERVER_ERROR",
            "statusCode": 500
        }), 500

@app.route('/api/gemini/test', methods=['GET'])
def test_gemini():
    """Test endpoint to verify Gemini API connection"""
    try:
        if not GEMINI_API_KEY:
            return jsonify({
                "status": "error",
                "message": "Gemini API key not configured",
                "configured": False
            }), 500
            
        # Test with the new genai.Client
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Test basic text generation first
            test_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[{"text": "Say 'Gemini API is working correctly' if you can read this."}]
            )
            
            # Try to extract text response
            response_text = "API test completed"
            if hasattr(test_response, 'text'):
                response_text = test_response.text
            elif hasattr(test_response, 'candidates') and test_response.candidates:
                for candidate in test_response.candidates:
                    if hasattr(candidate, 'text'):
                        response_text = candidate.text
                        break
                    elif hasattr(candidate, 'parts') and candidate.parts:
                        for part in candidate.parts:
                            if hasattr(part, 'text'):
                                response_text = part.text
                                break
            
            return jsonify({
                "status": "success", 
                "message": "Gemini API is working correctly",
                "configured": True,
                "client_type": "google.genai.Client",
                "models_available": ["gemini-2.5-flash", "gemini-2.5-flash-image"],
                "response": response_text
            })
            
        except Exception as model_error:
            return jsonify({
                "status": "error",
                "message": f"Gemini client test failed: {str(model_error)}",
                "configured": True,
                "error_type": str(type(model_error))
            })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Gemini API test failed: {str(e)}",
            "configured": bool(GEMINI_API_KEY)
        }), 500

@app.route('/api/message')
def get_message():
    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE
        )
        cursor = conn.cursor()
        cursor.execute('SELECT message FROM hello LIMIT 1;')
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result:
            return jsonify({'message': result[0]})
        else:
            return jsonify({'message': 'No message found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save-clothing', methods=['POST'])
def save_clothing():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(WARDROBE_FOLDER, filename)
        os.makedirs(WARDROBE_FOLDER, exist_ok=True)
        file.save(save_path)
        return jsonify({"success": True, "filename": filename}), 200
    else:
        return jsonify({"error": "Invalid file type"}), 400

@app.route('/api/wardrobe-images', methods=['GET'])
def get_wardrobe_images():
    wardrobe_folder = "../frontend/public/images/wardrobe"
    try:
        files = [
            f for f in os.listdir(wardrobe_folder)
            if os.path.isfile(os.path.join(wardrobe_folder, f))
               and f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
        ]
        return jsonify({"images": files})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/create-account', methods=['POST'])
def create_account():
    try:
        # Get form data
        data = request.get_json() if request.is_json else request.form
        
        # Extract required fields
        email = data.get('email', '').strip()
        first_name = data.get('firstname', '').strip()
        last_name = data.get('lastname', '').strip()
        password = data.get('password', '')
        age = data.get('age', '')
        gender = data.get('gender', '')
        weight = data.get('weight', '')
        height = data.get('height', '')
        physique = data.get('physique', '')
        
        # Validate required fields
        if not all([email, first_name, last_name, password, age, gender, weight, height, physique]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
        
        # Validate email format
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_regex, email):
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        # Validate password length
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'Password must be at least 6 characters long'
            }), 400
        
        # Validate numeric fields
        try:
            age = int(age)
            weight = float(weight)
            height = float(height)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Age, weight, and height must be valid numbers'
            }), 400
        
        # Validate ranges
        if not (13 <= age <= 100):
            return jsonify({
                'success': False,
                'error': 'Age must be between 13 and 100'
            }), 400
        
        if not (30 <= weight <= 300):
            return jsonify({
                'success': False,
                'error': 'Weight must be between 30 and 300 kg'
            }), 400
        
        if not (100 <= height <= 250):
            return jsonify({
                'success': False,
                'error': 'Height must be between 100 and 250 cm'
            }), 400
        
        # Validate enum values
        valid_genders = ['male', 'female', 'other', 'prefer-not-to-say']
        valid_physiques = ['slim', 'muscular', 'thick']
        
        if gender not in valid_genders:
            return jsonify({
                'success': False,
                'error': 'Invalid gender selection'
            }), 400
        
        if physique not in valid_physiques:
            return jsonify({
                'success': False,
                'error': 'Invalid physique selection'
            }), 400
        
        # Generate unique userid
        userid = str(uuid.uuid4())[:8]  # 8-character unique ID
        
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({
                'success': False,
                'error': 'Email already registered'
            }), 409
        
        # Insert user data (avatar left as NULL)
        insert_query = """
        INSERT INTO users (userid, email, first_name, last_name, password, age, gender, weight, height, physique, avatar)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(insert_query, (
            userid, email, first_name, last_name, hashed_password,
            age, gender, weight, height, physique, None  # avatar is NULL
        ))
        
        connection.commit()
        user_id = cursor.lastrowid
        
        cursor.close()
        connection.close()
        
        return jsonify({
            'success': True,
            'message': 'Account created successfully',
            'user_data': {
                'id': user_id,
                'userid': userid,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'age': age,
                'gender': gender,
                'weight': weight,
                'height': height,
                'physique': physique
            }
        }), 201
        
    except mysql.connector.Error as e:
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/login', methods=['POST'])
def login():
        try:
            # Get form data
            data = request.get_json() if request.is_json else request.form
            
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            if not email or not password:
                return jsonify({
                    'success': False,
                    'error': 'Email and password are required'
                }), 400
            
            # Connect to database
            connection = mysql.connector.connect(**db_config)
            cursor = connection.cursor(dictionary=True)
            
            # Get user by email
            cursor.execute("""
                SELECT id, userid, email, first_name, last_name, password, age, gender, 
                    weight, height, physique, created_at, is_active 
                FROM users WHERE email = %s AND is_active = TRUE
            """, (email,))
            
            user = cursor.fetchone()
            
            if not user or not check_password_hash(user['password'], password):
                return jsonify({
                    'success': False,
                    'error': 'Invalid email or password'
                }), 401
            
            # Remove password from response
            del user['password']
            
            cursor.close()
            connection.close()
            
            return jsonify({
                'success': True,
                'message': 'Login successful',
                'user_data': user
            }), 200
            
        except mysql.connector.Error as e:
            return jsonify({
                'success': False,
                'error': f'Database error: {str(e)}'
            }), 500
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Server error: {str(e)}'
            }), 500

@app.route('/api/save-avatar', methods=['POST'])
def save_avatar():
    try:
        # Check if file and user_id are provided
        if 'avatar' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No avatar file provided'
            }), 400
        
        user_id = request.form.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID is required'
            }), 400
        
        avatar_file = request.files['avatar']
        
        # Validate file type
        if not avatar_file or not allowed_file(avatar_file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Please upload PNG, JPG, JPEG, or WEBP'
            }), 400
        
        # Read file as binary data
        avatar_data = avatar_file.read()
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(avatar_data) > max_size:
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 5MB'
            }), 400
        
        print(f"📸 Saving avatar for user: {user_id}, size: {len(avatar_data)} bytes")
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE userid = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Update user's avatar
        update_query = "UPDATE users SET avatar = %s WHERE userid = %s"
        cursor.execute(update_query, (avatar_data, user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"✅ Avatar saved successfully for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Avatar saved successfully'
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to get avatar blob
@app.route('/api/get-avatar/<user_id>', methods=['GET'])
def get_avatar(user_id):
    try:
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # Get user's avatar
        cursor.execute("SELECT avatar FROM users WHERE userid = %s", (user_id,))
        result = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not result or not result[0]:
            return jsonify({
                'success': False,
                'error': 'Avatar not found'
            }), 404
        
        avatar_data = result[0]
        
        # Return the image as binary response
        return Response(
            avatar_data,
            mimetype='image/png',
            headers={
                'Content-Disposition': f'inline; filename=avatar_{user_id}.png',
                'Cache-Control': 'max-age=300'  # Cache for 5 minutes
            }
        )
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to update avatar (alternative endpoint)
@app.route('/api/update-avatar', methods=['PUT'])
def update_avatar():
    try:
        # Get JSON data with base64 encoded image
        data = request.get_json()
        
        if not data or 'user_id' not in data or 'avatar_data' not in data:
            return jsonify({
                'success': False,
                'error': 'User ID and avatar data are required'
            }), 400
        
        user_id = data.get('user_id')
        avatar_base64 = data.get('avatar_data')
        
        # Remove data URL prefix if present (e.g., "data:image/png;base64,")
        if avatar_base64.startswith('data:'):
            avatar_base64 = avatar_base64.split(',')[1]
        
        # Decode base64 to binary
        try:
            avatar_data = base64.b64decode(avatar_base64)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'Invalid base64 data'
            }), 400
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB
        if len(avatar_data) > max_size:
            return jsonify({
                'success': False,
                'error': 'File too large. Maximum size is 5MB'
            }), 400
        
        print(f"📸 Updating avatar for user: {user_id}, size: {len(avatar_data)} bytes")
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE userid = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Update user's avatar
        update_query = "UPDATE users SET avatar = %s WHERE userid = %s"
        cursor.execute(update_query, (avatar_data, user_id))
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"✅ Avatar updated successfully for user: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Avatar updated successfully'
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to get user data
@app.route('/api/get-user-data/<user_id>', methods=['GET'])
def get_user_data(user_id):
    try:
        print(f"📥 Fetching user data for user: {user_id}")
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # Get user data (excluding password and avatar for security/performance)
        cursor.execute("""
            SELECT id, userid, email, first_name, last_name, age, gender, 
                   weight, height, physique, created_at, updated_at, is_active
            FROM users WHERE userid = %s
        """, (user_id,))
        
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Convert datetime objects to strings for JSON serialization
        if user['created_at']:
            user['created_at'] = user['created_at'].isoformat()
        if user['updated_at']:
            user['updated_at'] = user['updated_at'].isoformat()
        
        print(f"✅ User data retrieved successfully for: {user_id}")
        
        return jsonify({
            'success': True,
            'user_data': user
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to get user data by email (alternative endpoint)
@app.route('/api/get-user-data-by-email/<email>', methods=['GET'])
def get_user_data_by_email(email):
    try:
        print(f"📥 Fetching user data for email: {email}")
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # Get user data (excluding password and avatar)
        cursor.execute("""
            SELECT id, userid, email, first_name, last_name, age, gender, 
                   weight, height, physique, created_at, updated_at, is_active
            FROM users WHERE email = %s
        """, (email,))
        
        user = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Convert datetime objects to strings for JSON serialization
        if user['created_at']:
            user['created_at'] = user['created_at'].isoformat()
        if user['updated_at']:
            user['updated_at'] = user['updated_at'].isoformat()
        
        print(f"✅ User data retrieved successfully for email: {email}")
        
        return jsonify({
            'success': True,
            'user_data': user
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# API to update user data
@app.route('/api/update-user-data/<user_id>', methods=['PUT'])
def update_user_data(user_id):
    try:
        print(f"📝 Updating user data for user: {user_id}")
        
        # Get JSON data
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE userid = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Build update query dynamically based on provided fields
        allowed_fields = ['first_name', 'last_name', 'age', 'gender', 'weight', 'height', 'physique']
        update_fields = []
        update_values = []
        
        for field in allowed_fields:
            if field in data:
                update_fields.append(f"{field} = %s")
                
                # Validate and convert data types
                if field in ['age']:
                    try:
                        update_values.append(int(data[field]))
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid {field}: must be a number'
                        }), 400
                elif field in ['weight', 'height']:
                    try:
                        update_values.append(float(data[field]))
                    except ValueError:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid {field}: must be a number'
                        }), 400
                else:
                    update_values.append(data[field])
        
        if not update_fields:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400
        
        # Add updated_at timestamp
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        # Build and execute update query
        update_query = f"UPDATE users SET {', '.join(update_fields)} WHERE userid = %s"
        update_values.append(user_id)
        
        cursor.execute(update_query, update_values)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        print(f"✅ User data updated successfully for: {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'User data updated successfully'
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

# ===== WARDROBE ENDPOINTS =====

@app.route('/api/wardrobe/save', methods=['POST'])
def save_to_wardrobe():
    """Save a garment to user's wardrobe"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Extract required fields
        user_id = data.get('user_id')
        garment_id = data.get('garment_id')
        garment_image = data.get('garment_image')  # Base64 string
        garment_type = data.get('garment_type')
        garment_url = data.get('garment_url')
        
        if not all([user_id, garment_id, garment_image, garment_type]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: user_id, garment_id, garment_image, garment_type'
            }), 400
        
        # Convert base64 to binary for storage
        try:
            # Remove data URL prefix if present
            if garment_image.startswith('data:'):
                garment_image = garment_image.split(',')[1]
            
            image_binary = base64.b64decode(garment_image)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Invalid image data: {str(e)}'
            }), 400
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # Insert or replace garment in wardrobe
        insert_query = """
            INSERT INTO wardrobe (user_id, garment_id, garment_image, garment_type, garment_url, date_added)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
            garment_image = VALUES(garment_image),
            garment_type = VALUES(garment_type),
            garment_url = VALUES(garment_url),
            date_added = NOW()
        """
        
        cursor.execute(insert_query, (user_id, garment_id, image_binary, garment_type, garment_url))
        connection.commit()
        
        cursor.close()
        connection.close()
        
        print(f"✅ Garment saved to wardrobe: {garment_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Garment saved to wardrobe successfully',
            'garment_id': garment_id
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/wardrobe/user/<user_id>', methods=['GET'])
def get_user_wardrobe(user_id):
    """Get all wardrobe items for a specific user"""
    try:
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        
        # Query to get all wardrobe items for the user
        select_query = """
            SELECT 
                id,
                user_id,
                garment_id,
                garment_image,
                garment_type,
                garment_url,
                date_added
            FROM wardrobe 
            WHERE user_id = %s 
            ORDER BY date_added DESC
        """
        
        cursor.execute(select_query, (user_id,))
        wardrobe_items = cursor.fetchall()
        
        # Convert binary image data to base64 for JSON response
        for item in wardrobe_items:
            if item['garment_image']:
                # Convert binary to base64 string
                image_b64 = base64.b64encode(item['garment_image']).decode('utf-8')
                item['garment_image'] = f"data:image/png;base64,{image_b64}"
            
            # Convert datetime to string for JSON serialization
            if item['date_added']:
                item['date_added'] = item['date_added'].isoformat()
        
        cursor.close()
        connection.close()
        
        print(f"✅ Retrieved {len(wardrobe_items)} wardrobe items for user {user_id}")
        
        return jsonify(wardrobe_items), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/wardrobe/remove', methods=['DELETE'])
def remove_from_wardrobe():
    """Remove a garment from user's wardrobe"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        user_id = data.get('user_id')
        garment_id = data.get('garment_id')
        
        if not all([user_id, garment_id]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: user_id, garment_id'
            }), 400
        
        # Connect to database
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        # Delete garment from wardrobe
        delete_query = "DELETE FROM wardrobe WHERE user_id = %s AND garment_id = %s"
        cursor.execute(delete_query, (user_id, garment_id))
        
        if cursor.rowcount == 0:
            cursor.close()
            connection.close()
            return jsonify({
                'success': False,
                'error': 'Garment not found in wardrobe'
            }), 404
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"✅ Garment removed from wardrobe: {garment_id} for user {user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Garment removed from wardrobe successfully'
        }), 200
        
    except mysql.connector.Error as e:
        print(f"❌ Database error: {e}")
        return jsonify({
            'success': False,
            'error': f'Database error: {str(e)}'
        }), 500
        
    except Exception as e:
        print(f"❌ Server error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/chat', methods=['POST'])
def chat_assistance():
    """AI chat assistant for garment search and recommendations"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        message = data.get('message', '').strip()
        user_id = data.get('user_id', 'guest')
        context = data.get('context', {})
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message cannot be empty'
            }), 400
        
        print(f"💬 Chat request from user {user_id}: {message}")
        
        # Initialize Google Genai client
        if not GEMINI_API_KEY:
            return jsonify({
                'success': False,
                'error': 'Gemini API key not configured'
            }), 500
        
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Create system prompt for garment search assistant
        system_prompt = f"""You are an online fashion garments discovery assistant. 
        
        Guidelines:
        - Take the user request for online fashion garment and give exact matching recommendations
        - Strictly follow brand, gender, garment size, color, style preferences
        - Respond only with results from the brand for that garment type 
        - If no brand is mentioned give the preference to garment and gender

        User message: {message}"""
        
        try:
            # Send request to Gemini
            response = client.models.generate_content(
                model='gemini-2.0-flash-exp',
                contents=[{
                    'parts': [{'text': system_prompt}]
                }]
            )
            
            if hasattr(response, 'text') and response.text:
                ai_response = response.text.strip()
                print(f"AI response: {ai_response}")
                
                return jsonify({
                    'success': True,
                    'response': ai_response,
                    'user_message': message
                }), 200
            else:
                print("❌ Empty response from Gemini")
                return jsonify({
                    'success': False,
                    'error': 'Empty response from AI'
                }), 500
                
        except Exception as gemini_error:
            print(f"❌ Gemini API error: {gemini_error}")
            # Fallback response
            fallback_response = generate_fallback_response(message)
            return jsonify({
                'success': True,
                'response': fallback_response,
                'user_message': message,
                'note': 'Fallback response used due to AI service issues'
            }), 200
            
    except Exception as e:
        print(f"❌ Chat endpoint error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/unified-search', methods=['POST'])
def unified_search():
    """
    Unified search endpoint that performs a direct Google search
    based on the provided query.
    """
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'success': False, 'error': 'No query provided'}), 400

        query = data.get('query', '').strip()
        if not query:
            return jsonify({'success': False, 'error': 'Query cannot be empty'}), 400

        print(f"🔍 Direct search request for: \"{query}\"")

        search_results = perform_google_search(query)
        garment_images = extract_garment_images_from_results(search_results, query) if search_results else []

        print(f"🖼️ Found {len(garment_images)} images after filtering.")

        return jsonify({
            'success': True,
            'query': query,
            'garment_images': garment_images[:12], # Return up to 12 images
            'total_results': len(garment_images),
            'has_results': len(garment_images) > 0
        }), 200

    except Exception as e:
        print(f"❌ Unified search error: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

def perform_google_search(query):
    """Perform Google Custom Search API for fashion images"""
    try:    
        print(f"🔍 Google Custom Search API for query: '{query}'")
        
        # Check API configuration
        if not GOOGLE_API_KEY:
            print("❌ GOOGLE_API_KEY not configured")
            return []
            
        if not GOOGLE_CSE_ID:
            print("❌ GOOGLE_CSE_ID not configured")
            return []
        
        # Build the Google Custom Search service
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        
        # Detect brand in query and map to official domain
        brand_domains = {
            'nike': 'nike.com',
            'adidas': 'adidas.com',
            'zara': 'zara.com',
            'h&m': 'hm.com',
            'hm': 'hm.com',
            'gap': 'gap.com',
            'uniqlo': 'uniqlo.com',
            'target': 'target.com',
            'walmart': 'walmart.com',
            'amazon': 'amazon.com',
            'levi': 'levi.com',
            'levis': 'levi.com',
            'gucci': 'gucci.com',
            'prada': 'prada.com',
            'versace': 'versace.com',
            'burberry': 'burberry.com',
            'calvin klein': 'calvinklein.com',
            'tommy hilfiger': 'tommy.com',
            'ralph lauren': 'ralphlauren.com',
            'forever 21': 'forever21.com',
            'forever21': 'forever21.com',
            'old navy': 'oldnavy.com',
            'oldnavy': 'oldnavy.com',
            'banana republic': 'bananarepublic.com',
            'j crew': 'jcrew.com',
            'jcrew': 'jcrew.com'
        }
        
        # Check if query contains a brand name
        query_lower = query.lower()
        detected_brand = None
        brand_site = None
        
        for brand, domain in brand_domains.items():
            if brand in query_lower:
                detected_brand = brand
                brand_site = domain
                print(f"🏷️ Brand detected: {brand} → {domain}")
                break
        
        # Construct search query based on brand detection
        if detected_brand and brand_site:
            # If brand is detected, search specifically on that brand's site
            search_query = f"site:{brand_site} {query}"
            print(f"🔍 Brand-specific search: '{search_query}'")
        else:
            # No brand detected, use general fashion search
            search_query = f"{query} clothing fashion"
            print(f"🔍 General fashion search: '{search_query}'")
        
        # Search parameters optimized for fashion images from quality retailers
        search_params = {
            'q': search_query,
            'cx': GOOGLE_CSE_ID,
            'searchType': 'image',  # Image search
            'num': 10,  # Number of results (max 10 per request)
            'imgType': 'photo',  # Photo images (not clipart)
            'imgSize': 'LARGE',  # Changed to LARGE for better quality images
            'safe': 'active',  # Safe search
            'fields': 'items(title,link,image,displayLink,snippet)'  # Only get needed fields
        }
        
        # Perform the search
        print(f"🔍 Calling Google Custom Search API...")
        response = service.cse().list(**search_params).execute()
        
        # Process results
        search_results = []
        items = response.get('items', [])
        
        print(f"🔍 API returned {len(items)} image results")
        
        for i, item in enumerate(items):
            try:
                # Extract image information
                image_info = item.get('image', {})
                
                title = item.get('title', 'Fashion Item')
                image_url = item.get('link')  # Direct image URL
                context_url = image_info.get('contextLink') or item.get('formattedUrl')  # Page URL where image is found
                snippet = item.get('snippet', '')
                source_site = item.get('displayLink', '')
                
                # Validate image URL and source quality
                if not image_url or len(image_url) < 10:
                    continue
                
                # Skip if image is from Google itself
                if 'google' in image_url.lower():
                    continue
                
                # Filter out low-quality sources and non-fashion sites
                excluded_domains = [
                    'ebay', 'vecteezy', 'shutterstock', 'getty', 'alamy', 'depositphotos',
                    'unsplash', 'pexels', 'pixabay', 'cart2india', 'alibaba', 'aliexpress',
                    'pinterest', 'instagram', 'facebook', 'twitter', 'youtube',
                    'modaknits.com'  # This seems to be a blog/info site, not retail
                ]
                
                source_domain = source_site.lower()
                if any(excluded in source_domain for excluded in excluded_domains):
                    print(f"   ❌ Skipping low-quality source: {source_site}")
                    continue
                
                # Prefer established fashion retailers
                preferred_domains = [
                    'target.com', 'walmart.com', 'amazon.com', 'kohls.com', 'macys.com',
                    'nordstrom.com', 'zappos.com', 'asos.com', 'hm.com', 'zara.com',
                    'gap.com', 'oldnavy.com', 'express.com', 'forever21.com',
                    'nike.com', 'adidas.com', 'uniqlo.com', 'jcrew.com', 'bananarepublic.com'
                ]
                
                # Give priority to known fashion retailers
                is_preferred_retailer = any(domain in source_domain for domain in preferred_domains)
                
                search_results.append({
                    'title': title,
                    'image_url': image_url,
                    'page_url': context_url,  # URL of the page containing the image
                    'price': None,  # Custom Search API doesn't provide price directly
                    'store': source_site,
                    'query': query,
                    'snippet': snippet[:100] if snippet else None  # Truncate snippet
                })
                
                print(f"   {i+1}. {title[:50]}... from {source_site}")
                
            except Exception as e:
                print(f"   ❌ Error processing result {i+1}: {e}")
                continue
        
        print(f"🔍 Successfully processed {len(search_results)} valid results")
        
        # If no results from API, return empty list
        if not search_results:
            print("🔍 No valid results from API")
            return []
        
        return search_results
        
    except ImportError as e:
        print(f"❌ Google API client not installed: {e}")
        print("   Please install: pip install google-api-python-client")
        return []
        
    except Exception as e:
        print(f"❌ Google Custom Search API error: {e}")
        return []

def extract_garment_images_from_results(results, query=None):
    """Process and filter search results to extract valid garment images"""
    garment_images = []
    
    # Detect if a brand was mentioned in the query
    detected_brand_domain = None
    if query:
        query_lower = query.lower()
        brand_domains = {
            'nike': 'nike.com',
            'adidas': 'adidas.com',
            'zara': 'zara.com',
            'h&m': 'hm.com',
            'hm': 'hm.com',
            'gap': 'gap.com',
            'uniqlo': 'uniqlo.com',
            'target': 'target.com',
            'walmart': 'walmart.com',
            'amazon': 'amazon.com',
            'levi': 'levi.com',
            'levis': 'levi.com',
            'gucci': 'gucci.com',
            'prada': 'prada.com',
            'versace': 'versace.com'
        }
        
        for brand, domain in brand_domains.items():
            if brand in query_lower:
                detected_brand_domain = domain
                print(f"🏷️ Filtering results for brand: {domain}")
                break
    
    # Define quality criteria for fashion results
    excluded_domains = [
        'ebay', 'vecteezy', 'shutterstock', 'getty', 'alamy', 'depositphotos',
        'unsplash', 'pexels', 'pixabay', 'cart2india', 'alibaba', 'aliexpress',
        'pinterest', 'instagram', 'facebook', 'twitter', 'youtube', 'tiktok',
        'modaknits', 'blog', 'wiki', 'reddit'
    ]
    
    preferred_retailers = [
        'target', 'walmart', 'amazon', 'kohls', 'macys', 'nordstrom', 'zappos',
        'asos', 'hm', 'zara', 'gap', 'oldnavy', 'express', 'forever21',
        'nike', 'adidas', 'uniqlo', 'jcrew', 'bananarepublic', 'loft',
        'anntaylor', 'chicos', 'dressbarn', 'talbots', 'lanebryant'
    ]
    
    for result in results:
        try:
            img_url = result.get('image_url')
            if not img_url:
                continue
            
            title = result.get('title', '').lower()
            store = result.get('store', '').lower()
            
            # If a brand was detected, ONLY include results from that brand's domain
            if detected_brand_domain:
                if detected_brand_domain not in store:
                    print(f"   ❌ Skipping non-brand result: {store} (looking for {detected_brand_domain})")
                    continue
                else:
                    print(f"   ✅ Brand match: {store}")
            
            # Skip excluded domains
            if any(excluded in store for excluded in excluded_domains):
                print(f"   ❌ Skipping excluded domain: {store}")
                continue
            
            # Check for fashion keywords in title
            fashion_keywords = [
                'dress', 'shirt', 'blouse', 'top', 'sweater', 'cardigan', 'jacket', 'coat',
                'pants', 'jeans', 'trousers', 'shorts', 'skirt', 'leggings',
                'shoes', 'sneakers', 'boots', 'sandals', 'heels', 'flats',
                'hoodie', 'sweatshirt', 't-shirt', 'tank', 'camisole',
                'suit', 'blazer', 'vest', 'jumpsuit', 'romper'
            ]
            
            has_fashion_keywords = any(keyword in title for keyword in fashion_keywords)
            is_preferred_retailer = any(retailer in store for retailer in preferred_retailers)
            
            # Filter out non-fashion items
            non_fashion_keywords = ['dog', 'pet', 'vlog', 'filming', 'medium shot', 'handheld', 'stock', 'photo']
            has_non_fashion = any(keyword in title for keyword in non_fashion_keywords)
            
            if has_non_fashion:
                print(f"   ❌ Skipping non-fashion item: {title[:50]}...")
                continue
            
            # Include if it has fashion keywords OR is from a preferred retailer OR brand match
            if has_fashion_keywords or is_preferred_retailer or detected_brand_domain:
                garment_images.append({
                    'id': f"item-{len(garment_images)}",
                    'image_url': img_url,  # For frontend compatibility
                    'src': img_url,  # Alternative field name
                    'title': result.get('title', 'Fashion Item'),
                    'price': result.get('price'),
                    'store': result.get('store'),
                    'source_url': result.get('page_url') or img_url,  # For frontend compatibility
                    'url': result.get('page_url') or img_url  # Alternative field name
                })
                print(f"   ✅ Including: {title[:50]}... from {store}")
            else:
                print(f"   ❌ Skipping non-qualifying item: {title[:50]}... from {store}")
                
        except Exception as e:
            print(f"❌ Error processing search result: {e}")
            continue
    
    print(f"🔍 Final filtered results: {len(garment_images)} valid garment images")
    return garment_images

def generate_fallback_response(message):
    """Generate a fallback response when AI service is unavailable"""
    message_lower = message.lower()
    
    # Simple keyword-based responses
    if any(word in message_lower for word in ['jeans', 'denim']):
        return "I'd recommend looking for slim-fit or straight-leg jeans. Brands like Levis, Zara, and Uniqlo offer great options. What's your preferred fit and color?"
    
    elif any(word in message_lower for word in ['shirt', 'top', 'blouse']):
        return "For shirts and tops, consider the occasion and fit you prefer. Zara and H&M have trendy options, while Uniqlo offers classic styles. What type of shirt are you looking for?"
    
    elif any(word in message_lower for word in ['dress', 'gown']):
        return "Dresses come in many styles! Are you looking for casual, formal, or something in between? Brands like Zara, Mango, and COS have great selections."
    
    elif any(word in message_lower for word in ['shoe', 'sneaker', 'boot']):
        return "For footwear, comfort and style are key. Consider brands like Adidas, Nike for sneakers, or check out Zara for fashion-forward options. What's the occasion?"
    
    elif any(word in message_lower for word in ['jacket', 'coat', 'blazer']):
        return "Outerwear is essential! For blazers, try Zara or COS. For casual jackets, Uniqlo and H&M have good options. What style are you going for?"
    
    else:
        return "I'd love to help you find the perfect garment! Could you tell me more specifics about what you're looking for? (type, color, brand preferences, occasion, etc.)"

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Starting Flask Server")
    print("=" * 50)
    print(f"📝 Environment Variables Check:")
    print(f"   GEMINI_API_KEY: {'✅ Configured' if GEMINI_API_KEY else '❌ Missing'}")
    if GEMINI_API_KEY:
        print(f"   GEMINI_API_KEY Preview: {GEMINI_API_KEY[:10]}...")
    print(f"   MYSQL_HOST: {MYSQL_HOST}")
    print(f"   MYSQL_USER: {MYSQL_USER}")
    print(f"   MYSQL_DATABASE: {MYSQL_DATABASE}")
    
    print(f"\n🔧 Python Configuration:")
    import sys
    print(f"   Python Version: {sys.version}")
    print(f"   Python Executable: {sys.executable}")
    
    print(f"\n📦 Module Check:")
    try:
        from google import genai as test_genai
        print(f"   google.genai: ✅ Available")
    except ImportError as e:
        print(f"   google.genai: ❌ Import Error - {e}")
    
    # PIL not required for current functionality
    # try:
    #     from PIL import Image as test_image
    #     print(f"   PIL (Pillow): ✅ Available")
    # except ImportError as e:
    #     print(f"   PIL (Pillow): ❌ Import Error - {e}")
    
    try:
        import mysql.connector as test_mysql
        print(f"   mysql.connector: ✅ Available")
    except ImportError as e:
        print(f"   mysql.connector: ❌ Import Error - {e}")
    
    print("=" * 50)
    print("🌐 Starting server on http://0.0.0.0:5000")
    print("🎯 Gemini Try-On API: /api/tryon-gemini")
    print("👔 Multi-Garment Try-On API: /api/tryon-gemini-multi")
    print("�️ Remove Person Background API: /api/remove-person-bg")
    print("🖼️  Remove Background (Rembg) API: /api/remove-bg-rembg")
    print("�🔍🤖 Unified Search API: /api/unified-search")
    print("💬 Chat Assistant API: /api/chat")
    print("🧪 Gemini Test API: /api/gemini/test")
    print("=" * 50)
    
    app.run(debug=True, host="0.0.0.0", port=5000)