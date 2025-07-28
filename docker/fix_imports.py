#!/usr/bin/env python3
"""
Import Fix Script for Docker Container
Validates that all imports work correctly in the container environment.
"""

import sys
import os
from pathlib import Path

def fix_python_path():
    """Ensure Python path is correctly configured."""
    app_path = Path(__file__).parent
    src_path = app_path / 'src'
    
    # Convert to string for sys.path
    app_path = str(app_path)
    src_path = str(src_path)
    
    # Add paths if not already present
    if app_path not in sys.path:
        sys.path.insert(0, app_path)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    print(f"✅ Python path configured: {sys.path[:3]}")
    print(f"Resolved src path: {src_path}, exists: {os.path.exists(src_path)}")

def test_imports():
    """Test critical imports."""
    try:
        from src.canvas_orchestrator import CanvasOrchestrator
        from src.supabase_client import get_supabase_client
        from src.canvas_client import CanvasClient
        
        print("✅ All critical imports successful")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Main import validation."""
    print("🔧 Docker Import Fix Script")
    print("=" * 40)
    
    # Fix Python path
    fix_python_path()
    
    # Test imports
    if test_imports():
        print("🎉 Import validation passed!")
        sys.exit(0)
    else:
        print("⚠️ Import validation failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()