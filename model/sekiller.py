"""Bildiri 1 şekilleri. Çıktı: ../sekiller/*.png (300 dpi) ve *.pdf"""
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle, FancyArrowPatch, Polygon
import matplotlib.patheffects as pe

import ag
import koridorlar as kor

BURASI = os.path.dirname(os.path.abspath(__file__))
CIKTI = os.path.join(BURASI, "..", "sekiller")
GEOJSON = os.path.join(BURASI, "..", "veri_harici", "ne_50m_countries.geojson")
os.makedirs(CIKTI, exist_ok=True)

plt.rcParams.update({
    "font.family": "Arial", "font.size": 8.5, "axes.edgecolor": "#8a8984",
    "axes.labelcolor": "#2b2b2a", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.linewidth": 0.6, "savefig.dpi": 300, "pdf.fonttype": 42,
})

YUZEY = "#fcfcfb"
METIN = "#0b0b0b"
METIN2 = "#52514e"
SOLUK = "#8a8984"
KARA = "#e9e7e2"
KARA_TR = "#d9d4c7"
SINIR_CIZGI = "#ffffff"
DENIZ = "#f4f7f9"

MOD_RENK = {"demiryolu": "#2a78d6", "karayolu": "#eb6834", "okyanus": "#1baf7a", "kisa_deniz": "#1baf7a"}
MOD_STIL = {"demiryolu": "-", "karayolu": "-", "okyanus": "-", "kisa_deniz": (0, (3, 1.6))}
MOD_KALINLIK = {"demiryolu": 1.7, "karayolu": 1.2, "okyanus": 1.5, "kisa_deniz": 1.5}

KOMPONENT_RENK = {"hareket": "#6250d6", "bekleme_liman": "#e87ba4", "bekleme_sinir": "#eda100"}
KOMPONENT_AD = {"hareket": "Hareket (yolda geçen süre)", "bekleme_liman": "Liman bekleme / aktarma",
                "bekleme_sinir": "Sınır ve ray açıklığı geçişi"}


DIL = os.environ.get("SEKIL_DIL", "tr")


def kaydet(fig, ad):
    if DIL == "en":
        from ceviri_en import cevir_figur
        cevir_figur(fig)
        ad += "_en"
    for uz in ("png", "pdf"):
        fig.savefig(os.path.join(CIKTI, f"{ad}.{uz}"), bbox_inches="tight", facecolor=YUZEY)
    plt.close(fig)
    print("yazıldı:", ad)


# ------------------------------------------------------------------ harita
def _ulkeler():
    with open(GEOJSON, encoding="utf-8") as f:
        d = json.load(f)
    for ft in d["features"]:
        ad = ft["properties"].get("ADMIN", "")
        geo = ft["geometry"]
        polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        yield ad, polys


def _proj(lon, lat, lat0):
    return lon * math.cos(math.radians(lat0)), lat


# Yalnızca çizim için ara noktalar (enlem, boylam): deniz hatlarının haritada karadan geçmesini önler.
# Model mesafeleri değişmez (büyük daire × dolaşma katsayısı).
CIZIM_BUKUMLERI = {
    ("SIN", "DND"): [(2.5, 101.0), (5.2, 99.0), (6.3, 95.0)],
    ("SIN", "CGH"): [(2.5, 101.0), (5.2, 99.0), (6.3, 95.0), (-27.5, 45.0), (-36.0, 26.0)],
    ("DND", "BAB"): [(12.2, 52.3)],
    ("DKR", "CGH"): [(9.0, -17.0), (2.0, -8.0), (-10.0, 6.0), (-25.0, 12.0)],
    ("DKR", "GIB"): [(24.0, -17.5), (33.5, -10.0)],
    ("GIB", "FIN"): [(37.0, -10.0)],
    ("PIR", "GIB"): [(36.2, 23.3), (36.3, 15.0), (37.4, 11.6), (37.9, 8.0), (37.0, 0.0)],
}


