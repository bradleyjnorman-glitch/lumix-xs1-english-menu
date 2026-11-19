# Reproduce the verified firmware image

No Panasonic firmware is included in this repository, so tests require your own official stock v1.1 ZIP or extracted `.elf`.

```sh
python tools/xs1_patch.py XS1_V11.zip --out output
python tests/verify_output.py XS1_V11.zip output/english/XS1_110S.elf
```

`xs1_patch.py` checks the input original SHA-256, rebuilds the frame, independently decodes it, verifies the single-byte difference, the 32 KiB history, frame consistency, following frame and negative-control corruption, then checks the exact physically tested output hash before finishing.

`verify_output.py` is a separate, fast package-level auditor. It rejects alternate model/version input and wrong output hashes and checks the two allowed file-change regions.
