from app import validation

VALID_GSTINS = [
    "27AAGCH3162H1ZM",
    "27AABPS7063A1ZV",
    "24FNPPS1201A1ZF",
    "27CAEPM9391J1Z2",
    "27AAPFU0939F1ZV",
    "29AADCD6975H1Z6",
]


def test_checksum_accepts_known_valid_gstins():
    for gstin in VALID_GSTINS:
        result = validation.validate_gstin(gstin)
        assert result["status"] == "valid", f"{gstin}: {result}"


def test_checksum_rejects_tampered_gstins():
    assert validation.validate_gstin("27AAGCH3162H1Z1")["status"] == "invalid"
    assert validation.validate_gstin("27GHJKL6789M1Z2")["status"] == "invalid"


def test_gstin_state_resolution():
    assert validation.gstin_state("27AAGCH3162H1ZM") == "Maharashtra"
    assert validation.gstin_state("24FNPPS1201A1ZF") == "Gujarat"
    assert validation.gstin_state("29AADCD6975H1Z6") == "Karnataka"


def test_tax_split_intra_state():
    split = validation.split_tax(1000, 18, inter_state=False)
    assert split["cgst"] == 90
    assert split["sgst"] == 90
    assert split["igst"] == 0
    assert split["tax"] == 180


def test_tax_split_inter_state():
    split = validation.split_tax(1000, 18, inter_state=True)
    assert split["igst"] == 180
    assert split["cgst"] == 0
    assert split["sgst"] == 0


def test_amount_in_words():
    assert validation.amount_in_words(185000) == "Rupees One Lakh Eighty Five Thousand Only"
    assert (
        validation.amount_in_words(1234567.50)
        == "Rupees Twelve Lakh Thirty Four Thousand Five Hundred Sixty Seven and Fifty Paise Only"
    )
    assert validation.amount_in_words(0) == "Rupees Zero Only"
    assert validation.amount_in_words(999) == "Rupees Nine Hundred Ninety Nine Only"
    assert validation.amount_in_words(1000.05) == "Rupees One Thousand and Five Paise Only"
