import csv

from scripts.export_leads import FIELDS


def test_export_schema_contains_only_evidence_backed_fields():
    assert "company_name" in FIELDS
    assert "evidence_url" in FIELDS
    assert "company_size" not in FIELDS
    assert "industry_guess" not in FIELDS


def test_exported_csv_can_be_read_with_utf8_bom(tmp_path):
    output = tmp_path / "leads.csv"
    output.write_text("company_name,domain\nExample,example.com\n", encoding="utf-8-sig")

    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["domain"] == "example.com"
