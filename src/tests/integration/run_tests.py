#!/usr/bin/env python3
"""Run all integration tests for SUDP."""

import os
import sys
import unittest
import argparse
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_tests(test_type="all", verbose=False):
    """Run the specified tests.
    
    Args:
        test_type: Type of tests to run ("all", "multi_instance", "tcp_server", "performance")
        verbose: Whether to show verbose output
    """
    # Determine test directory
    test_dir = Path(__file__).parent
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add tests based on type
    if test_type in ("all", "multi_instance"):
        from test_multi_instance import MultiInstanceTest
        for test_method in [
            method for method in dir(MultiInstanceTest) 
            if method.startswith("test_")
        ]:
            suite.addTest(MultiInstanceTest(test_method))
    
    if test_type in ("all", "tcp_server"):
        from test_tcp_server import TCPServerTest
        for test_method in [
            method for method in dir(TCPServerTest) 
            if method.startswith("test_")
        ]:
            suite.addTest(TCPServerTest(test_method))
    
    if test_type in ("all", "performance"):
        from test_performance import PerformanceBenchmark
        for test_method in [
            method for method in dir(PerformanceBenchmark) 
            if method.startswith("test_")
        ]:
            suite.addTest(PerformanceBenchmark(test_method))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2 if verbose else 1)
    result = runner.run(suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SUDP integration tests")
    parser.add_argument(
        "--type", 
        choices=["all", "multi_instance", "tcp_server", "performance"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output"
    )
    
    args = parser.parse_args()
    sys.exit(run_tests(args.type, args.verbose)) 