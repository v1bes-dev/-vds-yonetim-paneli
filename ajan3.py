import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import random
import requests
import datetime
import sqlite3
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()
client = Anthropic()

requests.packages.urllib3.disable_warnings()

PVE_URL = "https://localhost:8006/api2/json"
PVE_TOKEN = os.getenv("PVE_TOKEN")

def sirkete_bildir(mesaj):
    print(f"[BILDIRIM] {mesaj}")

def veritabani_hazirla():
    baglanti = sqlite3.connect("destek.db")
    baglanti.execute("""
        CREATE TABLE IF NOT EXISTS talepler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            musteri TEXT,
            sorun TEXT,
            tarih TEXT,
            durum TEXT
        )
    """)
    baglanti.commit()
    baglanti.close()

veritabani_hazirla()

def toplama_yap(a, b):
    return a + b

def zar_at():
    return random.randint(1, 6)

def not_al(icerik):
    with open("notlar.txt", "a", encoding="utf-8") as f:
        f.write(icerik + "\n")
    return "Not kaydedildi."

def notlari_oku():
    try:
        with open("notlar.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Hiç not yok."

def hava_durumu(sehir):
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": sehir, "count": 1}
    ).json()

    if not geo.get("results"):
        return "Bu şehri bulamadım."

    yer = geo["results"][0]

    hava = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": yer["latitude"],
            "longitude": yer["longitude"],
            "current": "temperature_2m"
        }
    ).json()

    sicaklik = hava["current"]["temperature_2m"]
    return f"{sehir}: {sicaklik} derece"

def hesapla(islem, a, b):
    if islem == "topla":
        return a + b
    if islem == "cikar":
        return a - b
    if islem == "carp":
        return a * b
    if islem == "bol":
        if b == 0:
            return "Sıfıra bölünemez."
        return a / b
    return "Bilinmeyen işlem."

def simdiki_zaman():
    return datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

def sunucu_durumu(vmid):
    r = requests.get(
        f"{PVE_URL}/nodes/pve/lxc/{vmid}/status/current",
        headers={"Authorization": PVE_TOKEN},
        verify=False
    )
    veri = r.json()["data"]
    return f"Sunucu {vmid} ({veri['name']}): {veri['status']}"

def sunucu_kaynak_kullanimi(vmid):
    r = requests.get(
        f"{PVE_URL}/nodes/pve/lxc/{vmid}/status/current",
        headers={"Authorization": PVE_TOKEN},
        verify=False
    )
    v = r.json()["data"]

    if v["status"] != "running":
        return f"Sunucu {vmid} ({v['name']}) şu an çalışmıyor, kaynak bilgisi yok."

    cpu_yuzde = round(v["cpu"] * 100, 2)
    ram_mb = round(v["mem"] / 1024 / 1024, 1)
    ram_max_mb = round(v["maxmem"] / 1024 / 1024, 1)
    disk_gb = round(v["disk"] / 1024 / 1024 / 1024, 2)
    disk_max_gb = round(v["maxdisk"] / 1024 / 1024 / 1024, 2)
    uptime_saat = round(v["uptime"] / 3600, 1)

    return (
        f"Sunucu {vmid} ({v['name']}) kaynak kullanımı:\n"
        f"CPU: %{cpu_yuzde}\n"
        f"RAM: {ram_mb} MB / {ram_max_mb} MB\n"
        f"Disk: {disk_gb} GB / {disk_max_gb} GB\n"
        f"Ağ: giren {v['netin']} bayt, çıkan {v['netout']} bayt\n"
        f"Çalışma süresi: {uptime_saat} saat"
    )

def sunucu_baslat(vmid):
    requests.post(
        f"{PVE_URL}/nodes/pve/lxc/{vmid}/status/start",
        headers={"Authorization": PVE_TOKEN},
        verify=False
    )
    return f"Sunucu {vmid} başlatma isteği gönderildi."

def sunucu_durdur(vmid):
    requests.post(
        f"{PVE_URL}/nodes/pve/lxc/{vmid}/status/stop",
        headers={"Authorization": PVE_TOKEN},
        verify=False
    )
    return f"Sunucu {vmid} durdurma isteği gönderildi."

