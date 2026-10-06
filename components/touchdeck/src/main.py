"""Standalone entrypoint. Never imports Caelestia Dev Manager."""
import sys
sys.dont_write_bytecode = True
from app import main

if __name__ == "__main__":
    raise SystemExit(main())
