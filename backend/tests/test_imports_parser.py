import io

import openpyxl

from app.imports import parse_contacts_xlsx


def _workbook_bytes(rows):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parser_handles_canonical_and_messy_rows():
    header = [
        "Company Name", "PAN No", "GST No", "Email", "Person Phone Number", "Shipping Address State",
    ]
    rows = [
        header,
        ["Alpha Industries", "ABCDE1234F", "24FNPPS1201A1ZF", "alpha@example.com", "9812345678", "Gujarat"],
        [None, "beta@example.com", "Beta Works", None, "24AAEPK1893K1ZJ", "Gujarat"],
    ]
    records, errors = parse_contacts_xlsx(_workbook_bytes(rows))

    assert not errors, errors
    assert len(records) == 2

    alpha = records[0]
    assert alpha["legal_name"] == "Alpha Industries"
    assert alpha["gstin"] == "24FNPPS1201A1ZF"
    assert alpha["email"] == "alpha@example.com"
    assert alpha["phone"] == "9812345678"
    assert alpha["state"] == "Gujarat"

    beta = records[1]
    assert beta["legal_name"] == "Beta Works"
    assert beta["gstin"] == "24AAEPK1893K1ZJ"
    assert beta["email"] == "beta@example.com"
    assert not beta["phone"]


def test_parser_skips_rows_without_a_name():
    rows = [
        ["Company Name", "Email"],
        [None, "orphan@example.com"],
        ["Gamma Traders", "gamma@example.com"],
    ]
    records, errors = parse_contacts_xlsx(_workbook_bytes(rows))
    assert len(records) == 1
    assert records[0]["legal_name"] == "Gamma Traders"
    assert len(errors) == 1
