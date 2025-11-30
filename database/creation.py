# Run this in a Python shell
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.database.db_connection import engine, Base
from backend.database.models import *

Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully!")
