import pygame
import sys

pygame.init()

GENISLIK, YUKSEKLIK = 960, 540
ekran = pygame.display.set_mode((GENISLIK, YUKSEKLIK))
pygame.display.set_caption("Platform Oyunu")
saat = pygame.time.Clock()

BEYAZ = (255, 255, 255)
GOKYUZU = (135, 206, 235)
YESIL = (60, 179, 75)
KAHVE = (139, 90, 43)
KIRMIZI = (220, 50, 50)
SARI = (255, 215, 0)
SIYAH = (20, 20, 20)

YERCEKIMI = 0.8
ZIPLAMA_GUCU = -16
OYUNCU_HIZ = 5

font = pygame.font.SysFont("arial", 28)
font_buyuk = pygame.font.SysFont("arial", 60, bold=True)


class Oyuncu:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 36, 54)
        self.vy = 0
        self.yerde = False
        self.can = 3

    def guncelle(self, platformlar):
        tuslar = pygame.key.get_pressed()
        dx = 0
        if tuslar[pygame.K_LEFT] or tuslar[pygame.K_a]:
            dx = -OYUNCU_HIZ
        if tuslar[pygame.K_RIGHT] or tuslar[pygame.K_d]:
            dx = OYUNCU_HIZ

        self.rect.x += dx
        for p in platformlar:
            if self.rect.colliderect(p):
                if dx > 0:
                    self.rect.right = p.left
                elif dx < 0:
                    self.rect.left = p.right

        self.vy += YERCEKIMI
        if self.vy > 20:
            self.vy = 20
        self.rect.y += self.vy
        self.yerde = False
        for p in platformlar:
            if self.rect.colliderect(p):
                if self.vy > 0:
                    self.rect.bottom = p.top
                    self.vy = 0
                    self.yerde = True
                elif self.vy < 0:
                    self.rect.top = p.bottom
                    self.vy = 0

    def zipla(self):
        if self.yerde:
            self.vy = ZIPLAMA_GUCU

    def ciz(self, ekran, kamera_x):
        pygame.draw.rect(ekran, KIRMIZI, (self.rect.x - kamera_x, self.rect.y, self.rect.w, self.rect.h), border_radius=6)


PLATFORMLAR = [
    pygame.Rect(0, 500, 800, 40),
    pygame.Rect(850, 500, 400, 40),
    pygame.Rect(950, 400, 150, 20),
    pygame.Rect(1150, 320, 150, 20),
    pygame.Rect(1350, 500, 600, 40),
    pygame.Rect(1500, 380, 120, 20),
    pygame.Rect(1680, 280, 120, 20),
    pygame.Rect(1850, 500, 500, 40),
    pygame.Rect(2050, 400, 100, 20),
    pygame.Rect(2200, 300, 100, 20),
    pygame.Rect(2350, 500, 700, 40),
]

BOSLUKLAR = [
    pygame.Rect(800, 540, 50, 60),
    pygame.Rect(1250, 540, 100, 60),
]

PARALAR = [(900, 360), (1000, 260), (1200, 280), (1550, 340), (1700, 240),
           (1900, 460), (2080, 360), (2230, 260), (2500, 460)]

HEDEF = pygame.Rect(2900, 420, 50, 80)
BASLANGIC = (50, 420)


def oyunu_sifirla():
    oyuncu = Oyuncu(*BASLANGIC)
    toplanan = set()
    return oyuncu, toplanan


def main():
    oyuncu, toplanan = oyunu_sifirla()
    kazanildi = False
    dusuldu_sayaci = 0

    calisiyor = True
    while calisiyor:
        for olay in pygame.event.get():
            if olay.type == pygame.QUIT:
                calisiyor = False
            if olay.type == pygame.KEYDOWN:
                if olay.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    oyuncu.zipla()
                if olay.key == pygame.K_r:
                    oyuncu, toplanan = oyunu_sifirla()
                    kazanildi = False

        if not kazanildi:
            oyuncu.guncelle(PLATFORMLAR)

            if oyuncu.rect.y > YUKSEKLIK + 200:
                oyuncu, toplanan = oyunu_sifirla()

            for i, (px, py) in enumerate(PARALAR):
                if i not in toplanan:
                    para_rect = pygame.Rect(px, py, 20, 20)
                    if oyuncu.rect.colliderect(para_rect):
                        toplanan.add(i)

            if oyuncu.rect.colliderect(HEDEF):
                kazanildi = True

        kamera_x = oyuncu.rect.centerx - GENISLIK // 2
        kamera_x = max(0, kamera_x)

        ekran.fill(GOKYUZU)

        for p in PLATFORMLAR:
            ekran_rect = pygame.Rect(p.x - kamera_x, p.y, p.w, p.h)
            pygame.draw.rect(ekran, KAHVE, ekran_rect)
            pygame.draw.rect(ekran, YESIL, (ekran_rect.x, ekran_rect.y, ekran_rect.w, 10))

        for i, (px, py) in enumerate(PARALAR):
            if i not in toplanan:
                pygame.draw.circle(ekran, SARI, (px - kamera_x, py), 10)

        hedef_ekran = pygame.Rect(HEDEF.x - kamera_x, HEDEF.y, HEDEF.w, HEDEF.h)
        pygame.draw.rect(ekran, (120, 120, 120), hedef_ekran)
        pygame.draw.rect(ekran, BEYAZ, (hedef_ekran.x + 5, hedef_ekran.y - 30, 30, 30))

        oyuncu.ciz(ekran, kamera_x)

        skor_yazi = font.render(f"Para: {len(toplanan)}/{len(PARALAR)}", True, SIYAH)
        ekran.blit(skor_yazi, (20, 20))
        ipucu_yazi = font.render("Ok/A-D: Hareket  |  Space: Zipla  |  R: Basa don", True, SIYAH)
        ekran.blit(ipucu_yazi, (20, 50))

        if kazanildi:
            yazi = font_buyuk.render("KAZANDIN!", True, (255, 255, 255))
            kutu = yazi.get_rect(center=(GENISLIK // 2, YUKSEKLIK // 2))
            ekran.blit(yazi, kutu)
            alt_yazi = font.render("Tekrar oynamak icin R'ye bas", True, SIYAH)
            ekran.blit(alt_yazi, alt_yazi.get_rect(center=(GENISLIK // 2, YUKSEKLIK // 2 + 50)))

        pygame.display.flip()
        saat.tick(60)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
