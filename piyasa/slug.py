"""İsimleri adres dostu metne çevirir: 'Graves Jeffrey A' -> 'graves-jeffrey-a'"""

import re

TR_HARFLER = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slugify(metin):
    if not metin:
        return ""
    metin = metin.translate(TR_HARFLER).lower()
    metin = re.sub(r"[^a-z0-9]+", "-", metin)
    return metin.strip("-")