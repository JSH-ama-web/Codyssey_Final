"""Vercel Python 서버리스 진입점: FastAPI(ASGI) 앱을 그대로 노출한다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401
