"""One-time curated translations for text excluded by the original scanner."""

import csv

import aw_vi_tool as tool


TRANSLATIONS = {
    0x082704: "DEN", 0x08273C: "MAY", 0x280B2A: "Tin", 0x280B3A: "Het",
    0x282CA0: "Truc B", 0x282CA8: "Truc T",
    0x28B552: "Quan", 0x28B55A: "Tin", 0x28B562: "Luc", 0x28B56A: "Luu",
    0x28B572: "Tuychon", 0x28B57E: "Het", 0x28B586: "Thuat",
    0x28B58E: "Trang", 0x28B59A: "CO", 0x28B5A2: "Luat",
    0x28B5AA: "Bat Nhac", 0x28B5B6: "Tat Nhac",
    0x28B5C2: "Canh A", 0x28B5CE: "Canh B", 0x28B5DA: "Canh C",
    0x28B5E6: "Tat Canh", 0x28B5F2: "Xoa", 0x28B5FE: "Hang",
    0x28B604: "Ra Map", 0x28B612: "Thang", 0x28B61E: "Khi Hau",
    0x28B62A: "Ban", 0x28B632: "Ban", 0x28B63A: "Doat", 0x28B642: "Doat",
    0x28B64E: "Chat", 0x28B656: "Tha", 0x28B65E: "Tha",
    0x28B666: "Ghep", 0x28B66E: "TiepTe", 0x28B67A: "Cho",
    0x28B682: "Lan", 0x28B68A: "Noi",
    0x2BC74C: "Um... Toi khong.{PAGE}",
    0x2BCC88: "A, um...{PAGE}", 0x2BE1C0: "Um...{PAGE}",
    0x2BE8C0: "Hic... Toi lai thua...{PAGE}",
    0x2BF494: "O... do la...{PAGE}", 0x2C0608: "A... Duoc...{PAGE}",
    0x2C079C: "A, ta...{PAGE}", 0x2C0CC0: "Toi... thua mot co gai?{PAGE}",
    0x2C0DC8: "A, OK...{PAGE}", 0x2C1114: "Huh...{PAGE}",
    0x2C1228: "A, OK...{PAGE}", 0x2C14D8: "A, OK...{PAGE}",
    0x2C29D0: "Nhung... Sonja, toi...{PAGE}",
    0x2C2AE8: "A, toi...{PAGE}", 0x2C2B60: "Um...{PAGE}",
    0x2C2EEC: "Sao...?{PAGE}", 0x2C34D4: "A...{PAGE}",
    0x2C39A4: "(tho dai){PAGE}", 0x2C4470: "Um...{PAGE}",
    0x2C8C04: "Hm.{PAGE}", 0x2C9FF8: "Nhung...{PAGE}",
    0x2E9F14: "   Co      Ko", 0x2EA284: "Thua",
    0x2EC710: "Dong bang xanh tot.{NL}De di lai nhung{NL}gan nhu khong co{NL}cho an nap.",
    0x2F13A8: "Chien su bat dau!{NL}{PLAYER}, san sang chua?",
    0x3B7F94: "{0C}Loi ket noi.{NL}Nhan START de khoi dong lai.{PAGE}",
    0x2F62D0: "Ha ha ha ha!{PAGE}",
    0x2FB6E4: "A, toi... Um...{PAGE}",
    0x2FCA9C: "Hm...{PAGE}",
    0x2FCBAC: "Nhung...{PAGE}",
    0x2FCCA8: "Hm...",
    0x2FDAC0: "Toi... choang vang...{PAGE}",
    0x2FFD6C: "Nhung...{PAGE}",
    0x30208C: "Nhung...{PAGE}",
    0x30438C: "Nhung...{PAGE}",
    0x3075DC: "Co! Ta thang!",
    0x3D8ED8: "Het", 0x3D8EDC: "Tuychon",
    0x3D8EE4: "Hang", 0x3D8EEC: "Cho",
    0x3D8EF4: "Ghep", 0x3D8EFC: "Ban",
    0x3D923C: "CHO", 0x3D9264: "CHUA KET NOI",
    0x3D9274: "XONG", 0x3D927C: "LOI",
    0x3D9284: "DA NOI", 0x3D9290: "CHU",
    0x3D92F8: "NHAN START", 0x3D9304: "CHO VAO",
    0x3F3604: "   co       ko",
    0x3F609C: "Quan Orange Star da thua!{0E}{0E}",
    0x3F60C0: "Quan Blue Moon da thua!{0E}{0E}",
    0x3F60E0: "Quan Green Earth da thua!{0E}{0E}",
    0x3F6104: "Quan Yellow Comet da thua!{0E}{0E}",
    0x3F6264: "Dau hang la thua.{NL}Ban chac muon dau hang?{0E}{18}",
    0x3F6A8C: ("Vung Alara rat xa xoi.{PAGE}Vi vay Olaf chua dua{NL}"
               "nhieu quan den day.{PAGE}Ban co hai {UNIT}bo binh{NORMAL}{NL}"
               "duoi quyen chi huy.{PAGE}").replace(" ", "{1A}"),
}


def main() -> None:
    assert TRANSLATIONS.keys() == tool.SUPPLEMENTAL_TEXT.keys()
    with tool.DEFAULT_CSV.open("r", encoding="utf-8-sig", newline="") as file:
        existing = {int(row["offset"], 16) for row in csv.DictReader(file)}
    rows = []
    errors = []
    for offset, raw in sorted(tool.SUPPLEMENTAL_TEXT.items()):
        if offset in existing:
            continue
        value = TRANSLATIONS[offset]
        try:
            tool.validate_translation(raw, tool.parse_translation(value), offset)
        except tool.ToolError as exc:
            errors.append(str(exc))
        rows.append({
            "offset": f"{offset:06X}", "max_bytes": len(raw),
            "original_hex": raw.hex().upper(), "english": tool.display(raw),
            "vietnamese": value,
        })
    if errors:
        raise tool.ToolError("\n".join(errors))
    with tool.DEFAULT_CSV.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=tool.CSV_FIELDS)
        writer.writerows(rows)
    print(f"Added {len(rows)} translated entries")


if __name__ == "__main__":
    main()