def harita(ax, sinir, lat0, etiketler, etiket_konum, yol_ofset=0.0, nokta_olcek=1.0,
           ara_etiket=False, cerceve=None):
    lon0, lon1, la0, la1 = sinir
    ax.set_facecolor(DENIZ)
    for ad, polys in _ulkeler():
        renk = KARA_TR if ad == "Turkey" else KARA
        for poly in polys:
            dis = poly[0]
            if not any(lon0 - 15 < x < lon1 + 15 and la0 - 15 < y < la1 + 15 for x, y in dis[::5] or dis):
                continue
            xy = [_proj(x, y, lat0) for x, y in dis]
            ax.add_patch(Polygon(xy, closed=True, facecolor=renk, edgecolor=SINIR_CIZGI, linewidth=0.45, zorder=1))

    # hatlar (aynı çift üzerinde demiryolu + karayolu varsa karayolunu kaydır)
    ciftler = {}
    for a, b, mod in ag.HATLAR:
        ciftler.setdefault(frozenset((a, b)), set()).add(mod)
    for a, b, mod in ag.HATLAR:
        _, la_a, lo_a, *_ = ag.DUGUMLER[a]
        _, la_b, lo_b, *_ = ag.DUGUMLER[b]
        xa, ya = _proj(lo_a, la_a, lat0)
        xb, yb = _proj(lo_b, la_b, lat0)
        if mod == "karayolu" and "demiryolu" in ciftler[frozenset((a, b))] and yol_ofset:
            dx, dy = xb - xa, yb - ya
            n = math.hypot(dx, dy) or 1
            ox, oy = -dy / n * yol_ofset, dx / n * yol_ofset
            xa, ya, xb, yb = xa + ox, ya + oy, xb + ox, yb + oy
        xs, ys = [xa], [ya]
        bukum = CIZIM_BUKUMLERI.get((a, b)) or list(reversed(CIZIM_BUKUMLERI.get((b, a), [])))
        for la_k, lo_k in bukum:
            xk, yk = _proj(lo_k, la_k, lat0)
            xs.append(xk); ys.append(yk)
        xs.append(xb); ys.append(yb)
        ax.plot(xs, ys, color=MOD_RENK[mod], linestyle=MOD_STIL[mod],
                linewidth=MOD_KALINLIK[mod], solid_capstyle="round", zorder=3 if mod != "karayolu" else 2)

    # düğümler
    stil = {"liman": ("s", 26), "sinir": ("D", 24), "sehir": ("o", 26), "ara": ("o", 7)}
    for kod, (ad, la, lo, tip, _) in ag.DUGUMLER.items():
        x, y = _proj(lo, la, lat0)
        if not (lon0 <= lo <= lon1 and la0 <= la <= la1):
            continue
        m, s = stil[tip]
        if tip == "ara":
            ax.scatter([x], [y], marker=m, s=s * nokta_olcek, color=SOLUK, zorder=4, linewidths=0)
        else:
            ax.scatter([x], [y], marker=m, s=s * nokta_olcek, facecolor="#ffffff", edgecolor=METIN,
                       linewidths=1.0, zorder=5)
        goster = kod in etiketler or (ara_etiket and tip == "ara")
        if goster:
            dx, dy, ha = etiket_konum.get(kod, (0.6, 0.6, "left"))
            renk, stil_y = (METIN2, "italic") if tip == "ara" else (METIN, "normal")
            ax.text(x + dx, y + dy, ad, fontsize=7.2 if tip != "ara" else 6.6, color=renk, style=stil_y,
                    ha=ha, va="center", zorder=6,
                    path_effects=[pe.withStroke(linewidth=2.2, foreground=YUZEY)])
    if cerceve:
        c0, c1, d0, d1 = cerceve
        x0, y0 = _proj(c0, d0, lat0)
        x1, y1 = _proj(c1, d1, lat0)
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, edgecolor=METIN, linewidth=0.8,
                               linestyle=(0, (2, 1.5)), zorder=7))
    x0, y0 = _proj(lon0, la0, lat0)
    x1, y1 = _proj(lon1, la1, lat0)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_edgecolor(SOLUK)


def lejant(ax, loc="lower left", ncol=1, disari=False):
    ogeler = [
        Line2D([], [], color=MOD_RENK["demiryolu"], lw=1.7, label="Demiryolu"),
        Line2D([], [], color=MOD_RENK["karayolu"], lw=1.2, label="Karayolu"),
        Line2D([], [], color=MOD_RENK["okyanus"], lw=1.5, label="Okyanus"),
        Line2D([], [], color=MOD_RENK["kisa_deniz"], lw=1.5, ls=(0, (3, 1.6)), label="Kısa mesafe deniz / feribot"),
        Line2D([], [], marker="s", ls="", mfc="#fff", mec=METIN, ms=5, label="Liman"),
        Line2D([], [], marker="D", ls="", mfc="#fff", mec=METIN, ms=4.5, label="Sınır / ray açıklığı değişimi"),
        Line2D([], [], marker="o", ls="", mfc="#fff", mec=METIN, ms=5, label="Şehir / iç terminal"),
        Line2D([], [], marker="o", ls="", color=SOLUK, ms=2.5, label="Deniz yolu ara noktası"),
    ]
    ek = dict(bbox_to_anchor=(0.5, -0.02)) if disari else {}
    lg = ax.legend(handles=ogeler, loc=loc, ncol=ncol, fontsize=7, frameon=not disari, framealpha=0.95, **ek,
                   facecolor=YUZEY, edgecolor="#d6d4cd", borderpad=0.6, handlelength=2.2)
    lg.get_frame().set_linewidth(0.5)
    lg.set_zorder(10)


