import json

sunucular = []

def sunuculari_yukle(dosya_adi="sunucular.json"):
    global sunucular
    try:
        with open(dosya_adi, "r", encoding="utf-8") as dosya:
            sunucular = json.load(dosya)
    except FileNotFoundError:
        sunucular = []

def dosyaya_kaydet(dosya_adi="sunucular.json"):
    with open(dosya_adi, "w", encoding="utf-8") as dosya:
        json.dump(sunucular, dosya, ensure_ascii=False, indent=4)

def sunucu_ekle():
    isim = input("Sunucu Adı: ")
    ip = input("IP Adresi: ")
    ram = input("RAM Miktarı: ")
    
    yeni_sunucu = {
        "isim": isim,
        "ip": ip,
        "ram": ram
    }
    
    sunucular.append(yeni_sunucu)
    dosyaya_kaydet()
    print(f"--> '{isim}' başarıyla eklendi ve JSON dosyasına kaydedildi!")

def sunucu_listele():
    print("\n--- Kayıtlı Sunucular ---")
    if len(sunucular) == 0:
        print("Henüz hiç sunucu eklenmemiş.")
    else:
        for s in sunucular:
            print(f"İsim: {s['isim']} | IP: {s['ip']} | RAM: {s['ram']}")

def sunucu_sil():
    silinecek = input("Silinecek sunucu adı: ")
    bulunan = None
    
    for s in sunucular:
        if s["isim"] == silinecek:
            bulunan = s
            break
            
    if bulunan:
        sunucular.remove(bulunan)
        dosyaya_kaydet()
        print(f"--> '{silinecek}' başarıyla silindi ve dosya güncellendi!")
    else:
        print("Bu isimde bir sunucu bulunamadı!")