"""
Bildiri 1 — Asya–Avrupa çok modlu taşıma ağı (Türkiye karaköprüsü odaklı).

Durum uzayı: (düğüm, mod). Kenar türleri:
  - hat     : aynı mod içinde iki düğüm arası taşıma
  - aktarma : aynı düğümde mod değişimi (liman/terminal bekleme + elleçleme)
Amaçlar: maliyet (USD/FEU), süre (gün), CO2 (kg/FEU).

Parametre kaynakları:
  WB23 = World Bank (2023) Middle Trade and Transport Corridor
  VARS = varsayım (bildiride etiketlenir, duyarlılık analizi yapılır)
"""
from __future__ import annotations
import math
from collections import defaultdict

MODLAR = ("demiryolu", "karayolu", "okyanus", "kisa_deniz")
MOD_AD = {"demiryolu": "Demiryolu", "karayolu": "Karayolu",
          "okyanus": "Okyanus", "kisa_deniz": "Kısa mesafe deniz / feribot"}

# ---------------------------------------------------------------- DÜĞÜMLER
# kod: (ad, enlem, boylam, tip, bölge)   tip: sehir | liman | sinir | ara
DUGUMLER = {
    "XIA": ("Xi'an", 34.27, 108.95, "sehir", "Çin"),
    "SHA": ("Şanghay", 31.23, 121.47, "liman", "Çin"),
    "KHO": ("Khorgos", 44.21, 80.41, "sinir", "Kazakistan"),
    "DOS": ("Dostyk", 45.25, 82.48, "sinir", "Kazakistan"),
    "ALA": ("Almatı", 43.24, 76.89, "sehir", "Kazakistan"),
    "AKT": ("Aktau", 43.65, 51.17, "liman", "Kazakistan"),
    "KUR": ("Kuryk", 43.17, 51.67, "liman", "Kazakistan"),
    "BAK": ("Bakü/Alat", 39.94, 49.40, "liman", "Kafkasya"),
    "GAR": ("Gardabani", 41.37, 45.10, "sinir", "Kafkasya"),
    "TBS": ("Tiflis", 41.72, 44.79, "sehir", "Kafkasya"),
    "AHK": ("Ahılkelek", 41.40, 43.49, "sinir", "Kafkasya"),
    "POT": ("Poti", 42.15, 41.67, "liman", "Kafkasya"),
    "BAT": ("Batum", 41.65, 41.64, "liman", "Kafkasya"),
    "KRS": ("Kars", 40.60, 43.10, "sehir", "Türkiye"),
    "ERZ": ("Erzurum", 39.90, 41.27, "sehir", "Türkiye"),
    "SIV": ("Sivas", 39.75, 37.02, "sehir", "Türkiye"),
    "ANK": ("Ankara", 39.93, 32.86, "sehir", "Türkiye"),
    "IST": ("İstanbul", 41.03, 28.78, "sehir", "Türkiye"),
    "KPK": ("Kapıkule", 41.72, 26.36, "sinir", "Türkiye"),
    "SAM": ("Samsun", 41.29, 36.33, "liman", "Türkiye"),
    "TZX": ("Trabzon", 41.00, 39.72, "liman", "Türkiye"),
    "MER": ("Mersin", 36.80, 34.63, "liman", "Türkiye"),
    "AMB": ("Ambarlı", 40.97, 28.69, "liman", "Türkiye"),
    "IZM": ("İzmir", 38.44, 27.14, "liman", "Türkiye"),
    "CND": ("Köstence", 44.17, 28.65, "liman", "Avrupa"),
    "SOF": ("Sofya", 42.70, 23.32, "sehir", "Avrupa"),
    "BUD": ("Budapeşte", 47.50, 19.04, "sehir", "Avrupa"),
    "MOW": ("Moskova", 55.76, 37.62, "sehir", "Kuzey"),
    "BRE": ("Brest", 52.08, 23.65, "sinir", "Kuzey"),
    "DUI": ("Duisburg", 51.43, 6.76, "sehir", "Avrupa"),
    "RTM": ("Rotterdam", 51.95, 4.14, "liman", "Avrupa"),
    "PIR": ("Pire", 37.94, 23.64, "liman", "Avrupa"),
    # deniz ara noktaları (aktarma yok)
    "SIN": ("Singapur", 1.26, 103.82, "ara", "Deniz"),
    "DND": ("Sri Lanka açığı", 5.50, 80.50, "ara", "Deniz"),
    "BAB": ("Bab-el-Mandeb", 12.58, 43.33, "ara", "Deniz"),
    "PSD": ("Süveyş Kanalı", 31.26, 32.31, "ara", "Deniz"),
    "GIB": ("Cebelitarık", 35.95, -5.60, "ara", "Deniz"),
    "FIN": ("Finisterre", 43.00, -9.80, "ara", "Deniz"),
    "USH": ("Manş girişi", 48.50, -5.50, "ara", "Deniz"),
    "CGH": ("Ümit Burnu", -34.50, 18.40, "ara", "Deniz"),
    "DKR": ("Dakar açığı", 14.70, -17.90, "ara", "Deniz"),
    "CNK": ("Çanakkale Boğazı", 40.00, 26.20, "ara", "Deniz"),
    "BOS": ("İstanbul Boğazı", 41.23, 29.12, "ara", "Deniz"),
}