def sekil_ag_genel():
    fig, ax = plt.subplots(figsize=(6.7, 4.9))
    etiket = ["XIA", "SHA", "ALA", "KHO", "AKT", "BAK", "IST", "MOW", "BRE", "DUI", "RTM", "CND", "MER"]
    konum = {"XIA": (1.2, -1.6, "left"), "SHA": (1.3, 0.6, "left"), "ALA": (0.6, -1.8, "center"),
             "KHO": (0.8, 1.6, "left"), "AKT": (0.4, 1.8, "center"), "BAK": (1.2, -1.2, "left"),
             "IST": (-1.0, -1.6, "right"), "MOW": (1.0, 1.2, "left"), "BRE": (0.6, 1.4, "left"),
             "DUI": (1.0, 1.6, "left"), "RTM": (-1.4, -1.0, "right"), "CND": (-0.6, 1.5, "right"),
             "MER": (0.8, -1.6, "left"),
             "SIN": (1.2, 0, "left"), "PSD": (-1.0, -1.4, "right"), "CGH": (1.2, 0, "left"),
             "BAB": (1.0, -1.0, "left"), "GIB": (-1.0, -1.4, "right"), "DKR": (-1.0, 0, "right"),
             "DND": (1.0, -1.2, "left"), "FIN": (-1.0, 0, "right"), "USH": (-1.0, -1.2, "right"),
             "CNK": (0, 0, "left"), "BOS": (0, 0, "left")}
    for k in ("CNK", "BOS"):  # zoom haritasında gösteriliyor
        konum.pop(k)
    harita(ax, (-24, 126, -38, 61), 30, etiket, konum, nokta_olcek=0.75, ara_etiket=True,
           cerceve=(22, 56, 35, 48))
    # CNK, BOS etiketlerini gizle
    for t in list(ax.texts):
        if t.get_text() in ("Çanakkale Boğazı", "İstanbul Boğazı"):
            t.remove()
    lejant(ax, loc="lower right")
    x, y = _proj(22, 48.6, 30)
    ax.text(x, y, "Şekil 1b", fontsize=6.8, color=METIN2, va="bottom")
    kaydet(fig, "sekil1a_ag_genel")


def sekil_ag_turkiye():
    fig, ax = plt.subplots(figsize=(6.7, 3.75))
    etiket = [k for k, v in ag.DUGUMLER.items() if v[3] != "ara"]
    konum = {
        "AKT": (0.3, 0.55, "left"), "KUR": (0.3, -0.5, "left"), "BAK": (0.3, -0.45, "left"),
        "GAR": (0.25, 0.45, "left"), "TBS": (0.15, 0.55, "center"), "AHK": (0.2, -0.45, "left"),
        "POT": (-0.25, 0.4, "right"), "BAT": (0.0, -0.5, "center"), "KRS": (0.3, -0.35, "left"),
        "ERZ": (0.0, -0.55, "center"), "SIV": (0.0, -0.55, "center"), "ANK": (0.0, -0.55, "center"),
        "IST": (0.25, -0.5, "left"), "AMB": (-0.3, -0.35, "right"), "KPK": (-0.2, 0.45, "right"),
        "SAM": (0.0, 0.5, "center"), "TZX": (0.0, -0.55, "center"), "MER": (0.0, -0.55, "center"),
        "IZM": (-0.3, 0.0, "right"), "CND": (0.3, 0.3, "left"), "SOF": (0.0, 0.5, "center"),
        "PIR": (0.3, -0.35, "left"),
    }
    harita(ax, (22, 56, 35, 48), 41, etiket, konum, yol_ofset=0.12, nokta_olcek=1.0)
    # boğaz ara noktaları
    for kod in ("CNK", "BOS"):
        ad, la, lo, *_ = ag.DUGUMLER[kod]
        x, y = _proj(lo, la, 41)
        ax.text(x - 0.25 if kod == "CNK" else x + 0.25, y + (-0.3 if kod == "CNK" else 0.35), ad,
                fontsize=6.2, style="italic", color=METIN2, ha="right" if kod == "CNK" else "left",
                path_effects=[pe.withStroke(linewidth=2, foreground=YUZEY)], zorder=6)
    for ad_, lo, la in (("Hazar Denizi", 50.6, 41.6), ("Karadeniz", 32.6, 42.25), ("Akdeniz", 30.0, 35.4)):
        x, y = _proj(lo, la, 41)
        ax.text(x, y, ad_, fontsize=7, style="italic", color="#7aa6b8", ha="center", zorder=2)
    x, y = _proj(37.2, 38.2, 41)
    ax.text(x, y, "TÜRKİYE", fontsize=8, color="#8f8a7c", ha="center", fontweight="bold", zorder=2)
    lejant(ax, loc="upper center", ncol=4, disari=True)
    kaydet(fig, "sekil1b_ag_turkiye")


