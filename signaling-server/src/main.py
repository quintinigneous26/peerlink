#!/usr/bin/env python3
"""
Signaling Server Entry Point
"""

import logging
import sys
import uvicorn

from signaling_server.config import config
from signaling_server.service import app

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main():
    """Run the signaling server."""
    logger.info(f"Starting Signaling Server on {config.host}:{config.ws_port}")

    uvicorn.run(
        "signaling_server.service:app",
        host=config.host,
        port=config.ws_port,
        reload=False,
        access_log=True,
        log_level=config.log_level.lower(),
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