# ---------------------------------------------------------------- HATLAR
# (a, b, mod)  — çift yönlü
HATLAR = [
    # Çin içi ve Çin–Kazakistan
    ("XIA", "KHO", "demiryolu"), ("XIA", "DOS", "demiryolu"), ("XIA", "SHA", "demiryolu"),
    ("KHO", "ALA", "demiryolu"), ("DOS", "ALA", "demiryolu"),
    ("ALA", "AKT", "demiryolu"), ("ALA", "KUR", "demiryolu"),
    # Kuzey koridoru
    ("DOS", "MOW", "demiryolu"), ("MOW", "BRE", "demiryolu"), ("BRE", "DUI", "demiryolu"),
    # Hazar geçişi
    ("AKT", "BAK", "kisa_deniz"), ("KUR", "BAK", "kisa_deniz"),
    # Kafkasya demiryolu
    ("BAK", "GAR", "demiryolu"), ("GAR", "TBS", "demiryolu"), ("TBS", "POT", "demiryolu"),
    ("TBS", "BAT", "demiryolu"), ("TBS", "AHK", "demiryolu"), ("AHK", "KRS", "demiryolu"),
    # Türkiye demiryolu
    ("KRS", "ERZ", "demiryolu"), ("ERZ", "SIV", "demiryolu"), ("SIV", "ANK", "demiryolu"),
    ("ANK", "IST", "demiryolu"), ("IST", "KPK", "demiryolu"), ("SAM", "SIV", "demiryolu"),
    ("MER", "ANK", "demiryolu"), ("IZM", "ANK", "demiryolu"), ("AMB", "IST", "demiryolu"),
    # Balkan / Avrupa demiryolu
    ("KPK", "SOF", "demiryolu"), ("SOF", "BUD", "demiryolu"), ("CND", "BUD", "demiryolu"),
    ("BUD", "DUI", "demiryolu"), ("RTM", "DUI", "demiryolu"),
    # Karayolu
    ("BAK", "GAR", "karayolu"), ("GAR", "TBS", "karayolu"), ("TBS", "POT", "karayolu"),
    ("TBS", "BAT", "karayolu"), ("BAT", "TZX", "karayolu"), ("TZX", "ERZ", "karayolu"),
    ("TBS", "KRS", "karayolu"), ("KRS", "ERZ", "karayolu"), ("ERZ", "SIV", "karayolu"),
    ("SIV", "ANK", "karayolu"), ("ANK", "IST", "karayolu"), ("IST", "KPK", "karayolu"),
    ("KPK", "SOF", "karayolu"), ("SOF", "BUD", "karayolu"), ("BUD", "DUI", "karayolu"),
    ("ANK", "MER", "karayolu"), ("ANK", "SAM", "karayolu"), ("IZM", "IST", "karayolu"),
    ("AMB", "IST", "karayolu"), ("CND", "BUD", "karayolu"), ("RTM", "DUI", "karayolu"),
    # Karadeniz kısa mesafe
    ("POT", "CND", "kisa_deniz"), ("BAT", "CND", "kisa_deniz"), ("SAM", "CND", "kisa_deniz"),
    ("AMB", "BOS", "kisa_deniz"), ("BOS", "CND", "kisa_deniz"),
    # Okyanus — Süveyş hattı
    ("SHA", "SIN", "okyanus"), ("SIN", "DND", "okyanus"), ("DND", "BAB", "okyanus"),
    ("BAB", "PSD", "okyanus"), ("PSD", "PIR", "okyanus"), ("PSD", "MER", "okyanus"),
    ("PIR", "IZM", "okyanus"), ("PIR", "CNK", "okyanus"), ("CNK", "AMB", "okyanus"),
    ("AMB", "BOS", "okyanus"), ("BOS", "CND", "okyanus"),
    ("PIR", "GIB", "okyanus"), ("GIB", "FIN", "okyanus"), ("FIN", "USH", "okyanus"),
    ("USH", "RTM", "okyanus"),
    # Okyanus — Ümit Burnu hattı
    ("SIN", "CGH", "okyanus"), ("CGH", "DKR", "okyanus"), ("DKR", "FIN", "okyanus"),
    ("DKR", "GIB", "okyanus"),
]

