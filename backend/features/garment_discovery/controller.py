"""
API Blueprint for Conversational Garment Discovery.
Endpoints:
- POST   /api/garment-discovery/chat
- POST   /api/garment-discovery/sessions
- GET    /api/garment-discovery/sessions
- GET    /api/garment-discovery/sessions/<session_id>
- DELETE /api/garment-discovery/sessions/<session_id>
- POST   /api/garment-discovery/refine
"""

import json
from flask import Blueprint, request, jsonify, Response, stream_with_context
from shared.models.discovery import DiscoverySession, DiscoveryMessage
from shared.middleware import optional_auth
from shared.response import server_error_response
from shared.logger import logger
from features.garment_discovery.ai_engine import ConversationalAIEngine
from features.garment_discovery.search_service import GarmentSearchService

garment_discovery_bp = Blueprint('garment_discovery', __name__, url_prefix='/api/garment-discovery')

def _get_request_user_id() -> str:
    """
    Resolve the effective user_id for this request. A verified JWT (set by
    @optional_auth on request.user_id) always wins over anything client-
    supplied - otherwise a logged-in caller could pass someone else's
    user_id in the body/header and read or delete their discovery sessions.
    Falls back to a client-supplied id (for guest/pre-signup usage) or
    'guest' if nothing is present at all.
    """
    verified_user_id = getattr(request, 'user_id', None)
    if verified_user_id:
        return verified_user_id

    user_id = request.headers.get('X-User-ID')
    if user_id:
        return user_id

    if request.is_json and request.get_json(silent=True):
        user_id = request.get_json(silent=True).get('user_id')
        if user_id:
            return user_id

    return 'guest'


@garment_discovery_bp.route('/sessions', methods=['POST'])
@optional_auth
def create_session():
    """Start a new conversational discovery session."""
    try:
        data = request.get_json() or {}
        user_id = _get_request_user_id()
        title = data.get('title', 'New Garment Discovery')
        initial_preferences = data.get('initial_preferences', {})

        session = DiscoverySession.create(
            user_id=user_id,
            title=title,
            initial_preferences=initial_preferences
        )

        # Initial assistant greeting
        welcome_msg = "Hello! I am your AI fashion discovery assistant. What type of garment or outfit are you looking for today?"
        DiscoveryMessage.create(
            session_id=session.session_id,
            sender='assistant',
            content=welcome_msg,
            metadata={"suggested_followups": ["Summer Linen Blazer", "Casual Hoodie", "Formal Wedding Dress", "Denim Jacket"]}
        )

        return jsonify({
            "success": True,
            "session": session.to_dict(),
            "welcome_message": welcome_msg
        }), 201
    except Exception as e:
        logger.exception(f"garment_discovery: Request failed: {str(e)}")
        return server_error_response(e, context="Garment discovery request failed")


@garment_discovery_bp.route('/sessions', methods=['GET'])
@optional_auth
def list_sessions():
    """List active and past sessions for user."""
    try:
        user_id = _get_request_user_id()
        sessions = DiscoverySession.get_user_sessions(user_id=user_id)
        return jsonify({
            "success": True,
            "sessions": [s.to_dict() for s in sessions]
        }), 200
    except Exception as e:
        logger.exception(f"garment_discovery: Request failed: {str(e)}")
        return server_error_response(e, context="Garment discovery request failed")


@garment_discovery_bp.route('/sessions/<session_id>', methods=['GET'])
@optional_auth
def get_session(session_id):
    """Fetch session context, preference slots, and message history."""
    try:
        session = DiscoverySession.get_by_session_id(session_id)
        if not session:
            return jsonify({"success": False, "error": "Discovery session not found"}), 404

        history = DiscoveryMessage.get_history_for_session(session_id)
        return jsonify({
            "success": True,
            "session": session.to_dict(),
            "history": [m.to_dict() for m in history]
        }), 200
    except Exception as e:
        logger.exception(f"garment_discovery: Request failed: {str(e)}")
        return server_error_response(e, context="Garment discovery request failed")


@garment_discovery_bp.route('/sessions/<session_id>', methods=['DELETE'])
@optional_auth
def delete_session(session_id):
    """Delete a discovery session and its history."""
    try:
        session = DiscoverySession.get_by_session_id(session_id)
        if not session:
            return jsonify({"success": False, "error": "Discovery session not found"}), 404

        session.delete()
        return jsonify({
            "success": True,
            "message": "Session deleted successfully"
        }), 200
    except Exception as e:
        logger.exception(f"garment_discovery: Request failed: {str(e)}")
        return server_error_response(e, context="Garment discovery request failed")


