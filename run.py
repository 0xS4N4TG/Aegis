#!/usr/bin/env python3
"""
Convenience script to run the LLM Red Team Platform.
Run with: python run.py
"""
import sys
import os

# Add the project root to the Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    main()
