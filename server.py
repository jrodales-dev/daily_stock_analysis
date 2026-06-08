# -*- coding: utf-8 -*-
"""
===================================
Daily Stock Analysis - FastAPI Backend Service Entry
===================================

Responsibilities:
1. Provide RESTful API service
2. Configure CORS cross-origin support
3. Health check endpoints
4. Host frontend static files (production mode)

Usage:
    uvicorn server:app --reload --host 0.0.0.0 --port 8000
    
    Or use main.py:
    python main.py --serve-only      # Start API service only
    python main.py --serve           # API service + execute analysis
"""

import logging

from src.config import setup_env, get_config
from src.logging_config import setup_logging

# Initialize environment variables and logging
setup_env()

config = get_config()
level_name = (config.log_level or "INFO").upper()
level = getattr(logging, level_name, logging.INFO)

setup_logging(
    log_prefix="api_server",
    console_level=level,
    extra_quiet_loggers=['uvicorn', 'fastapi'],
)

# Import app instance from api.app
from api.app import app  # noqa: E402

# Export app for uvicorn
__all__ = ['app']


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
