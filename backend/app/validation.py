"""GST domain logic: GSTIN validation/checksum, state codes, tax split, amount in words."""

import re

GSTIN_RE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]$")
PAN_RE = re.compile(r"^[A-Z]{5}\d{4}[A-Z]$")

STATE_CODES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "25": "Daman and Diu",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "28": "Andhra Pradesh (old code)",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}

_GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _char_value(character: str) -> int:
    return _GSTIN_CHARS.index(character)


def gstin_checksum(gstin: str) -> str:
    """The 15th character of a GSTIN is a mod-36 check digit over the first 14."""
    total = 0
    factor = 1
    for character in gstin[:14]:
        product = _char_value(character) * factor
        total += product // 36 + product % 36
        factor = 3 - factor
    return _GSTIN_CHARS[(36 - total % 36) % 36]


def gstin_state(gstin: str):
    if not gstin or len(gstin) < 2:
        return None
    return STATE_CODES.get(gstin[:2])


def validate_gstin(gstin) -> dict:
    """Returns {'status': 'valid'|'invalid'|'empty', 'reason': ..., 'state': ...}."""
    value = (gstin or "").strip().upper()
    if not value:
        return {"status": "empty", "reason": "No GSTIN provided", "state": None}
    if not GSTIN_RE.match(value):
        return {"status": "invalid", "reason": "GSTIN format is not valid", "state": None}
    if value[:2] not in STATE_CODES:
        return {"status": "invalid", "reason": f"Unknown state code {value[:2]}", "state": None}
    if gstin_checksum(value) != value[14]:
        return {"status": "invalid", "reason": "GSTIN checksum failed", "state": gstin_state(value)}
    return {"status": "valid", "reason": "", "state": gstin_state(value)}


def is_inter_state(party_state, company_state) -> bool:
    """IGST applies when the place of supply differs from the supplier's state."""
    if not party_state or not company_state:
        return False
    return party_state.strip().lower() != company_state.strip().lower()


def split_tax(taxable_value: float, gst_rate: float, inter_state: bool) -> dict:
    taxable = round(float(taxable_value or 0), 2)
    rate = float(gst_rate or 0)
    tax = round(taxable * rate / 100.0, 2)
    if inter_state:
        return {"cgst": 0.0, "sgst": 0.0, "igst": tax, "tax": tax}
    cgst = round(tax / 2.0, 2)
    sgst = round(tax - cgst, 2)
    return {"cgst": cgst, "sgst": sgst, "igst": 0.0, "tax": tax}


_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digits(number: int) -> str:
    if number < 20:
        return _ONES[number]
    return _TENS[number // 10] + (" " + _ONES[number % 10] if number % 10 else "")


def _three_digits(number: int) -> str:
    parts = []
    hundreds = number // 100
    remainder = number % 100
    if hundreds:
        parts.append(_ONES[hundreds] + " Hundred")
    if remainder:
        parts.append(_two_digits(remainder))
    return " ".join(parts)


def amount_in_words(amount) -> str:
    amount = round(float(amount or 0), 2)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))
    if rupees == 0 and paise == 0:
        return "Rupees Zero Only"

    parts = []
    crore = rupees // 10000000
    rupees %= 10000000
    lakh = rupees // 100000
    rupees %= 100000
    thousand = rupees // 1000
    rupees %= 1000
    if crore:
        parts.append(_three_digits(crore) + " Crore")
    if lakh:
        parts.append(_three_digits(lakh) + " Lakh")
    if thousand:
        parts.append(_three_digits(thousand) + " Thousand")
    if rupees:
        parts.append(_three_digits(rupees))

    words = " ".join(part for part in parts if part)
    text = "Rupees " + words if words else "Rupees"
    if paise:
        text += " and " + _two_digits(paise) + " Paise"
    return text + " Only"
