from backend.database.db import init_db
import logging

init_db()
logging.basicConfig(level=logging.INFO)
logging.info("✅ Database & tables created successfully!")
