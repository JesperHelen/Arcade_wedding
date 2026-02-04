import os
import sys
import math
import random
import pygame
import importlib
from datetime import date
import joystick_keys as jk


# ----------------------------
# Config (Pi-friendly)
# ----------------------------
# 30 FPS är ofta "sweet spot" på äldre Pi. Höj till 45/60 om den klarar.
FPS = 30

TITLE = "Arcade Machine"
MUSIC_PATH = os.path.join("assets", "music", "music_base_1.wav")

GAME_MODULES = ["game_1", "game_2", "game_3", "game_4"]
GAME_FILES = ["Game_1.txt", "Game_2.txt", "Game_3.txt", "Game_4.txt"]
COMP_FILE = "Competition.txt"

MAX_SCORES = 10

ARCADE_FONT_PATH = os.path.join("assets", "fonts", "PressStart2P-Regular.ttf")


# ----------------------------
# Small utils / caching
# ----------------------------
def clamp(x, a, b):
    return max(a, min(b, x))


def fmt_score(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return str(n)


def base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def file_path(fname: str) -> str:
    return os.path.join(base_dir(), fname)


def load_font(size: int) -> pygame.font.Font:
    # Font creation is expensive; cache is handled externally in FontCache.
    try:
        if os.path.exists(ARCADE_FONT_PATH):
            return pygame.font.Font(ARCADE_FONT_PATH, size)
    except Exception:
        pass
    f = pygame.font.SysFont("consolas", size)
    f.set_bold(True)
    return f


class FontCache:
    def __init__(self):
        self._fonts = {}

    def get(self, size: int) -> pygame.font.Font:
        key = size
        f = self._fonts.get(key)
        if f is None:
            f = load_font(size)
            self._fonts[key] = f
        return f


class TextCache:
    """
    Cache for rendered text surfaces: (font_id, text, color) -> Surface.
    Use for static labels to avoid render cost each frame.
    """
    def __init__(self):
        self._cache = {}

    def render(self, font: pygame.font.Font, text: str, color):
        key = (id(font), text, color)
        s = self._cache.get(key)
        if s is None:
            s = font.render(text, True, color)
            self._cache[key] = s
        return s

    def clear(self):
        self._cache.clear()


FONTS = FontCache()
TEXT = TextCache()


# ----------------------------
# Music resume helper
# ----------------------------
def resume_menu_music():
    try:
        if not pygame.mixer.get_init():
            return

        pygame.mixer.music.unpause()
        if not pygame.mixer.music.get_busy():
            if os.path.exists(MUSIC_PATH):
                pygame.mixer.music.load(MUSIC_PATH)
                pygame.mixer.music.set_volume(0.35)
                pygame.mixer.music.play(-1)
    except Exception as e:
        print("Resume music error:", e)


# ----------------------------
# Helpers: scores
# ----------------------------
def _parse_scores(text: str):
    text = (text or "").strip()
    if not text:
        return []
    if text.isdigit():
        return [("AAA", int(text), "")]

    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            ini = (parts[0].upper() + "AAA")[:3]
            try:
                sc = int(parts[1])
            except Exception:
                continue
            dd = parts[2] if len(parts) >= 3 else ""
            out.append((ini, sc, dd))
        else:
            sp = line.split()
            if len(sp) >= 2:
                ini = (sp[0].upper() + "AAA")[:3]
                try:
                    sc = int(sp[1])
                except Exception:
                    continue
                out.append((ini, sc, ""))
    return out


def read_scores_file(fname: str):
    try:
        with open(file_path(fname), "r", encoding="utf-8") as f:
            scores = _parse_scores(f.read())
            scores.sort(key=lambda t: t[1], reverse=True)
            return scores[:MAX_SCORES]
    except FileNotFoundError:
        return []
    except Exception:
        return []


def add_score_to_file(fname: str, initials: str, score: int):
    initials = (initials.upper() + "AAA")[:3]
    score = int(score)
    d = date.today().isoformat()

    scores = read_scores_file(fname)
    scores.append((initials, score, d))
    scores.sort(key=lambda t: t[1], reverse=True)
    scores = scores[:MAX_SCORES]

    with open(file_path(fname), "w", encoding="utf-8") as f:
        for ini, sc, dd in scores:
            f.write(f"{ini},{int(sc)},{dd}\n")


# ----------------------------
# Helpers: run games
# ----------------------------
def import_game(module_name: str):
    candidates = [module_name, module_name.lower(), module_name.upper(), module_name.capitalize()]
    if module_name.startswith("game_"):
        idx = module_name.split("_")[-1]
        candidates.append(f"Game_{idx}")

    last_err = None
    for name in candidates:
        try:
            mod = importlib.import_module(name)
            importlib.reload(mod)
            return mod
        except Exception as e:
            last_err = e
    raise ImportError(f"Could not import {module_name}. Last error: {last_err}")


def run_game_by_index(screen, index: int):
    only_game4 = (index == 3)  # game_4

    if only_game4:
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                pygame.mixer.music.pause()
        except Exception:
            pass

    mod = import_game(GAME_MODULES[index])
    result = mod.run(screen)

    if only_game4:
        resume_menu_music()

    if isinstance(result, dict):
        return {
            "result": result.get("result", "quit"),
            "score": int(result.get("score", 0)),
        }
    return {"result": "quit", "score": 0}


# ----------------------------
# Visual FX (optimized)
# ----------------------------
class ScanlinesCache:
    def __init__(self):
        self._cache = {}  # (w,h,strength,gap)->Surface

    def get(self, w, h, strength=32, gap=3):
        key = (w, h, strength, gap)
        s = self._cache.get(key)
        if s is None:
            s = pygame.Surface((w, h), pygame.SRCALPHA)
            alpha = clamp(strength, 0, 255)
            # Draw horizontal lines once.
            for y in range(0, h, gap):
                pygame.draw.line(s, (0, 0, 0, alpha), (0, y), (w, y))
            self._cache[key] = s
        return s

    def clear(self):
        self._cache.clear()


SCANLINES = ScanlinesCache()


class GlowCache:
    """
    Cache a glow overlay surface for common rect sizes (icons/keys/boxes).
    This avoids per-frame inflate loops for glow_rect calls.
    """
    def __init__(self):
        self._cache = {}  # (w,h,color,glow,corner)->Surface

    def get(self, w, h, base_color, glow=12, corner=18):
        key = (w, h, base_color, glow, corner)
        s = self._cache.get(key)
        if s is None:
            # Overlay surface slightly bigger than base
            pad = glow * 2
            s = pygame.Surface((w + pad, h + pad), pygame.SRCALPHA)
            # Draw glow as expanding rounded rects into overlay surface
            rect = pygame.Rect(glow, glow, w, h)
            for i in range(glow, 0, -1):
                a = int(14 * (i / glow))  # same-ish as original
                r = rect.inflate(i * 2, i * 2)
                pygame.draw.rect(s, (*base_color, a), r, border_radius=corner)
            self._cache[key] = s
        return s

    def clear(self):
        self._cache.clear()


GLOW = GlowCache()


def draw_scanlines(surf, strength=32, gap=3):
    w, h = surf.get_size()
    overlay = SCANLINES.get(w, h, strength, gap)
    surf.blit(overlay, (0, 0))


def glow_rect_cached(surf, rect, base_color, glow=12, corner=18):
    # Blit cached glow overlay centered on rect
    overlay = GLOW.get(rect.w, rect.h, base_color, glow=glow, corner=corner)
    pad = glow
    surf.blit(overlay, (rect.x - pad, rect.y - pad))


class Starfield:
    """
    Optimized starfield:
    - draw small filled rects instead of circle()
    - stars count tuned a bit lower by default
    """
    def __init__(self, w, h, count=180):
        self.w = w
        self.h = h
        self.stars = []
        self.set_count(count)

    def set_count(self, count: int):
        self.stars.clear()
        for _ in range(count):
            x = random.randint(0, self.w)
            y = random.randint(0, self.h)
            z = random.random()
            speed = 50 + 180 * z
            self.stars.append([x, y, z, speed])

    def resize(self, w, h):
        self.w = w
        self.h = h
        for s in self.stars:
            s[0] = clamp(s[0], 0, w)
            s[1] = clamp(s[1], 0, h)

    def update(self, dt):
        for s in self.stars:
            s[1] += s[3] * dt
            if s[1] > self.h + 10:
                s[0] = random.randint(0, self.w)
                s[1] = -10
                s[2] = random.random()
                s[3] = 50 + 180 * s[2]

    def draw(self, surf):
        # Using fill with tiny rects is often faster on Pi than draw.circle.
        for x, y, z, _spd in self.stars:
            if z < 0.35:
                r = 1
            elif z < 0.75:
                r = 2
            else:
                r = 3
            c = 120 + int(120 * z)
            surf.fill((c, c, c), (int(x), int(y), r, r))


def blit_rotated_text(surf, font, text, color, center, angle_deg, shadow=True):
    # This is not used every frame except leader ribbon; keep as-is but avoid extra work.
    base = font.render(text, True, color)
    if shadow:
        sh = font.render(text, True, (20, 20, 30))
        sh_r = pygame.transform.rotate(sh, angle_deg)
        sh_rect = sh_r.get_rect(center=(center[0] + 2, center[1] + 2))
        surf.blit(sh_r, sh_rect)
    rot = pygame.transform.rotate(base, angle_deg)
    rect = rot.get_rect(center=center)
    surf.blit(rot, rect)


# ----------------------------
# Icons (mostly ok; created once)
# ----------------------------
def make_icon(kind: str, size: int) -> pygame.Surface:
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2

    pygame.draw.rect(s, (255, 255, 255, 40), (0, 0, size, size), border_radius=16)
    pygame.draw.rect(s, (255, 255, 255, 70), (2, 2, size - 4, size - 4), 2, border_radius=16)

    if kind == "competition":
        pygame.draw.rect(s, (255, 230, 140), pygame.Rect(cx - 18, cy - 10, 36, 22), border_radius=6)
        pygame.draw.rect(s, (255, 230, 140), pygame.Rect(cx - 6, cy + 12, 12, 16), border_radius=4)
        pygame.draw.rect(s, (255, 230, 140), pygame.Rect(cx - 18, cy + 26, 36, 8), border_radius=4)

    elif kind == "scores":
        for i, w in enumerate([44, 36, 28, 40]):
            y = 24 + i * 14
            pygame.draw.rect(s, (220, 220, 255), pygame.Rect(cx - w // 2, y, w, 8), border_radius=4)

    elif kind == "Hoppande fågeln":
        def bird_icon_path():
            candidates = [
                os.path.join(base_dir(), "Assets", "Flappy-bird", "bird_base.png"),
                os.path.join(base_dir(), "assets", "Flappy-bird", "bird_base.png"),
            ]
            for p in candidates:
                if os.path.exists(p):
                    return p
            return candidates[0]

        try:
            bird = pygame.image.load(bird_icon_path()).convert_alpha()
            target_h = int(size * 0.36)
            scale = target_h / bird.get_height()
            bird = pygame.transform.smoothscale(bird, (int(bird.get_width() * scale), target_h))
            bird = pygame.transform.rotate(bird, -10)
            rect = bird.get_rect(center=(cx, cy))
            s.blit(bird, rect)
        except Exception:
            pygame.draw.circle(s, (255, 230, 140), (cx, cy), size // 3)

    elif kind == "Snoken":
        body = [(cx - 18, cy + 10), (cx - 6, cy + 10), (cx + 6, cy + 10), (cx + 6, cy - 2), (cx + 18, cy - 2)]
        for (x, y) in body:
            pygame.draw.rect(s, (140, 200, 255), pygame.Rect(x, y, 12, 12), border_radius=4)
        pygame.draw.rect(s, (180, 220, 255), pygame.Rect(cx + 18, cy - 2, 12, 12), border_radius=4)
        pygame.draw.circle(s, (255, 170, 170), (cx - 14, cy - 6), 7)
        pygame.draw.circle(s, (255, 255, 255), (cx - 16, cy - 8), 2)

    elif kind == "Pac-Mannen":
        pac = (255, 230, 140)
        pcx, pcy = cx - 6, cy
        r = 18
        points = [(pcx, pcy)]
        mouth_angle = math.radians(40)
        start_angle = mouth_angle
        end_angle = 2 * math.pi - mouth_angle
        steps = 40
        for i in range(steps + 1):
            a = start_angle + (end_angle - start_angle) * i / steps
            x = pcx + math.cos(a) * r
            y = pcy + math.sin(a) * r
            points.append((x, y))
        pygame.draw.polygon(s, pac, points)
        pygame.draw.circle(s, (70, 70, 90), (pcx - 5, pcy - 6), 2)
        pygame.draw.circle(s, (245, 245, 255), (cx + 22, cy), 4)

    elif kind == "Muraren":
        col = (220, 180, 255)
        blocks = [(cx - 18, cy - 10), (cx - 6, cy - 10), (cx + 6, cy - 10), (cx - 6, cy + 2)]
        for x, y in blocks:
            rct = pygame.Rect(x, y, 12, 12)
            pygame.draw.rect(s, col, rct, border_radius=3)
            pygame.draw.rect(s, (255, 255, 255), rct, 1, border_radius=3)

    else:
        f = FONTS.get(22)
        txt = f.render(kind, True, (240, 240, 255))
        s.blit(txt, txt.get_rect(center=(cx, cy)))

    return s


# ----------------------------
# Initials keyboard
# ----------------------------
class InitialsKeyboard:
    def __init__(self, screen, title: str):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.starfield = Starfield(self.w, self.h, count=140)

        self.title_font = FONTS.get(26)
        self.big_font = FONTS.get(34)
        self.small_font = FONTS.get(14)

        self.title = title
        self.initials = ["A", "A", "A"]
        self.pos = 0

        self.keys = [
            ["Left", "Right"],
            list("ABCDE"),
            list("FGHIJ"),
            list("KLMNO"),
            list("PQRST"),
            list("UVWXY"),
            ["Z", "Å", "Ä", "Ö", "OK"],
        ]

        self.kx = 0
        self.ky = 0

        self.TEXT_NORMAL = (205, 205, 220)
        self.TEXT_SELECTED = (230, 230, 245)
        self.TEXT_TITLE = (230, 230, 245)

        self.KEY_BG = (255, 255, 255, 10)
        self.KEY_BG_SEL = (120, 180, 255, 90)
        self.BOX_BG = (255, 255, 255, 10)
        self.BOX_BG_SEL = (120, 180, 255, 90)

    def resize(self):
        self.w, self.h = self.screen.get_size()
        self.starfield.resize(self.w, self.h)
        # Clear scanline cache if you like; not necessary.

    def _row_len(self, row_i: int) -> int:
        return len(self.keys[row_i])

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return (None, None)

        if event.key == pygame.K_ESCAPE:
            return ("cancel", None)

        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.kx = max(0, self.kx - 1)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.kx = min(self._row_len(self.ky) - 1, self.kx + 1)
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.ky = max(0, self.ky - 1)
            self.kx = min(self.kx, self._row_len(self.ky) - 1)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.ky = min(len(self.keys) - 1, self.ky + 1)
            self.kx = min(self.kx, self._row_len(self.ky) - 1)

        elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
            key = self.keys[self.ky][self.kx]

            if key == "OK":
                return ("done", "".join(self.initials))

            if key == "Left":
                self.pos = max(0, self.pos - 1)
                return (None, None)

            if key == "Right":
                self.pos = min(2, self.pos + 1)
                return (None, None)

            if key in "ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ":
                self.initials[self.pos] = key
                if self.pos < 2:
                    self.pos += 1
                else:
                    self.ky = 6
                    self.kx = 4
                return (None, None)

        return (None, None)

    def update(self, dt):
        self.starfield.update(dt)

    def draw(self):
        self.screen.fill((10, 10, 18))
        self.starfield.draw(self.screen)

        t = TEXT.render(self.title_font, self.title, self.TEXT_TITLE)
        self.screen.blit(t, t.get_rect(center=(self.w // 2, int(self.h * 0.16))))

        base_y = int(self.h * 0.30)
        gap = 70
        start_x = self.w // 2 - gap

        for i in range(3):
            x = start_x + i * gap
            rect = pygame.Rect(x - 28, base_y - 40, 56, 80)

            if i == self.pos:
                glow_rect_cached(self.screen, rect, (120, 180, 255), glow=10, corner=14)
                pygame.draw.rect(self.screen, self.BOX_BG_SEL, rect, border_radius=14)
                col = self.TEXT_SELECTED
            else:
                pygame.draw.rect(self.screen, self.BOX_BG, rect, border_radius=14)
                col = self.TEXT_NORMAL

            ch = TEXT.render(self.big_font, self.initials[i], col)
            self.screen.blit(ch, ch.get_rect(center=rect.center))

        key_w = 90
        key_h = 56
        gap_x = 14
        gap_y = 12
        start_ky = int(self.h * 0.44)

        def row_total_width(row):
            widths = []
            for key in row:
                widths.append(key_w * 2 + gap_x if key == "OK" else key_w)
            return sum(widths) + gap_x * (len(widths) - 1)

        for row_i, row in enumerate(self.keys):
            row_w = row_total_width(row)
            start_kx = (self.w - row_w) // 2
            y = start_ky + row_i * (key_h + gap_y)

            x = start_kx
            for col_i, key in enumerate(row):
                w = key_w * 2 + gap_x if key == "OK" else key_w
                rect = pygame.Rect(x, y, w, key_h)
                selected = (row_i == self.ky and col_i == self.kx)

                if selected:
                    glow_rect_cached(self.screen, rect, (120, 180, 255), glow=10, corner=14)
                    pygame.draw.rect(self.screen, self.KEY_BG_SEL, rect, border_radius=14)
                    col = self.TEXT_SELECTED
                else:
                    pygame.draw.rect(self.screen, self.KEY_BG, rect, border_radius=14)
                    col = self.TEXT_NORMAL

                label = TEXT.render(self.title_font, key, col)
                self.screen.blit(label, label.get_rect(center=rect.center))

                x += w + gap_x

        hint = TEXT.render(self.small_font, "Pilar = flytta • Space = välj • ESC = avbryt", (150, 150, 170))
        self.screen.blit(hint, hint.get_rect(center=(self.w // 2, int(self.h * 0.92))))
        draw_scanlines(self.screen, strength=30, gap=3)


# ----------------------------
# Score Screen
# ----------------------------
class ScoreScreen:
    def __init__(self, screen, title: str, initials: str, score: int):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.starfield = Starfield(self.w, self.h, count=160)

        self.arc_big = FONTS.get(44)
        self.arc_mid = FONTS.get(24)
        self.arc_small = FONTS.get(14)

        self.title = title
        self.initials = (initials.upper() + "AAA")[:3]
        self.score = int(score)

    def resize(self):
        self.w, self.h = self.screen.get_size()
        self.starfield.resize(self.w, self.h)

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return (None, None)
        if event.key == pygame.K_ESCAPE:
            return ("back", None)
        if event.key in (pygame.K_SPACE, pygame.K_RETURN):
            return ("back", None)
        return (None, None)

    def update(self, dt):
        self.starfield.update(dt)

    def draw(self):
        self.screen.fill((10, 10, 18))
        self.starfield.draw(self.screen)

        t = TEXT.render(self.arc_mid, self.title, (230, 230, 245))
        self.screen.blit(t, t.get_rect(center=(self.w // 2, int(self.h * 0.18))))

        s = TEXT.render(self.arc_big, "SCORE", (255, 230, 140))
        self.screen.blit(s, s.get_rect(center=(self.w // 2, int(self.h * 0.34))))

        sc = TEXT.render(self.arc_big, fmt_score(self.score), (235, 235, 255))
        self.screen.blit(sc, sc.get_rect(center=(self.w // 2, int(self.h * 0.46))))

        ini = TEXT.render(self.arc_mid, self.initials, (140, 200, 255))
        self.screen.blit(ini, ini.get_rect(center=(self.w // 2, int(self.h * 0.60))))

        hint = TEXT.render(self.arc_small, "Enter/Space = tillbaka   ESC = tillbaka", (160, 160, 190))
        self.screen.blit(hint, hint.get_rect(center=(self.w // 2, int(self.h * 0.90))))

        draw_scanlines(self.screen, strength=32, gap=3)


# ----------------------------
# Main Menu + Highscore
# ----------------------------
class MainMenu:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()

        # Star count tuned down a bit for Pi
        self.starfield = Starfield(self.w, self.h, count=180)

        self.ribbon_font = FONTS.get(20)
        self.title_font = FONTS.get(136)
        self.item_font = FONTS.get(16)

        self.cols = 3
        self.items = [
            ("competition", None, "Competition", make_icon("competition", 96)),
            ("game", 0, "Hoppande fågeln", make_icon("Hoppande fågeln", 96)),
            ("game", 1, "Snoken", make_icon("Snoken", 96)),
            ("game", 2, "Pac-Mannen", make_icon("Pac-Mannen", 96)),
            ("game", 3, "Muraren", make_icon("Muraren", 96)),
            ("scores", None, "Highscore", make_icon("scores", 96)),
        ]
        self.selected = 0
        self.pulse_t = 0.0

        # Prebuild icon card backgrounds once (HUGE win)
        icon = 96
        self.card_bg = pygame.Surface((icon, icon), pygame.SRCALPHA)
        self.card_bg_sel = pygame.Surface((icon, icon), pygame.SRCALPHA)

        # Ljus, tydlig bakgrundsplatta
        pygame.draw.rect(
            self.card_bg_sel,
            (180, 210, 255, 200),   # blåvit, hög alpha
            self.card_bg_sel.get_rect(),
            border_radius=18
        )

        pygame.draw.rect(self.card_bg_sel, (255, 255, 255, 0), self.card_bg_sel.get_rect(), border_radius=18)

        self._cached_title = TEXT.render(self.title_font, TITLE, (235, 235, 255))
        self._cached_subtitle = TEXT.render(self.item_font,
                                            "",
                                            (180, 180, 210))

    def resize(self):
        self.w, self.h = self.screen.get_size()
        self.starfield.resize(self.w, self.h)
        # text depends on resolution only for centering, surfaces are fine

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return (None, None)

        if event.key == pygame.K_ESCAPE:
            return (None, None)

        n = len(self.items)

        if event.key in (pygame.K_LEFT, pygame.K_a):
            self.selected = (self.selected - 1) % n
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.selected = (self.selected + 1) % n
        elif event.key in (pygame.K_UP, pygame.K_w):
            self.selected = (self.selected - self.cols) % n
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.selected = (self.selected + self.cols) % n
        elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
            return ("activate", self.items[self.selected])

        return (None, None)

    def update(self, dt):
        self.pulse_t += dt
        self.starfield.update(dt)

    def draw(self):
        self.screen.fill((10, 10, 18))
        self.starfield.draw(self.screen)

        self.screen.blit(self._cached_title, self._cached_title.get_rect(center=(self.w // 2, int(self.h * 0.16))))
        self.screen.blit(self._cached_subtitle, self._cached_subtitle.get_rect(center=(self.w // 2, int(self.h * 0.24))))

        icon = 96
        gap_x = 28
        gap_y = 56
        cols = self.cols
        total_w = cols * icon + (cols - 1) * gap_x
        start_x = (self.w - total_w) // 2
        start_y = int(self.h * 0.44)

        for i, item in enumerate(self.items):
            cx = i % cols
            cy = i // cols
            x = start_x + cx * (icon + gap_x)
            y = start_y + cy * (icon + gap_y)
            r = pygame.Rect(x, y, icon, icon)

            is_sel = (i == self.selected)
            # === TYDLIG RAM RUNT VALD KNAPP ===
            if is_sel:
                # Ytterram – extremt tydlig
                outer = r.inflate(10, 10)
                pygame.draw.rect(
                    self.screen,
                    (255, 255, 255),   # helt vit, ingen alpha
                    outer,
                    5,
                    border_radius=22
                )



            else:
                self.card_bg.set_alpha(255)
                self.screen.blit(self.card_bg, r.topleft)

            kind, idx, label, icon_surf = item
            self.screen.blit(icon_surf, icon_surf.get_rect(center=r.center))

            lab_col = (230, 230, 240) if is_sel else (170, 170, 190)
            lab = TEXT.render(self.item_font, label, lab_col)
            self.screen.blit(lab, lab.get_rect(center=(r.centerx, r.bottom + 20)))

        draw_scanlines(self.screen, strength=32, gap=3)

        # Leader ribbon (reads file each frame in original; keep functionality but make it cheaper)
        # We'll read once per second (still "same feature", but not wasting IO).
        leader = getattr(self, "_leader_cache", None)
        leader_t = getattr(self, "_leader_cache_t", 999.0)
        if leader is None or leader_t > 1.0:
            leader_scores = read_scores_file(COMP_FILE)
            if leader_scores:
                ini, sc, _dd = leader_scores[0]
            else:
                ini, sc = "---", 0
            self._leader_cache = (ini, sc)
            self._leader_cache_t = 0.0
        else:
            self._leader_cache_t = leader_t + (1.0 / FPS)

        ini, sc = self._leader_cache
        label = f"LEADER  {ini}  SCORE  {fmt_score(sc)}"
        blit_rotated_text(
            self.screen,
            self.ribbon_font,
            label,
            (255, 230, 140),
            center=(int(self.w * 0.58), int(self.h * 0.40)),
            angle_deg=-28,
            shadow=True
        )


class HighscoreScene:
    def __init__(self, screen):
        self.screen = screen
        self.w, self.h = screen.get_size()
        self.starfield = Starfield(self.w, self.h, count=160)
        self.title_font = FONTS.get(26)
        self.item_font = FONTS.get(16)

        self.boards = [
            (COMP_FILE, "Competition"),
            (GAME_FILES[0], "Hoppande fågeln"),
            (GAME_FILES[1], "Snoken"),
            (GAME_FILES[2], "Pac-Mannen"),
            (GAME_FILES[3], "Muraren"),
        ]
        self.idx = 0

        # Cached hint
        self._hint = TEXT.render(self.item_font, "←/→ byt lista • ESC tillbaka", (150, 150, 170))

    def resize(self):
        self.w, self.h = self.screen.get_size()
        self.starfield.resize(self.w, self.h)

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return (None, None)

        if event.key == pygame.K_ESCAPE:
            return ("back", None)

        if event.key == pygame.K_LEFT:
            self.idx = (self.idx - 1) % len(self.boards)
        elif event.key == pygame.K_RIGHT:
            self.idx = (self.idx + 1) % len(self.boards)

        return (None, None)

    def update(self, dt):
        self.starfield.update(dt)

    def draw(self):
        self.screen.fill((10, 10, 18))
        self.starfield.draw(self.screen)

        fname, label = self.boards[self.idx]
        title = TEXT.render(self.title_font, f"HIGHSCORE — {label}", (235, 235, 255))
        self.screen.blit(title, title.get_rect(center=(self.w // 2, int(self.h * 0.18))))

        scores = read_scores_file(fname)
        if not scores:
            scores = [("---", 0, "")]

        y = int(self.h * 0.30)
        for i, entry in enumerate(scores, start=1):
            ini = entry[0]
            sc = entry[1]
            dd = entry[2] if len(entry) >= 3 else ""
            date_txt = dd if dd else "---- -- --"
            line = TEXT.render(self.item_font, f"{i:>2}.  {ini}   {fmt_score(sc)}   {date_txt}", (220, 220, 240))
            self.screen.blit(line, line.get_rect(center=(self.w // 2, y)))
            y += 34

        self.screen.blit(self._hint, self._hint.get_rect(center=(self.w // 2, int(self.h * 0.92))))
        draw_scanlines(self.screen, strength=30, gap=3)


# ----------------------------
# Competition runner
# ----------------------------
def run_competition(screen):
    total = 1
    for i in range(4):
        res = run_game_by_index(screen, i)
        if res["result"] == "quit":
            return {"result": "quit", "score": total}
        total *= int(res["score"])
    return {"result": "done", "score": total}


# ----------------------------
# Main state machine
# ----------------------------
def main():
    pygame.init()
    pygame.display.set_caption(TITLE)

    # Flags that can help on some setups (esp. Desktop)
    flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
    screen = pygame.display.set_mode((0, 0), flags)
    clock = pygame.time.Clock()

    menu = MainMenu(screen)
    highs = HighscoreScene(screen)

    # ---- music (loop forever) ----
    try:
        pygame.mixer.init()
        if os.path.exists(MUSIC_PATH):
            pygame.mixer.music.load(MUSIC_PATH)
            pygame.mixer.music.set_volume(0.35)
            pygame.mixer.music.play(-1)
    except Exception as e:
        print("Music error:", e)

    state = "menu"  # menu | highs | initials | score
    current = menu

    pending = None
    initials_ui = None
    score_ui = None

    while True:
        jk.update()
        dt = clock.tick(FPS) / 1000.0

        # --- SAFE QUIT: ESC + Enter + S samtidigt ---
        keys = pygame.key.get_pressed()
        if keys[pygame.K_ESCAPE] and (keys[pygame.K_RETURN] or keys[pygame.K_KP_ENTER]) and keys[pygame.K_s]:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            pygame.quit()
            sys.exit()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if state == "initials":
                act, payload = initials_ui.handle_event(event)
                if act == "cancel":
                    state = "menu"
                    current = menu
                    pending = None
                    initials_ui = None
                elif act == "done":
                    initials = payload

                    if pending and pending[0] == "single":
                        _, idx, label = pending
                        pending = None
                        initials_ui = None

                        res = run_game_by_index(screen, idx)
                        if res["result"] == "quit":
                            state = "menu"
                            current = menu
                        else:
                            sc = int(res["score"])
                            if sc > 0:
                                add_score_to_file(GAME_FILES[idx], initials, sc)
                            score_ui = ScoreScreen(screen, label, initials, sc)
                            state = "score"
                            current = score_ui

                    elif pending and pending[0] == "competition":
                        _, _none, label = pending
                        pending = None
                        initials_ui = None

                        res = run_competition(screen)
                        if res["result"] == "quit":
                            state = "menu"
                            current = menu
                        else:
                            sc = int(res["score"])
                            if sc > 0:
                                add_score_to_file(COMP_FILE, initials, sc)
                            score_ui = ScoreScreen(screen, label, initials, sc)
                            state = "score"
                            current = score_ui

                continue

            if state == "score":
                act, _payload = current.handle_event(event)
                if act == "back":
                    state = "menu"
                    current = menu
                    score_ui = None
                continue

            act, payload = current.handle_event(event)

            if act == "quit":
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                pygame.quit()
                sys.exit()

            if act == "back":
                state = "menu"
                current = menu

            if act == "activate":
                kind, idx, label, _icon = payload

                if kind == "scores":
                    state = "highs"
                    current = highs
                    continue

                if kind == "game":
                    state = "initials"
                    pending = ("single", idx, label)
                    initials_ui = InitialsKeyboard(screen, f"ENTER INITIALS ({label})")
                    continue

                if kind == "competition":
                    state = "initials"
                    pending = ("competition", None, "Competition")
                    initials_ui = InitialsKeyboard(screen, "ENTER INITIALS (COMPETITION)")
                    continue

        # Update & draw
        if state == "initials":
            initials_ui.update(dt)
            initials_ui.draw()
        else:
            current.update(dt)
            current.draw()

        pygame.display.flip()


if __name__ == "__main__":
    main()
