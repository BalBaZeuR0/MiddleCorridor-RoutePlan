"""
Bildiri 1 deneyleri. Çıktılar: ../sonuclar/*.json, *.csv
  E1  senaryo × amaç için en iyi rotalar (Dijkstra = A* = ALT; doğruluk kontrolü)
  E2  NAMOA* Pareto cepheleri
  E3  gerçek ağda algoritma verimliliği (tüm düğüm çiftleri)
  E4  sentetik ağlarda bekleme payı ve ölçek etkisi
  E5  duyarlılık analizi (±%30)
"""
import copy
import json
import math
import os
import random
import statistics
import sys
import time

import ag
import koridorlar as kor
from algoritmalar import astar, ALT, landmark_sec, namoa, INF

BURASI = os.path.dirname(os.path.abspath(__file__))
SONUC = os.path.join(BURASI, "..", "sonuclar")
os.makedirs(SONUC, exist_ok=True)
AMAC_AD = ["maliyet", "sure", "co2"]
OD = [("XIA", "DUI"), ("SHA", "DUI"), ("ALA", "IST"), ("XIA", "ANK")]


# ------------------------------------------------------------------ sorgu grafı
class SorguGraf:
    """Temel grafa dokunmadan sanal kaynak ('*') ve hedef ('#') ekler."""

    def __init__(self, temel, kaynak, hedef):
        self.temel = temel
        self.s, self.t = (kaynak, "*"), (hedef, "#")
        self.ek = {self.s: [((kaynak, m), (0.0, 0.0, 0.0), {"tur": "sanal"}) for m in ag.MODLAR
                            if (kaynak, m) in temel]}
        self.hedef_durumlari = [(hedef, m) for m in ag.MODLAR if (hedef, m) in temel]
        self.hedefe = {d: ((self.t, (0.0, 0.0, 0.0), {"tur": "sanal"}),) for d in self.hedef_durumlari}

    def get(self, u, varsayilan=()):
        if u in self.ek:
            return self.ek[u]
        b = self.temel.get(u, varsayilan)
        if u in self.hedefe:
            return list(b) + list(self.hedefe[u])
        return b


def taban_kenarlar(senaryo, p=ag.P):
    return dict(ag.graf_kur(senaryo, p).kenarlar)


# ------------------------------------------------------------------ büyük daire sezgiseli
def bd_katsayilari(p=ag.P):
    """Her amaç için: kenar ağırlığı >= katsayı × büyük daire mesafesi olacak en büyük katsayı."""
    f = p["dolasma"]
    maliyet = min(f[m] * p["birim_maliyet"][m] for m in ag.MODLAR)
    for (a, b), c in p["sabit_hat_maliyeti"].items():
        maliyet = min(maliyet, c / ag.buyuk_daire_km(a, b))
    sure = 1.0 / max(p["hiz"][m] / f[m] for m in ag.MODLAR)
    co2 = min(f[m] * p["co2"][m] * p["yuk_ton"] / 1000.0 for m in ag.MODLAR)
    return (maliyet, sure, co2)


def bd_sezgisel(hedef, k, p=ag.P):
    c = bd_katsayilari(p)[k]
    onbellek = {n: c * ag.buyuk_daire_km(n, hedef) for n in ag.DUGUMLER}
    return lambda v: onbellek[v[0]]


def bd_vektor(hedef, p=ag.P):
    c = bd_katsayilari(p)
    onbellek = {n: tuple(ci * ag.buyuk_daire_km(n, hedef) for ci in c) for n in ag.DUGUMLER}
    return lambda v: onbellek[v[0]]


# ------------------------------------------------------------------ rota etiketi
def koridor_etiketi(yol):
    n = [d[0] for d in yol]
    if "MOW" in n:
        return "Kuzey Koridoru"
    if "AKT" in n or "KUR" in n or "BAK" in n:
        if "AHK" in n or ("KRS" in n and "TBS" in n):
            return "Orta Koridor – Türkiye (BTK)"
        if "TZX" in n:
            return "Orta Koridor – Batum–Trabzon karayolu"
        if "CND" in n:
            return "Orta Koridor – Karadeniz geçişi"
        return "Orta Koridor"
    if "PSD" in n:
        return "Deniz – Süveyş"
    if "CGH" in n:
        return "Deniz – Ümit Burnu"
    return "Doğrudan / diğer"


