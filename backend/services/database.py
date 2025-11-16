"""
Database abstraction layer for becauseFuture backend
Currently SQLite-based, but structured for easy migration to MySQL/PostgreSQL in the future.
All database operations should go through this class.
"""

import os
import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
from dotenv import load_dotenv  # type: ignore

load_dotenv()


class DatabaseManager:
    """
    Database abstraction class for SQLite.
    Structured to make it easy to switch to MySQL/PostgreSQL later.
    All database operations should use this class.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file (defaults to DATABASE_PATH env var or 'database.db')
        """
        self.db_path = db_path or os.environ.get('DATABASE_PATH', 'database.db')
        self.db_type = 'sqlite'  # Currently SQLite only, easy to extend later
        
    def _get_connection(self):
        """
        Get SQLite database connection with dictionary-like row access
        
        Returns:
            sqlite3.Connection with row_factory set to Row
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dictionary-like access
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
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
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
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            
            if fetch_one:
                result = cursor.fetchone()
                return dict(result) if result else None
            elif fetch_all:
                results = cursor.fetchall()
                return [dict(row) for row in results]
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
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
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
            cursor = conn.cursor()
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
            cursor = conn.cursor()
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
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self.execute_query(query, (table_name,), fetch_one=True)
        return result is not None
    
    def get_tables(self) -> List[str]:
        """
        Get list of all tables in the database
        
        Returns:
            List of table names
        """
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