# ---------------------------------------------------------------- PARAMETRELER
P = {
    # dolaşma katsayısı (gerçek güzergâh / büyük daire)                   VARS
    "dolasma": {"demiryolu": 1.25, "karayolu": 1.20, "okyanus": 1.05, "kisa_deniz": 1.05},
    # etkin hız (km/gün)
    "hiz": {"demiryolu": 600.0,          # 25 km/s etkin (duruşlar dahil)   VARS
            "karayolu": 650.0,           # sürücü çalışma süresi dahil       VARS
            "okyanus": 16 * 1.852 * 24,  # 16 knot                           VARS
            "kisa_deniz": 8 * 1.852 * 24},  # 8 knot (Hazar, WB23 s.42); Karadeniz için de kullanılır
    # birim taşıma maliyeti (USD / FEU-km)
    "birim_maliyet": {"demiryolu": None,   # kalibre: ERA 3.121 USD / Dostyk–Brest mesafesi (WB23 s.39)
                      "karayolu": 1.60,    # VARS (Avrupa FTL ~1,5–2 EUR/km)
                      "okyanus": None,     # kalibre: 1.349 USD / Şanghay–Rotterdam (WB23 s.42)
                      "kisa_deniz": 0.50},  # VARS (Karadeniz feeder)
    "sabit_hat_maliyeti": {("AKT", "BAK"): 460.0, ("KUR", "BAK"): 460.0},  # WB23 s.42
    # CO2 yoğunluğu (g CO2e / t-km) — GLEC v3 ikincil kaynaklar (doğrulanacak)
    "co2": {"demiryolu": 22.0, "karayolu": 80.0, "okyanus": 8.0, "kisa_deniz": 16.0},
    "yuk_ton": 20.0,  # FEU başına net yük                                   VARS
    # liman toplam bekleme (gün) ve elleçleme (USD/FEU)
    "liman": {
        "AKT": (8.5, 148.0, "WB23 s.45 (5–12 gün)"),
        "KUR": (8.5, 148.0, "VARS (Aktau ile aynı)"),
        "BAK": (27.0, 148.0, "WB23 s.45"),
        "POT": (12.0, 275.0, "WB23 Tablo 7"),
        "BAT": (17.0, 430.0, "WB23 Tablo 7"),
    },
    "liman_varsayilan": (7.0, 150.0, "WB23 s.45 'modern limanlar ≈ 7 gün'; maliyet VARS"),
    # iç terminal demiryolu<->karayolu aktarması
    "terminal": (1.0, 120.0),  # VARS
    "terminaller": ("XIA", "ALA", "TBS", "KRS", "ERZ", "SIV", "ANK", "IST", "SOF", "BUD", "DUI", "MOW"),
    # sınır/ray açıklığı geçişi: düğüme (o modla) varışta eklenen süre (gün)
    "gecis": {
        ("KHO", "demiryolu"): (2.5, "WB23 s.50 (Dostyk ≈ 60 saat; Khorgos benzer)"),
        ("DOS", "demiryolu"): (2.5, "WB23 s.50"),
        ("GAR", "demiryolu"): (3.0, "WB23 s.51 (ort. > 3 gün)"),
        ("GAR", "karayolu"): (0.5, "VARS"),
        ("AHK", "demiryolu"): (1.0, "VARS (BTK ray açıklığı değişimi)"),
        ("BRE", "demiryolu"): (1.5, "VARS (ray açıklığı değişimi)"),
        ("KPK", "demiryolu"): (1.0, "VARS"),
        ("KPK", "karayolu"): (1.0, "VARS"),
        ("IST", "demiryolu"): (0.5, "VARS (Marmaray yük slotu)"),
    },
    "hat_ek_gecis": {("BAT", "TZX", "karayolu"): 0.5, ("TBS", "KRS", "karayolu"): 0.5},  # VARS sınır
    "alfa": 1.0,  # liman bekleme kalibrasyon katsayısı (kalibrasyon.py hesaplar)
}

