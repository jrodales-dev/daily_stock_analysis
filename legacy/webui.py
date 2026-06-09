# -*- coding: utf-8 -*-
"""
===================================
Web Management Interface Entry
===================================

This script is kept for backward compatibility.
The recommended way to start the web service is:
    python main.py --webui-only

Usage:
    python webui.py
"""

from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)


def main() -> int:
    """
    Start Web Service
    """
    # Backward compatibility with old environment variables
    host = os.getenv("WEBUI_HOST", os.getenv("API_HOST", "127.0.0.1"))
    port = int(os.getenv("WEBUI_PORT", os.getenv("API_PORT", "8000")))

    print(f"Starting Web Service: http://{host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print()

    try:
        import uvicorn
        from src.config import setup_env
        from src.logging_config import setup_logging

        setup_env()
        setup_logging(log_prefix="web_server")

        uvicorn.run(
            "api.app:app",
            host=host,
            port=port,
            log_level="info"
        )
        return 0
    except KeyboardInterrupt:
        print("\nWeb service has been stopped.")
        return 0
    except Exception as e:
        logger.exception(f"Web service startup failed: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