@garment_discovery_bp.route('/chat/stream', methods=['POST'])
@garment_discovery_bp.route('/chat', methods=['POST'])
@optional_auth
def chat():
    """
    Conversational turn endpoint with optional SSE streaming.
    Supports standard JSON response or Server-Sent Events (SSE) streaming when calling
    /chat/stream or passing ?stream=true.
    """
    try:
        data = request.get_json() or {}
        user_message = data.get('message', '').strip()
        session_id = data.get('session_id')
        user_id = _get_request_user_id()
        is_stream = request.args.get('stream') == 'true' or request.path.endswith('/stream') or data.get('stream') == True

        if not user_message:
            return jsonify({"success": False, "error": "Message content is required"}), 400

        # Retrieve existing session or create a new one
        session = None
        if session_id:
            session = DiscoverySession.get_by_session_id(session_id)

        if not session:
            session = DiscoverySession.create(
                user_id=user_id,
                title=user_message[:30] + ("..." if len(user_message) > 30 else "")
            )

        # Apply any explicit preference overrides passed in request
        if data.get('preferences_override'):
            session.update_preferences(data.get('preferences_override'))

        # Fetch conversation history
        history = DiscoveryMessage.get_history_for_session(session.session_id)
        history_dicts = [m.to_dict() for m in history]

        # Record user message in DB
        DiscoveryMessage.create(
            session_id=session.session_id,
            sender='user',
            content=user_message
        )

        if is_stream:
            def generate_sse():
                # 1. Yield initial session context immediately (0 ms)
                yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id, 'preferences': session.preferences})}\n\n"

                # 2. Fast AI processing (< 300 ms)
                ai_result = ConversationalAIEngine.process_message(
                    user_message=user_message,
                    history=history_dicts,
                    current_preferences=session.preferences,
                    user_profile={"user_id": user_id}
                )

                # Update session preferences
                extracted_prefs = ai_result.get('extracted_preferences', {})
                session.update_preferences(extracted_prefs)

                # 3. Yield assistant text message immediately (< 300 ms)
                reply_text = ai_result.get('reply_text', '')
                yield f"data: {json.dumps({'type': 'text', 'content': reply_text})}\n\n"

                # 4. Stream garments progressively as discovered/scraped
                discovered_garments = []
                if ai_result.get('ready_to_search') or ai_result.get('intent') in ['search_garments', 'refine_search']:
                    flash_garments = ai_result.get('live_garments', [])
                    for garment in GarmentSearchService.search_garments_stream(session.preferences, limit=6, flash_garments=flash_garments):
                        discovered_garments.append(garment)
                        yield f"data: {json.dumps({'type': 'garment', 'garment': garment})}\n\n"

                # 5. Save to database
                assistant_msg = DiscoveryMessage.create(
                    session_id=session.session_id,
                    sender='assistant',
                    content=reply_text,
                    garments=discovered_garments,
                    metadata={
                        "intent": ai_result.get('intent'),
                        "suggested_followups": ai_result.get('suggested_followups', []),
                        "search_query": ai_result.get('search_query', '')
                    }
                )

                # 6. Yield completion event
                yield f"data: {json.dumps({'type': 'done', 'message_id': assistant_msg.id, 'suggested_followups': ai_result.get('suggested_followups', [])})}\n\n"

            return Response(stream_with_context(generate_sse()), mimetype='text/event-stream')

        # Standard non-streaming REST Response
        ai_result = ConversationalAIEngine.process_message(
            user_message=user_message,
            history=history_dicts,
            current_preferences=session.preferences,
            user_profile={"user_id": user_id}
        )
        session.update_preferences(ai_result.get('extracted_preferences', {}))

        discovered_garments = []
        if ai_result.get('ready_to_search') or ai_result.get('intent') in ['search_garments', 'refine_search']:
            flash_garments = ai_result.get('live_garments', [])
            discovered_garments = GarmentSearchService.search_garments(session.preferences, limit=6, flash_garments=flash_garments)

        # Record assistant message in DB
        assistant_msg = DiscoveryMessage.create(
            session_id=session.session_id,
            sender='assistant',
            content=ai_result.get('reply_text', ''),
            garments=discovered_garments,
            metadata={
                "intent": ai_result.get('intent'),
                "suggested_followups": ai_result.get('suggested_followups', []),
                "search_query": ai_result.get('search_query', '')
            }
        )

        return jsonify({
            "success": True,
            "session_id": session.session_id,
            "preferences": session.preferences,
            "message": assistant_msg.to_dict(),
            "garments": discovered_garments,
            "suggested_followups": ai_result.get('suggested_followups', []),
            "intent": ai_result.get('intent')
        }), 200

    except Exception as e:
        logger.exception(f"garment_discovery: Request failed: {str(e)}")
        return server_error_response(e, context="Garment discovery request failed")


