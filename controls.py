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

# Sätt till False för att dölja felsökningsraden ("Joystick-knapp: 6") när en knapp hålls in
SHOW_RAW_BUTTON_NUMBERS = True

# Knapparnas plats på panelen (andel av bildens bredd/höjd), som på skåpet:
# spak till vänster, Action 1/2 bredvid, romben W/A/S/D till höger, Coin + ESC uppe till höger.
BUTTON_POS = {
    "act1": (0.33, 0.66),
    "act2": (0.45, 0.66),
    "w": (0.76, 0.44),
    "a": (0.67, 0.64),
    "d": (0.85, 0.64),
    "s": (0.76, 0.84),
    "coin": (0.80, 0.16),
    "esc": (0.91, 0.16),
}
STICK_POS = (0.13, 0.62)

C_LINE = (110, 110, 140)
C_ON = (140, 200, 255)
C_OFF = (70, 70, 92)
C_PRESS = (255, 230, 140)
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


def _pressed_state():
    """Vad som hålls in just nu, från joysticken eller tangentbordet."""
    js = jk.pressed()
    keys = pygame.key.get_pressed()

    def k(*codes):
        return any(keys[c] for c in codes)

    return {
        "act1": js.get("enter") or k(pygame.K_RETURN, pygame.K_KP_ENTER),
        "act2": js.get("act2") or k(pygame.K_q),
        "w": js.get("w") or k(pygame.K_w),
        "a": js.get("a") or k(pygame.K_a),
        "s": js.get("s") or k(pygame.K_s),
        "d": js.get("d") or k(pygame.K_d),
        "esc": js.get("esc") or k(pygame.K_ESCAPE),
        "coin": js.get("coin", False),
        "up": js.get("up") or k(pygame.K_UP),
        "down": js.get("down") or k(pygame.K_DOWN),
        "left": js.get("left") or k(pygame.K_LEFT),
        "right": js.get("right") or k(pygame.K_RIGHT),
    }


def _draw_panel(surf, box, mapping, pressed, pass_name):
    """pass_name "base" ritar allt som inte hålls in, "pressed" ritar bara det som hålls in."""
    want_pressed = (pass_name == "pressed")
    r = max(6, int(min(box.w * 0.035, box.h * 0.085)))
    tiny = _font(max(10, int(r * 0.9)), True)

    def at(pos):
        return box.x + int(box.w * pos[0]), box.y + int(box.h * pos[1])

    # spak: kulan lutar åt hållet som trycks
    sx, sy = at(STICK_POS)
    dx = (1 if pressed["right"] else 0) - (1 if pressed["left"] else 0)
    dy = (1 if pressed["down"] else 0) - (1 if pressed["up"] else 0)
    stick_pressed = bool(dx or dy)
    if stick_pressed == want_pressed:
        stick_on = "stick" in mapping
        if stick_pressed:
            knob_col, line_col, txt_col = C_PRESS, (255, 255, 255), C_PRESS
        else:
            knob_col = C_ON if stick_on else C_OFF
            line_col = C_LINE
            txt_col = C_TEXT if stick_on else C_DIM
        lean = int(r * 0.9)
        kx = sx + dx * lean
        ky = sy - int(r * 2.2) + dy * lean
        pygame.draw.circle(surf, line_col, (sx, sy), int(r * 1.3), 2)
        pygame.draw.line(surf, line_col, (sx, sy), (kx, ky), 3)
        pygame.draw.circle(surf, knob_col, (kx, ky), int(r * 1.1))
        lab = tiny.render("Spak", True, txt_col)
        surf.blit(lab, lab.get_rect(midtop=(sx, sy + int(r * 1.5))))

    short = {"act1": "1", "act2": "2", "w": "W", "a": "A", "s": "S", "d": "D", "esc": "ESC", "coin": "Coin"}
    for key, pos in BUTTON_POS.items():
        if pressed[key] != want_pressed:
            continue
        cx, cy = at(pos)
        on = key in mapping
        if want_pressed:
            fill, edge, txt_in, txt_out = C_PRESS, (255, 255, 255), (20, 20, 30), C_PRESS
        elif on:
            fill, edge, txt_in, txt_out = C_ON, (255, 255, 255), (20, 20, 30), C_TEXT
        else:
            fill, edge, txt_in, txt_out = None, C_OFF, C_DIM, C_DIM
        if fill is not None:
            pygame.draw.circle(surf, fill, (cx, cy), r)
        pygame.draw.circle(surf, edge, (cx, cy), r, 2)
        t = tiny.render(short[key], True, txt_in)
        if t.get_width() <= r * 2 - 4:
            surf.blit(t, t.get_rect(center=(cx, cy)))
        else:
            t = tiny.render(short[key], True, txt_out)
            surf.blit(t, t.get_rect(midtop=(cx, cy + r + 2)))


