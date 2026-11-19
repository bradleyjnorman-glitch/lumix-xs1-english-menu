# Technical notes — physically tested XS1 patch v25

## Firmware identity

Panasonic's global and Japanese Mac downloads contain the same original `XS1_110S.elf`, SHA-256 `5c1324098d4e456764eae117e31c5b007ea4efafb4a38fed6b5f82d4356f354b`, size 27,918,528 bytes. The original ZIP SHA-256 is `32dc69d2edeeb6d0dd334d963d84b1f296c56ef24a89aa3a0fc1b64b78f7b2e9` (applies to the two checked downloads, not an open-ended guarantee). The original ELF contains embedded MIPS modules using a proprietary Panasonic/Zoran VLC + LZ representation.

## Language permission

The recovered ELF5 regional settings table has 31 entries; the Japanese row (`0x0100`) defaults to Japanese and has available-language mask `0x00000000`. The code contains `app_ship_tbl_chk_language_can_change` at `0x80C71250` and `app_ship_tbl_chk_language_can_select` at `0x80C71274`. English has mask `0x00000001`.

One decoded data byte at runtime `0x804F3724` (ELF5 `.text` offset `0x20024`, frame #3 output index `4328`) changes `00 → 01`. **No change to factory region/model key or other language mask bits** is intended.

## Compression and exact repacking

- Four stock segments: ELF3 code 127 frames; ELF4 code 69; ELF5 code 603; ELF5 data 10. **809 frames total.**
- The original VLC tables can be decoded using a two-type lookup allocation scheme and a DEFLATE-style literal/length/distance + LZ history model. It is *not* raw DEFLATE and standard zlib cannot decode the stream.
- Compressed byte stream containing Japanese mask: ELF5 frame #3, stock file offset `0x005DD0BC`, **10,496 bytes**.
- The original byte is generated from an LZ match. Replacing the match alone changed 51 unwanted decoded bytes via subsequent LZ references. The tested patcher repairs **six** token sites in total (one target and five downstream token repairs), preserving the original stream byte length.
- The modified compressed stream differs at **9,090 bytes** from stock due to bit-packing shifts. This does not reflect 9,090 changes in decompressed code/data.
- The frame decodes to the exact expected **42,360 bytes** with **only one decoded byte different**.
- Its outgoing 32,768-byte LZ history equals stock; all **808 other frame streams** are byte-identical, establishing that their decoded output remains stock given unchanged input and history.
- The following frame #4 was independently decoded to the original expected digest. Corruption negative-controls were rejected.

## Version and installation

The program-version display remains `1.1`. To pass one verified updater gate, the package field at `0x200084` is changed from `0x0113` to `0x0114` (big-endian). Native MIPS code in `FWupdateCheck_form_SDCard` reads this field.

The stock SD-card flash path contains MD5-check switches; inspection found a header value `0x55AA` and a branch that skips a preliminary MD5, and the normal path clears the flag for a later burn-time MD5. These observations are **not** proof that all XS1 updater checks or flash stages were emulated.

The actual physical Japanese XS1 **accepted and installed** the v25 image. This settles installation feasibility for that particular camera and image, but does not eliminate brick risk for other devices.

## Reproducibility

From stock Panasonic ZIP/ELF:

```sh
python tools/xs1_patch.py XS1_V11.zip --out output
```

The builder checks the original hash and the exact candidate SHA-256 `d4ccf2473d498901015cdbc89dd6f59affa821ea50a649af3dad2128fea3316c`, including all 809 compressed frame structures, decoded single-byte difference, subsequent LZ-history equivalence and negative control.

The byte-level version increase does **not** make the image firmware v1.2; it only affects a separate update-advertisement field. Official program version displayed after installation is still v1.1.
