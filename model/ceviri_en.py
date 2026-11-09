# -*- coding: utf-8 -*-
"""Şekil metinlerini İngilizceye çevirir (AIAPP İngilizce sürüm için).
Kullanım: SEKIL_DIL=en python sekiller.py  → ../sekiller/*_en.png|pdf
sekiller.kaydet() kaydetmeden önce cevir_figur(fig) çağırır."""
import re



SOZLUK = {
    # düğümler
    "Şanghay": "Shanghai", "Almatı": "Almaty", "Bakü/Alat": "Baku/Alat", "Tiflis": "Tbilisi",
    "Ahılkelek": "Akhalkalaki", "Batum": "Batumi", "İstanbul": "Istanbul", "İzmir": "Izmir",
    "Köstence": "Constanța", "Sofya": "Sofia", "Budapeşte": "Budapest", "Moskova": "Moscow",
    "Pire": "Piraeus", "Singapur": "Singapore", "Sri Lanka açığı": "off Sri Lanka",
    "Süveyş Kanalı": "Suez Canal", "Cebelitarık": "Gibraltar", "Manş girişi": "English Channel",
    "Ümit Burnu": "Cape of Good Hope", "Dakar açığı": "off Dakar", "Çanakkale Boğazı": "Dardanelles",
    "İstanbul Boğazı": "Bosphorus",
    # koridorlar
    "Kuzey Koridoru\n(Rusya–Belarus)": "Northern Corridor\n(Russia–Belarus)",
    "Orta Koridor –\nGürcistan limanları": "Middle Corridor –\nGeorgian ports",
    "Orta Koridor –\nTürkiye (BTK)": "Middle Corridor –\nTürkiye (BTK)",
    "Deniz yolu –\nSüveyş": "Maritime –\nSuez",
    "Deniz yolu –\nÜmit Burnu": "Maritime –\nCape of Good Hope",
    "Deniz – Süveyş": "Maritime – Suez", "Deniz – Ümit Burnu": "Maritime – Cape of Good Hope",
    "Kuzey Koridoru": "Northern Corridor", "Orta Koridor – Türkiye (BTK)": "Middle Corridor – Türkiye (BTK)",
    "Orta Koridor – Karadeniz geçişi": "Middle Corridor – Black Sea crossing",
    # harita lejantı ve etiketleri
    "Demiryolu": "Rail", "Karayolu": "Road", "Okyanus": "Ocean",
    "Kısa mesafe deniz / feribot": "Short-sea / ferry", "Liman": "Port",
    "Sınır / ray açıklığı değişimi": "Border / gauge change", "Şehir / iç terminal": "City / inland terminal",
    "Deniz yolu ara noktası": "Sea-route waypoint", "Şekil 1b": "Fig. 1b",
    "Hazar Denizi": "Caspian Sea", "Karadeniz": "Black Sea", "Akdeniz": "Mediterranean Sea",
    # süre kırılımı
    "Hareket (yolda geçen süre)": "Movement (in transit)", "Liman bekleme / aktarma": "Port dwell / transshipment",
    "Sınır ve ray açıklığı geçişi": "Border and gauge-change crossing",
    "(a) S1 — 2022 mevcut durum": "(a) S1 — 2022 baseline", "(b) S2 — 2030 hedefi": "(b) S2 — 2030 improvement",
    "Xi'an → Duisburg kapıdan kapıya süre (gün)": "Xi'an → Duisburg door-to-door time (days)",
    # kalibrasyon
    "Khorgos → Köstence\n(Gürcistan limanları)": "Khorgos → Constanța\n(via Georgian ports)",
    "Khorgos → Kapıkule\n(Türkiye üzerinden)": "Khorgos → Kapıkule\n(via Türkiye)",
    "Süre (gün), 2022": "Time (days), 2022",
    # durum grafı
    "Deniz\nkatmanı": "Sea\nlayer", "Demiryolu\nkatmanı": "Rail\nlayer", "Karayolu\nkatmanı": "Road\nlayer",
    "aktarma kenarı:\nliman bekleme\n+ elleçleme": "transfer edge:\nport dwell\n+ handling",
    "sınır geçişi\n(+3 gün)": "border crossing\n(+3 days)", "terminal aktarması": "terminal transfer",
    "durum = (düğüm, mod)\nkenar ağırlığı = (maliyet, süre, CO$_2$)":
        "state = (node, mode)\nedge weight = (cost, time, CO$_2$)",
    # Pareto
    "(b) S5 — Kızıldeniz ve Kuzey kapalı": "(b) S5 — Red Sea & Northern closed",
    "(c) S6 — S5 + 2030 hedefi": "(c) S6 — S5 with 2030 improvement",
    "Maliyet (bin USD/FEU)": "Cost (thousand USD/FEU)", "Süre (gün)": "Time (days)",
    # verimlilik
    "Maliyet": "Cost", "Süre": "Time", "A* (büyük daire)": "A* (great circle)",
    "Ort. genişletilen durum": "Mean expanded states",
    "(a) Arama eforu (992 sorgu, S1)": "(a) Search effort (992 queries, S1)",
    "(b) Sezgisel kalitesi (1 = mükemmel)": "(b) Heuristic quality (1 = perfect)",
    # sentetik
    "Dijkstra = %100": "Dijkstra = 100%",
    "Bekleme süresi çarpanı λ (0 = hiç bekleme yok)": "Delay multiplier λ (0 = no delays)",
    "Genişletilen durum\n(Dijkstra'ya göre, %)": "Expanded states\n(% of Dijkstra)",
    "(a) Bekleme süresinin etkisi (n = 3.000)": "(c) Effect of node delays (n = 3,000)",
    "Durum sayısı (bin, log)": "Number of states (thousands, log)",
    "Sorgu süresi (ms, log)": "Query time (ms, log)", "(b) Ölçeklenebilirlik": "(d) Scalability",
}