# ------------------------------------------------------------------ süre kırılımı
def sekil_sure_kirilimi():
    senaryolar = [("S1", "(a) S1 — 2022 mevcut durum"), ("S2", "(b) S2 — 2030 hedefi")]
    adlar = list(kor.KORIDORLAR)
    fig, axes = plt.subplots(1, 2, figsize=(6.7, 2.9), sharey=True)
    for ax, (sen, baslik) in zip(axes, senaryolar):
        g = ag.graf_kur(sen)
        for i, ad in enumerate(adlar):
            oz = ag.yol_ozeti(g, kor.KORIDORLAR[ad])
            sol = 0
            for kmp in ("hareket", "bekleme_liman", "bekleme_sinir"):
                w = oz[kmp]
                ax.barh(i, w, left=sol, height=0.62, color=KOMPONENT_RENK[kmp], edgecolor=YUZEY, linewidth=1.0)
                if w >= 4.5:
                    ax.text(sol + w / 2, i, f"{w:.0f}", ha="center", va="center", fontsize=6.6,
                            color="#ffffff" if kmp == "hareket" else METIN)
                sol += w
            ax.text(sol + 1.0, i, f"{oz['sure']:.1f} gün", va="center", fontsize=7, color=METIN)
        ax.set_yticks(range(len(adlar)))
        ax.set_yticklabels(adlar, fontsize=7.2)
        ax.invert_yaxis()
        ax.set_xlim(0, 82)
        ax.set_xlabel("Xi'an → Duisburg kapıdan kapıya süre (gün)")
        ax.set_title(baslik, fontsize=8.3, loc="left", color=METIN)
        ax.grid(axis="x", color="#e6e4df", linewidth=0.5)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
    ogeler = [Rectangle((0, 0), 1, 1, color=KOMPONENT_RENK[k], label=KOMPONENT_AD[k]) for k in KOMPONENT_RENK]
    fig.legend(handles=ogeler, loc="lower center", ncol=3, fontsize=7.2, frameon=False,
               bbox_to_anchor=(0.55, -0.06))
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    kaydet(fig, "sekil2_sure_kirilimi")


