from app.services.importer import import_fbref_csv

class FakeDB:
    def __init__(self): self.rows=[]
    def add(self, row): self.rows.append(row)
    def commit(self): pass

def test_csv_import_creates_rows():
    db=FakeDB()
    n=import_fbref_csv(db, b"Player,Goals\nPlayer A,12\nPlayer B,8\n", "standard", "2024-2025", "League")
    assert n == 2
    assert db.rows[0].source == "fbref_authorized_import"
    assert db.rows[0].payload["columns"]["Goals"] == "12"