def talep_olustur(musteri, sorun):
    baglanti = sqlite3.connect("destek.db")
    tarih = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    imlec = baglanti.execute(
        "INSERT INTO talepler (musteri, sorun, tarih, durum) VALUES (?, ?, ?, ?)",
        (musteri, sorun, tarih, "açık")
    )
    baglanti.commit()
    talep_id = imlec.lastrowid
    baglanti.close()
    sirkete_bildir(f"🔔 Yeni destek talebi #{talep_id}\nMüşteri: {musteri}\nSorun: {sorun}")
    return f"Talep #{talep_id} olusturuldu. Musteri: {musteri}, Sorun: {sorun}"

def _sadelestir(metin):
    donusum = str.maketrans("çÇıİğĞüÜöÖşŞ", "cCiIgGuUoOsS")
    return metin.translate(donusum).lower()

def talepleri_listele(durum=None):
    baglanti = sqlite3.connect("destek.db")
    satirlar = baglanti.execute(
        "SELECT id, musteri, sorun, tarih, durum FROM talepler"
    ).fetchall()
    baglanti.close()

    if durum:
        hedef = _sadelestir(durum)
        satirlar = [s for s in satirlar if _sadelestir(s[4]) == hedef]

    if not satirlar:
        return "Hiç talep yok."

    sonuc = []
    for satir in satirlar:
        sonuc.append(f"#{satir[0]} | {satir[1]} | {satir[2]} | {satir[3]} | durum: {satir[4]}")
    return "\n".join(sonuc)

def talep_durumu_guncelle(talep_id, yeni_durum):
    baglanti = sqlite3.connect("destek.db")
    baglanti.execute("UPDATE talepler SET durum = ? WHERE id = ?", (yeni_durum, talep_id))
    baglanti.commit()
    etkilenen = baglanti.total_changes
    baglanti.close()
    if etkilenen == 0:
        return f"Talep #{talep_id} bulunamadi."
    return f"Talep #{talep_id} durumu '{yeni_durum}' olarak guncellendi."

def sunucu_loglarini_oku(vmid):
    r = requests.get(
        f"{PVE_URL}/nodes/pve/tasks",
        headers={"Authorization": PVE_TOKEN},
        params={"vmid": vmid, "limit": 3},
        verify=False
    )
    gorevler = r.json()["data"]
    if not gorevler:
        return "Bu sunucu için kayıtlı işlem yok."

    son_gorev = gorevler[0]
    upid = son_gorev["upid"]

    log_r = requests.get(
        f"{PVE_URL}/nodes/pve/tasks/{upid}/log",
        headers={"Authorization": PVE_TOKEN},
        verify=False
    )
    satirlar = [s["t"] for s in log_r.json()["data"]]
    durum = son_gorev.get("status", "devam ediyor")
    return f"Son işlem ({son_gorev['type']}, durum: {durum}):\n" + "\n".join(satirlar[-10:])