# ------------------------------------------------------------------ kalibrasyon
def sekil_kalibrasyon():
    g = ag.graf_kur("S1")
    satirlar = [
        ("Khorgos → Köstence\n(Gürcistan limanları)", kor.KALIBRASYON_YOLU, (50, 53), "kalibrasyon"),
        ("Khorgos → Kapıkule\n(Türkiye üzerinden)", kor.DOGRULAMA_TR_YOLU, (40, 45), "doğrulama"),
    ]
    fig, ax = plt.subplots(figsize=(4.6, 1.75))
    for i, (ad, yol, (lo, hi), tur) in enumerate(satirlar):
        oz = ag.yol_ozeti(g, yol)
        ax.add_patch(Rectangle((lo, i - 0.22), hi - lo, 0.44, color="#d6d4cd", zorder=1))
        ax.scatter([oz["sure"]], [i], s=46, color="#2a78d6", edgecolor=YUZEY, linewidth=1.5, zorder=3)
        ax.text(oz["sure"], i - 0.36, f"model: {oz['sure']:.1f} gün ({tur})", ha="center", fontsize=6.8,
                color=METIN)
        ax.text(hi + 0.4, i, f"WB (2023): {lo}–{hi} gün", va="center", fontsize=6.8, color=METIN2)
    ax.set_yticks([0, 1])
    ax.set_yticklabels([s[0] for s in satirlar], fontsize=7.2)
    ax.set_ylim(1.6, -0.75)
    ax.set_xlim(36, 60)
    ax.set_xlabel("Süre (gün), 2022")
    ax.grid(axis="x", color="#e6e4df", linewidth=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.tight_layout()
    kaydet(fig, "sekil3_kalibrasyon")


# ------------------------------------------------------------------ yöntem şeması
def sekil_durum_grafi():
    fig, ax = plt.subplots(figsize=(6.7, 2.9))
    katmanlar = [("kisa_deniz", "Deniz\nkatmanı", 2.0), ("demiryolu", "Demiryolu\nkatmanı", 1.0),
                 ("karayolu", "Karayolu\nkatmanı", 0.0)]
    sutun = {"AKT": 1.9, "BAK": 3.3, "GAR": 4.6, "TBS": 5.7, "KRS": 7.0, "ANK": 8.3}
    mevcut = {"kisa_deniz": ["AKT", "BAK"], "demiryolu": ["AKT", "BAK", "GAR", "TBS", "KRS", "ANK"],
              "karayolu": ["BAK", "GAR", "TBS", "KRS", "ANK"]}
    for mod, ad, y in katmanlar:
        ax.add_patch(Rectangle((0.35, y - 0.32), 8.45, 0.64, color="#f1f0ec", zorder=0))
        ax.text(0.45, y, ad, fontsize=6.8, color=METIN2, va="center")
        xs = [sutun[n] for n in mevcut[mod]]
        for x0, x1 in zip(xs, xs[1:]):
            ax.annotate("", xy=(x1 - 0.16, y), xytext=(x0 + 0.16, y),
                        arrowprops=dict(arrowstyle="-|>", color=MOD_RENK[mod], lw=1.5,
                                        linestyle="--" if mod == "kisa_deniz" else "-", mutation_scale=8))
        for n in mevcut[mod]:
            ax.scatter([sutun[n]], [y], s=120, facecolor="#ffffff", edgecolor=MOD_RENK[mod], linewidth=1.5, zorder=4)
    # aktarma kenarları
    for n, y0, y1 in (("AKT", 1.0, 2.0), ("BAK", 2.0, 1.0)):
        ax.annotate("", xy=(sutun[n] + 0.0, y1 + (0.17 if y1 < y0 else -0.17)),
                    xytext=(sutun[n], y0 + (-0.17 if y1 < y0 else 0.17)),
                    arrowprops=dict(arrowstyle="-|>", color=METIN, lw=1.0, mutation_scale=8), zorder=3)
    for n in ("TBS", "KRS", "ANK"):
        ax.annotate("", xy=(sutun[n] + 0.08, 0.17), xytext=(sutun[n] + 0.08, 0.83),
                    arrowprops=dict(arrowstyle="<|-|>", color=SOLUK, lw=0.8, mutation_scale=7), zorder=3)
    # sütun başlıkları
    adlar = {"AKT": "Aktau", "BAK": "Bakü/Alat", "GAR": "Gardabani", "TBS": "Tiflis", "KRS": "Kars", "ANK": "Ankara"}
    for n, x in sutun.items():
        ax.text(x, 2.55, adlar[n], ha="center", fontsize=7.4, color=METIN, fontweight="bold")
    # açıklamalar
    ax.text(sutun["AKT"] + 0.12, 1.5, "aktarma kenarı:\nliman bekleme\n+ elleçleme", fontsize=6.3,
            color=METIN, va="center")
    ax.text(sutun["GAR"], 1.42, "sınır geçişi\n(+3 gün)", fontsize=6.3, color=METIN, ha="center", va="center")
    ax.text(sutun["KRS"] + 0.2, 0.5, "terminal aktarması", fontsize=6.3, color=METIN2, va="center")
    ax.text(6.1, 2.0, "durum = (düğüm, mod)\nkenar ağırlığı = (maliyet, süre, CO$_2$)", fontsize=6.8,
            color=METIN, va="center",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#ffffff", edgecolor="#d6d4cd", linewidth=0.6))
    ax.set_xlim(0.3, 8.85)
    ax.set_ylim(-0.45, 2.75)
    ax.axis("off")
    kaydet(fig, "sekil4_durum_grafi")


if __name__ == "__main__":
    kor.kalibre_et()
    secim = sys.argv[1:] or ["genel", "turkiye", "kirilim", "kalibrasyon", "durum"]
    for s in secim:
        {"genel": sekil_ag_genel, "turkiye": sekil_ag_turkiye, "kirilim": sekil_sure_kirilimi,
         "kalibrasyon": sekil_kalibrasyon, "durum": sekil_durum_grafi}[s]()
