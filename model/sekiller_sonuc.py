"""Bulgu şekilleri: Şekil 5 (Pareto), Şekil 6 (gerçek ağ verimliliği), Şekil 7 (sentetik ağlar)."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from sekiller import kaydet, YUZEY, METIN, METIN2, SOLUK

BURASI = os.path.dirname(os.path.abspath(__file__))
SON = os.path.join(BURASI, "..", "sonuclar")

KOR_RENK = {"Deniz": "#1baf7a", "Kuzey": "#2a78d6", "Orta": "#eb6834"}
KOR_MARKER = {"Deniz – Süveyş": ("Deniz", "s"), "Deniz – Ümit Burnu": ("Deniz", "D"),
              "Kuzey Koridoru": ("Kuzey", "o"), "Orta Koridor – Türkiye (BTK)": ("Orta", "o"),
              "Orta Koridor – Karadeniz geçişi": ("Orta", "^")}
ALG_RENK = {"Dijkstra": "#8a8984", "A* (büyük daire)": "#2a78d6", "ALT (landmark)": "#eb6834"}


def _eksen(ax):
    ax.grid(color="#e6e4df", linewidth=0.5)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def sekil_pareto():
    d = json.load(open(os.path.join(SON, "e2_pareto.json"), encoding="utf-8"))
    paneller = [("S1", "(a) S1 — 2022 mevcut durum"), ("S5", "(b) S5 — Kızıldeniz ve Kuzey kapalı"),
                ("S6", "(c) S6 — S5 + 2030 hedefi")]
    fig, axes = plt.subplots(1, 3, figsize=(6.9, 2.75), sharey=True, sharex=True)
    for ax, (sen, baslik) in zip(axes, paneller):
        coz = sorted(d[sen]["cozumler"], key=lambda c: c["maliyet"])
        xs = [c["maliyet"] / 1000 for c in coz]
        ys = [c["sure"] for c in coz]
        ax.step(xs + [13.5], ys + [ys[-1]], where="post", color="#c9c7c0", linewidth=1.0, zorder=1)
        for c in coz:
            grup, mk = KOR_MARKER.get(c["koridor"], ("Orta", "o"))
            ax.scatter(c["maliyet"] / 1000, c["sure"], s=34, marker=mk, color=KOR_RENK[grup],
                       edgecolor=YUZEY, linewidth=1.0, zorder=3)
        ax.set_title(baslik, fontsize=7.8, loc="left", color=METIN)
        ax.text(0.97, 0.96, f"{len(coz)} Pareto çözüm", transform=ax.transAxes, ha="right", va="top",
                fontsize=6.8, color=METIN2)
        ax.set_xlabel("Maliyet (bin USD/FEU)")
        _eksen(ax)
    axes[0].set_ylabel("Süre (gün)")
    axes[0].set_xlim(2, 13.5)
    axes[0].set_ylim(15, 85)
    ogeler = [Line2D([], [], marker=mk, ls="", color=KOR_RENK[g], ms=5.5, label=ad)
              for ad, (g, mk) in KOR_MARKER.items()]
    fig.legend(handles=ogeler, loc="lower center", ncol=3, fontsize=6.9, frameon=False, bbox_to_anchor=(0.53, -0.1))
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    kaydet(fig, "sekil5_pareto")


def sekil_verimlilik():
    d = json.load(open(os.path.join(SON, "e3_verimlilik.json"), encoding="utf-8"))
    amaclar = [("maliyet", "Maliyet"), ("sure", "Süre"), ("co2", "CO$_2$")]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.7, 2.5))
    gen = 0.26
    for i, (k, ad) in enumerate(amaclar):
        r = d[k]
        for j, (alg, anahtar) in enumerate([("Dijkstra", "ort_genis_dijkstra"),
                                            ("A* (büyük daire)", "ort_genis_astar_bd"),
                                            ("ALT (landmark)", "ort_genis_alt")]):
            v = r[anahtar]
            a1.bar(i + (j - 1) * gen, v, width=gen - 0.03, color=ALG_RENK[alg], edgecolor=YUZEY, linewidth=0.8)
            a1.text(i + (j - 1) * gen, v + 0.8, f"{v:.0f}", ha="center", fontsize=6.4, color=METIN)
        for j, (alg, anahtar) in enumerate([("A* (büyük daire)", "ort_h_kalite_bd"),
                                            ("ALT (landmark)", "ort_h_kalite_alt")]):
            v = r[anahtar]
            a2.bar(i + (j - 0.5) * 0.34, v, width=0.31, color=ALG_RENK[alg], edgecolor=YUZEY, linewidth=0.8)
            a2.text(i + (j - 0.5) * 0.34, v + 0.02, f"{v:.2f}", ha="center", fontsize=6.4, color=METIN)
    for ax in (a1, a2):
        ax.set_xticks(range(3))
        ax.set_xticklabels([a for _, a in amaclar])
        _eksen(ax)
        ax.grid(axis="x", visible=False)
    a1.set_ylabel("Ort. genişletilen durum")
    a1.set_title("(a) Arama eforu (992 sorgu, S1)", fontsize=7.8, loc="left")
    a2.set_ylabel("h(s) / d*(s,t)")
    a2.set_ylim(0, 1.12)
    a2.set_title("(b) Sezgisel kalitesi (1 = mükemmel)", fontsize=7.8, loc="left")
    ogeler = [Line2D([], [], marker="s", ls="", color=c, ms=6, label=a) for a, c in ALG_RENK.items()]
    fig.legend(handles=ogeler, loc="lower center", ncol=3, fontsize=7, frameon=False, bbox_to_anchor=(0.5, -0.07))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    kaydet(fig, "sekil6_verimlilik")


def sekil_sentetik():
    d = json.load(open(os.path.join(SON, "e4_sentetik.json"), encoding="utf-8"))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.7, 2.6))
    b = d["bekleme"]
    x = list(range(len(b)))
    for alg, k in (("A* (büyük daire)", "ort_astar_bd"), ("ALT (landmark)", "ort_alt")):
        y = [100 * r[k] / r["ort_dijkstra"] for r in b]
        a1.plot(x, y, color=ALG_RENK[alg], linewidth=2, marker="o", ms=4.5, mec=YUZEY, mew=1)
        a1.text(x[-1] + 0.15, y[-1], alg.split(" (")[0], fontsize=6.8, va="center", color=METIN)
    a1.axhline(100, color=ALG_RENK["Dijkstra"], linewidth=1.2, linestyle=(0, (3, 2)))
    a1.text(0, 104, "Dijkstra = %100", fontsize=6.6, color=METIN2)
    a1.set_xticks(x)
    a1.set_xticklabels([f"{r['carpan']:g}".replace(".", ",") for r in b])
    a1.set_xlabel("Bekleme süresi çarpanı λ (0 = hiç bekleme yok)")
    a1.set_ylabel("Genişletilen durum\n(Dijkstra'ya göre, %)")
    a1.set_ylim(0, 115)
    a1.set_xlim(-0.3, len(b) - 0.2)
    a1.set_title("(a) Bekleme süresinin etkisi (n = 3.000)", fontsize=7.8, loc="left")
    _eksen(a1)
    o = d["olcek"]
    n = [r["durum"] / 1000 for r in o]
    for alg, k in (("Dijkstra", "ort_ms_d"), ("A* (büyük daire)", "ort_ms_a"), ("ALT (landmark)", "ort_ms_alt")):
        a2.plot(n, [r[k] for r in o], color=ALG_RENK[alg], linewidth=2, marker="o", ms=4.5, mec=YUZEY, mew=1,
                label=alg)
    a2.set_xscale("log"); a2.set_yscale("log")
    from matplotlib.ticker import NullFormatter, FixedLocator, NullLocator
    a2.xaxis.set_major_locator(FixedLocator(n))
    a2.xaxis.set_minor_locator(NullLocator())
    a2.set_xticklabels([f"{v:.1f}".replace(".", ",") for v in n])
    a2.set_xlabel("Durum sayısı (bin, log)")
    a2.set_ylabel("Sorgu süresi (ms, log)")
    a2.set_title("(b) Ölçeklenebilirlik", fontsize=7.8, loc="left")
    a2.legend(fontsize=6.6, frameon=False, loc="upper left")
    _eksen(a2)
    fig.tight_layout()
    kaydet(fig, "sekil7_sentetik")


if __name__ == "__main__":
    for s in (sys.argv[1:] or ["pareto", "verimlilik", "sentetik"]):
        {"pareto": sekil_pareto, "verimlilik": sekil_verimlilik, "sentetik": sekil_sentetik}[s]()