ORTA_KORIDOR_LIMANLARI = ("AKT", "KUR", "BAK", "POT", "BAT")
ORTA_KORIDOR_GECISLERI = ("KHO", "GAR", "AHK")

SENARYOLAR = {
    "S1": "2022 mevcut durum",
    "S2": "2030 hedefi (Orta Koridor bekleme süreleri yarıya)",
    "S3": "Kızıldeniz kapalı (Ümit Burnu)",
    "S4": "Kuzey koridoru kullanılamaz",
    "S5": "S3 + S4 (iki alternatif birden kapalı)",
    "S6": "S2 + S3 + S4 (2030 hedefi, alternatifler kapalı)",
}
# senaryo bayrakları: (iyilestirme_2030, kizildeniz_kapali, kuzey_kapali)
_BAYRAK = {"S1": (0, 0, 0), "S2": (1, 0, 0), "S3": (0, 1, 0), "S4": (0, 0, 1),
           "S5": (0, 1, 1), "S6": (1, 1, 1)}


def iyilestirme(s): return bool(_BAYRAK[s][0])
def kizildeniz_kapali(s): return bool(_BAYRAK[s][1])
def kuzey_kapali(s): return bool(_BAYRAK[s][2])


# ---------------------------------------------------------------- yardımcılar
def buyuk_daire_km(a: str, b: str) -> float:
    _, la1, lo1, *_ = DUGUMLER[a]
    _, la2, lo2, *_ = DUGUMLER[b]
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def hat_uzunlugu(a, b, mod):
    return buyuk_daire_km(a, b) * P["dolasma"][mod]


def _kalibre_birim_maliyetler(p):
    # demiryolu: ERA batı yönü tarifesi 3.121 USD/FEU, Dostyk→Moskova→Brest
    d = hat_uzunlugu("DOS", "MOW", "demiryolu") + hat_uzunlugu("MOW", "BRE", "demiryolu")
    p["birim_maliyet"]["demiryolu"] = 3121.0 / d
    # okyanus: Drewry WCI 1.349 USD/FEU, Şanghay→Süveyş→Rotterdam
    yol = ["SHA", "SIN", "DND", "BAB", "PSD", "PIR", "GIB", "FIN", "USH", "RTM"]
    d = sum(hat_uzunlugu(x, y, "okyanus") for x, y in zip(yol, yol[1:]))
    p["birim_maliyet"]["okyanus"] = 1349.0 / d


_kalibre_birim_maliyetler(P)


# ---------------------------------------------------------------- GRAF
class Graf:
    """Durum grafı. kenarlar[u] = [(v, (maliyet, sure, co2), bilgi), ...]"""

    def __init__(self):
        self.kenarlar = defaultdict(list)

    def ekle(self, u, v, vek, bilgi):
        self.kenarlar[u].append((v, vek, bilgi))

    def durumlar(self):
        s = set(self.kenarlar)
        for u in self.kenarlar:
            s.update(v for v, *_ in self.kenarlar[u])
        return s

    def kenar(self, u, v):
        for w, vek, bilgi in self.kenarlar[u]:
            if w == v:
                return vek, bilgi
        raise KeyError(f"kenar yok: {u} -> {v}")


def liman_parametresi(n, senaryo, p=P):
    sure, maliyet, _ = p["liman"].get(n, p["liman_varsayilan"])
    sure *= p["alfa"]
    if iyilestirme(senaryo) and n in ORTA_KORIDOR_LIMANLARI:
        sure *= 0.5
    return sure, maliyet


