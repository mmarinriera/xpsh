import subprocess
import sys
from pathlib import Path

APP_PATH = Path(__file__).with_name("app.py")

PORT = 4242  # 8501


def main() -> None:
    args = sys.argv[1:]
    command: list[str] = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.headless",
        "true",
        "--server.port",
        str(PORT),
    ] + args
    subprocess.run(command)


if __name__ == "__main__":
    main()
