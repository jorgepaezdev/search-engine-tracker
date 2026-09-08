"""Search Engine Tracker."""

import sys

if sys.version_info[:2] != (3, 10):
    raise RuntimeError(
        "Search Engine Tracker requires Python 3.10, "
        f"but this interpreter is {sys.version.split()[0]}."
    )