def yol_metni(yol):
    """Okunur rota: mod değişim noktaları + uçlar. Örn. "Xi'an –D→ Şanghay –O→ Rotterdam –D→ Duisburg"."""
    kisalt = {"demiryolu": "D", "karayolu": "K", "okyanus": "O", "kisa_deniz": "F"}
    gercek = [d for d in yol if d[1] in kisalt]
    segment = []  # [bas_dugum, mod, son_dugum]
    for u, v in zip(gercek, gercek[1:]):
        if u[0] == v[0]:
            continue  # aktarma kenarı
        m = u[1]
        if segment and segment[-1][1] == m and segment[-1][2] == u[0]:
            segment[-1][2] = v[0]
        else:
            segment.append([u[0], m, v[0]])
    if not segment:
        return ""
    out = ag.DUGUMLER[segment[0][0]][0]
    for bas, m, son in segment:
        out += f" –{kisalt[m]}→ {ag.DUGUMLER[son][0]}"
    return out


def ozet(yol, kenarlar):
    top = {"maliyet": 0.0, "sure": 0.0, "co2": 0.0, "bekleme": 0.0, "km": 0.0}
    for u, v in zip(yol, yol[1:]):
        for w, vek, b in kenarlar.get(u, ()):
            if w == v:
                top["maliyet"] += vek[0]; top["sure"] += vek[1]; top["co2"] += vek[2]
                top["bekleme"] += b.get("bekleme", 0.0); top["km"] += b.get("km", 0.0)
                break
    top["bekleme_payi"] = top["bekleme"] / top["sure"] if top["sure"] else 0.0
    return top


