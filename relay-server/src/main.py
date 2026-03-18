#!/usr/bin/env python3
"""
Relay Server Entry Point
"""

import logging
import sys
import uvicorn

from relay_server.config import config
from relay_server.service import app

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main():
    """Run the relay server."""
    logger.info(f"Starting Relay Server on {config.host}:{config.port}")

    uvicorn.run(
        "relay_server.service:app",
        host=config.host,
        port=config.api_port,
        reload=False,
        access_log=True,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
