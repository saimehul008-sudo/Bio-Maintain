#!/usr/bin/env python
"""Quick start script for Bio-Maintain"""
import subprocess
import sys
import os

def main():
    print("Bio-Maintain - Medical Machine Tracking System")
    print("=" * 50)
    
    # Change to bio_maintain directory
    os.chdir("bio_maintain")
    
    # Install dependencies
    print("\n[1/2] Installing dependencies...")
    print("Upgrading pip first...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        capture_output=True
    )
    
    print("Installing packages from requirements.txt...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
    )
    if result.returncode != 0:
        print("\n❌ Failed to install dependencies")
        print("Try manually running: python -m pip install -r requirements.txt")
        return 1
    
    # Start server
    print("\n[2/2] Starting FastAPI server...")
    print("✓ Server will run on: http://127.0.0.1:8000")
    print("✓ Press Ctrl+C to stop\n")
    
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"]
    )
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
