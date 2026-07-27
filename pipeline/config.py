"""Environment configuration.

`require_env` now lives in `lehcore` (see `pipeline/client.py`'s docstring
for why); re-exported here so `app/twilio_client.py` and existing tests
keep working unchanged.
"""

from lehcore.client import require_env

__all__ = ["require_env"]
