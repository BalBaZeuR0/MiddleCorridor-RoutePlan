"""
Arama algoritmaları (sıfırdan): Dijkstra, A*, ALT (landmark) sezgiseli, NAMOA* (çok amaçlı A*).

Graf arayüzü: kenarlar[u] = [(v, vek, bilgi), ...]; vek = (maliyet, süre, co2)
Tek amaçlı aramalar 'k' indeksli amacı (0/1/2) en küçükler.
"""
from __future__ import annotations
import heapq
import itertools
import math
import time

INF = float("inf")


class Sonuc:
    __slots__ = ("yol", "deger", "genisletilen", "sure_ms", "itilen")

    def __init__(self, yol, deger, genisletilen, sure_ms, itilen):
        self.yol, self.deger, self.genisletilen, self.sure_ms, self.itilen = yol, deger, genisletilen, sure_ms, itilen


def _yol_kur(onceki, t):
    if t not in onceki:
        return None
    yol = [t]
    while onceki[yol[-1]] is not None:
        yol.append(onceki[yol[-1]])
    return yol[::-1]


def astar(kenarlar, s, t, k, h=None):
    """h=None ise Dijkstra. h tutarlı (consistent) olmalı; kapalı küme yeniden açılmaz."""
    t0 = time.perf_counter()
    h = h or (lambda v: 0.0)
    g = {s: 0.0}
    onceki = {s: None}
    kapali = set()
    sayac = itertools.count()
    acik = [(h(s), next(sayac), s)]
    genis = itilen = 0
    while acik:
        f, _, u = heapq.heappop(acik)
        if u in kapali:
            continue
        kapali.add(u)
        genis += 1
        if u == t:
            break
        gu = g[u]
        for v, vek, _ in kenarlar.get(u, ()):
            if v in kapali:
                continue
            ng = gu + vek[k]
            if ng < g.get(v, INF):
                g[v] = ng
                onceki[v] = u
                heapq.heappush(acik, (ng + h(v), next(sayac), v))
                itilen += 1
    return Sonuc(_yol_kur(onceki, t), g.get(t, INF), genis, (time.perf_counter() - t0) * 1e3, itilen)


def dijkstra_hepsi(kenarlar, s, k):
    """Tek kaynaktan tüm durumlara en kısa mesafeler (ALT ön hesaplaması için)."""
    d = {s: 0.0}
    kapali = set()
    acik = [(0.0, s)]
    sayac = itertools.count()
    acik = [(0.0, next(sayac), s)]
    while acik:
        du, _, u = heapq.heappop(acik)
        if u in kapali:
            continue
        kapali.add(u)
        for v, vek, _ in kenarlar.get(u, ()):
            nd = du + vek[k]
            if nd < d.get(v, INF):
                d[v] = nd
                heapq.heappush(acik, (nd, next(sayac), v))
    return d


def ters_graf(kenarlar):
    r = {}
    for u, lst in kenarlar.items():
        for v, vek, b in lst:
            r.setdefault(v, []).append((u, vek, b))
    return r


# ------------------------------------------------------------------ ALT
class ALT:
    """Landmark tabanlı alt sınır. Hedef bir 'hedef kümesi' olabilir (hedef düğümündeki tüm modlar)."""

    def __init__(self, kenarlar, landmarklar, k):
        self.k = k
        self.L = list(landmarklar)
        ters = ters_graf(kenarlar)
        self.ileri = [dijkstra_hepsi(kenarlar, l, k) for l in self.L]   # d(L, v)
        self.geri = [dijkstra_hepsi(ters, l, k) for l in self.L]        # d(v, L)

    def sezgisel(self, hedef_durumlari):
        """h(v) = max_L max( min_m d(L,t_m) - d(L,v),  d(v,L) - max_m d(t_m,L), 0 )"""
        sabit1, sabit2 = [], []
        for i in range(len(self.L)):
            sabit1.append(min(self.ileri[i].get(t, INF) for t in hedef_durumlari))
            sabit2.append(max(self.geri[i].get(t, INF) for t in hedef_durumlari))
        ileri, geri, n = self.ileri, self.geri, len(self.L)

        def h(v):
            en = 0.0
            for i in range(n):
                a = ileri[i].get(v)
                if a is not None and sabit1[i] < INF:
                    x = sabit1[i] - a
                    if x > en:
                        en = x
                b = geri[i].get(v)
                if b is not None and sabit2[i] < INF:
                    x = b - sabit2[i]
                    if x > en:
                        en = x
            return en
        return h


