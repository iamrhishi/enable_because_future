"""
Database abstraction layer for becauseFuture backend.

Supports SQLite (local dev, default) and Postgres/Cloud SQL (when DATABASE_URL
is set) through the same interface. All database operations should go through
this class - callers write '?' placeholders as before; Postgres translation
happens transparently here.
"""

import os
import sqlite3
import datetime
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from dotenv import load_dotenv  # type: ignore

load_dotenv()


class DatabaseManager:
    """
    Database abstraction class. Backed by SQLite unless DATABASE_URL is set,
    in which case it connects to Postgres (e.g. Cloud SQL) instead.
    All database operations should use this class.
    """

    def __init__(self, db_path: str = None, database_url: str = None):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file (defaults to DATABASE_PATH env var or 'database.db')
            database_url: Postgres DSN (defaults to DATABASE_URL env var). When set, Postgres is used
                instead of SQLite - e.g. 'postgresql://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE'
        """
        self.database_url = database_url if database_url is not None else os.environ.get('DATABASE_URL', '')
        self.db_type = 'postgres' if self.database_url else 'sqlite'
        self.db_path = db_path or os.environ.get('DATABASE_PATH', 'database.db')

    def _get_connection(self):
        """
        Get a database connection with dictionary-like row access.

        Returns:
            sqlite3.Connection (row_factory=Row) or psycopg2 connection, depending on db_type
        """
        if self.db_type == 'postgres':
            import psycopg2
            conn = psycopg2.connect(self.database_url)
            return conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dictionary-like access
            conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
            return conn

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections
        Ensures proper cleanup and transaction handling

        Usage:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                result = cursor.fetchone()
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _cursor(self, conn):
        """Get a cursor that returns dict-like rows for the active engine."""
        if self.db_type == 'postgres':
            from psycopg2.extras import RealDictCursor
            return conn.cursor(cursor_factory=RealDictCursor)
        return conn.cursor()

    def _adapt(self, query: str) -> str:
        """Translate SQLite '?' placeholders to Postgres '%s' when needed."""
        if self.db_type == 'postgres':
            return query.replace('?', '%s')
        return query

    @staticmethod
    def _normalize_row(row: dict) -> dict:
        """
        Normalize a Postgres row to match SQLite's wire format, so API
        responses are identical regardless of which engine is behind them.

        Postgres has real BOOLEAN/DATE/TIMESTAMP types, so psycopg2 returns
        native Python bool/date/datetime objects. SQLite has no such types -
        it always returns 0/1 integers and plain date/datetime strings.
        Clients (e.g. a strictly-typed mobile app) built against the SQLite
        shape break the moment they see a real JSON boolean instead of 0/1,
        or an RFC-822-style datetime string instead of 'YYYY-MM-DD HH:MM:SS'.
        """
        for key, value in row.items():
            if isinstance(value, bool):
                row[key] = int(value)
            elif isinstance(value, datetime.datetime):
                row[key] = value.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(value, datetime.date):
                row[key] = value.strftime('%Y-%m-%d')
        return row

    def execute_query(self, query: str, params: Tuple = None, fetch_one: bool = False, fetch_all: bool = False) -> Optional[Any]:
        """
        Execute a database query

        Args:
            query: SQL query string (use ? placeholders for parameters)
            params: Query parameters as tuple
            fetch_one: Return single row as dictionary
            fetch_all: Return all rows as list of dictionaries

        Returns:
            - Dictionary if fetch_one=True
            - List of dictionaries if fetch_all=True
            - Number of affected rows otherwise

        Example:
            # Fetch one row
            user = db_manager.execute_query(
                "SELECT * FROM users WHERE email = ?",
                (email,),
                fetch_one=True
            )

            # Fetch all rows
            users = db_manager.execute_query(
                "SELECT * FROM users WHERE age > ?",
                (18,),
                fetch_all=True
            )

            # Update (returns rowcount)
            count = db_manager.execute_query(
                "UPDATE users SET name = ? WHERE id = ?",
                (new_name, user_id)
            )
        """
        with self.get_connection() as conn:
            cursor = self._cursor(conn)
            cursor.execute(self._adapt(query), params or ())

            if fetch_one:
                result = cursor.fetchone()
                if not result:
                    return None
                row = dict(result)
                return self._normalize_row(row) if self.db_type == 'postgres' else row
            elif fetch_all:
                results = cursor.fetchall()
                rows = [dict(row) for row in results]
                return [self._normalize_row(r) for r in rows] if self.db_type == 'postgres' else rows
            else:
                return cursor.rowcount

    def execute_many(self, query: str, params_list: List[Tuple]) -> int:
        """
        Execute a query multiple times with different parameters

        Args:
            query: SQL query string
            params_list: List of parameter tuples

        Returns:
            Number of affected rows

        Example:
            users = [('user1@email.com', 'John'), ('user2@email.com', 'Jane')]
            db_manager.execute_many(
                "INSERT INTO users (email, name) VALUES (?, ?)",
                users
            )
        """
        with self.get_connection() as conn:
            cursor = self._cursor(conn)
            cursor.executemany(self._adapt(query), params_list)
            return cursor.rowcount

    def execute_script(self, script: str) -> None:
        """
        Execute a SQL script (multiple statements)

        Args:
            script: SQL script string

        Example:
            db_manager.execute_script(
                "CREATE TABLE users (...); CREATE TABLE wardrobe (...);"
            )
        """
        with self.get_connection() as conn:
            cursor = self._cursor(conn)
            if self.db_type == 'postgres':
                # psycopg2/Postgres's simple query protocol runs multiple
                # ;-separated statements from a single execute() as long as
                # there are no bound parameters (true here - scripts only).
                cursor.execute(script)
            else:
                cursor.executescript(script)

    def get_lastrowid(self, query: str, params: Tuple = None) -> Optional[int]:
        """
        Execute INSERT query and return last inserted row ID

        Args:
            query: INSERT SQL query
            params: Query parameters

        Returns:
            Last inserted row ID

        Example:
            user_id = db_manager.get_lastrowid(
                "INSERT INTO users (email, name) VALUES (?, ?)",
                (email, name)
            )
        """
        with self.get_connection() as conn:
            cursor = self._cursor(conn)
            if self.db_type == 'postgres':
                adapted = self._adapt(query).rstrip().rstrip(';')
                if 'returning' not in adapted.lower():
                    adapted = f"{adapted} RETURNING id"
                cursor.execute(adapted, params or ())
                row = cursor.fetchone()
                return row['id'] if row else None
            else:
                cursor.execute(query, params or ())
                return cursor.lastrowid

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database

        Args:
            table_name: Name of the table

        Returns:
            True if table exists, False otherwise
        """
        if self.db_type == 'postgres':
            query = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ?"
        else:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.execute_query(query, (table_name,), fetch_one=True)
        return result is not None

    def get_tables(self) -> List[str]:
        """
        Get list of all tables in the database

        Returns:
            List of table names
        """
        if self.db_type == 'postgres':
            query = "SELECT table_name AS name FROM information_schema.tables WHERE table_schema = 'public'"
        else:
            query = "SELECT name FROM sqlite_master WHERE type='table'"
        results = self.execute_query(query, fetch_all=True)
        return [row['name'] for row in results]


# Global database manager instance
# Use this throughout the application for all database operations
db_manager = DatabaseManager()

# Convenience function for backward compatibility
def get_db_connection():
    """
    Get database connection (backward compatibility)
    Use db_manager.get_connection() context manager instead when possible
    """
    return db_manager._get_connection()
