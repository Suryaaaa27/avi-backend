# api/index.py

from app import create_app

app = create_app()

def handler(request, context):
    return app(request, context)
