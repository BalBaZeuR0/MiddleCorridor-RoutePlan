"""Referans koridorlar, kalibrasyon ve doğrulama (World Bank 2023 ile)."""
import ag

d, k, r, o = "demiryolu", "kisa_deniz", "karayolu", "okyanus"


def _yol(*parcalar):
    """[(dugum, mod), ...] kısa yazım: ('XIA', d), ..."""
    return list(parcalar)


# Xi'an → Duisburg referans koridorları
KORIDORLAR = {
    "Kuzey Koridoru\n(Rusya–Belarus)": _yol(
        ("XIA", d), ("DOS", d), ("MOW", d), ("BRE", d), ("DUI", d)),
    "Orta Koridor –\nGürcistan limanları": _yol(
        ("XIA", d), ("KHO", d), ("ALA", d), ("AKT", d), ("AKT", k), ("BAK", k), ("BAK", d),
        ("GAR", d), ("TBS", d), ("POT", d), ("POT", k), ("CND", k), ("CND", d), ("BUD", d), ("DUI", d)),
    "Orta Koridor –\nTürkiye (BTK)": _yol(
        ("XIA", d), ("KHO", d), ("ALA", d), ("AKT", d), ("AKT", k), ("BAK", k), ("BAK", d),
        ("GAR", d), ("TBS", d), ("AHK", d), ("KRS", d), ("ERZ", d), ("SIV", d), ("ANK", d),
        ("IST", d), ("KPK", d), ("SOF", d), ("BUD", d), ("DUI", d)),
    "Deniz yolu –\nSüveyş": _yol(
        ("XIA", d), ("SHA", d), ("SHA", o), ("SIN", o), ("DND", o), ("BAB", o), ("PSD", o),
        ("PIR", o), ("GIB", o), ("FIN", o), ("USH", o), ("RTM", o), ("RTM", d), ("DUI", d)),
    "Deniz yolu –\nÜmit Burnu": _yol(
        ("XIA", d), ("SHA", d), ("SHA", o), ("SIN", o), ("CGH", o), ("DKR", o), ("FIN", o),
        ("USH", o), ("RTM", o), ("RTM", d), ("DUI", d)),
}

# Kalibrasyon parçası: Khorgos → Köstence (WB23: 2022'de 50–53 gün)
KALIBRASYON_YOLU = _yol(("KHO", d), ("ALA", d), ("AKT", d), ("AKT", k), ("BAK", k), ("BAK", d),
                        ("GAR", d), ("TBS", d), ("POT", d), ("POT", k), ("CND", k))
KALIBRASYON_HEDEF_GUN = 51.5  # 50–53 aralığının orta noktası

# Doğrulama parçası: Khorgos → Kapıkule (WB23: Türkiye üzerinden 40–45 gün)
DOGRULAMA_TR_YOLU = _yol(("KHO", d), ("ALA", d), ("AKT", d), ("AKT", k), ("BAK", k), ("BAK", d),
                         ("GAR", d), ("TBS", d), ("AHK", d), ("KRS", d), ("ERZ", d), ("SIV", d),
                         ("ANK", d), ("IST", d), ("KPK", d))


def kalibre_et(p=ag.P):
    """Liman bekleme katsayısı alfa'yı, kalibrasyon yolunun süresi hedefe eşit olacak şekilde çözer."""
    p["alfa"] = 1.0
    g = ag.graf_kur("S1", p)
    oz = ag.yol_ozeti(g, KALIBRASYON_YOLU)
    liman = oz["bekleme_liman"]
    diger = oz["sure"] - liman
    p["alfa"] = (KALIBRASYON_HEDEF_GUN - diger) / liman
    return p["alfa"]


if __name__ == "__main__":
    a = kalibre_et()
    print(f"alfa (liman bekleme kalibrasyon katsayısı) = {a:.3f}")
    print(f"birim maliyet demiryolu = {ag.P['birim_maliyet']['demiryolu']:.3f} USD/FEU-km")
    print(f"birim maliyet okyanus   = {ag.P['birim_maliyet']['okyanus']:.4f} USD/FEU-km")
    g = ag.graf_kur("S1")
    for ad, yol in [("Kalibrasyon KHO→CND (hedef 50–53 g)", KALIBRASYON_YOLU),
                    ("Doğrulama KHO→KPK (WB: TR üzerinden 40–45 g)", DOGRULAMA_TR_YOLU)]:
        oz = ag.yol_ozeti(g, yol)
        print(f"{ad}: süre {oz['sure']:.1f} g, maliyet {oz['maliyet']:.0f} USD, {oz['km']:.0f} km")
    print()
    for sen in ag.SENARYOLAR:
        g = ag.graf_kur(sen)
        print(f"--- {sen}: {ag.SENARYOLAR[sen]}")
        for ad, yol in KORIDORLAR.items():
            try:
                oz = ag.yol_ozeti(g, yol)
            except KeyError:
                print(f"  {ad.replace(chr(10), ' '):38s}  (kapalı)")
                continue
            print(f"  {ad.replace(chr(10), ' '):38s} {oz['km']:7.0f} km  {oz['sure']:5.1f} g "
                  f"(hareket {oz['hareket']:4.1f}, liman {oz['bekleme_liman']:4.1f}, sınır {oz['bekleme_sinir']:4.1f})"
                  f"  {oz['maliyet']:6.0f} USD  {oz['co2']:6.0f} kg CO2")
