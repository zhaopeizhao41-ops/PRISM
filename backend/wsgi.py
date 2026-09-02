"""
gunicorn 生产入口：gunicorn --bind 0.0.0.0:5001 wsgi:app
"""

from app import create_app

app = create_app()
