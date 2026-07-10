"""
AI Conversation and Intent Engine for Garment Discovery.
Leverages Gemini LLM with structured prompts and a rich, context-aware rule-based fashion agent fallback.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Flag to disable Gemini calls if API key is invalid
_GEMINI_DISABLED = False

class ConversationalAIEngine:
    """
    Conversational agent engine that parses intent, extracts preferences,
    generates responses, asks clarifying questions, and recommends follow-up options.
    """

    @staticmethod
    def process_message(
        user_message: str,
        history: List[Dict[str, Any]],
        current_preferences: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for processing a conversational user turn.
        """
        gemini_key = os.environ.get('GEMINI_API_KEY', '') or GEMINI_API_KEY
        # Try LLM first if API key is present and valid
        if gemini_key and not gemini_key.startswith("YOUR_") and gemini_key != "placeholder":
            try:
                result = ConversationalAIEngine._call_gemini_llm(
                    user_message, history, current_preferences, user_profile
                )
                if result:
                    return result
            except Exception as e:
                print(f"[GarmentDiscovery][AIEngine] Gemini LLM warning: {e}. Using fallback rule engine.")

        # Enhanced Context-Aware Fashion Assistant Engine
        return ConversationalAIEngine._fallback_rule_engine(
            user_message, history, current_preferences, user_profile
        )

    @staticmethod
    def _call_gemini_llm(
        user_message: str,
        history: List[Dict[str, Any]],
        current_preferences: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Invoke Gemini LLM with JSON schema system instructions.
        """
        try:
            import google.genai as genai
            from google.genai import types

            gemini_key = os.environ.get('GEMINI_API_KEY', '') or GEMINI_API_KEY
            if not gemini_key:
                return None

            # Temporarily set GOOGLE_API_KEY in os.environ to gemini_key while instantiating client
            # so google.genai SDK uses GEMINI_API_KEY instead of any personal GOOGLE_API_KEY
            old_google_key = os.environ.get('GOOGLE_API_KEY')
            try:
                os.environ['GOOGLE_API_KEY'] = gemini_key
                client = genai.Client(api_key=gemini_key)
            finally:
                if old_google_key is not None:
                    os.environ['GOOGLE_API_KEY'] = old_google_key
                else:
                    os.environ.pop('GOOGLE_API_KEY', None)
            
            profile_context = ""
            if user_profile:
                profile_context = f"User Profile: Gender={user_profile.get('gender')}, Height={user_profile.get('height')}, Chest={user_profile.get('chest')}, Waist={user_profile.get('waist')}"

            formatted_history = []
            for msg in history[-6:]:  # Last 6 messages for turn context
                role = "user" if msg.get('sender') == 'user' else "model"
                formatted_history.append(f"{role.upper()}: {msg.get('content')}")
            
            history_str = "\n".join(formatted_history)

            system_instruction = f"""
You are an expert AI fashion stylist and conversational garment discovery assistant.
Your goal is to understand what garment/outfit the user is looking for through natural conversation.
Gather preferences such as: category (e.g. blazer, dress, trousers, shirt, hoodie, jeans, t-shirt), gender, color, budget (max_price), brand, style (casual, formal, boho, streetwear), material (linen, cotton, denim, silk, wool), occasion (wedding, party, workout, beach), size, and fit.

Whenever the user asks to see or search for garments, USE GoogleSearch to find 3-4 specific individual product items currently for sale on major e-commerce fashion stores (such as Zara, H&M, ASOS, Mango, Levi's, Nike). Populate `live_garments` with exact item titles, brand names, numeric prices, and direct store product page URLs (e.g. `zara.com/us/en/...`, `hm.com/en_us/productpage...`). Exclude general brand homepages, sustainability blog posts, or store indexes.

Current preferences already gathered: {json.dumps(current_preferences)}
{profile_context}

Respond in STRICT JSON format with the following keys:
{{
  "intent": "gather_info" | "search_garments" | "refine_search" | "chitchat",
  "reply_text": "Friendly conversational message to user, giving styling guidance or asking 1 clear follow-up question.",
  "extracted_preferences": {{
      "category": string or null,
      "subcategory": string or null,
      "gender": "men" | "women" | "unisex" | null,
      "color": string or null,
      "max_price": float or null,
      "min_price": float or null,
      "brand": string or null,
      "style": string or null,
      "material": string or null,
      "occasion": string or null,
      "size": string or null,
      "fit": string or null
  }},
  "ready_to_search": boolean (Set to TRUE ALWAYS whenever any garment category, brand, style, color, price, gender, or garment request is mentioned so search results are returned immediately),
  "search_query": "Optimized search query string for e-commerce catalog",
  "live_garments": [
    {{
      "title": "Exact product title e.g. 100% Linen Regular Fit Shirt",
      "brand": "Brand name e.g. Zara, H&M, ASOS, Mango",
      "price": 49.90,
      "url": "Direct e-commerce product page URL e.g. https://www.zara.com/us/en/100--linen-regular-fit-shirt-p05204021500.html",
      "color": "Color of garment"
    }}
  ],
  "suggested_followups": ["Option 1", "Option 2", "Option 3"]
}}
"""

            prompt = f"{system_instruction}\n\nRecent History:\n{history_str}\n\nUSER LATEST MESSAGE: {user_message}"

            config = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            )

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=config
            )

            if response and response.text:
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                res_json = json.loads(json_match.group(0)) if json_match else json.loads(response.text)
                
                # Merge deterministic NLU rules to guarantee subcategory/category/color precision
                try:
                    rule_res = ConversationalAIEngine._fallback_rule_engine(user_message, history, current_preferences, user_profile)
                    if isinstance(res_json.get('extracted_preferences'), dict):
                        rule_prefs = rule_res.get('extracted_preferences', {})
                        for k, v in rule_prefs.items():
                            if v and not res_json['extracted_preferences'].get(k):
                                res_json['extracted_preferences'][k] = v
                        color_val = res_json['extracted_preferences'].get('color')
                        if color_val and isinstance(color_val, str):
                            res_json['extracted_preferences']['color'] = color_val.capitalize()
                except Exception:
                    pass
                    
                return res_json
        except Exception as e:
            print(f"[GarmentDiscovery][Gemini] Warning: {e}")
            return None

    @staticmethod
    def _fallback_rule_engine(
        user_message: str,
        history: List[Dict[str, Any]],
        current_preferences: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Advanced, Context-Aware Fashion NLU Assistant Engine.
        """
        msg_lower = user_message.lower().strip()
        new_prefs = dict(current_preferences)

        # Handle Greetings / Chitchat
        is_greeting = any(re.search(r'\b' + word + r'\b', msg_lower) for word in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon"])
        if is_greeting and len(msg_lower.split()) <= 3:
            return {
                "intent": "chitchat",
                "reply_text": "Hello! I'm your AI personal fashion stylist. I can help you discover outfits, blazers, dresses, jeans, or shirts tailored to your taste, budget, and occasion. What are you looking for today?",
                "extracted_preferences": new_prefs,
                "ready_to_search": False,
                "search_query": "",
                "suggested_followups": ["Black Blazers", "Summer Linen Shirts", "Casual Hoodies", "Elegant Dresses"]
            }

        # 1. Category and Subcategory Extraction
        categories = {
            "blazer": ("Upper body", "Blazers & Jackets"),
            "blazers": ("Upper body", "Blazers & Jackets"),
            "suit jacket": ("Upper body", "Blazers & Jackets"),
            "tuxedo": ("Upper body", "Blazers & Jackets"),
            "jacket": ("Upper body", "Jackets"),
            "jackets": ("Upper body", "Jackets"),
            "leather jacket": ("Upper body", "Jackets"),
            "denim jacket": ("Upper body", "Jackets"),
            "trouser": ("Lower body", "Trousers"),
            "trousers": ("Lower body", "Trousers"),
            "pant": ("Lower body", "Trousers"),
            "pants": ("Lower body", "Trousers"),
            "chinos": ("Lower body", "Trousers"),
            "jean": ("Lower body", "Jeans"),
            "jeans": ("Lower body", "Jeans"),
            "dress": ("Dresses", "Midi Dresses"),
            "dresses": ("Dresses", "Midi Dresses"),
            "gown": ("Dresses", "Evening Dresses"),
            "shirt": ("Upper body", "Shirts"),
            "shirts": ("Upper body", "Shirts"),
            "button-down": ("Upper body", "Shirts"),
            "t-shirt": ("Upper body", "T-Shirts"),
            "t-shirts": ("Upper body", "T-Shirts"),
            "tee": ("Upper body", "T-Shirts"),
            "tees": ("Upper body", "T-Shirts"),
            "hoodie": ("Upper body", "Hoodies & Sweatshirts"),
            "hoodies": ("Upper body", "Hoodies & Sweatshirts"),
            "sweatshirt": ("Upper body", "Hoodies & Sweatshirts"),
            "sweatshirts": ("Upper body", "Hoodies & Sweatshirts"),
            "suit": ("Upper body", "Suits & Blazers")
        }

        found_category = False
        for kw, (cat, subcat) in categories.items():
            if re.search(r'\b' + re.escape(kw) + r'\b', msg_lower):
                new_prefs['category'] = cat
                new_prefs['subcategory'] = subcat
                found_category = True
                break

        # Generic clothing request (e.g. "show me black clothes" or "outfit")
        is_generic_clothing = any(word in msg_lower for word in ["clothes", "clothing", "outfit", "attire", "wear", "items", "stuff"])

        # 2. Price Extraction
        price_match = re.search(r'(?:under|below|less than|max|cheaper than|\$)\s*(\d+)', msg_lower)
        if price_match:
            try:
                new_prefs['max_price'] = float(price_match.group(1))
            except ValueError:
                pass

        # 3. Refinement: "different_color" or "different color" or "another color"
        is_refine_color = any(phrase in msg_lower for phrase in ["different color", "different_color", "another color", "other colors", "change color", "different colors"])
        if is_refine_color:
            current_color = new_prefs.pop('color', None)
            if current_color:
                excluded = new_prefs.get('excluded_colors', [])
                if current_color not in excluded:
                    excluded.append(current_color)
                new_prefs['excluded_colors'] = excluded

        # 4. Color Extraction
        colors = [
            "black", "white", "beige", "navy", "blue", "sage green", "green",
            "emerald green", "yellow", "pink", "red", "grey", "gray", "olive", "charcoal", "brown", "ecru"
        ]
        for color in colors:
            if re.search(r'\b' + re.escape(color) + r'\b', msg_lower):
                new_prefs['color'] = color.title()
                # Clear exclusion if user explicitly picks a new color
                new_prefs.pop('excluded_colors', None)
                break

        # 5. Gender Extraction
        if any(re.search(r'\b' + w + r'\b', msg_lower) for w in ["women", "woman", "female", "ladies", "girls", "womens"]):
            new_prefs['gender'] = "women"
        elif any(re.search(r'\b' + w + r'\b', msg_lower) for w in ["men", "man", "male", "guys", "boys", "mens"]):
            new_prefs['gender'] = "men"
        elif user_profile and user_profile.get('gender') and 'gender' not in new_prefs:
            new_prefs['gender'] = user_profile.get('gender')

        # 6. Brand Extraction
        brands = ["zara", "asos", "h&m", "nike", "levi's", "levis", "uniqlo", "mango"]
        for b in brands:
            if b in msg_lower:
                new_prefs['brand'] = b.title()
                break

        # 7. Material / Occasion / Style
        materials = ["linen", "cotton", "denim", "silk", "wool", "fleece", "satin", "viscose", "leather"]
        for m in materials:
            if m in msg_lower:
                new_prefs['material'] = m.capitalize()

        occasions = ["wedding", "beach", "party", "formal", "casual", "gym", "work", "prom", "date night", "vacation", "gala", "office"]
        for o in occasions:
            if o in msg_lower:
                new_prefs['occasion'] = o.capitalize()

        styles = ["formal", "casual", "smart casual", "streetwear", "athleisure", "boho", "minimalist", "edgy"]
        for s in styles:
            if s in msg_lower:
                new_prefs['style'] = s.title()

        # Check Refinements
        is_refinement = is_refine_color or any(w in msg_lower for w in ["cheaper", "different", "another", "instead", "other", "lower price", "refine"])

        has_category = bool(new_prefs.get('category'))
        has_color = bool(new_prefs.get('color'))
        has_price = bool(new_prefs.get('max_price'))
        has_brand = bool(new_prefs.get('brand'))
        has_gender = bool(new_prefs.get('gender'))
        has_style = bool(new_prefs.get('style'))
        has_occasion = bool(new_prefs.get('occasion'))
        has_material = bool(new_prefs.get('material'))

        # Search is triggered for any non-greeting fashion prompt
        ready_to_search = not is_greeting or has_category or has_color or has_price or has_brand or has_gender or has_style or has_occasion or has_material or is_generic_clothing or is_refinement

        # Intent classification
        if is_refinement:
            intent = "refine_search"
        elif has_category or is_generic_clothing:
            intent = "search_garments"
        else:
            intent = "gather_info"

        # Build Dynamic Response Text & Follow-up options
        if is_refine_color:
            cat_label = new_prefs.get('subcategory') or new_prefs.get('category') or "garments"
            reply_text = f"Showing stylish alternative color options for {cat_label} (such as Beige, Navy, and Sage Green)!"
            suggested_followups = ["Show under $50", "Show Zara items", "Filter for formal", "Show black again"]
        elif not has_category and has_color and not is_generic_clothing:
            reply_text = f"I've noted you're looking for {new_prefs.get('color')} items! What kind of garment would you like to see (e.g. blazer, trousers, dress, shirt, hoodie)?"
            suggested_followups = [f"{new_prefs.get('color')} Blazer", f"{new_prefs.get('color')} Trousers", f"{new_prefs.get('color')} Dress", f"{new_prefs.get('color')} Shirt"]
        elif not has_category and is_generic_clothing:
            color_str = f" in {new_prefs.get('color')}" if has_color else ""
            reply_text = f"Here are top popular clothing items{color_str}! You can tell me if you'd like to narrow down to blazers, dresses, trousers, or shirts."
            suggested_followups = ["Show Blazers", "Show Dresses", "Show Trousers", "Under $50"]
        elif has_category:
            cat_label = new_prefs.get('subcategory') or new_prefs.get('category')
            color_clause = f" in {new_prefs.get('color')}" if new_prefs.get('color') else ""
            price_clause = f" under ${new_prefs.get('max_price')}" if has_price else ""
            brand_clause = f" from {new_prefs.get('brand')}" if new_prefs.get('brand') else ""

            reply_text = f"Here are the top garments matching your request for {cat_label}{color_clause}{price_clause}{brand_clause}. You can click any item to view product details or start a virtual try-on!"

            if not has_price:
                suggested_followups = ["Show under $50", "Show under $100", "Try a different color", "Show another brand"]
            else:
                suggested_followups = ["Show cheaper options", "Try a different color", "Show another brand", "Filter for casual style"]
        else:
            reply_text = "I'd love to help you discover the perfect outfit! What kind of garment are you looking for today (e.g. blazer, dress, trousers, shirt, hoodie, jeans)?"
            suggested_followups = ["Black Blazer", "Summer Linen Shirt", "Casual Hoodie", "Elegant Dress"]

        search_query = f"{new_prefs.get('color', '')} {new_prefs.get('brand', '')} {new_prefs.get('subcategory', new_prefs.get('category', ''))}".strip()

        return {
            "intent": intent,
            "reply_text": reply_text,
            "extracted_preferences": new_prefs,
            "ready_to_search": ready_to_search,
            "search_query": search_query or user_message,
            "suggested_followups": suggested_followups
        }