def _draw_list(surf, rect, mapping, center_v):
    """Textlista "Action 1  Starta / välj". Returnerar y under sista raden."""
    size = max(14, min(22, rect.w // 26))
    lab_font = _font(size, True)
    txt_font = _font(size)
    line_h = max(lab_font.get_linesize(), txt_font.get_linesize())

    keys = [k for k in ORDER if k in mapping]
    lab_w = max((lab_font.size(LABELS[k])[0] for k in keys), default=0) + 14
    rows = []
    for k in keys:
        for i, line in enumerate(_wrap(txt_font, mapping[k], rect.w - lab_w - 8)):
            rows.append((LABELS[k] if i == 0 else "", line))

    total = len(rows) * line_h
    y = rect.y + max(0, (rect.h - total) // 2) if center_v else rect.y
    for label, line in rows:
        if y + line_h > rect.bottom:
            break
        if label:
            surf.blit(lab_font.render(label, True, C_LABEL), (rect.x + 4, y))
        surf.blit(txt_font.render(line, True, C_TEXT), (rect.x + 4 + lab_w, y))
        y += line_h
    return y


def draw_layout(surf, rect, game_key, alpha=255):
    """
    Ritar kontrollpanelen (bara knapparna, ingen ram/bakgrund) och vad knapparna gör inom rect.
    alpha < 255 gör panelen genomskinlig. Knappar som hålls in lyser alltid med full styrka.
    Bred rect: knappar till vänster, text till höger. Annars knappar överst, text under.
    """
    mapping = CONTROLS.get(game_key, {})
    rect = pygame.Rect(rect)
    if rect.w < 200 or rect.h < 80:
        return

    pressed = _pressed_state()
    layer = pygame.Surface(rect.size, pygame.SRCALPHA)
    local = layer.get_rect()

    if rect.w > rect.h * 2.5:
        panel_w = min(int(local.h * 2.2), local.w // 2)
        box = pygame.Rect(0, 0, panel_w, local.h)
        list_rect = pygame.Rect(panel_w + 20, 0, local.w - panel_w - 20, local.h)
        center_v = True
    else:
        panel_h = int(min(local.w * 0.45, local.h * 0.45))
        box = pygame.Rect(0, 0, local.w, panel_h)
        list_rect = pygame.Rect(0, panel_h + 14, local.w, local.h - panel_h - 14)
        center_v = False

    _draw_panel(layer, box, mapping, pressed, "base")
    list_end = _draw_list(layer, list_rect, mapping, center_v)

    if alpha < 255:
        layer.set_alpha(alpha)
    surf.blit(layer, rect.topleft)

    _draw_panel(surf, box.move(rect.topleft), mapping, pressed, "pressed")

    if SHOW_RAW_BUTTON_NUMBERS:
        nums = jk.raw_buttons()
        if nums:
            f = _font(max(12, min(18, rect.w // 34)), True)
            t = f.render("Joystick-knapp: " + ", ".join(str(n) for n in nums), True, C_PRESS)
            y = min(rect.y + list_end + 4, rect.bottom - t.get_height())
            surf.blit(t, (rect.x + list_rect.x + 4, y))


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
