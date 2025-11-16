#!/usr/bin/env python3
"""
Initialize database for becauseFuture backend
Runs all migrations to set up the database schema
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.run_migrations import main

if __name__ == '__main__':
    main()

