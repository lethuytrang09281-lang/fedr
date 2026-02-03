#!/usr/bin/env python3
import subprocess
import sys

print("Testing Docker and docker-compose...")

# Test 1: Docker version
print("\n1. Docker version:")
result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
print(f"  stdout: {result.stdout.strip()}")
print(f"  stderr: {result.stderr}")
print(f"  returncode: {result.returncode}")

# Test 2: docker-compose version
print("\n2. docker-compose version:")
result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True)
print(f"  stdout: {result.stdout.strip()}")
print(f"  stderr: {result.stderr}")
print(f"  returncode: {result.returncode}")

# Test 3: List containers
print("\n3. Docker containers:")
result = subprocess.run(["docker", "ps", "-a"], capture_output=True, text=True)
print(f"  stdout:\n{result.stdout}")
print(f"  stderr: {result.stderr}")
print(f"  returncode: {result.returncode}")

# Test 4: Check fedr containers
print("\n4. fedr containers:")
result = subprocess.run(["docker-compose", "ps", "-a"], capture_output=True, text=True, cwd="/root/fedr")
print(f"  stdout:\n{result.stdout}")
print(f"  stderr: {result.stderr}")
print(f"  returncode: {result.returncode}")

# Test 5: Check if we can run a simple command in a container
print("\n5. Test container access:")
result = subprocess.run(["docker-compose", "exec", "-T", "app", "echo", "hello"], 
                       capture_output=True, text=True, cwd="/root/fedr")
print(f"  stdout: {result.stdout.strip()}")
print(f"  stderr: {result.stderr.strip()}")
print(f"  returncode: {result.returncode}")

print("\nTest completed.")