def landmark_sec(kenarlar, adaylar, sayi, k, baslangic=None):
    """En uzak nokta (farthest) seçimi; uzaklık iki yönlü toplam en kısa yol ile."""
    adaylar = list(adaylar)
    ters = ters_graf(kenarlar)
    en_yakin = {a: INF for a in adaylar}

    def guncelle(l):
        di = dijkstra_hepsi(kenarlar, l, k)
        dg = dijkstra_hepsi(ters, l, k)
        for a in adaylar:
            en_yakin[a] = min(en_yakin[a], di.get(a, INF) + dg.get(a, INF))

    def en_uzak(haric):
        aday = [a for a in adaylar if a not in haric and en_yakin[a] < INF]
        return max(aday, key=lambda a: en_yakin[a])

    # başlangıç noktasından en uzak düğüm ilk landmark olur; sonra kümeye en uzak olan eklenir
    bas = baslangic or adaylar[0]
    guncelle(bas)
    secilen = [en_uzak({bas})]
    en_yakin = {a: INF for a in adaylar}
    guncelle(secilen[0])
    while len(secilen) < sayi:
        l = en_uzak(set(secilen))
        secilen.append(l)
        guncelle(l)
    return secilen


# ------------------------------------------------------------------ NAMOA*
def _baskin(a, b):
    """a, b'yi domine eder mi (<= hepsinde, < en az birinde)"""
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def _baskin_veya_esit(a, b):
    return all(x <= y for x, y in zip(a, b))


def namoa(kenarlar, s, t, h=None, amaclar=(0, 1, 2)):
    """
    NAMOA* (Mandow & Pérez de la Cruz, 2010). h(v) -> amaç vektörü alt sınırı (tutarlı).
    Dönüş: [(maliyet_vektörü, yol), ...] Pareto-optimal çözümler; istatistikler.
    """
    t0 = time.perf_counter()
    m = len(amaclar)
    h = h or (lambda v: (0.0,) * m)
    sayac = itertools.count()
    G_op, G_cl = {s: [(0.0,) * m]}, {}
    ebeveyn = {}  # (v, g) -> (u, g_u)
    COSTS = []
    acik = [(tuple(h(s)), next(sayac), s, (0.0,) * m)]
    genis = 0
    while acik:
        f, _, u, gu = heapq.heappop(acik)
        if gu not in G_op.get(u, []):
            continue  # budanmış etiket
        # çözüm kümesi tarafından domine ediliyor mu?
        if any(_baskin_veya_esit(c, f) for c in COSTS):
            G_op[u].remove(gu)
            continue
        G_op[u].remove(gu)
        G_cl.setdefault(u, []).append(gu)
        genis += 1
        if u == t:
            COSTS = [c for c in COSTS if not _baskin(gu, c)] + [gu]
            continue
        for v, vek, _ in kenarlar.get(u, ()):
            gv = tuple(gu[i] + vek[a] for i, a in enumerate(amaclar))
            hv = tuple(h(v))
            fv = tuple(x + y for x, y in zip(gv, hv))
            if any(_baskin_veya_esit(c, fv) for c in COSTS):
                continue
            op, cl = G_op.setdefault(v, []), G_cl.get(v, [])
            if gv in op or gv in cl:
                continue
            if any(_baskin_veya_esit(x, gv) for x in op) or any(_baskin_veya_esit(x, gv) for x in cl):
                continue
            # gv tarafından domine edilenleri buda
            G_op[v] = [x for x in op if not _baskin(gv, x)]
            if v in G_cl:
                G_cl[v] = [x for x in cl if not _baskin(gv, x)]
            G_op[v].append(gv)
            ebeveyn[(v, gv)] = (u, gu)
            heapq.heappush(acik, (fv, next(sayac), v, gv))
    cozumler = []
    for c in COSTS:
        yol, dugum, g_ = [t], t, c
        while (dugum, g_) in ebeveyn:
            dugum, g_ = ebeveyn[(dugum, g_)]
            yol.append(dugum)
        cozumler.append((c, yol[::-1]))
    cozumler.sort()
    return cozumler, {"genisletilen": genis, "sure_ms": (time.perf_counter() - t0) * 1e3}
