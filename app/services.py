import os
import subprocess
import sys
import tempfile
import textwrap


def run_code_with_tests(student_code, test_code):
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            solution_path = os.path.join(temp_dir, "solution.py")
            test_path = os.path.join(temp_dir, "test_solution.py")

            # Write student code
            with open(solution_path, "w") as f:
                f.write(student_code)

            # Write test code
            with open(test_path, "w") as f:
                indented_test_code = textwrap.indent(test_code.strip(), "    ")
                f.write(
                    f"""
import unittest
from solution import *

class TestSolution(unittest.TestCase):
{indented_test_code}

if __name__ == '__main__':
    unittest.main()
"""
                )

            # Run the test script and capture output
            result = subprocess.run(
                [sys.executable, test_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=5,
                text=True,
            )

            output = result.stdout
            success = result.returncode == 0  # this is more reliable

            return output, success

    except Exception as e:
        return str(e), False
