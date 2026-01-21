"""wa-sort-media package.

Expose a small public surface for package consumers.
"""

__all__ = ["main"]
__version__ = "0.1.0"

from .main import main  # re-export CLI entrypoint
