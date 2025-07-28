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
    app_path = '/app'
    src_path = '/app/src'
    
    # Add paths if not already present
    if app_path not in sys.path:
        sys.path.insert(0, app_path)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    print(f"✅ Python path configured: {sys.path[:3]}")

def test_imports():
    """Test critical imports."""
    try:
        # Test absolute imports
        from src.canvas_orchestrator import CanvasOrchestrator
        from src.supabase_client import get_supabase_client
        from src.config import Config
        from src.canvas_client import CanvasClient
        
        print("✅ All critical imports successful")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        
        # Try alternative import strategy
        try:
            import canvas_orchestrator
            import supabase_client
            import config
            print("✅ Alternative imports successful")
            return True
        except ImportError as e2:
            print(f"❌ Alternative imports also failed: {e2}")
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