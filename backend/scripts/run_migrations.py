#!/usr/bin/env python3
"""
Run database migrations
Usage: python scripts/run_migrations.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from migrations.migration_manager import migration_manager


def load_migration(version: int, name: str) -> str:
    """Load migration SQL from file"""
    migration_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'migrations',
        f"{version:03d}_{name}.sql"
    )
    with open(migration_file, 'r') as f:
        return f.read()


def main():
    """Run all pending migrations"""
    print("🔄 Running database migrations...")
    
    # Define migrations in order
    migrations = [
        (1, 'initial_schema', load_migration(1, 'initial_schema')),
        (2, 'add_body_measurements', load_migration(2, 'add_body_measurements')),
        (3, 'add_tryon_jobs', load_migration(3, 'add_tryon_jobs')),
        (4, 'enhance_wardrobe', load_migration(4, 'enhance_wardrobe')),
        (5, 'add_garment_metadata', load_migration(5, 'add_garment_metadata')),
    ]
    
    migration_manager.run_migrations(migrations)
    print("✅ Migrations complete!")


if __name__ == '__main__':
    main()

