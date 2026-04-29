import pygame
import sys
import os

pygame.init()

SCREEN_W, SCREEN_H = 400, 400
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Warrior Sprite Test")

sprite_path = os.path.join(os.path.dirname(__file__), "assets", "warrior.png")
warrior = pygame.image.load(sprite_path).convert_alpha()

clock = pygame.time.Clock()

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()

    screen.fill((0, 0, 0))

    x = (SCREEN_W - warrior.get_width()) // 2
    y = (SCREEN_H - warrior.get_height()) // 2
    screen.blit(warrior, (x, y))

    pygame.display.flip()
    clock.tick(60)
