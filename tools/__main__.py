from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
from tools.cli import cli

if __name__ == "__main__":
    cli()
