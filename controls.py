# controls.py
# Knapplayout för arcadeskåpet + pausskärmen som visas när man trycker ESC i ett spel.
#
# Allt i CONTROLS visas på skärmen för spelarna. Lägg aldrig in den hemliga avslutskombon här.
import pygame
import joystick_keys as jk

# Vad varje knapp gör per skärm. Knappar som saknas i en lista ritas dimmade.
# Knappar: stick, act1, act2, w, a, s, d, esc, coin
CONTROLS = {
    "menu": {
        "stick": "Välj spel",
        "act1": "Starta / välj",
        "act2": "Håll + spak upp/ned = volym",
        "esc": "Tillbaka",
    },
    "flappy": {
        "stick": "Upp = flaxa",
        "act1": "Flaxa",
        "w": "Flaxa",
        "esc": "Paus / hjälp",
    },
    "snake": {
        "stick": "Styr ormen",
        "w": "Upp",
        "a": "Vänster",
        "s": "Ned",
        "d": "Höger",
        "esc": "Paus / hjälp",
    },
    "pacman": {
        "stick": "Styr Pac-Man",
        "w": "Upp",
        "a": "Vänster",
        "s": "Ned",
        "d": "Höger",
        "esc": "Paus / hjälp",
    },
    "tetris": {
        "stick": "Vänster/höger = flytta, upp = rotera, ned = snabbare",
        "act1": "Släpp ned",
        "act2": "Rotera",
        "esc": "Paus / hjälp",
    },
}

LABELS = {
    "stick": "Spak",
    "act1": "Action 1",
    "act2": "Action 2",
    "w": "W",
    "a": "A",
    "s": "S",
    "d": "D",
    "esc": "ESC",
    "coin": "Coin",
}
ORDER = ["stick", "act1", "act2", "w", "a", "s", "d", "esc", "coin"]

# Knapparnas plats på panelen (andel av bildens bredd/höjd), som på skåpet:
# spak till vänster, Action 1/2 bredvid, romben W/A/S/D till höger, ESC + Coin uppe till höger.
BUTTON_POS = {
    "act1": (0.33, 0.66),
    "act2": (0.45, 0.66),
    "w": (0.76, 0.44),
    "a": (0.67, 0.64),
    "d": (0.85, 0.64),
    "s": (0.76, 0.84),
    "esc": (0.80, 0.16),
    "coin": (0.91, 0.16),
}
STICK_POS = (0.13, 0.62)

C_PANEL = (20, 20, 34)
C_BORDER = (90, 90, 120)
C_ON = (140, 200, 255)
C_OFF = (55, 55, 75)
C_LABEL = (255, 230, 140)
C_TEXT = (225, 225, 240)
C_DIM = (120, 120, 140)

_fonts = {}


def _font(size, bold=False):
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        f = pygame.font.SysFont("consolas", size, bold=bold)
        _fonts[key] = f
    return f