# ------------------------------------------------------------------ E1
def e1():
    sonuc = []
    for sen in ag.SENARYOLAR:
        temel = taban_kenarlar(sen)
        for (a, b) in OD:
            q = SorguGraf(temel, a, b)
            for k in range(3):
                r_d = astar(q, q.s, q.t, k)
                r_a = astar(q, q.s, q.t, k, bd_sezgisel(b, k))
                assert abs(r_d.deger - r_a.deger) < 1e-6, (sen, a, b, k)
                oz = ozet(r_d.yol, q)
                sonuc.append({"senaryo": sen, "kaynak": a, "hedef": b, "amac": AMAC_AD[k],
                              "koridor": koridor_etiketi(r_d.yol), "rota": yol_metni(r_d.yol), **oz})
    with open(os.path.join(SONUC, "e1_rotalar.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    print("E1 tamam:", len(sonuc), "satır; Dijkstra ve A* tüm sorgularda aynı optimum değeri verdi.")
    return sonuc


# ------------------------------------------------------------------ E2
def e2():
    sonuc = {}
    for sen in ("S1", "S2", "S5", "S6"):
        temel = taban_kenarlar(sen)
        q = SorguGraf(temel, "XIA", "DUI")
        coz0, ist0 = namoa(q, q.s, q.t, None)
        coz, ist = namoa(q, q.s, q.t, bd_vektor("DUI"))
        assert sorted(c for c, _ in coz0) == sorted(c for c, _ in coz), sen
        sonuc[sen] = {"cozumler": [{"maliyet": c[0], "sure": c[1], "co2": c[2],
                                    "koridor": koridor_etiketi(y), "rota": yol_metni(y)} for c, y in coz],
                      "genisletilen_bilgisiz": ist0["genisletilen"], "genisletilen_bd": ist["genisletilen"],
                      "ms_bilgisiz": ist0["sure_ms"], "ms_bd": ist["sure_ms"]}
        print(f"E2 {sen}: {len(coz)} Pareto çözüm; etiket genişletme {ist0['genisletilen']} → {ist['genisletilen']}")
    with open(os.path.join(SONUC, "e2_pareto.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    return sonuc


# ------------------------------------------------------------------ E3
def e3(landmark_sayisi=6):
    sen = "S1"
    temel = taban_kenarlar(sen)
    dugumler = [n for n, v in ag.DUGUMLER.items() if v[3] != "ara"]
    adaylar = [d for d in temel if d[0] in dugumler]
    sonuc = {}
    for k in range(3):
        t0 = time.perf_counter()
        lm = landmark_sec(temel, adaylar, landmark_sayisi, k, baslangic=("IST", "demiryolu"))
        alt = ALT(temel, lm, k)
        on_ms = (time.perf_counter() - t0) * 1e3
        kayit = {"dijkstra": [], "astar_bd": [], "alt": [], "h_bd": [], "h_alt": []}
        for a in dugumler:
            for b in dugumler:
                if a == b:
                    continue
                q = SorguGraf(temel, a, b)
                r0 = astar(q, q.s, q.t, k)
                if r0.deger == INF:
                    continue
                hb = bd_sezgisel(b, k)
                ha = alt.sezgisel(q.hedef_durumlari)
                r1 = astar(q, q.s, q.t, k, hb)
                r2 = astar(q, q.s, q.t, k, ha)
                assert abs(r0.deger - r1.deger) < 1e-6 and abs(r0.deger - r2.deger) < 1e-6
                kayit["dijkstra"].append(r0.genisletilen)
                kayit["astar_bd"].append(r1.genisletilen)
                kayit["alt"].append(r2.genisletilen)
                # sezgisel kalitesi: kaynağın en iyi başlangıç durumunda h / gerçek mesafe
                if r0.deger > 0:
                    ilk = r0.yol[1]
                    kalan = r0.deger
                    kayit["h_bd"].append(hb(ilk) / kalan)
                    kayit["h_alt"].append(ha(ilk) / kalan)
        n = len(kayit["dijkstra"])
        sonuc[AMAC_AD[k]] = {
            "sorgu": n, "landmarklar": [f"{ag.DUGUMLER[x[0]][0]}/{x[1]}" for x in lm], "on_hesap_ms": on_ms,
            "ort_genis_dijkstra": statistics.mean(kayit["dijkstra"]),
            "ort_genis_astar_bd": statistics.mean(kayit["astar_bd"]),
            "ort_genis_alt": statistics.mean(kayit["alt"]),
            "ort_h_kalite_bd": statistics.mean(kayit["h_bd"]),
            "ort_h_kalite_alt": statistics.mean(kayit["h_alt"]),
            "durum_sayisi": len({u for u in temel} | {v for l in temel.values() for v, *_ in l}),
        }
        print(f"E3 {AMAC_AD[k]}: {sonuc[AMAC_AD[k]]}")
    with open(os.path.join(SONUC, "e3_verimlilik.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    return sonuc


# ------------------------------------------------------------------ E4 (sentetik)
def sentetik_ag(n, bekleme_carpani, tohum=1, komsu=4, liman_orani=0.12, sinir_orani=0.15):
    """Düzlemde (km) n düğümlü 3 modlu ağ. Süre amacı tek ağırlık olarak kullanılır (k=1)."""
    rnd = random.Random(tohum)
    W, H = 6000.0, 3500.0
    xy = [(rnd.uniform(0, W), rnd.uniform(0, H)) for _ in range(n)]
    liman = set(rnd.sample(range(n), max(4, int(n * liman_orani))))
    sinir = set(rnd.sample(range(n), int(n * sinir_orani)))
    hiz = {"demiryolu": 600.0, "karayolu": 650.0, "okyanus": 677.0 * 1.05}
    dol = {"demiryolu": 1.25, "karayolu": 1.20, "okyanus": 1.05}
    # grid tabanlı kNN
    hucre = max(W, H) / max(1, int(math.sqrt(n)))
    izgara = {}
    for i, (x, y) in enumerate(xy):
        izgara.setdefault((int(x // hucre), int(y // hucre)), []).append(i)

    def knn(i, kume, kk):
        x, y = xy[i]
        r = 1
        while True:
            ad = []
            cx, cy = int(x // hucre), int(y // hucre)
            for gx in range(cx - r, cx + r + 1):
                for gy in range(cy - r, cy + r + 1):
                    ad.extend(j for j in izgara.get((gx, gy), ()) if j != i and (kume is None or j in kume))
            if len(ad) >= kk or r > 50:
                return sorted(ad, key=lambda j: (xy[j][0] - x) ** 2 + (xy[j][1] - y) ** 2)[:kk]
            r += 1

    ken = {}

    def ekle(u, v, w, bekl):
        ken.setdefault(u, []).append((v, (0.0, w, 0.0), {"bekleme": bekl}))

    sinir_gec = {i: rnd.uniform(1.0, 3.0) * bekleme_carpani for i in sinir}
    liman_bek = {i: rnd.uniform(5.0, 20.0) * bekleme_carpani for i in liman}
    for mod, kume, kk in (("demiryolu", None, komsu), ("karayolu", None, komsu), ("okyanus", liman, 3)):
        for i in (range(n) if kume is None else kume):
            for j in knn(i, kume, kk):
                d = math.dist(xy[i], xy[j]) * dol[mod]
                t = d / hiz[mod]
                for u, v in ((i, j), (j, i)):
                    ek = sinir_gec.get(v, 0.0) if mod != "okyanus" else 0.0
                    ekle((u, mod), (v, mod), t + ek, ek)
    for i in range(n):
        ekle((i, "demiryolu"), (i, "karayolu"), 1.0 * bekleme_carpani, 1.0 * bekleme_carpani)
        ekle((i, "karayolu"), (i, "demiryolu"), 1.0 * bekleme_carpani, 1.0 * bekleme_carpani)
        if i in liman:
            for m in ("demiryolu", "karayolu"):
                ekle((i, m), (i, "okyanus"), liman_bek[i], liman_bek[i])
                ekle((i, "okyanus"), (i, m), liman_bek[i], liman_bek[i])
    vmax = max(hiz[m] / dol[m] for m in hiz)
    return ken, xy, vmax


def e4(sorgu=40, landmark_sayisi=8):
    sonuc = {"bekleme": [], "olcek": []}

    def olc(n, carpan, tohum):
        ken, xy, vmax = sentetik_ag(n, carpan, tohum)
        rnd = random.Random(tohum + 99)
        adaylar = list(ken)
        t0 = time.perf_counter()
        lm = landmark_sec(ken, adaylar, landmark_sayisi, 1, baslangic=adaylar[0])
        alt = ALT(ken, lm, 1)
        on_ms = (time.perf_counter() - t0) * 1e3
        g = {"dijkstra": [], "astar_bd": [], "alt": [], "ms_d": [], "ms_a": [], "ms_alt": [], "bekleme_payi": []}
        while len(g["dijkstra"]) < sorgu:
            a, b = rnd.randrange(n), rnd.randrange(n)
            if a == b:
                continue
            s, t = (a, "demiryolu"), (b, "demiryolu")
            r0 = astar(ken, s, t, 1)
            if r0.deger == INF:
                continue
            bx, by = xy[b]
            hb = lambda v: math.dist(xy[v[0]], (bx, by)) / vmax
            ha = alt.sezgisel([t])
            r1 = astar(ken, s, t, 1, hb)
            r2 = astar(ken, s, t, 1, ha)
            assert abs(r0.deger - r1.deger) < 1e-6 and abs(r0.deger - r2.deger) < 1e-6
            bek = 0.0
            for u, v in zip(r0.yol, r0.yol[1:]):
                for w, vek, inf in ken[u]:
                    if w == v:
                        bek += inf["bekleme"]
                        break
            g["dijkstra"].append(r0.genisletilen); g["astar_bd"].append(r1.genisletilen); g["alt"].append(r2.genisletilen)
            g["ms_d"].append(r0.sure_ms); g["ms_a"].append(r1.sure_ms); g["ms_alt"].append(r2.sure_ms)
            g["bekleme_payi"].append(bek / r0.deger)
        return {"n": n, "durum": len(ken), "carpan": carpan, "on_hesap_ms": on_ms,
                **{f"ort_{k}": statistics.mean(v) for k, v in g.items()}}

    for carpan in (0.0, 0.25, 0.5, 1.0, 2.0, 4.0):
        r = olc(3000, carpan, 7)
        sonuc["bekleme"].append(r)
        print(f"E4 bekleme ×{carpan}: pay {r['ort_bekleme_payi']:.2f}  genişletilen D {r['ort_dijkstra']:.0f} "
              f"A* {r['ort_astar_bd']:.0f} ALT {r['ort_alt']:.0f}")
    for n in (1000, 5000, 20000):
        r = olc(n, 1.0, 11)
        sonuc["olcek"].append(r)
        print(f"E4 ölçek n={n}: D {r['ort_dijkstra']:.0f} ({r['ort_ms_d']:.1f} ms) A* {r['ort_astar_bd']:.0f} "
              f"({r['ort_ms_a']:.1f} ms) ALT {r['ort_alt']:.0f} ({r['ort_ms_alt']:.1f} ms) ön {r['on_hesap_ms']:.0f} ms")
    with open(os.path.join(SONUC, "e4_sentetik.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    return sonuc


# ------------------------------------------------------------------ E5 (duyarlılık)
def e5():
    taban_p = copy.deepcopy(ag.P)
    degisimler = [
        ("Karayolu birim maliyeti", lambda p, x: p["birim_maliyet"].__setitem__("karayolu", p["birim_maliyet"]["karayolu"] * x)),
        ("Kısa deniz birim maliyeti", lambda p, x: p["birim_maliyet"].__setitem__("kisa_deniz", p["birim_maliyet"]["kisa_deniz"] * x)),
        ("Demiryolu birim maliyeti", lambda p, x: p["birim_maliyet"].__setitem__("demiryolu", p["birim_maliyet"]["demiryolu"] * x)),
        ("Demiryolu hızı", lambda p, x: p["hiz"].__setitem__("demiryolu", p["hiz"]["demiryolu"] * x)),
        ("Okyanus hızı", lambda p, x: p["hiz"].__setitem__("okyanus", p["hiz"]["okyanus"] * x)),
        ("Liman bekleme (α)", lambda p, x: p.__setitem__("alfa", p["alfa"] * x)),
        ("Demiryolu CO2 yoğunluğu", lambda p, x: p["co2"].__setitem__("demiryolu", p["co2"]["demiryolu"] * x)),
        ("Okyanus CO2 yoğunluğu", lambda p, x: p["co2"].__setitem__("okyanus", p["co2"]["okyanus"] * x)),
    ]

    def en_iyi(p, sen, k):
        temel = taban_kenarlar(sen, p)
        q = SorguGraf(temel, "XIA", "DUI")
        r = astar(q, q.s, q.t, k)
        return koridor_etiketi(r.yol), r.deger

    sonuc = []
    for sen in ("S1", "S2", "S6"):
        for k in range(3):
            ref, refv = en_iyi(taban_p, sen, k)
            for ad, f in degisimler:
                for x in (0.7, 1.3):
                    p = copy.deepcopy(taban_p)
                    f(p, x)
                    kor_, v = en_iyi(p, sen, k)
                    sonuc.append({"senaryo": sen, "amac": AMAC_AD[k], "parametre": ad, "carpan": x,
                                  "referans": ref, "yeni": kor_, "degisti": kor_ != ref,
                                  "deger_degisim_%": 100 * (v - refv) / refv})
    deg = [r for r in sonuc if r["degisti"]]
    print(f"E5: {len(sonuc)} deneme, rota değişen: {len(deg)}")
    for r in deg:
        print("   ", r)
    with open(os.path.join(SONUC, "e5_duyarlilik.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    return sonuc


# ------------------------------------------------------------------ E6 (koridor sıralamasının sağlamlığı)
def _koridor_sureleri(sen, p):
    g = ag.graf_kur(sen, p)
    out = {}
    for ad, yol in kor.KORIDORLAR.items():
        try:
            out[ad.replace("\n", " ")] = ag.yol_ozeti(g, yol)["sure"]
        except KeyError:
            pass
    return out


def e6(cekilis=2000, aralik=0.30, tohum=2026):
    """Ortak belirsizlik: her liman beklemesi, her sınır geçişi, her mod hızı ve terminal süresi
    birbirinden bağımsız U(1-aralik, 1+aralik) çarpanıyla aynı anda değiştirilir (alfa sabit).
    Ayrıca BTK'nın Süveyş'i geçtiği Orta Koridor bekleme azaltımı (başabaş) hesaplanır."""
    rnd = random.Random(tohum)
    taban = copy.deepcopy(ag.P)
    BTK, SUV, UMT, GUR = ("Orta Koridor – Türkiye (BTK)", "Deniz yolu – Süveyş",
                          "Deniz yolu – Ümit Burnu", "Orta Koridor – Gürcistan limanları")
    limanlar = [n for n, v in ag.DUGUMLER.items() if v[3] == "liman"]

    def ornek():
        p = copy.deepcopy(taban)
        u = lambda: rnd.uniform(1 - aralik, 1 + aralik)
        for n in limanlar:
            s, c, kay = taban["liman"].get(n, taban["liman_varsayilan"])
            p["liman"][n] = (s * u(), c, kay)
        p["gecis"] = {k: (v[0] * u(), v[1]) for k, v in taban["gecis"].items()}
        p["hat_ek_gecis"] = {k: v * u() for k, v in taban["hat_ek_gecis"].items()}
        p["hiz"] = {m: v * u() for m, v in taban["hiz"].items()}
        p["terminal"] = (taban["terminal"][0] * u(), taban["terminal"][1])
        return p

    say = {"S2_btk_suveysten_hizli": 0, "S6_btk_en_hizli": 0, "S5_btk_umitten_hizli": 0}
    farklar_s2, farklar_s6 = [], []
    for _ in range(cekilis):
        p = ornek()
        t2 = _koridor_sureleri("S2", p)
        t6 = _koridor_sureleri("S6", p)
        t5 = _koridor_sureleri("S5", p)
        say["S2_btk_suveysten_hizli"] += t2[BTK] < t2[SUV]
        say["S6_btk_en_hizli"] += t6[BTK] < min(t6[UMT], t6[GUR])
        say["S5_btk_umitten_hizli"] += t5[BTK] < t5[UMT]
        farklar_s2.append(t2[SUV] - t2[BTK])
        farklar_s6.append(t6[UMT] - t6[BTK])

    # başabaş: S1 koşullarında Orta Koridor liman+geçiş beklemeleri hangi oranda azalınca BTK = Süveyş?
    def btk_eksi_suveys(azalim):
        p = copy.deepcopy(taban)
        for n in ag.ORTA_KORIDOR_LIMANLARI:
            s, c, kay = p["liman"][n]
            p["liman"][n] = (s * (1 - azalim), c, kay)
        p["gecis"] = {k: ((v[0] * (1 - azalim)) if k[0] in ag.ORTA_KORIDOR_GECISLERI else v[0], v[1])
                      for k, v in p["gecis"].items()}
        t = _koridor_sureleri("S1", p)
        return t[BTK] - t[SUV]
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if btk_eksi_suveys(mid) > 0 else (lo, mid)
    basabas = (lo + hi) / 2

    q = lambda xs, a: sorted(xs)[int(a * (len(xs) - 1))]
    sonuc = {"cekilis": cekilis, "aralik": aralik,
             **{k: v / cekilis for k, v in say.items()},
             "S2_suveys_eksi_btk_gun": {"p05": q(farklar_s2, .05), "medyan": q(farklar_s2, .5), "p95": q(farklar_s2, .95)},
             "S6_umit_eksi_btk_gun": {"p05": q(farklar_s6, .05), "medyan": q(farklar_s6, .5), "p95": q(farklar_s6, .95)},
             "basabas_bekleme_azalimi": basabas}
    print("E6:", json.dumps(sonuc, ensure_ascii=False, indent=1))
    with open(os.path.join(SONUC, "e6_saglamlik.json"), "w", encoding="utf-8") as f:
        json.dump(sonuc, f, ensure_ascii=False, indent=1)
    return sonuc


if __name__ == "__main__":
    kor.kalibre_et()
    secim = sys.argv[1:] or ["e1", "e2", "e3", "e4", "e5"]
    for s in secim:
        globals()[s]()