araclar = [
    {
        "name": "toplama_yap",
        "description": "Iki sayiyi toplar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"}
            },
            "required": ["a", "b"]
        }
    },
    {
        "name": "zar_at",
        "description": "1 ile 6 arasinda rastgele bir zar atar.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "not_al",
        "description": "Bir notu dosyaya kalici olarak kaydeder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "icerik": {"type": "string"}
            },
            "required": ["icerik"]
        }
    },
    {
        "name": "notlari_oku",
        "description": "Daha once kaydedilmis tum notlari okur.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "hava_durumu",
        "description": "Bir sehrin su anki gercek hava durumunu (sicaklik) internetten cekip getirir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sehir": {"type": "string"}
            },
            "required": ["sehir"]
        }
    },
    {
        "name": "hesapla",
        "description": "Iki sayi ile toplama, cikarma, carpma veya bolme yapar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "islem": {"type": "string", "enum": ["topla", "cikar", "carp", "bol"]},
                "a": {"type": "number"},
                "b": {"type": "number"}
            },
            "required": ["islem", "a", "b"]
        }
    },
    {
        "name": "simdiki_zaman",
        "description": "Su anki gercek tarih ve saati verir.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "sunucu_durumu",
        "description": "Proxmox VDS panelindeki bir sunucunun (konteynerin) su anki durumunu (calisiyor/durmus) sorgular.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer"}
            },
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_baslat",
        "description": "Proxmox VDS panelindeki bir sunucuyu (konteyneri) baslatir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer"}
            },
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_durdur",
        "description": "Proxmox VDS panelindeki bir sunucuyu (konteyneri) durdurur.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer"}
            },
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_kaynak_kullanimi",
        "description": "Bir sunucunun CPU, RAM, disk ve ag kullanimini detayli sekilde verir (yavaslik/dolu disk gibi sorunlari teshis etmek icin).",
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer"}
            },
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_loglarini_oku",
        "description": "Bir sunucuda en son yapilan islemin (baslatma, durdurma vb.) gercek log kayitlarini okur, sorun teshisi icin kullanilir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "vmid": {"type": "integer"}
            },
            "required": ["vmid"]
        }
    },
    {
        "name": "talep_olustur",
        "description": "Bir musterinin bildirdigi sorunu destek talebi olarak veritabanina kaydeder. Musteri bir sorun bildirdiginde bu mutlaka cagrilmali.",
        "input_schema": {
            "type": "object",
            "properties": {
                "musteri": {"type": "string", "description": "Musterinin adi veya kullanici adi"},
                "sorun": {"type": "string", "description": "Bildirilen sorunun kisa ozeti"}
            },
            "required": ["musteri", "sorun"]
        }
    },
    {
        "name": "talepleri_listele",
        "description": "Kayitli destek taleplerini listeler. Durum belirtilirse (acik/kapali) sadece o durumdakileri gosterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "durum": {"type": "string", "description": "Filtrelenecek durum, ornegin 'acik' veya 'kapali'. Bos birakilirsa hepsi listelenir."}
            }
        }
    },
    {
        "name": "talep_durumu_guncelle",
        "description": "Bir destek talebinin durumunu gunceller (ornegin cozuldugunde 'kapali' yapmak icin).",
        "input_schema": {
            "type": "object",
            "properties": {
                "talep_id": {"type": "integer"},
                "yeni_durum": {"type": "string", "description": "ornegin 'kapali', 'islemde', 'acik'"}
            },
            "required": ["talep_id", "yeni_durum"]
        }
    }
]

SISTEM_PROMPT = """Sen bir hosting/VDS şirketinin müşteri destek ve sistem yönetim asistanısın.

Görevin: müşterilerin VDS, hosting ve domain ile ilgili sorularına yardımcı olmak, sunucu durumlarını
kontrol etmek, kaynak kullanımı ve log analiziyle sorun teşhisi yapmak, günlük sohbet edebilmek.

Kurallar:
- Müşterilerle her zaman kibar, net ve profesyonel Türkçe konuş.
- Bir sunucu sorunu bildirilirse: önce durumunu kontrol et, sonra kaynak kullanımına bak, gerekirse logları oku.
  Bulduğun teknik detayı, teknik bilgisi olmayan birinin de anlayacağı şekilde özetle.
- Müşteri VDS, hosting veya domain fark etmeksizin herhangi bir sorun bildirdiğinde ("domainim gelmedi",
  "vds hatalı", "siteme giremiyorum" gibi) bunu mutlaka talep_olustur ile kaydet, böylece hiçbir sorun
  kaybolmaz ve şirkete otomatik haber gider. Bu, konuşmanın en başında, elinden geldiğince erken yapılmalı.
  Sorun çözüldüğünde talep_durumu_guncelle ile "kapalı" yap.
- Domain/hosting sorunlarında (VDS gibi kontrol edebileceğin bir panel olmadığı için) talebi kaydettikten
  sonra müşteriye "talebiniz kaydedildi, ekibimiz en kısa sürede dönüş yapacak" de.
- Domain/hosting genel sorularında (DNS, yenileme, transfer nedir gibi) kendi bilgini kullanarak yardımcı ol.
- Ödeme, iptal, domain transferi gibi hassas/geri döndürülemez işlemlerde tahmin yürütme —
  bunun bir insan yetkiliye (yöneticiye) iletilmesi gerektiğini söyle.
- İlk selamlaşmada sadece "Merhaba! Size nasıl yardımcı olabilirim?" gibi genel, sıcak bir
  karşılama yap. VDS/hosting/domain konusunu zorla gündeme getirme.
- Bir sorunu çözdüğünde veya bir konuyu kapattığında "Başka bir konuda yardımcı olabilir miyim?"
  diye sorabilirsin.
- Müşteri sıradan/günlük bir konuda sohbet ediyorsa (bir sorun bildirmiyorsa) normal, doğal
  sohbet et. Her cevabının sonuna "VDS/hosting sorununuz var mı" tarzı sorular ekleme, bu
  gereksiz ve sıkıcı olur.
- Kısa ve anlaşılır cevaplar ver, gereksiz uzatma."""

