"""Search Engine Tracker."""

import sys

if sys.version_info[:3] != (3, 9, 6):
    raise RuntimeError(
        "Search Engine Tracker requires Python 3.9.6, "
        f"but this interpreter is {sys.version.split()[0]}."
    )

