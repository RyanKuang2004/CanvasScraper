#!/usr/bin/env python3
"""
Canvas Scraper Health Check

Validates that the Canvas Scraper container is healthy and can perform basic operations.
"""

import sys
import os
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, '/app/src')

def check_environment():
    """Check if required environment variables are present."""
    required_vars = ['CANVAS_API_TOKEN', 'CANVAS_URL']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ Environment variables check passed")
    return True

def check_dependencies():
    """Check if critical dependencies can be imported."""
    try:
        import aiohttp
        import asyncio
        from config import Config
        print("✅ Core dependencies import check passed")
        return True
    except ImportError as e:
        print(f"❌ Dependency import failed: {e}")
        return False

def check_file_permissions():
    """Check if required directories are writable."""
    dirs_to_check = ['/app/logs', '/app/data']
    
    for dir_path in dirs_to_check:
        try:
            Path(dir_path).mkdir(exist_ok=True)
            test_file = Path(dir_path) / '.health_check'
            test_file.write_text('test')
            test_file.unlink()
            print(f"✅ Directory {dir_path} is writable")
        except Exception as e:
            print(f"❌ Directory {dir_path} permission check failed: {e}")
            return False
    
    return True

def check_canvas_config():
    """Check if Canvas configuration is valid."""
    try:
        from config import Config
        
        # Basic URL validation
        if not Config.CANVAS_URL.startswith(('http://', 'https://')):
            print("❌ Canvas URL format is invalid")
            return False
        
        # Token length validation (Canvas tokens are typically long)
        if len(Config.CANVAS_API_TOKEN) < 20:
            print("❌ Canvas API token appears to be invalid (too short)")
            return False
        
        print("✅ Canvas configuration validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Canvas configuration check failed: {e}")
        return False

def main():
    """Main health check function."""
    print("🔍 Canvas Scraper Health Check")
    print("=" * 40)
    
    checks = [
        ("Environment Variables", check_environment),
        ("Dependencies", check_dependencies),
        ("File Permissions", check_file_permissions),
        ("Canvas Configuration", check_canvas_config),
    ]
    
    all_passed = True
    
    for check_name, check_func in checks:
        print(f"\n📋 Checking {check_name}...")
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"❌ {check_name} check crashed: {e}")
            all_passed = False
    
    print("\n" + "=" * 40)
    
    if all_passed:
        print("🎉 All health checks passed - Container is healthy!")
        sys.exit(0)
    else:
        print("⚠️  Some health checks failed - Container is unhealthy!")
        sys.exit(1)

if __name__ == "__main__":
    main()