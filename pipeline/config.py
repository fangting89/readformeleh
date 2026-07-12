"""Environment configuration for the pipeline. Load `.env` and validate
required variables here, rather than reading `os.environ` ad hoc elsewhere."""

import os

from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    """Returns a required environment variable.

    Args:
        name: The environment variable name.

    Returns:
        The variable's value.

    Raises:
        RuntimeError: If the variable is unset or empty.
    """
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set — check your .env file.")
    return value
