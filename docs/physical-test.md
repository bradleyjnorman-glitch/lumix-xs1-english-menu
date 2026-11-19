# Physical hardware test — 19 November 2026

## Confirmed by the camera owner

- Camera: **Japanese-market Panasonic Lumix DMC-XS1**.
- Original installed camera firmware: **v1.1**.
- Source: original stock Panasonic v1.1 image, reproduced using the v25 patcher.
- Modified filename: `XS1_110S.elf`, size **27,918,528 bytes**.
- Modified SHA-256: `d4ccf2473d498901015cdbc89dd6f59affa821ea50a649af3dad2128fea3316c`.

After physically installing this experimental image, the owner reported:

1. The firmware updater loaded and the camera switched itself off.
2. On restarting, **no Language item appeared in ordinary Setup**.
3. The owner entered Panasonic's temporary **INITIAL SETTINGS cancellation** function by holding **Playback + Up + Zoom W** while switching the camera on. The **Language** item was then enabled (not greyed out).
4. The owner selected **English**, and the menus displayed English.
5. After switching the camera off and on, English still worked.
6. The normal Setup menu still did not contain a Language item.
7. The owner reported that everything else worked normally, and **Version Disp. showed v1.1**.

This is a successful **persistent English-language conversion**, with the exact temporary INITIAL SETTINGS cancellation button sequence confirmed by the camera owner for making the initial English selection.

## Not verified

- Identical behaviour on a second XS1, or on DMC-FH10/DMC-FS50.
- Comprehensive testing of every camera feature, service setting or calibration.
- Reinstalling Panasonic stock firmware as a rollback.
- Recovery after a failed or interrupted flash.

No service backup files, serial numbers, photographs, or other user-specific data are included in this public repository.
