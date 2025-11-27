"""
Database migration manager for SQLite
Handles version tracking and applying migrations
"""

import os
from typing import List, Tuple
from shared.database import db_manager


class MigrationManager:
    """Manages database migrations"""
    
    def __init__(self):
        self.migrations_table = 'schema_migrations'
        self.migrations_dir = os.path.join(os.path.dirname(__file__))
    
    def ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        if not db_manager.table_exists(self.migrations_table):
            db_manager.execute_script(f"""
                CREATE TABLE {self.migrations_table} (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
    
    def get_applied_migrations(self) -> List[int]:
        """Get list of applied migration versions"""
        self.ensure_migrations_table()
        results = db_manager.execute_query(
            f"SELECT version FROM {self.migrations_table} ORDER BY version",
            fetch_all=True
        )
        return [row['version'] for row in results] if results else []
    
    def apply_migration(self, version: int, name: str, sql: str):
        """Apply a single migration"""
        try:
            db_manager.execute_script(sql)
            db_manager.execute_query(
                f"INSERT INTO {self.migrations_table} (version, name) VALUES (?, ?)",
                (version, name)
            )
            print(f"✅ Applied migration {version}: {name}")
            return True
        except Exception as e:
            print(f"❌ Failed to apply migration {version}: {e}")
            return False
    
    def run_migrations(self, migrations: List[Tuple[int, str, str]]):
        """
        Run all pending migrations
        
        Args:
            migrations: List of (version, name, sql) tuples, sorted by version
        """
        self.ensure_migrations_table()
        applied = self.get_applied_migrations()
        
        for version, name, sql in migrations:
            if version not in applied:
                self.apply_migration(version, name, sql)
            else:
                print(f"⏭️  Skipping migration {version}: {name} (already applied)")


# Global migration manager instance
migration_manager = MigrationManager()

