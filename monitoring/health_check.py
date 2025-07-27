#!/usr/bin/env python3
"""
Health check script for Canvas Scraper application.
Used by monitoring systems to verify application health.
"""

import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional

import aiohttp
from config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthChecker:
    """Health check implementation for Canvas Scraper."""
    
    def __init__(self):
        self.config = Config()
        self.start_time = time.time()
        
    async def check_config(self) -> Dict[str, Any]:
        """Check configuration validity."""
        try:
            Config.validate()
            return {
                "status": "healthy",
                "message": "Configuration is valid",
                "details": {
                    "canvas_url": Config.CANVAS_URL,
                    "token_configured": bool(Config.CANVAS_API_TOKEN)
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Configuration error: {str(e)}",
                "details": {}
            }
    
    async def check_canvas_api(self) -> Dict[str, Any]:
        """Check Canvas API connectivity."""
        try:
            headers = {'Authorization': f'Bearer {Config.CANVAS_API_TOKEN}'}
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Test basic API connectivity
                url = f"{Config.CANVAS_URL}/users/self"
                start_time = time.time()
                
                async with session.get(url, headers=headers) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": "healthy",
                            "message": "Canvas API is accessible",
                            "details": {
                                "response_time_ms": round(response_time, 2),
                                "user_id": data.get("id"),
                                "user_name": data.get("name")
                            }
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "message": f"Canvas API returned status {response.status}",
                            "details": {
                                "response_time_ms": round(response_time, 2),
                                "status_code": response.status
                            }
                        }
                        
        except asyncio.TimeoutError:
            return {
                "status": "unhealthy",
                "message": "Canvas API request timed out",
                "details": {"timeout_seconds": 10}
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Canvas API error: {str(e)}",
                "details": {"error_type": type(e).__name__}
            }
    
    async def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            # Determine overall health
            status = "healthy"
            warnings = []
            
            if cpu_percent > 80:
                status = "degraded"
                warnings.append(f"High CPU usage: {cpu_percent}%")
                
            if memory_percent > 80:
                status = "degraded"
                warnings.append(f"High memory usage: {memory_percent}%")
                
            if disk_percent > 80:
                status = "degraded"
                warnings.append(f"High disk usage: {disk_percent}%")
            
            return {
                "status": status,
                "message": "System resources checked" + (f" - {', '.join(warnings)}" if warnings else ""),
                "details": {
                    "cpu_percent": round(cpu_percent, 1),
                    "memory_percent": round(memory_percent, 1),
                    "disk_percent": round(disk_percent, 1),
                    "warnings": warnings
                }
            }
            
        except ImportError:
            return {
                "status": "unknown",
                "message": "psutil not available for system monitoring",
                "details": {}
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"System check error: {str(e)}",
                "details": {"error_type": type(e).__name__}
            }
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        logger.info("Starting health checks...")
        
        checks = {
            "config": await self.check_config(),
            "canvas_api": await self.check_canvas_api(),
            "system_resources": await self.check_system_resources()
        }
        
        # Determine overall health
        statuses = [check["status"] for check in checks.values()]
        
        if "unhealthy" in statuses:
            overall_status = "unhealthy"
        elif "degraded" in statuses:
            overall_status = "degraded"
        elif "unknown" in statuses:
            overall_status = "unknown"
        else:
            overall_status = "healthy"
        
        uptime_seconds = time.time() - self.start_time
        
        result = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_status": overall_status,
            "uptime_seconds": round(uptime_seconds, 1),
            "checks": checks,
            "version": "1.0.0"
        }
        
        logger.info(f"Health check completed - Status: {overall_status}")
        return result


async def main():
    """Main function for health check."""
    health_checker = HealthChecker()
    result = await health_checker.run_all_checks()
    
    # Output JSON result
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    if result["overall_status"] == "healthy":
        sys.exit(0)
    elif result["overall_status"] in ["degraded", "unknown"]:
        sys.exit(1)
    else:  # unhealthy
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())