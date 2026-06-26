#!/usr/bin/env python
"""Quick start script for Bio-Maintain"""
import subprocess
import sys
import os
import socket


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return None


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
    local_ip = get_local_ip()
    print("\n[2/2] Starting FastAPI server...")
    print("✓ Server is binding to all interfaces on port 8000")
    if local_ip:
        print(f"✓ Open from this machine at: http://127.0.0.1:8000")
        print(f"✓ Open from another device on the same network at: http://{local_ip}:8000")
    else:
        print("✓ Open in a browser at: http://127.0.0.1:8000")
        print("✓ Or replace with your machine IP if you are on the same network")
    print("✓ Press Ctrl+C to stop\n")
    
    result = subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
    )
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
