#!/usr/bin/env python3
"""
DID Service Entry Point
"""

import logging
import sys
import uvicorn

from did_service.config import config
from did_service.service import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main():
    """Run the DID service."""
    logger.info(f"Starting DID Service on {config.host}:{config.port}")

    uvicorn.run(
        "did_service.service:app",
        host=config.host,
        port=config.port,
        reload=False,
        access_log=True,
        log_level="info",
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
