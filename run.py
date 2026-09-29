#!/usr/bin/env python3
"""Convenience launcher for ClipMine."""

import uvicorn
from backend.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print(f"""
╔══════════════════════════════════════╗
║           ClipMine v0.1.0            ║
║  Privacy-first AI Video Clipper      ║
╚══════════════════════════════════════╝
""")
    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