def gecis_suresi(n, mod, senaryo, p=P):
    if (n, mod) not in p["gecis"]:
        return 0.0
    s = p["gecis"][(n, mod)][0]
    if iyilestirme(senaryo) and n in ORTA_KORIDOR_GECISLERI:
        s *= 0.5
    return s


def graf_kur(senaryo="S1", p=P) -> Graf:
    g = Graf()
    for a, b, mod in HATLAR:
        if kizildeniz_kapali(senaryo) and {a, b} == {"BAB", "PSD"}:
            continue
        if kuzey_kapali(senaryo) and {a, b} == {"DOS", "MOW"}:
            continue
        L = hat_uzunlugu(a, b, mod)
        sabit = p["sabit_hat_maliyeti"].get((a, b)) or p["sabit_hat_maliyeti"].get((b, a))
        maliyet = sabit if sabit is not None else L * p["birim_maliyet"][mod]
        hareket = L / p["hiz"][mod]
        co2 = L * p["yuk_ton"] * p["co2"][mod] / 1000.0
        ek = p["hat_ek_gecis"].get((a, b, mod)) or p["hat_ek_gecis"].get((b, a, mod)) or 0.0
        for u, v in ((a, b), (b, a)):
            bekleme = ek + gecis_suresi(v, mod, senaryo, p)
            g.ekle((u, mod), (v, mod), (maliyet, hareket + bekleme, co2),
                   {"tur": "hat", "mod": mod, "km": L, "hareket": hareket, "bekleme": bekleme})
    # aktarmalar
    modlar_dugumde = defaultdict(set)
    for a, b, mod in HATLAR:
        modlar_dugumde[a].add(mod)
        modlar_dugumde[b].add(mod)
    for n, mods in modlar_dugumde.items():
        tip = DUGUMLER[n][3]
        if tip == "ara":
            continue
        for m1 in mods:
            for m2 in mods:
                if m1 == m2:
                    continue
                deniz = m1 in ("okyanus", "kisa_deniz") or m2 in ("okyanus", "kisa_deniz")
                if deniz and tip == "liman":
                    sure, maliyet = liman_parametresi(n, senaryo, p)
                elif not deniz and n in p["terminaller"]:
                    sure, maliyet = p["terminal"]
                else:
                    continue
                g.ekle((n, m1), (n, m2), (maliyet, sure, 0.0),
                       {"tur": "aktarma", "mod": f"{m1}->{m2}", "km": 0.0, "hareket": 0.0, "bekleme": sure})
    return g


def kaynak_hedef_ekle(g: Graf, kaynak: str, hedef: str):
    """Sanal başlangıç/bitiş durumları: ('*', kaynak) ve ('#', hedef)."""
    s, t = (kaynak, "*"), (hedef, "#")
    for (n, mod) in list(g.durumlar()):
        if n == kaynak and mod in MODLAR:
            g.ekle(s, (n, mod), (0.0, 0.0, 0.0), {"tur": "sanal", "mod": mod, "km": 0, "hareket": 0, "bekleme": 0})
        if n == hedef and mod in MODLAR:
            g.ekle((n, mod), t, (0.0, 0.0, 0.0), {"tur": "sanal", "mod": mod, "km": 0, "hareket": 0, "bekleme": 0})
    return s, t


def yol_ozeti(g: Graf, durumlar):
    """Durum dizisi boyunca maliyet/süre/CO2 ve süre kırılımı."""
    top = {"maliyet": 0.0, "sure": 0.0, "co2": 0.0, "hareket": 0.0, "bekleme_liman": 0.0,
           "bekleme_sinir": 0.0, "km": 0.0}
    for u, v in zip(durumlar, durumlar[1:]):
        vek, b = g.kenar(u, v)
        top["maliyet"] += vek[0]
        top["sure"] += vek[1]
        top["co2"] += vek[2]
        top["km"] += b["km"]
        top["hareket"] += b["hareket"]
        if b["tur"] == "aktarma":
            top["bekleme_liman"] += b["bekleme"]
        else:
            top["bekleme_sinir"] += b["bekleme"]
    return top