def _wrap(font, text, max_w):
    words = text.split()
    lines = []
    cur = ""
    for word in words:
        test = word if not cur else cur + " " + word
        if font.size(test)[0] <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _draw_panel(surf, box, mapping):
    pygame.draw.rect(surf, C_PANEL, box, border_radius=16)
    pygame.draw.rect(surf, C_BORDER, box, 2, border_radius=16)

    r = max(6, int(min(box.w * 0.035, box.h * 0.085)))
    tiny = _font(max(10, int(r * 0.9)), True)

    def at(pos):
        return box.x + int(box.w * pos[0]), box.y + int(box.h * pos[1])

    # spak
    sx, sy = at(STICK_POS)
    stick_on = "stick" in mapping
    pygame.draw.circle(surf, C_BORDER, (sx, sy), int(r * 1.3), 2)
    pygame.draw.line(surf, (200, 200, 210), (sx, sy), (sx, sy - int(r * 2.2)), 3)
    pygame.draw.circle(surf, C_ON if stick_on else C_OFF, (sx, sy - int(r * 2.2)), int(r * 1.1))
    lab = tiny.render("Spak", True, C_TEXT if stick_on else C_DIM)
    surf.blit(lab, lab.get_rect(midtop=(sx, sy + int(r * 1.5))))

    short = {"act1": "1", "act2": "2", "w": "W", "a": "A", "s": "S", "d": "D", "esc": "ESC", "coin": "Coin"}
    for key, pos in BUTTON_POS.items():
        cx, cy = at(pos)
        on = key in mapping
        pygame.draw.circle(surf, C_ON if on else C_OFF, (cx, cy), r)
        pygame.draw.circle(surf, (255, 255, 255) if on else C_BORDER, (cx, cy), r, 2)
        txt = short[key]
        col = (20, 20, 30) if on else C_DIM
        t = tiny.render(txt, True, col)
        if t.get_width() <= r * 2 - 4:
            surf.blit(t, t.get_rect(center=(cx, cy)))
        else:
            t = tiny.render(txt, True, C_TEXT if on else C_DIM)
            surf.blit(t, t.get_rect(midtop=(cx, cy + r + 2)))


def draw_layout(surf, rect, game_key):
    """Ritar kontrollpanelen och vad knapparna gör inom rect. Ritar inget utanför rect."""
    mapping = CONTROLS.get(game_key, {})
    rect = pygame.Rect(rect)
    if rect.w < 200 or rect.h < 160:
        return

    old_clip = surf.get_clip()
    surf.set_clip(rect)

    panel_h = int(min(rect.w * 0.45, rect.h * 0.45))
    box = pygame.Rect(rect.x, rect.y, rect.w, panel_h)
    _draw_panel(surf, box, mapping)

    size = max(14, min(22, rect.w // 26))
    lab_font = _font(size, True)
    txt_font = _font(size)
    line_h = max(lab_font.get_linesize(), txt_font.get_linesize())

    keys = [k for k in ORDER if k in mapping]
    lab_w = max((lab_font.size(LABELS[k])[0] for k in keys), default=0) + 14
    y = box.bottom + 14
    for k in keys:
        if y + line_h > rect.bottom:
            break
        surf.blit(lab_font.render(LABELS[k], True, C_LABEL), (rect.x + 4, y))
        for line in _wrap(txt_font, mapping[k], rect.w - lab_w - 8):
            if y + line_h > rect.bottom:
                break
            surf.blit(txt_font.render(line, True, C_TEXT), (rect.x + 4 + lab_w, y))
            y += line_h
        y += 4

    surf.set_clip(old_clip)


def pause(screen, game_key):
    """Pausskärm med knapphjälp. Returnerar "resume" eller "quit"."""
    clock = pygame.time.Clock()
    w, h = screen.get_size()

    bg = screen.copy()
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    shade.fill((0, 0, 0, 230))
    bg.blit(shade, (0, 0))

    title_font = _font(max(28, h // 12), True)
    hint_font = _font(max(16, h // 36), True)

    title = title_font.render("PAUS", True, (240, 240, 255))
    hint = hint_font.render("Action 1 = fortsätt      ESC = tillbaka till menyn", True, C_LABEL)

    title_rect = title.get_rect(midtop=(w // 2, int(h * 0.05)))
    hint_rect = hint.get_rect(midbottom=(w // 2, h - int(h * 0.05)))
    pw = min(w - 48, 820)
    layout_rect = pygame.Rect((w - pw) // 2, title_rect.bottom + 20, pw,
                              hint_rect.top - 20 - (title_rect.bottom + 20))

    pygame.event.clear()
    while True:
        jk.update()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.event.clear()
                    return "quit"
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    pygame.event.clear()
                    return "resume"

        screen.blit(bg, (0, 0))
        screen.blit(title, title_rect)
        draw_layout(screen, layout_rect, game_key)
        screen.blit(hint, hint_rect)
        pygame.display.flip()
        clock.tick(30)
