"""Run the bundled application tests under the portable data/cache environment."""
import sys
from portable_launcher import prepare_environment
prepare_environment()
import pytest
raise SystemExit(pytest.main(["tests", "-q", "-p", "no:cacheprovider", "--basetemp=portable-data/test-temp"] + sys.argv[1:]))
