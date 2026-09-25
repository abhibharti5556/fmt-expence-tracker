"""Production entrypoint. Point a WSGI server at this module's `app`
object instead of running app.py directly, e.g.:

    waitress-serve --listen=0.0.0.0:8000 wsgi:app        # Windows
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app                # Linux

Keeps app.py's `if __name__ == "__main__": app.run(...)` dev-server block
out of the production code path.
"""

from app import create_app

app = create_app()
