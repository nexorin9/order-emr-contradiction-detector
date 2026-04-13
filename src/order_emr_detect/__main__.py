"""
CLI entry point for python -m order_emr_detect
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.py.cli import main as cli_main


def main():
    """Entry point for the CLI."""
    return cli_main()


if __name__ == "__main__":
    sys.exit(main() or 0)