KRITIK_ARACLAR = {"sunucu_baslat", "sunucu_durdur"}

def araci_calistir(isim, girdi, yetkili=True):
    if isim in KRITIK_ARACLAR and not yetkili:
        sirkete_bildir(f"⚠️ Yetkisiz erişim denemesi: '{isim}' araci, girdi: {girdi}")
        return "Bu islem sadece yetkili yoneticiler tarafindan yapilabilir. Talebiniz bir yetkiliye iletildi."
    if isim == "toplama_yap":
        return toplama_yap(girdi["a"], girdi["b"])
    if isim == "zar_at":
        return zar_at()
    if isim == "not_al":
        return not_al(girdi["icerik"])
    if isim == "notlari_oku":
        return notlari_oku()
    if isim == "hava_durumu":
        return hava_durumu(girdi["sehir"])
    if isim == "hesapla":
        return hesapla(girdi["islem"], girdi["a"], girdi["b"])
    if isim == "simdiki_zaman":
        return simdiki_zaman()
    if isim == "sunucu_durumu":
        return sunucu_durumu(girdi["vmid"])
    if isim == "sunucu_baslat":
        return sunucu_baslat(girdi["vmid"])
    if isim == "sunucu_durdur":
        return sunucu_durdur(girdi["vmid"])
    if isim == "sunucu_kaynak_kullanimi":
        return sunucu_kaynak_kullanimi(girdi["vmid"])
    if isim == "sunucu_loglarini_oku":
        return sunucu_loglarini_oku(girdi["vmid"])
    if isim == "talep_olustur":
        return talep_olustur(girdi["musteri"], girdi["sorun"])
    if isim == "talepleri_listele":
        return talepleri_listele(girdi.get("durum"))
    if isim == "talep_durumu_guncelle":
        return talep_durumu_guncelle(girdi["talep_id"], girdi["yeni_durum"])

GECMIS_DOSYASI = "sohbet_gecmisi.json"

def gecmisi_yukle():
    try:
        with open(GECMIS_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def gecmisi_kaydet():
    with open(GECMIS_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(gecmis, f, ensure_ascii=False, indent=2, default=lambda o: o.model_dump())

gecmis = gecmisi_yukle()

def claude_ile_konus(mesaj, yetkili=True):
    gecmis.append({"role": "user", "content": mesaj})

    while True:
        cevap = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=500,
            system=SISTEM_PROMPT,
            tools=araclar,
            messages=gecmis
        )
        gecmis.append({"role": "assistant", "content": cevap.content})

        arac_sonuclari = []
        for parca in cevap.content:
            if parca.type == "text":
                print("Claude:", parca.text)
            if parca.type == "tool_use":
                hata_var = False
                try:
                    sonuc = araci_calistir(parca.name, parca.input, yetkili)
                except Exception as e:
                    sonuc = f"Hata olustu: {e}"
                    hata_var = True
                print("Python çalıştı:", parca.name, "->", sonuc)
                arac_sonuclari.append({
                    "type": "tool_result",
                    "tool_use_id": parca.id,
                    "content": str(sonuc),
                    "is_error": hata_var
                })

        if not arac_sonuclari:
            break

        gecmis.append({"role": "user", "content": arac_sonuclari})

    gecmisi_kaydet()

if __name__ == "__main__":
    while True:
        kullanici_mesaji = input("Sen: ")
        if kullanici_mesaji == "çık":
            break

        claude_ile_konus(kullanici_mesaji)
