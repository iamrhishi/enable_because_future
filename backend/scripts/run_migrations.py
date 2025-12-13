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
        (6, 'extend_user_and_measurements', load_migration(6, 'extend_user_and_measurements')),
        (7, 'add_categories_and_wardrobe_updates', load_migration(7, 'add_categories_and_wardrobe_updates')),
        (8, 'add_wardrobe_item_fields', load_migration(8, 'add_wardrobe_item_fields')),
        (9, 'add_category_section', load_migration(9, 'add_category_section')),
        (10, 'create_category_sections', load_migration(10, 'create_category_sections')),
        (11, 'seed_platform_categories', load_migration(11, 'seed_platform_categories')),
        (12, 'add_user_category_sections', load_migration(12, 'add_user_category_sections')),
        (13, 'add_hip_circumference', load_migration(13, 'add_hip_circumference')),
        (14, 'add_image_path', load_migration(14, 'add_image_path')),
    ]
    
    migration_manager.run_migrations(migrations)
    print("✅ Migrations complete!")


if __name__ == '__main__':
    main()

