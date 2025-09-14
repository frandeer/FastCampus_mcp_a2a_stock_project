#!/usr/bin/env python3
"""
Test runner script for simplified architecture tests.
Provides comprehensive test execution with coverage reporting.
"""

import os
import sys
import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a shell command and return the result."""
    print(f"\n🔧 {description}")
    print(f"📋 Command: {command}")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=Path(__file__).parent,
            capture_output=False
        )
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False


def main():
    """Main test execution function."""
    print("🧪 Simplified Architecture Test Suite")
    print("====================================")
    
    # Check if pytest is installed
    try:
        import pytest
        print(f"✅ pytest version: {pytest.__version__}")
    except ImportError:
        print("❌ pytest not found. Please install test requirements:")
        print("   pip install -r test_requirements.txt")
        sys.exit(1)
    
    # Test commands to run
    test_commands = [
        {
            "command": "python3 -m pytest tests/ -v --tb=short",
            "description": "Running basic test suite"
        },
        {
            "command": "python3 -m pytest tests/ --cov=. --cov-report=html --cov-report=term-missing --cov-fail-under=95",
            "description": "Running tests with coverage analysis (95% threshold)"
        },
        {
            "command": "python3 -m pytest tests/test_entities.py -v",
            "description": "Running domain entity tests"
        },
        {
            "command": "python3 -m pytest tests/test_use_cases.py -v",
            "description": "Running application use case tests"
        },
        {
            "command": "python3 -m pytest tests/test_adapters.py -v",
            "description": "Running infrastructure adapter tests"
        }
    ]
    
    # Execute test commands
    results = []
    for test_cmd in test_commands:
        success = run_command(test_cmd["command"], test_cmd["description"])
        results.append((test_cmd["description"], success))
    
    # Summary
    print("\n📊 Test Execution Summary")
    print("=" * 60)
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    
    for description, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {description}")
    
    print(f"\n📈 Results: {success_count}/{total_count} test suites passed")
    
    if success_count == total_count:
        print("🎉 All tests completed successfully!")
        
        # Additional reports
        print("\n📋 Additional Information:")
        print("- Coverage report available at: htmlcov/index.html")
        print("- Test results comply with 95% coverage standard")
        print("- All three layers (domain, application, infrastructure) tested")
        
        return 0
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)