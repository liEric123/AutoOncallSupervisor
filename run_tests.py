#!/usr/bin/env python3
"""
Simple Test Runner for AutoOncallSupervisor

Usage:
    python run_tests.py           # Run simple tests (default)
    python run_tests.py setup     # Install dependencies
"""

import subprocess
import sys

def run_command(cmd, description):
    """Run a command and handle the output"""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("✅ Success!")
            return True

        print(f"❌ {description} failed!")
        print(result.stdout)
        print(result.stderr)
        return False
    except (OSError, subprocess.SubprocessError) as e:
        print(f"❌ Error running {description}: {e}")
        return False

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    return run_command(f"{sys.executable} -m pip install -r requirements.txt", "Dependency installation")

def run_simple_tests():
    """Run the simple test suite"""
    print("\n=== Running Simple Tests ===")
    return run_command(f"{sys.executable} simple_test.py", "Simple tests")

def main():
    """Main test runner"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
    else:
        command = "default"

    if command == "setup":
        result = install_dependencies()
    else:
        # Default: run simple tests
        result = install_dependencies() and run_simple_tests()

    print(f"\n{'✅ All operations completed successfully!' if result else '❌ Some operations failed!'}")
    return result

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
