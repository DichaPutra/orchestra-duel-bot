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


def configure_vision():
    """Load keys and configure vision module."""
    import vision
    
    keys = {
        "gemini_key": os.getenv("GEMINI_API_KEY", ""),
        "openai_key": os.getenv("OPENAI_API_KEY", ""),
        "openrouter_key": os.getenv("OPENROUTER_API_KEY", ""),
        "groq_key": os.getenv("GROQ_API_KEY", ""),
    }
    
    models = {}
    for m in ["gemini_model", "openai_model", "openrouter_model", "groq_model"]:
        val = os.getenv(m.upper(), "")
        if val:
            models[m] = val
            
    provider = os.getenv("LLM_PROVIDER", "gemini")
    vision.configure(provider, keys, models)


def server_mode(port: int = 5555):
    """Mode server-only: jalanin ZMQ server."""
    import window
    import capture
    import vision
    import input as inp
    import memory_state  # Opsi B
    from orchestra_server import OrchestraServer, run_server

    configure_vision()

    server = OrchestraServer()
    server.bind_modules(capture, vision, inp, window, memory_state)

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

    configure_vision()

    # Start server di thread terpisah
    server = OrchestraServer()
    server.bind_modules(capture, vision, inp, window, memory_state)
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


def free_port(port: int = 5555):
    """Find and terminate any process using the specified port to avoid address-in-use errors."""
    import os
    import subprocess
    logger.info("Checking if port %d is in use...", port)
    killed = False

    # 1. Try to find and kill using psutil
    try:
        import psutil
        for conn in psutil.net_connections(kind='tcp'):
            if conn.laddr and conn.laddr.port == port:
                pid = conn.pid
                if pid and pid != os.getpid():
                    try:
                        proc = psutil.Process(pid)
                        name = proc.name()
                        logger.info("Found process using port %d: %s (PID: %d). Terminating...", port, name, pid)
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            logger.info("Process did not respond, forcing kill...")
                            proc.kill()
                        logger.info("Successfully terminated process on port %d.", port)
                        killed = True
                    except Exception as e:
                        logger.error("Failed to terminate process %d: %s", pid, e)
        
        if not killed:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['pid'] == os.getpid():
                        continue
                    for conn in proc.connections(kind='tcp'):
                        if conn.laddr and conn.laddr.port == port:
                            pid = proc.info['pid']
                            name = proc.info['name']
                            logger.info("Found process using port %d: %s (PID: %d) via iteration. Terminating...", port, name, pid)
                            proc.terminate()
                            try:
                                proc.wait(timeout=2)
                            except psutil.TimeoutExpired:
                                proc.kill()
                            logger.info("Successfully terminated process on port %d.", port)
                            killed = True
                except Exception:
                    pass
    except Exception as e:
        logger.debug("psutil check failed: %s", e)

    # 2. Windows fallback
    if not killed and os.name == 'nt':
        try:
            output = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True)
            pids = set()
            for line in output.strip().split('\n'):
                parts = line.split()
                if len(parts) >= 5:
                    pid_str = parts[-1]
                    if pid_str.isdigit():
                        pids.add(int(pid_str))
            for pid in pids:
                if pid != os.getpid() and pid > 0:
                    logger.info("Found PID %d using port %d via netstat. Killing via taskkill...", pid, port)
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    logger.info("Successfully killed PID %d via taskkill.", pid)
                    killed = True
        except subprocess.CalledProcessError:
            pass
        except Exception as e:
            logger.error("netstat/taskkill fallback failed: %s", e)

    if not killed:
        logger.info("Port %d is free.", port)


def main():
    setup_dotenv()

    parser = argparse.ArgumentParser(
        description="Orchestra Duel Bot — Yu-Gi-Oh! Master Duel")
    parser.add_argument("--server", action="store_true",
                        help="Run server only (no bot)")
    parser.add_argument("--port", type=int, default=5555,
                        help="ZMQ server port (default: 5555)")
    parser.add_argument("--bot", type=str, default="llm",
                        choices=["self_burn", "pass_turn", "llm"],
                        help="Bot script to use (default: llm)")
    args = parser.parse_args()

    # Bebaskan port sebelum menjalankan server ZMQ
    free_port(args.port)

    if args.server:
        server_mode(args.port)
    else:
        standalone_mode(args.bot)


if __name__ == "__main__":
    main()
