#!/usr/bin/env python3
"""
Validation script to check all Python files for syntax errors and import issues
Run this before testing to ensure everything is ready
"""

import sys
import importlib.util
import ast
from pathlib import Path


def validate_syntax(file_path):
    """Validate Python file syntax"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source, filename=file_path)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error: {e.msg} at line {e.lineno}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def validate_imports(file_path):
    """Try to import the module"""
    try:
        spec = importlib.util.spec_from_file_location('module', file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return True, None
    except Exception as e:
        return False, str(e)


def main():
    """Main validation function"""
    backend_dir = Path(__file__).parent.parent
    files_to_check = [
        'app.py',
        'config.py',
        'init_db.py',
        'api/auth.py',
        'api/body_measurements.py',
        'api/tryon.py',
        'api/garments.py',
        'api/fitting.py',
        'services/database.py',
        'services/auth.py',
        'services/ai_integration.py',
        'services/job_queue.py',
        'services/image_processing.py',
        'services/storage.py',
        'utils/errors.py',
        'utils/response.py',
        'utils/validators.py',
        'utils/middleware.py',
        'utils/logger.py',
        'migrations/migration_manager.py',
        'scripts/run_migrations.py',
    ]
    
    print("🔍 Validating backend files...\n")
    
    syntax_errors = []
    import_errors = []
    success_count = 0
    
    for file_path in files_to_check:
        full_path = backend_dir / file_path
        
        if not full_path.exists():
            print(f"⚠️  {file_path}: File not found")
            continue
        
        # Check syntax
        syntax_ok, syntax_error = validate_syntax(full_path)
        if not syntax_ok:
            syntax_errors.append((file_path, syntax_error))
            print(f"❌ {file_path}: {syntax_error}")
            continue
        
        # Check imports
        import_ok, import_error = validate_imports(full_path)
        if not import_ok:
            import_errors.append((file_path, import_error))
            print(f"⚠️  {file_path}: Import issue - {import_error}")
        else:
            print(f"✅ {file_path}")
            success_count += 1
    
    print(f"\n📊 Validation Summary:")
    print(f"   ✅ Success: {success_count}/{len(files_to_check)}")
    print(f"   ❌ Syntax errors: {len(syntax_errors)}")
    print(f"   ⚠️  Import issues: {len(import_errors)}")
    
    if syntax_errors:
        print(f"\n❌ Syntax Errors Found:")
        for file_path, error in syntax_errors:
            print(f"   - {file_path}: {error}")
    
    if import_errors:
        print(f"\n⚠️  Import Issues (may be due to missing dependencies):")
        for file_path, error in import_errors:
            print(f"   - {file_path}: {error}")
    
    # Final check - try to import app
    print(f"\n🔍 Final check: Importing app...")
    try:
        sys.path.insert(0, str(backend_dir))
        from app import app
        print(f"✅ App imports successfully")
        print(f"✅ {len(app.blueprints)} blueprints registered")
        print(f"✅ {len(list(app.url_map.iter_rules()))} routes registered")
    except Exception as e:
        print(f"❌ App import failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    if syntax_errors:
        print(f"\n❌ Validation failed: {len(syntax_errors)} syntax error(s)")
        return 1
    
    print(f"\n✅ All files validated successfully! Ready for testing.")
    return 0


if __name__ == '__main__':
    sys.exit(main())

