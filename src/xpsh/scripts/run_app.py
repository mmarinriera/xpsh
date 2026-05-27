import subprocess
import sys
from pathlib import Path

APP_PATH = Path(__file__).with_name("app.py")


def main() -> None:
    file_path = sys.argv[1]
    print(f"{APP_PATH}: {file_path}")
    subprocess.run([sys.executable, "-m", "streamlit", "run", APP_PATH, file_path])


if __name__ == "__main__":
    main()
