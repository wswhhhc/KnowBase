"""Test package — shared warning filters for the whole suite."""

import warnings

# starlette.testclient + httpx emits StarletteDeprecationWarning at import time
# (inherits UserWarning, not DeprecationWarning). httpx2 is not yet available.
warnings.simplefilter("ignore", category=UserWarning)
