#!/usr/bin/env python3
"""
Run a single poll of all sports and print results.

Usage: activate your backend venv and run:
  python backend/tools/run_poll_once.py

This is a helper for one-off execution on servers where the background
scheduler may not have started. It does not start any scheduler jobs,
only runs the consolidated poll once.
"""
import os
import sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

def main():
    try:
        from services.scheduler import poll_all_sports
        print("🔁 Running a one-off poll of all sports...")
        poll_all_sports()
        print("✅ One-off poll complete")
    except Exception as e:
        print("❌ One-off poll failed:")
        traceback.print_exc()

if __name__ == '__main__':
    main()