KURALLAR = [
    (r"^(\d+),(\d+)$", r"\1.\2"),                 # 0,25 → 0.25
    (r"(\d+) Pareto çözüm$", r"\1 Pareto solutions"),
    (r"\(kalibrasyon\)", "(calibration)"), (r"\(doğrulama\)", "(validation)"),
    (r"\bgün\b", "days"),
]
# Türkçe karakter içerse de İngilizce metinde kalabilecek özel adlar
IZINLI = ("Türkiye", "Kapıkule", "Ambarlı", "TÜRKİYE", "Constanța")
_kalan = set()


def cevir(s):
    if not s:
        return s
    if s in SOZLUK:
        return SOZLUK[s]
    t = s
    for a, b in KURALLAR:
        t = re.sub(a, b, t)
    temiz = t
    for ad in IZINLI:
        temiz = temiz.replace(ad, "")
    if re.search(r"[çğıöşüÇĞİÖŞÜ]", temiz):
        _kalan.add(t)
    return t


def cevir_figur(fig):
    fig.canvas.draw()
    for ax in fig.axes:
        for ad in ("title", "_left_title", "_right_title"):
            tt = getattr(ax, ad, None)
            if tt is not None:
                tt.set_text(cevir(tt.get_text()))
        for eksen in (ax.xaxis, ax.yaxis):
            eksen.label.set_text(cevir(eksen.label.get_text()))
            etiketler = eksen.get_ticklabels()
            eski = [t.get_text() for t in etiketler]
            yeni = [cevir(s) for s in eski]
            if yeni != eski:
                fs = etiketler[0].get_fontsize()
                eksen.set_ticks(eksen.get_ticklocs())
                eksen.set_ticklabels(yeni, fontsize=fs)
        for t in ax.texts:
            t.set_text(cevir(t.get_text()))
        lg = ax.get_legend()
        if lg:
            for t in lg.get_texts():
                t.set_text(cevir(t.get_text()))
    for lg in fig.legends:
        for t in lg.get_texts():
            t.set_text(cevir(t.get_text()))
    for t in fig.texts:
        t.set_text(cevir(t.get_text()))
    if _kalan:
        print("  ! çevrilmemiş olabilir:", sorted(_kalan))
        _kalan.clear()
