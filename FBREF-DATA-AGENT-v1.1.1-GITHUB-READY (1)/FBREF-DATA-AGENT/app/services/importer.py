import csv, io
from app.models import DataRecord

def import_fbref_csv(db, content: bytes, dataset: str, season: str | None, competition: str | None):
    # Import only files the operator is authorized to use. Preserve raw columns and provenance.
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV sem cabeçalhos.")
    count = 0
    for index, row in enumerate(reader, start=1):
        clean = {str(k): (v if v != "" else None) for k, v in row.items() if k is not None}
        db.add(DataRecord(source="fbref_authorized_import", dataset=dataset,
                          external_id=str(index), competition=competition, season=season,
                          payload={"columns": clean, "source_file_type": "csv"}))
        count += 1
    db.commit()
    return count
