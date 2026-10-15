import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import time
import random
import requests
import datetime
import threading
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from anthropic import Anthropic

import db
import pii
import audit
import kod_gorevi
from guardrails import GUARDRAIL_EK, sanitize_input
from grounding import check_grounded
from rate_limit import check_rate_limit, RateLimitExceeded

load_dotenv()
client = Anthropic()

OWNER_JID = os.getenv("OWNER_JID")
_TR_FOLD = str.maketrans("çÇıİğĞüÜöÖşŞ", "cCiIgGuUoOsS")
_ONAY_KELIMELERI = {"evet", "ok", "onayla", "onayliyorum", "tamam"}
_RED_KELIMELERI = {"hayir", "iptal", "vazgectim"}

requests.packages.urllib3.disable_warnings()

PVE_URL = "https://localhost:8006/api2/json"
PVE_TOKEN = os.getenv("PVE_TOKEN")
BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3000")


def sirkete_bildir(mesaj):
    # Telegram yerine: sahibinin kendi WhatsApp sohbetine bildirim gonderilir.
    chat_id = ana_sohbeti_oku()
    if chat_id:
        bridge_mesaj_gonder(chat_id, f"🔔 {mesaj}")

db.init_db()

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
    talep_id = db.talep_olustur(musteri, sorun)
    sirkete_bildir(f"Yeni destek talebi #{talep_id}\nMüşteri: {musteri}\nSorun: {sorun}")
    return f"Talep #{talep_id} olusturuldu. Musteri: {musteri}, Sorun: {sorun}"

def talepleri_listele(durum=None):
    satirlar = db.talepleri_listele(durum)
    if not satirlar:
        return "Hiç talep yok."
    return "\n".join(f"#{s[0]} | {s[1]} | {s[2]} | {s[3]} | durum: {s[4]}" for s in satirlar)

def talep_durumu_guncelle(talep_id, yeni_durum):
    if not db.talep_durumu_guncelle(talep_id, yeni_durum):
        return f"Talep #{talep_id} bulunamadi."
    return f"Talep #{talep_id} durumu '{yeni_durum}' olarak guncellendi."

def web_ara(sorgu):
    r = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": sorgu},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15
    )
    soup = BeautifulSoup(r.text, "html.parser")
    sonuclar = []
    for a in soup.select("a.result__a")[:5]:
        baslik = a.get_text(strip=True)
        link = a.get("href")
        if baslik and link:
            sonuclar.append(f"{baslik} - {link}")
    if not sonuclar:
        return "Sonuç bulunamadı."
    return "\n".join(sonuclar)

