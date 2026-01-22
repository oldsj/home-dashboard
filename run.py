#!/usr/bin/env python3
"""
Dashboard entry point.

Usage:
    python run.py [--host HOST] [--port PORT] [--reload]

Examples:
    python run.py                    # Run on 0.0.0.0:8000
    python run.py --port 8080        # Run on port 8080
    python run.py --reload           # Auto-reload on code changes
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="Run the dashboard server")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=9753, help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload on code changes"
    )

    args = parser.parse_args()

    import uvicorn

    print(f"Starting dashboard server at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    uvicorn.run(
        "server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
