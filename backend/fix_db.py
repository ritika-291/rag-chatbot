import sqlite3
import logging

# Make sure this matches your DB file
conn = sqlite3.connect("chat.db")
cur = conn.cursor()

# Check current columns
cur.execute("PRAGMA table_info(messages)")
columns = [col[1] for col in cur.fetchall()]

logging.basicConfig(level=logging.INFO)
logging.info("Existing columns: %s", columns)

# Add metadata column if missing
if "metadata" not in columns:
    cur.execute("ALTER TABLE messages ADD COLUMN metadata TEXT")
    logging.info("✅ metadata column added successfully!")
else:
    logging.info("✅ metadata already exists")

conn.commit()
conn.close()
