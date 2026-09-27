"""Vercel entrypoint. Vercel's Python runtime looks for a WSGI-compatible
`app` object in this file; every request (per vercel.json's catch-all
rewrite) is routed here regardless of path.

See config.py's IS_VERCEL note: the deployed filesystem is read-only
except /tmp, and /tmp does not persist between invocations. This makes
the app bootable on Vercel, not durable -- data can be lost at any time.
A real deployment needs a persistent disk (e.g. Render, Railway, Fly.io)
or a hosted database + object storage swapped in for SQLite/local files.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