@garment_discovery_bp.route('/refine', methods=['POST'])
@optional_auth
def refine():
    """
    Refinement endpoint for quick preference tweaks:
    Body:
    {
       "session_id": "uuid",
       "refinement_type": "cheaper" | "different_color" | "different_brand" | "different_style",
       "value": "optional specific value"
    }
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        refinement_type = data.get('refinement_type')
        value = data.get('value')

        if not session_id or not refinement_type:
            return jsonify({"success": False, "error": "session_id and refinement_type are required"}), 400

        session = DiscoverySession.get_by_session_id(session_id)
        if not session:
            return jsonify({"success": False, "error": "Discovery session not found"}), 404

        prefs = dict(session.preferences)
        refine_prompt = ""

        if refinement_type == "cheaper":
            current_max = prefs.get('max_price', 100)
            new_max = max(20, round(float(current_max) * 0.75, 2))
            prefs['max_price'] = new_max
            refine_prompt = f"Show me cheaper options under ${new_max}"

        elif refinement_type == "different_color":
            old_color = prefs.pop('color', None)
            if value:
                prefs['color'] = value
                prefs.pop('excluded_colors', None)
                refine_prompt = f"Show me options in {value}"
            else:
                if old_color:
                    excluded = list(prefs.get('excluded_colors', []))
                    if old_color not in excluded:
                        excluded.append(old_color)
                    prefs['excluded_colors'] = excluded
                refine_prompt = "Show me different color options"

        elif refinement_type == "different_brand":
            if value:
                prefs['brand'] = value
                refine_prompt = f"Show me garments from {value}"
            else:
                prefs.pop('brand', None)
                refine_prompt = "Show me garments from another brand"

        elif refinement_type == "different_style":
            if value:
                prefs['style'] = value
                refine_prompt = f"Show me {value} style options"

        session.update_preferences(prefs)

        # Search new garments
        garments = GarmentSearchService.search_garments(session.preferences, limit=6)

        reply_text = f"Updated your preference recommendations: {refine_prompt}."
        assistant_msg = DiscoveryMessage.create(
            session_id=session.session_id,
            sender='assistant',
            content=reply_text,
            garments=garments,
            metadata={"refinement_type": refinement_type}
        )

        return jsonify({
            "success": True,
            "session_id": session.session_id,
            "preferences": session.preferences,
            "message": assistant_msg.to_dict(),
            "garments": garments
        }), 200

    except Exception as e:
        logger.exception(f"garment_discovery: Request failed: {str(e)}")
        return server_error_response(e, context="Garment discovery request failed")


@garment_discovery_bp.route('/resolve-image', methods=['POST'])
@optional_auth
def resolve_image():
    """
    Lazy-load image resolution endpoint.
    Allows frontend to resolve images asynchronously for each card.
    Body:
    {
       "url": "https://www.zara.com/...",
       "category": "Shirts",
       "color": "pink"
    }
    """
    try:
        data = request.get_json() or {}
        url = data.get('url')
        category = data.get('category', 'Shirts')
        color = data.get('color', '')

        if not url or url == '#':
            return jsonify({"success": False, "error": "Valid URL is required"}), 400

        img_url = GarmentSearchService._resolve_product_image_from_url(url)
        
        # If scraping failed, use the color-aware placeholder
        from features.garment_discovery.search_service import get_color_aware_photo
        if not img_url:
            img_url = get_color_aware_photo(category, color)

        return jsonify({
            "success": True,
            "url": url,
            "image_url": img_url
        }), 200
    except Exception as e:
        logger.exception(f"garment_discovery: Request failed: {str(e)}")
        return server_error_response(e, context="Garment discovery request failed")