def sayfa_oku(url):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    soup = BeautifulSoup(r.text, "html.parser")
    for etiket in soup(["script", "style"]):
        etiket.decompose()
    metin = soup.get_text(separator="\n")
    satirlar = [s.strip() for s in metin.splitlines() if s.strip()]
    sonuc = "\n".join(satirlar)[:4000]
    # internetten gelen metin GUVENILMEZ veri: komut icerebilir, maskelenip
    # isaretlenmeli ki model bunu talimat degil veri olarak gorsun.
    kontrol = sanitize_input(sonuc, max_len=4000)
    if kontrol.blocked:
        audit.log_blocked_attempt(url, kontrol.reason, sonuc)
        return "[Bu sayfada supheli/talimat benzeri icerik tespit edildi, atlandi.]"
    return pii.redact(sonuc)

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
        "name": "web_ara",
        "description": "Internette bir konuyu arar, en alakali 5 sonucun basligini ve linkini getirir.",
        "input_schema": {
            "type": "object",
            "properties": {"sorgu": {"type": "string"}},
            "required": ["sorgu"]
        }
    },
    {
        "name": "sayfa_oku",
        "description": "Bir web sayfasinin linkini verince, o sayfanin yazi icerigini okuyup getirir.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"]
        }
    },
    {
        "name": "toplama_yap",
        "description": "Iki sayiyi toplar.",
        "input_schema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"]
        }
    },
    {
        "name": "zar_at",
        "description": "1 ile 6 arasinda rastgele bir zar atar.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "not_al",
        "description": "Bir notu dosyaya kalici olarak kaydeder.",
        "input_schema": {
            "type": "object",
            "properties": {"icerik": {"type": "string"}},
            "required": ["icerik"]
        }
    },
    {
        "name": "notlari_oku",
        "description": "Daha once kaydedilmis tum notlari okur.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "hava_durumu",
        "description": "Bir sehrin su anki gercek hava durumunu (sicaklik) internetten cekip getirir.",
        "input_schema": {
            "type": "object",
            "properties": {"sehir": {"type": "string"}},
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
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "sunucu_durumu",
        "description": "Proxmox VDS panelindeki bir sunucunun (konteynerin) su anki durumunu (calisiyor/durmus) sorgular.",
        "input_schema": {
            "type": "object",
            "properties": {"vmid": {"type": "integer"}},
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_baslat",
        "description": "Proxmox VDS panelindeki bir sunucuyu (konteyneri) baslatir.",
        "input_schema": {
            "type": "object",
            "properties": {"vmid": {"type": "integer"}},
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_durdur",
        "description": "Proxmox VDS panelindeki bir sunucuyu (konteyneri) durdurur.",
        "input_schema": {
            "type": "object",
            "properties": {"vmid": {"type": "integer"}},
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_kaynak_kullanimi",
        "description": "Bir sunucunun CPU, RAM, disk ve ag kullanimini detayli sekilde verir (yavaslik/dolu disk gibi sorunlari teshis etmek icin).",
        "input_schema": {
            "type": "object",
            "properties": {"vmid": {"type": "integer"}},
            "required": ["vmid"]
        }
    },
    {
        "name": "sunucu_loglarini_oku",
        "description": "Bir sunucuda en son yapilan islemin (baslatma, durdurma vb.) gercek log kayitlarini okur, sorun teshisi icin kullanilir.",
        "input_schema": {
            "type": "object",
            "properties": {"vmid": {"type": "integer"}},
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
            "properties": {"durum": {"type": "string", "description": "Filtrelenecek durum, ornegin 'acik' veya 'kapali'. Bos birakilirsa hepsi listelenir."}}
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
Şu an WhatsApp üzerinden, telefondan yazan biriyle konuşuyorsun.

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
- Telefon ekranında okunacağı için kısa ve anlaşılır cevaplar ver, gereksiz uzatma.
- Internetten bir şey araştırman gerekirse web_ara ve sayfa_oku araçlarını kullanabilirsin.""" + GUARDRAIL_EK

KRITIK_ARACLAR = {"sunucu_baslat", "sunucu_durdur"}

def araci_calistir(isim, girdi, yetkili=True, chat_id=None):
    if isim in KRITIK_ARACLAR and not yetkili:
        audit.log_unauthorized_tool(chat_id or "unknown", isim, girdi)
        sirkete_bildir(f"⚠️ Yetkisiz erişim denemesi: '{isim}' araci, girdi: {girdi}")
        return "Bu islem sadece yetkili yoneticiler tarafindan yapilabilir. Talebiniz bir yetkiliye iletildi."
    if isim == "web_ara":
        return web_ara(girdi["sorgu"])
    if isim == "sayfa_oku":
        return sayfa_oku(girdi["url"])
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

SOHBET_DOSYASI = "whatsapp_sohbetleri.json"

def gecmisleri_yukle():
    try:
        with open(SOHBET_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def gecmisleri_kaydet():
    with open(SOHBET_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(sohbet_gecmisleri, f, ensure_ascii=False, indent=2, default=lambda o: o.model_dump())

sohbet_gecmisleri = gecmisleri_yukle()

def claude_ile_konus(chat_id, mesaj):
    chat_id = str(chat_id)
    yetkili = True  # WhatsApp bridge'i zaten sadece sahibinin kendi mesajlarini isliyor (self-chat modu)
    gecmis = sohbet_gecmisleri.setdefault(chat_id, [])
    gecmis.append({"role": "user", "content": pii.redact(mesaj)})
    tur_arac_ciktilari = []

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
        metin_parcalari = []
        for parca in cevap.content:
            if parca.type == "text":
                metin_parcalari.append(parca.text)
            if parca.type == "tool_use":
                hata_var = False
                try:
                    sonuc = araci_calistir(parca.name, parca.input, yetkili, chat_id)
                except Exception as e:
                    sonuc = f"Hata olustu: {e}"
                    hata_var = True
                sonuc = pii.redact(str(sonuc))
                tur_arac_ciktilari.append(sonuc)
                arac_sonuclari.append({
                    "type": "tool_result",
                    "tool_use_id": parca.id,
                    "content": sonuc,
                    "is_error": hata_var
                })

        if not arac_sonuclari:
            gecmisleri_kaydet()
            metin = "\n".join(metin_parcalari) if metin_parcalari else "..."
            saglam, guvenli_metin = check_grounded(metin, tur_arac_ciktilari)
            if not saglam:
                audit.log_blocked_attempt(chat_id, "hallucination", metin)
            return guvenli_metin

        gecmis.append({"role": "user", "content": arac_sonuclari})

ANA_SOHBET_DOSYASI = "whatsapp_ana_sohbet.json"

def ana_sohbeti_kaydet(chat_id):
    with open(ANA_SOHBET_DOSYASI, "w", encoding="utf-8") as f:
        json.dump({"chat_id": chat_id}, f)

def ana_sohbeti_oku():
    try:
        with open(ANA_SOHBET_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f).get("chat_id")
    except FileNotFoundError:
        return None

AKSAM_OZETI_SAATI = "20:00"

def aksam_ozeti_dongusu():
    gonderilen_gun = None
    while True:
        time.sleep(30)
        simdi = datetime.datetime.now()
        hedef_saat, hedef_dakika = map(int, AKSAM_OZETI_SAATI.split(":"))
        if simdi.hour == hedef_saat and simdi.minute == hedef_dakika and gonderilen_gun != simdi.date():
            chat_id = ana_sohbeti_oku()
            if chat_id:
                try:
                    cevap = claude_ile_konus(
                        chat_id,
                        "Bugünün Türkiye ve dünya gündemindeki en önemli 3-4 haberini web_ara ve sayfa_oku "
                        "araçlarıyla araştır, kısa bir akşam özeti olarak sun."
                    )
                    bridge_mesaj_gonder(chat_id, "🌙 Akşam Özeti\n\n" + cevap)
                except Exception as e:
                    print(f"Aksam ozeti hatasi: {e}")
            gonderilen_gun = simdi.date()

def bridge_mesajlari_al():
    r = requests.get(f"{BRIDGE_URL}/messages", timeout=10)
    r.raise_for_status()
    return r.json()

def bridge_mesaj_gonder(chat_id, metin):
    requests.post(f"{BRIDGE_URL}/send", json={"chatId": chat_id, "message": metin}, timeout=15)

def main():
    print("WhatsApp botu calisiyor, kendine mesaj yazabilirsin...")
    threading.Thread(target=aksam_ozeti_dongusu, daemon=True).start()
    while True:
        try:
            mesajlar = bridge_mesajlari_al()
        except requests.exceptions.RequestException as e:
            print(f"Bridge'e baglanilamadi: {e}")
            time.sleep(5)
            continue

        for olay in mesajlar:
            metin = olay.get("body", "").strip()
            chat_id = olay.get("chatId")
            if not metin or not chat_id:
                continue

            if ana_sohbeti_oku() != chat_id:
                ana_sohbeti_kaydet(chat_id)

            try:
                check_rate_limit(chat_id)
            except RateLimitExceeded:
                audit.log_rate_limited(chat_id)
                bridge_mesaj_gonder(chat_id, "Çok hızlı mesaj gönderiyorsunuz, lütfen bir dakika bekleyip tekrar deneyin.")
                continue
            metin_sade = metin.strip().translate(_TR_FOLD).lower()

            if metin.strip().lower().startswith("/kod "):
                if chat_id != OWNER_JID:
                    audit.log_unauthorized_tool(chat_id, "kod_gorevi", metin)
                    continue
                gorev = metin.strip()[5:].strip()
                print(f"[kod_gorevi] plan isteniyor: {gorev}")
                bridge_mesaj_gonder(chat_id, "Plan hazırlanıyor, biraz sürebilir...")
                try:
                    plan = kod_gorevi.gorev_plani_iste(chat_id, gorev)
                except Exception as e:
                    plan = f"Plan olusturulamadi: {e}"
                bridge_mesaj_gonder(chat_id, f"📋 Plan:\n\n{plan}\n\nUygulayayım mı? ('evet' ya da 'hayır' yaz)")
                continue

            if chat_id == OWNER_JID and kod_gorevi.bekleyen_plan_var_mi(chat_id):
                if metin_sade in _ONAY_KELIMELERI:
                    bridge_mesaj_gonder(chat_id, "Uygulaniyor, biraz sürebilir...")
                    try:
                        sonuc_metni = kod_gorevi.plani_onayla(chat_id)
                    except Exception as e:
                        sonuc_metni = f"Hata olustu: {e}"
                    bridge_mesaj_gonder(chat_id, f"✅ {sonuc_metni}")
                    continue
                if metin_sade in _RED_KELIMELERI:
                    bridge_mesaj_gonder(chat_id, kod_gorevi.plani_reddet(chat_id))
                    continue

            sonuc = sanitize_input(metin)
            if sonuc.blocked:
                audit.log_blocked_attempt(chat_id, sonuc.reason, metin)
                bridge_mesaj_gonder(chat_id, "Bu konuda yardımcı olamam.")
                continue

            print(f"Gelen: {metin}")
            try:
                cevap = claude_ile_konus(chat_id, sonuc.clean_text)
            except Exception as e:
                cevap = f"Bir hata oluştu: {e}"
            print(f"Cevap: {cevap}")
            bridge_mesaj_gonder(chat_id, cevap)

        time.sleep(2)

if __name__ == "__main__":
    main()
