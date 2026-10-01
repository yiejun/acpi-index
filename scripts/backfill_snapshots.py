"""Rebuild fixed daily basket history from saved raw quotes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.build_dashboard import main

if __name__ == "__main__":
    main()
