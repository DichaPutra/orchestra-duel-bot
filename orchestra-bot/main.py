"""
Orchestra Duel Bot — Main Entry Point

Mode:
  1. server-only: Jalanin ZMQ server doang (client connect dari script terpisah)
  2. standalone: Jalanin bot langsung (built-in bot script)

Usage:
  python main.py                    # Standalone mode
  python main.py --server           # Server-only mode
  python main.py --bot self_burn    # Pake bot script tertentu
"""
import argparse
import logging
import sys
import time
import os
from pathlib import Path

# ── Setup logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestra")


def setup_dotenv():
    """Load .env file."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)


def server_mode(port: int = 5555):
    """Mode server-only: jalanin ZMQ server."""
    import window
    import capture
    import vision
    import input as inp
    import memory_state  # Opsi B
    from orchestra_server import OrchestraServer, run_server

    # Setup API key
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        vision.set_api_key(api_key)
        logger.info("Gemini API key loaded")
    else:
        logger.warning("GEMINI_API_KEY not set in .env")

    server = OrchestraServer()
    server.bind_modules(capture, inp, vision, window, memory_state)

    logger.info("Starting Orchestra Server on port %d...", port)
    run_server(port, server)


def standalone_mode(bot_name: str = "self_burn"):
    """Mode standalone: jalanin server + bot langsung."""
    import threading
    import window
    import capture
    import vision
    import input as inp
    import memory_state  # Opsi B
    from orchestra_server import OrchestraServer, run_server

    # Setup API key
    api_key = os.getenv("GEMINI_API_KEY", "")
    if api_key:
        vision.set_api_key(api_key)
    else:
        logger.warning("GEMINI_API_KEY not set. Vision will not work.")

    # Start server di thread terpisah
    server = OrchestraServer()
    server.bind_modules(capture, inp, vision, window, memory_state)
    server_thread = threading.Thread(
        target=run_server, args=(5555, server),
        daemon=True
    )
    server_thread.start()
    logger.info("Server thread started")
    time.sleep(1)

    # Import dan jalanin bot script
    if bot_name == "self_burn":
        from bots.self_burn import run as run_bot
    elif bot_name == "pass_turn":
        from bots.pass_turn import run as run_bot
    elif bot_name == "llm":
        from bots.llm_bot import run as run_bot
    else:
        logger.error("Unknown bot: %s", bot_name)
        sys.exit(1)

    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")


def main():
    setup_dotenv()

    parser = argparse.ArgumentParser(
        description="Orchestra Duel Bot — Yu-Gi-Oh! Master Duel")
    parser.add_argument("--server", action="store_true",
                        help="Run server only (no bot)")
    parser.add_argument("--port", type=int, default=5555,
                        help="ZMQ server port (default: 5555)")
    parser.add_argument("--bot", type=str, default="self_burn",
                        choices=["self_burn", "pass_turn", "llm"],
                        help="Bot script to use (default: self_burn)")
    args = parser.parse_args()

    if args.server:
        server_mode(args.port)
    else:
        standalone_mode(args.bot)


if __name__ == "__main__":
    main()
