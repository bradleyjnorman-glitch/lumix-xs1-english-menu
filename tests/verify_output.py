#!/usr/bin/env python3
"""Independent package-level check for the exact physically tested XS1 v25 image."""
import hashlib
import io
import sys
import zipfile
from pathlib import Path

STOCK = "5c1324098d4e456764eae117e31c5b007ea4efafb4a38fed6b5f82d4356f354b"
CANDIDATE = "d4ccf2473d498901015cdbc89dd6f59affa821ea50a649af3dad2128fea3316c"
OFFSET, STREAM_SIZE = 0x005DD0BC, 10496
VERSION = 0x200084
LENGTH = 27918528


def stock_bytes(path):
    data = Path(path).read_bytes()
    if zipfile.is_zipfile(io.BytesIO(data)):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = [name for name in z.namelist() if name.rsplit("/", 1)[-1].lower() == "xs1_110s.elf"]
            if len(names) != 1:
                raise ValueError("Expected exactly one XS1_110S.elf in ZIP")
            data = z.read(names[0])
    if hashlib.sha256(data).hexdigest() != STOCK:
        raise ValueError("Stock hash mismatch")
    return data


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python tests/verify_output.py <stock-zip-or-elf> <candidate-elf>")
    original, candidate = stock_bytes(sys.argv[1]), Path(sys.argv[2]).read_bytes()
    assert len(original) == len(candidate) == LENGTH
    assert hashlib.sha256(candidate).hexdigest() == CANDIDATE
    assert original[VERSION:VERSION+2] == bytes.fromhex("0113")
    assert candidate[VERSION:VERSION+2] == bytes.fromhex("0114")
    differences = [i for i, (a, b) in enumerate(zip(original, candidate)) if a != b]
    assert len(differences) == 9091
    assert sum(VERSION <= i < VERSION+2 for i in differences) == 1
    assert all(OFFSET <= i < OFFSET + STREAM_SIZE or VERSION <= i < VERSION+2 for i in differences)
    assert original[:0x200] == candidate[:0x200]
    print("PASS — exact physically tested v25 bytes; only expected compressed stream/version differ")
    print("SHA-256:", hashlib.sha256(candidate).hexdigest())


if __name__ == "__main__":
    main()
