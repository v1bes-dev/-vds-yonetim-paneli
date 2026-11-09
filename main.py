import kutuphane

# Program ilk açıldığında JSON'dan verileri yükle
kutuphane.sunuculari_yukle()

# Ana Menü Döngüsü
while True:
    print("\n--- VDS YÖNETİM PANELİ ---")
    print("1. Sunucu Ekle")
    print("2. Sunucuları Listele")
    print("3. Sunucu Sil")
    print("4. Çıkış")
    
    secim = input("Seçiminiz (1/2/3/4): ")
    
    if secim == "1":
        kutuphane.sunucu_ekle()
    elif secim == "2":
        kutuphane.sunucu_listele()
    elif secim == "3":
        kutuphane.sunucu_sil()
    elif secim == "4":
        print("Programdan çıkılıyor. Görüşmek üzere!")
        break
    else:
        print("Geçersiz seçim, lütfen 1-4 arasında bir sayı girin.")            