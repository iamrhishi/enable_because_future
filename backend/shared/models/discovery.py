"""
Discovery models for persistent conversational session state and dialogue history.
"""

import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from shared.database import db_manager

class DiscoverySession:
    """
    Data model representing a user's conversational garment discovery session.
    """
    def __init__(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        status: str = 'active',
        title: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        id: Optional[int] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        **kwargs
    ):
        self.id = id
        self.session_id = session_id
        self.user_id = user_id
        self.status = status
        self.title = title or "Garment Discovery Session"
        self.preferences = preferences if preferences is not None else {}
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "status": self.status,
            "title": self.title,
            "preferences": self.preferences,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }

    @classmethod
    def create(cls, user_id: Optional[str] = None, title: Optional[str] = None, initial_preferences: Optional[Dict[str, Any]] = None) -> 'DiscoverySession':
        session_id = str(uuid.uuid4())
        prefs_json = json.dumps(initial_preferences or {})
        title = title or "New Garment Search"
        
        db_manager.execute_query(
            """
            INSERT INTO discovery_sessions (session_id, user_id, status, title, preferences_json, created_at, updated_at)
            VALUES (?, ?, 'active', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (session_id, user_id, title, prefs_json)
        )
        return cls.get_by_session_id(session_id)

    @classmethod
    def get_by_session_id(cls, session_id: str) -> Optional['DiscoverySession']:
        row = db_manager.execute_query(
            "SELECT * FROM discovery_sessions WHERE session_id = ?",
            (session_id,),
            fetch_one=True
        )
        if not row:
            return None
        
        try:
            prefs = json.loads(row.get('preferences_json') or '{}')
        except Exception:
            prefs = {}

        return cls(
            id=row.get('id'),
            session_id=row.get('session_id'),
            user_id=row.get('user_id'),
            status=row.get('status'),
            title=row.get('title'),
            preferences=prefs,
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

    @classmethod
    def get_user_sessions(cls, user_id: str, limit: int = 20) -> List['DiscoverySession']:
        rows = db_manager.execute_query(
            "SELECT * FROM discovery_sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
            fetch_all=True
        )
        sessions = []
        for r in (rows or []):
            try:
                prefs = json.loads(r.get('preferences_json') or '{}')
            except Exception:
                prefs = {}
            sessions.append(cls(
                id=r.get('id'),
                session_id=r.get('session_id'),
                user_id=r.get('user_id'),
                status=r.get('status'),
                title=r.get('title'),
                preferences=prefs,
                created_at=r.get('created_at'),
                updated_at=r.get('updated_at')
            ))
        return sessions

    def update_preferences(self, new_prefs: Dict[str, Any], title: Optional[str] = None) -> None:
        merged_prefs = {**self.preferences, **new_prefs}
        # Clean null values if explicitly passed as empty string
        for k, v in list(merged_prefs.items()):
            if v is None or v == "":
                pass  # Keep valid preference entries
        
        self.preferences = merged_prefs
        if title:
            self.title = title

        db_manager.execute_query(
            """
            UPDATE discovery_sessions
            SET preferences_json = ?, title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
            """,
            (json.dumps(self.preferences), self.title, self.session_id)
        )

    def delete(self) -> None:
        db_manager.execute_query(
            "DELETE FROM discovery_messages WHERE session_id = ?",
            (self.session_id,)
        )
        db_manager.execute_query(
            "DELETE FROM discovery_sessions WHERE session_id = ?",
            (self.session_id,)
        )


class DiscoveryMessage:
    """
    Data model representing an individual message in a discovery dialogue.
    """
    def __init__(
        self,
        session_id: str,
        sender: str,
        content: str,
        garments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[int] = None,
        created_at: Optional[str] = None
    ):
        self.id = id
        self.session_id = session_id
        self.sender = sender
        self.content = content
        self.garments = garments or []
        self.metadata = metadata or {}
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "sender": self.sender,
            "content": self.content,
            "garments": self.garments,
            "metadata": self.metadata,
            "created_at": str(self.created_at) if self.created_at else None,
        }

    @classmethod
    def create(
        cls,
        session_id: str,
        sender: str,
        content: str,
        garments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'DiscoveryMessage':
        garments_json = json.dumps(garments or [])
        metadata_json = json.dumps(metadata or {})

        message_id = db_manager.get_lastrowid(
            """
            INSERT INTO discovery_messages (session_id, sender, content, garments_json, metadata_json, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (session_id, sender, content, garments_json, metadata_json)
        )

        # Touch session updated_at
        db_manager.execute_query(
            "UPDATE discovery_sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
            (session_id,)
        )

        return cls(
            id=message_id,
            session_id=session_id,
            sender=sender,
            content=content,
            garments=garments,
            metadata=metadata
        )

    @classmethod
    def get_history_for_session(cls, session_id: str, limit: int = 50) -> List['DiscoveryMessage']:
        rows = db_manager.execute_query(
            "SELECT * FROM discovery_messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, limit),
            fetch_all=True
        )
        messages = []
        for r in (rows or []):
            try:
                garments = json.loads(r.get('garments_json') or '[]')
            except Exception:
                garments = []
            try:
                meta = json.loads(r.get('metadata_json') or '{}')
            except Exception:
                meta = {}
            messages.append(cls(
                id=r.get('id'),
                session_id=r.get('session_id'),
                sender=r.get('sender'),
                content=r.get('content'),
                garments=garments,
                metadata=meta,
                created_at=r.get('created_at')
            ))
        return messages
