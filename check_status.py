#!/usr/bin/env python3
import subprocess
import sys
import os

def run(cmd):
    print(f"Running: {cmd}")
    sys.stdout.flush()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"Return code: {result.returncode}")
    if result.stdout:
        print(f"STDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"STDERR:\n{result.stderr}")
    return result

print("=" * 60)
print("Checking Fedresurs Radar container status")
print("=" * 60)

os.chdir("/root/fedr")

# Check docker version
run("docker --version")

# Check docker-compose version
run("docker-compose --version")

# List all containers
print("\n--- All Docker containers ---")
result = run("docker ps -a")

# Check fedr containers
print("\n--- Fedr docker-compose containers ---")
result = run("docker-compose ps")

# Check if we can access app container
print("\n--- Testing app container access ---")
result = run("docker-compose exec -T app whoami")

# Check if we can access db container
print("\n--- Testing db container access ---")
result = run("docker-compose exec -T db whoami")

# Check logs of app container
print("\n--- App container logs (last 10 lines) ---")
result = run("docker-compose logs --tail=10 app")

# Check logs of db container
print("\n--- DB container logs (last 10 lines) ---")
result = run("docker-compose logs --tail=10 db")

print("\n" + "=" * 60)
print("Status check complete")
print("=" * 60)