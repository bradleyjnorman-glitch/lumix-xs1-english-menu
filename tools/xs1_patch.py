#!/usr/bin/env python3
"""Reproduce the single physically tested XS1 v25 English unlock from stock firmware.

No camera I/O. Requires only Python standard library and the verified original
Panasonic XS1 v1.1 ELF or ZIP. Refuses unknown firmware and wrong output hashes.
"""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

CANDIDATE_SHA256 = "d4ccf2473d498901015cdbc89dd6f59affa821ea50a649af3dad2128fea3316c"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stock_firmware", type=Path, help="official unmodified XS1_V11.zip or XS1_110S.elf")
    ap.add_argument("--out", type=Path, default=Path("output"), help="output directory (default: output)")
    args = ap.parse_args()
    tools_dir = Path(__file__).resolve().parent
    manifest = tools_dir.parent / "data" / "stock_decode_manifest_v21.json"
    dest = args.out.resolve() / "english" / "XS1_110S.elf"
    report = args.out.resolve() / "build-report.json"
    # The original tested patcher refuses any unexpected stock image. This
    # wrapper only standardises the interface and verifies the final bytes.
    source = args.stock_firmware.resolve()
    cmd = [sys.executable, str(tools_dir / "_repair_frame3.py"),
           str(source), str(manifest), "--out", str(report),
           "--firmware-output", str(dest)]
    args.out.mkdir(parents=True, exist_ok=True)
    print("Building from the exact verified Panasonic XS1 v1.1 image...", flush=True)
    subprocess.run(cmd, check=True)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    if sha != CANDIDATE_SHA256:
        dest.unlink(missing_ok=True)
        raise RuntimeError("Output hash mismatch: removed candidate")
    print("\nPHYSICALLY TESTED v25 IMAGE REPRODUCED")
    print("File: ", dest)
    print("SHA-256:", sha)
    print("WARNING: No established recovery for interrupted or failed flashing.")
    print("On tested Japanese XS1, choose English through service mode AFTER update.")


if __name__ == "__main__":
    main()
