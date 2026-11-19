# Panasonic Lumix DMC-XS1: Japanese-to-English menu unlock

A **physically tested, reproducible firmware modification** that enables English on a Japanese-market Panasonic Lumix **DMC-XS1**, using Panasonic's official **v1.1** firmware.

**Confirmed on one real Japanese DMC-XS1 on 19 November 2026.** The modified update installed, the camera shut down normally, the Language option became selectable **in service mode**, English worked and persisted after power-off/power-on, the camera's regular functions continued working, and **Version Disp. still shows v1.1**.

> **Important limitation:** The Language item is **still absent in the normal Setup menu** on the tested Japanese XS1. The owner selected English from the **service-mode Language menu** once after flashing. The selected language then remained English in normal operation, including after restarting the camera.

**Independent, unofficial project. Not a Panasonic release. No known reliable recovery from a failed flash. Tested on one physical XS1 only.** Do not assume compatibility with the related DMC-FH10/DMC-FS50 despite the shared official firmware package, or with another firmware baseline.

## What changes

Exactly two intended *semantic* values in the original official v1.1 image:

1. The Japanese-region **English-permission bit**, recovered ELF5 runtime address `0x804F3724`, `00 → 01`. Original default remains Japanese until English is selected in service mode.
2. The updater's **advertised version field**, file offset `0x200084`, big-endian `0x0113 → 0x0114`, to pass a verified same-version gate. The installed version display remains **v1.1**.

Panasonic's compressed ELF5 frame #3 needs a targeted repack: a direct compressed-byte substitution was rejected because it corrupted 51 unintended decoded bytes. The supplied patcher repairs downstream LZ references and verifies **only one decoded language-permission byte differs**, the 32 KiB history passed to subsequent frames is identical, and the other 808 compressed streams are unchanged. No other executable instructions or regional records are deliberately changed.

## Why this repository has no firmware `.elf`

This repository **does not contain Panasonic firmware** or a ready-to-flash `.elf` file. Obtain your own original `XS1_V11.zip` from [Panasonic's official XS1/FH10/FS50 v1.1 firmware page](https://av.jpn.support.panasonic.com/support/global/cs/dsc/download/XS1_FH10_FS50/index.html) and its [download and update instructions](https://av.jpn.support.panasonic.com/support/global/cs/dsc/download/XS1_FH10_FS50/index2.html).

Panasonic's **Mac ZIP** also works on Windows; you do not need to run a downloaded `.exe`. The script accepts the ZIP or its extracted `XS1_110S.elf`.

| Verification | SHA-256 |
| --- | --- |
| Original Panasonic `XS1_110S.elf` | `5c1324098d4e456764eae117e31c5b007ea4efafb4a38fed6b5f82d4356f354b` |
| **Physically tested English candidate** | `d4ccf2473d498901015cdbc89dd6f59affa821ea50a649af3dad2128fea3316c` |

The extracted original image is **27,918,528 bytes**. The patcher refuses stock images whose hash differs from the value above.

## Build the tested firmware

Requires **Python 3.10+**, standard library only, on Windows, macOS or Linux. Download or clone this repository, then run from its root:

```sh
python tools/xs1_patch.py XS1_V11.zip --out output
```

Or supply the original ELF:

```sh
python tools/xs1_patch.py XS1_110S.elf --out output
```

The output is:

- `output/english/XS1_110S.elf` — the **exact v25 image physically installed** on one Japanese XS1; the script checks the final SHA-256 before completing.
- `output/build-report.json` — the verification and token-repair report, not firmware.

The patch operates locally; it does **not** connect to the camera, access USB, or flash anything. It deliberately refuses modified or unknown input images.

## Installing on a Japanese XS1 — at your own risk

1. Confirm the exact camera model **DMC-XS1** and baseline **firmware v1.1**. Back up photographs. Fully charge the battery.
2. Prepare a **microSD** card formatted by the camera (with at least 30 MB free).
3. Copy **only** `output/english/XS1_110S.elf` to the **root** of that card (not the ZIP and not in a folder).
4. Turn the camera **off** and insert the card. While holding **Delete/Trash**, press **Power**. This is the XS1-specific update method described by Panasonic.
5. When the update begins, do **not** press controls, remove the card/battery or interrupt power. Panasonic describes approximately 30–50 seconds and automatic shutdown.
6. After it finishes, remove the updater card. **The version display may still say v1.1; this is expected.** Panasonic recommends reformatting the update card before normal photography use.
7. **Access the temporary INITIAL SETTINGS cancellation (service function):** turn the camera **off**, then hold **Playback (▶) + Up (▲) + Zoom W** simultaneously while pressing **Power**. Open the now-selectable **Language** item and choose **English**. The tested XS1 did not show Language in the normal Setup menu.
8. Switch the camera off and on; confirm English persists, and test normal operation.

**Service-function caution:** Panasonic's [XS1 service manual](https://www.manualslib.com/manual/599754/Panasonic-Lumix-Dmc-Xs1p.html) calls this a *temporary cancellation of INITIAL SETTINGS*, rather than a general-purpose service mode. The button combination above is from the manual; **the owner did not record the exact keys used on the successfully converted camera**. Do not execute permanent factory *INITIAL SETTINGS*, region reinitialisation, ROM restore, or other service functions merely to choose a language. See [the hardware-test report](docs/physical-test.md).

The flash may **permanently disable the camera** if it fails. There is no demonstrated emergency recovery method. Nothing in the repo changes that risk.

## Reproducibility and evidence

- [Physical test and limitations](docs/physical-test.md)
- [Exact patch, compression and updater notes](docs/technical-notes.md)
- [Credits, related research and sources](docs/acknowledgements.md)
- [Build verification](tests/README.md)

Only one Japanese XS1 has been physically tested. This is not an officially supported regional conversion, and no rollback firmware has been tested.

## License and ownership

Original patching scripts and project documentation are released under the [MIT License](LICENSE). The Panasonic firmware remains proprietary, belongs to Panasonic and **is not distributed by this repository**. Reference material retains its respective owners' licenses.