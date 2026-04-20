import pytest
import tempfile
import os
from pathlib import Path

from openemail.storage.database import Database


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db = Database.__new__(Database)
    db._db_path = Path(db_path)
    db._conn = None
    db.connect()

    db.execute("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value INTEGER,
            status TEXT DEFAULT 'active'
        )
    """)
    db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test1", 100))
    db.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("test2", 200))
    db.commit()

    yield db

    db.close()
    os.unlink(db_path)
