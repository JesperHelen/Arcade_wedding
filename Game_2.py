import os
import glob
import math
import random
import pygame
import joystick_keys as jk
import controls
from typing import Set, Tuple

def run(screen):
    clock = pygame.time.Clock()
    SERIF = "georgia,dejavuserif,liberationserif,serif"
    serif_big = pygame.font.SysFont(SERIF, 44, bold=True)
    serif_mid = pygame.font.SysFont(SERIF, 22)
    serif_tiny = pygame.font.SysFont(SERIF, 15, bold=True)

    # ---- Settings ----
    CELL = 30
    START_LEN = 5

    # Spawn safety margin (i celler) från alla kanter
    SAFE_MARGIN = 3

    # speed ramp
    BASE_TPS = 10.0
    TPS_RAMP = 0.20
    MAX_TPS = 28.0
    JITTER = 0.12  # +-12% tick interval jitter

    # Powerups
    POWERUPS_LOCK_SECONDS = 3.0  # inga bonusar första sek

    P_RAGE = 0.10     # spawn-chans per nytt main-apple
    P_SLOWMO = 0.20

    POWERUP_LIFETIME = 10.0  # ligger kvar på kartan i 10s

    # Active effect durations
    RAGE_DURATION = 10.0
    RAGE_SPEED_MULT = 1.20
    RAGE_EVERY_N_TICKS = 10
    RAGE_MAX_EXTRA_APPLES = 6  # cap så det inte blir för mycket

    SLOWMO_DURATION = 5.0
    SLOWMO_SPEED_MULT = 0.40

    # ---- Assets (Assets/Snake) ----
    def base_dir():
        return os.path.dirname(os.path.abspath(__file__))

    def snake_dir():
        for d in (os.path.join(base_dir(), "Assets", "Snake"), os.path.join(base_dir(), "assets", "snake")):
            if os.path.isdir(d):
                return d
        return os.path.join(base_dir(), "Assets", "Snake")

    def load_img_safe(name):
        try:
            p = os.path.join(snake_dir(), name)
            if os.path.exists(p):
                return pygame.image.load(p).convert_alpha()
        except Exception:
            pass
        return None

    def load_sounds(pattern):
        # Röster: eat_1.mp3, eat_2.mp3 ... (wav/ogg funkar också)
        out = []
        if not pygame.mixer.get_init():
            return out
        for ext in ("mp3", "ogg", "wav"):
            for p in sorted(glob.glob(os.path.join(snake_dir(), f"{pattern}.{ext}"))):
                try:
                    out.append(pygame.mixer.Sound(p))
                except Exception:
                    pass
        return out

    snd_eat = load_sounds("eat_*")

    def play(sounds):
        if sounds:
            try:
                random.choice(sounds).play()
            except Exception:
                pass

    # Huvudet: bilden har hjässan åt höger, alltså "tittar" den åt höger.
    # Uppåt och nedåt används samma upprätta ansikte (annars blir det upp och ned när ormen åker nedåt).
    head_imgs = None
    _head = load_img_safe("head.png")
    if _head is not None:
        target_h = int(CELL * 1.6)
        target_w = max(1, int(_head.get_width() * target_h / _head.get_height()))
        right = pygame.transform.smoothscale(_head, (target_w, target_h))
        head_imgs = {
            (1, 0): right,
            (-1, 0): pygame.transform.flip(right, True, False),
            (0, -1): pygame.transform.rotate(right, 90),
            (0, 1): pygame.transform.rotate(right, 90),
        }

    # ---- Helpers ----
    def grid_size():
        w, h = screen.get_size()
        cols = w // CELL
        rows = h // CELL
        ox = (w - cols * CELL) // 2
        oy = (h - rows * CELL) // 2
        return w, h, cols, rows, ox, oy

    def spawn_bounds(cols, rows):
        """
        Returnerar (min_x, max_x, min_y, max_y) för spawnområde.
        Om brädet är för litet för SAFE_MARGIN, fallback till hela brädet.
        """
        if cols <= SAFE_MARGIN * 2 + 1 or rows <= SAFE_MARGIN * 2 + 1:
            return 0, cols - 1, 0, rows - 1
        return SAFE_MARGIN, cols - 1 - SAFE_MARGIN, SAFE_MARGIN, rows - 1 - SAFE_MARGIN

    def rand_cell(cols, rows):
        min_x, max_x, min_y, max_y = spawn_bounds(cols, rows)
        return (random.randint(min_x, max_x), random.randint(min_y, max_y))

    def draw_cell(x, y, color, ox, oy, r=6):
        rect = pygame.Rect(ox + x * CELL, oy + y * CELL, CELL, CELL)
        pygame.draw.rect(screen, color, rect, border_radius=r)

    def cell_center(x, y, ox, oy):
        return ox + x * CELL + CELL // 2, oy + y * CELL + CELL // 2

    # ---- Premium-stil: natthimmel, guld och pärlvitt ----
    GOLD = (232, 196, 110)
    GOLD_DARK = (160, 120, 55)
    GOLD_LIGHT = (255, 240, 190)

    def now():
        return pygame.time.get_ticks() / 1000.0

    _glow_cache = {}

    def blit_glow(cx, cy, radius, color, strength=90):
        key = (radius, color, strength)
        g = _glow_cache.get(key)
        if g is None:
            g = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            steps = 18
            for i in range(steps, 0, -1):
                k = i / steps
                a = min(255, int(strength * 1.8 * (1 - k) ** 1.5))
                pygame.draw.circle(g, (*color, a), (radius, radius), max(1, int(radius * k)))
            _glow_cache[key] = g
        screen.blit(g, (cx - radius, cy - radius))

    _bg_cache = {}

    def background(w, h, cols, rows, ox, oy):
        key = (w, h)
        bg = _bg_cache.get(key)
        if bg is not None:
            return bg

        bg = pygame.Surface((w, h))
        top, bot = (32, 18, 46), (8, 8, 14)
        for y in range(h):
            f = y / max(1, h - 1)
            bg.fill(tuple(int(top[i] + (bot[i] - top[i]) * f) for i in range(3)), (0, y, w, 1))

        # vinjett mot kanterna
        vig = pygame.Surface((w, h), pygame.SRCALPHA)
        steps = 30
        band = max(2, min(w, h) // (2 * steps) + 1)
        for i in range(steps):
            a = int(120 * (1 - i / steps) ** 2)
            pygame.draw.rect(vig, (0, 0, 0, a), pygame.Rect(i * band, i * band, w - 2 * i * band, h - 2 * i * band), band)
        bg.blit(vig, (0, 0))

        # diskret rutnät: små prickar i rutornas hörn
        for gx in range(cols + 1):
            for gy in range(rows + 1):
                bg.fill((58, 48, 78), (ox + gx * CELL, oy + gy * CELL, 2, 2))

        # guldram med svag glöd
        frame = pygame.Surface((w, h), pygame.SRCALPHA)
        border = pygame.Rect(ox, oy, cols * CELL, rows * CELL)
        for grow, a in ((5, 22), (3, 40), (1, 70)):
            pygame.draw.rect(frame, (*GOLD, a), border.inflate(grow * 2, grow * 2), width=2, border_radius=18)
        pygame.draw.rect(frame, (*GOLD, 200), border, width=2, border_radius=16)
        bg.blit(frame, (0, 0))

        _bg_cache[key] = bg
        return bg

    def draw_ring(x, y, ox, oy):
        cx, cy = cell_center(x, y, ox, oy)
        cy += CELL // 10 + int(math.sin(now() * 3.0) * CELL * 0.08)
        r = int(CELL * 0.36)
        width = max(3, CELL // 7)
        blit_glow(cx, cy, int(CELL * 1.1), GOLD, 110)
        pygame.draw.circle(screen, GOLD_DARK, (cx, cy), r, width)
        pygame.draw.circle(screen, GOLD, (cx, cy), r - 1, max(1, width - 2))
        pygame.draw.arc(screen, GOLD_LIGHT, pygame.Rect(cx - r + 1, cy - r + 1, 2 * r - 2, 2 * r - 2), 1.0, 2.6, 2)

        d = max(4, CELL // 5)
        top = cy - r - d // 2
        stone = [(cx, top - d), (cx + d, top), (cx, top + d), (cx - d, top)]
        pygame.draw.polygon(screen, (200, 232, 255), stone)
        pygame.draw.polygon(screen, (255, 255, 255), [(cx, top - d), (cx + d, top), (cx, top)])
        pygame.draw.polygon(screen, (140, 185, 225), stone, 1)

        # glimt i diamanten
        tw = (math.sin(now() * 4.0) + 1) / 2
        if tw > 0.55:
            sz = int(d * 1.6 * (tw - 0.55) / 0.45) + 1
            gx, gy = cx + d, top - d
            pygame.draw.line(screen, (255, 255, 255), (gx - sz, gy), (gx + sz, gy), 1)
            pygame.draw.line(screen, (255, 255, 255), (gx, gy - sz), (gx, gy + sz), 1)

    def draw_heart(x, y, ox, oy):
        cx, cy = cell_center(x, y, ox, oy)
        pulse = 1.0 + 0.09 * math.sin(now() * 5.0 + x * 0.7 + y * 1.3)
        r = max(3, int(CELL * 0.18 * pulse))
        blit_glow(cx, cy, int(CELL * 0.9), (255, 90, 130), 90)
        col = (226, 52, 88)
        pygame.draw.circle(screen, col, (cx - r, cy - r // 2), r)
        pygame.draw.circle(screen, col, (cx + r, cy - r // 2), r)
        pygame.draw.polygon(screen, col, [(cx - 2 * r, cy - r // 4), (cx + 2 * r, cy - r // 4), (cx, cy + int(r * 2.2))])
        pygame.draw.circle(screen, (255, 185, 205), (cx - r - r // 3, cy - r), max(1, r // 3))

    def draw_gem(x, y, ox, oy, color, light, rem):
        cx, cy = cell_center(x, y, ox, oy)
        r = int(CELL * 0.30)
        blit_glow(cx, cy, int(CELL * 1.0), color, 100)
        pygame.draw.circle(screen, color, (cx, cy), r)
        pygame.draw.circle(screen, light, (cx - r // 3, cy - r // 3), max(2, r // 3))
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), r, 1)
        # ringen runt krymper när tiden den ligger kvar rinner ut
        rr = int(CELL * 0.50)
        if rem > 0:
            pygame.draw.arc(screen, light, pygame.Rect(cx - rr, cy - rr, 2 * rr, 2 * rr),
                            math.pi / 2, math.pi / 2 + 2 * math.pi * rem, 2)

    def draw_veil(body, ox, oy):
        # Kroppen som ett pärlvitt brudslöjesläp med skugga och ett skimmer som vandrar längs släpet
        if not body:
            return
        n = len(body)
        pad = max(2, CELL // 10)
        sh_off = 4
        min_x = min(c[0] for c in body)
        min_y = min(c[1] for c in body)
        max_x = max(c[0] for c in body)
        max_y = max(c[1] for c in body)
        bx = ox + min_x * CELL
        by = oy + min_y * CELL
        size = ((max_x - min_x + 1) * CELL + sh_off, (max_y - min_y + 1) * CELL + sh_off)
        shadow = pygame.Surface(size, pygame.SRCALPHA)
        layer = pygame.Surface(size, pygame.SRCALPHA)

        shimmer = (now() * 7.0) % (n + 8) - 4
        for i, (sx, sy) in enumerate(body):
            f = i / max(1, n - 1)
            glint = max(0.0, 1.0 - abs(i - shimmer) / 2.5)
            col = (min(255, int(250 - 75 * f + 30 * glint)),
                   min(255, int(246 - 75 * f + 30 * glint)),
                   min(255, int(240 - 55 * f + 30 * glint)))
            lx, ly = (sx - min_x) * CELL, (sy - min_y) * CELL
            rect = pygame.Rect(lx + pad, ly + pad, CELL - 2 * pad, CELL - 2 * pad)
            shapes = [rect]
            if i + 1 < n:
                nx2, ny2 = body[i + 1][0] - min_x, body[i + 1][1] - min_y
                shapes.append(pygame.Rect(min(lx, nx2 * CELL) + pad, min(ly, ny2 * CELL) + pad,
                                          abs(lx - nx2 * CELL) + CELL - 2 * pad, abs(ly - ny2 * CELL) + CELL - 2 * pad))
            for shp in shapes:
                pygame.draw.rect(shadow, (0, 0, 0, 80), shp.move(sh_off, sh_off), border_radius=CELL // 3)
                pygame.draw.rect(layer, col, shp, border_radius=CELL // 3)
            # spets
            cx, cy = rect.center
            lace = (col[0] - 28, col[1] - 28, col[2] - 22)
            q = CELL // 5
            for ddx, ddy, rad in ((-q, -q, 2), (q, q, 2), (q, -q, 1), (-q, q, 1)):
                pygame.draw.circle(layer, lace, (cx + ddx, cy + ddy), rad)

        screen.blit(shadow, (bx, by))
        screen.blit(layer, (bx, by))

    # ---- Gnistor och "+5" ----
    particles = []  # [x, y, vx, vy, life, ttl, color, size]
    floaters = []   # [x, y, life, ttl, text]

    def burst(cx, cy, color):
        for _ in range(22):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(60, 220)
            ttl = random.uniform(0.35, 0.7)
            particles.append([cx, cy, math.cos(ang) * spd, math.sin(ang) * spd, ttl, ttl,
                              random.choice((color, (255, 255, 255))), random.uniform(1.5, 3.5)])
        floaters.append([cx, cy - CELL // 2, 0.9, 0.9, "+5"])

    def update_fx(dt):
        for p in particles:
            p[4] -= dt
            p[2] *= (1.0 - 2.0 * dt)
            p[3] *= (1.0 - 2.0 * dt)
            p[0] += p[2] * dt
            p[1] += p[3] * dt
        particles[:] = [p for p in particles if p[4] > 0]
        for fl in floaters:
            fl[2] -= dt
            fl[1] -= 40 * dt
        floaters[:] = [fl for fl in floaters if fl[2] > 0]

    def draw_fx():
        for x, y, _vx, _vy, life, ttl, col, size in particles:
            k = life / ttl
            pygame.draw.circle(screen, tuple(int(c * k) for c in col), (int(x), int(y)), max(1, int(size * (0.5 + 0.5 * k))))
        for x, y, life, ttl, text in floaters:
            img = serif_tiny.render(text, True, GOLD_LIGHT)
            img.set_alpha(int(255 * life / ttl))
            screen.blit(img, img.get_rect(center=(int(x), int(y))))

    def draw_hud():
        label = serif_tiny.render("POÄNG", True, (200, 188, 165))
        value = serif_big.render(str(score), True, GOLD)
        effects = []
        if rage_time > 0:
            effects.append(("RAGE", rage_time / RAGE_DURATION, (240, 200, 110)))
        if slowmo_time > 0:
            effects.append(("SLOWMO", slowmo_time / SLOWMO_DURATION, (120, 175, 255)))

        pad = 14
        pill_w, pill_h = 150, 22
        pw = max(label.get_width(), value.get_width(), pill_w if effects else 0) + pad * 2
        ph = pad + label.get_height() + value.get_height() + len(effects) * (pill_h + 6) + pad
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        pygame.draw.rect(panel, (12, 8, 20, 165), panel.get_rect(), border_radius=14)
        pygame.draw.rect(panel, (*GOLD, 90), panel.get_rect(), 1, border_radius=14)
        y = pad
        panel.blit(label, (pad, y))
        y += label.get_height()
        panel.blit(value, (pad, y))
        y += value.get_height() + 4
        for name, frac, col in effects:
            pill = pygame.Rect(pad, y, pill_w, pill_h)
            pygame.draw.rect(panel, (255, 255, 255, 28), pill, border_radius=pill_h // 2)
            fill = pygame.Rect(pad, y, max(pill_h, int(pill_w * frac)), pill_h)
            pygame.draw.rect(panel, (*col, 150), fill, border_radius=pill_h // 2)
            t_img = serif_tiny.render(name, True, (255, 255, 255))
            panel.blit(t_img, t_img.get_rect(midleft=(pad + 10, y + pill_h // 2)))
            y += pill_h + 6
        screen.blit(panel, (24, 18))

    def spawn_free_cell(cols, rows, occupied):

        # Försök slumpa inom safe bounds först
        min_x, max_x, min_y, max_y = spawn_bounds(cols, rows)

        # 1) Random försök i safe området
        for _ in range(4000):
            p = (random.randint(min_x, max_x), random.randint(min_y, max_y))
            if p not in occupied:
                return p

        # 2) Deterministisk scan i safe området
        for yy in range(min_y, max_y + 1):
            for xx in range(min_x, max_x + 1):
                if (xx, yy) not in occupied:
                    return (xx, yy)

        # 3) Om safe området blev helt fullt: fallback till hela brädet (hellre spawn än None)
        for _ in range(4000):
            p = (random.randrange(cols), random.randrange(rows))
            if p not in occupied:
                return p

        for yy in range(rows):
            for xx in range(cols):
                if (xx, yy) not in occupied:
                    return (xx, yy)

        return None

    # ---- Game state ----
    snake = []
    direction = (1, 0)
    next_dir = (1, 0)

    main_apple = (0, 0)
    extra_apples: set[tuple[int, int]] = set()  # rage-apples (vita)
    powerups: dict[str, dict] = {}  # {"rage": {"pos":..,"time":..}, ...}

    score = 0
    dead = False

    t = 0.0
    tick_accum = 0.0

    rage_time = 0.0
    slowmo_time = 0.0
    prev_rage_time = 0.0
    ticks_moved = 0

    def occupied_cells(include_apples=True, include_powerups=True):
        occ = set(snake)
        if include_apples:
            occ.add(main_apple)
            occ |= extra_apples
        if include_powerups:
            for v in powerups.values():
                occ.add(v["pos"])
        return occ

    def spawn_main_apple():
        nonlocal main_apple
        w, h, cols, rows, ox, oy = grid_size()
        occ = occupied_cells(include_apples=True, include_powerups=True)
        p = spawn_free_cell(cols, rows, occ)
        if p is not None:
            main_apple = p

    def spawn_extra_apple():
        """Spawn one extra (rage) apple on a free cell, if possible."""
        nonlocal extra_apples
        w, h, cols, rows, ox, oy = grid_size()
        occ = occupied_cells(include_apples=True, include_powerups=True)
        p = spawn_free_cell(cols, rows, occ)
        if p is not None:
            extra_apples.add(p)

    def maybe_spawn_powerups_after_main_apple():
        nonlocal powerups
        if t < POWERUPS_LOCK_SECONDS:
            return

        w, h, cols, rows, ox, oy = grid_size()
        occ = occupied_cells(include_apples=True, include_powerups=True)

        if "rage" not in powerups and random.random() < P_RAGE:
            rp = spawn_free_cell(cols, rows, occ)
            if rp is not None:
                powerups["rage"] = {"pos": rp, "time": POWERUP_LIFETIME}
                occ.add(rp)

        if "slowmo" not in powerups and random.random() < P_SLOWMO:
            sp = spawn_free_cell(cols, rows, occ)
            if sp is not None:
                powerups["slowmo"] = {"pos": sp, "time": POWERUP_LIFETIME}
                occ.add(sp)

    def spawn_new_main_apple_and_maybe_powerups():
        spawn_main_apple()
        maybe_spawn_powerups_after_main_apple()

    def reset():
        nonlocal snake, direction, next_dir, powerups, score, dead, t, tick_accum
        nonlocal rage_time, slowmo_time, prev_rage_time, ticks_moved, extra_apples

        w, h, cols, rows, ox, oy = grid_size()
        cx, cy = cols // 2, rows // 2

        snake = [(cx - i, cy) for i in range(START_LEN)]
        direction = (1, 0)
        next_dir = direction

        powerups = {}
        score = 0
        dead = False
        t = 0.0
        tick_accum = 0.0

        rage_time = 0.0
        slowmo_time = 0.0
        prev_rage_time = 0.0
        ticks_moved = 0
        extra_apples = set()

        spawn_new_main_apple_and_maybe_powerups()

    reset()

    # ---- Main loop ----
    while True:
        dt = clock.tick(120) / 1000.0
        jk.update()
        if dt > 0.05:
            dt = 0.05

        w, h, cols, rows, ox, oy = grid_size()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if controls.pause(screen, "snake") == "quit":
                        return {"result": "quit", "score": int(score)}
                    clock.tick()
                    tick_accum = 0.0
                    break

                if dead and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    reset()

                if event.key in (pygame.K_UP, pygame.K_w):
                    if direction != (0, 1):
                        next_dir = (0, -1)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    if direction != (0, -1):
                        next_dir = (0, 1)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    if direction != (1, 0):
                        next_dir = (-1, 0)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    if direction != (-1, 0):
                        next_dir = (1, 0)

        if not dead:
            t += dt

            # despawn powerups on map
            for key in list(powerups.keys()):
                powerups[key]["time"] -= dt
                if powerups[key]["time"] <= 0:
                    powerups.pop(key, None)

            # active effect timers
            prev_rage_time = rage_time
            if rage_time > 0:
                rage_time = max(0.0, rage_time - dt)
            if slowmo_time > 0:
                slowmo_time = max(0.0, slowmo_time - dt)

            # när RAGE tar slut: ta bort alla rage-äpplen
            if prev_rage_time > 0 and rage_time == 0:
                extra_apples.clear()

            # speed ramp + effects
            base_tps = min(MAX_TPS, BASE_TPS + TPS_RAMP * t)

            speed_mult = 1.0
            if rage_time > 0:
                speed_mult *= RAGE_SPEED_MULT
            if slowmo_time > 0:
                speed_mult *= SLOWMO_SPEED_MULT

            tps = min(MAX_TPS * 1.5, base_tps * speed_mult)
            tick_accum += dt
            base_interval = 1.0 / tps

            while True:
                interval = base_interval * random.uniform(1.0 - JITTER, 1.0 + JITTER)
                if tick_accum < interval:
                    break
                tick_accum -= interval

                direction = next_dir
                ticks_moved += 1

                hx, hy = snake[0]
                dx, dy = direction
                nx, ny = hx + dx, hy + dy

                if nx < 0 or nx >= cols or ny < 0 or ny >= rows:
                    return {"result": "game_over", "score": int(score)}

                new_head = (nx, ny)

                if new_head in set(snake[:-1]):
                    return {"result": "game_over", "score": int(score)}

                snake.insert(0, new_head)

                # RAGE: var N:e tick -> spawn extra (vita) äpplen
                if rage_time > 0 and (ticks_moved % RAGE_EVERY_N_TICKS == 0):
                    if len(extra_apples) < RAGE_MAX_EXTRA_APPLES:
                        spawn_extra_apple()

                ate_main = (new_head == main_apple)
                ate_extra = (new_head in extra_apples)

                if ate_main or ate_extra:
                    score += 5
                    play(snd_eat)
                    burst(*cell_center(nx, ny, ox, oy), GOLD if ate_main else (255, 110, 150))
                    if ate_main:
                        spawn_new_main_apple_and_maybe_powerups()
                    if ate_extra:
                        extra_apples.discard(new_head)
                    # grow: do NOT pop tail
                else:
                    snake.pop()

                # collect powerups
                if "rage" in powerups and new_head == powerups["rage"]["pos"]:
                    rage_time = RAGE_DURATION
                    powerups.pop("rage", None)

                if "slowmo" in powerups and new_head == powerups["slowmo"]["pos"]:
                    slowmo_time = SLOWMO_DURATION
                    powerups.pop("slowmo", None)

        update_fx(dt)

        # ---- Draw ----
        screen.blit(background(w, h, cols, rows, ox, oy), (0, 0))

        # bonusar som glödande ädelstenar
        if "rage" in powerups:
            x, y = powerups["rage"]["pos"]
            draw_gem(x, y, ox, oy, (240, 200, 110), (255, 240, 205), powerups["rage"]["time"] / POWERUP_LIFETIME)
        if "slowmo" in powerups:
            x, y = powerups["slowmo"]["pos"]
            draw_gem(x, y, ox, oy, (110, 170, 255), (205, 228, 255), powerups["slowmo"]["time"] / POWERUP_LIFETIME)

        # ring (huvudäpplet) och hjärtan (rage-äpplen)
        ax, ay = main_apple
        draw_ring(ax, ay, ox, oy)
        for (ex, ey) in extra_apples:
            draw_heart(ex, ey, ox, oy)

        # slöjan (kroppen) och huvudet
        draw_veil(snake[1:], ox, oy)
        hx, hy = snake[0]
        hc = cell_center(hx, hy, ox, oy)
        if head_imgs is not None:
            img = head_imgs.get(direction, head_imgs[(1, 0)])
            rect = img.get_rect(center=hc)
            blit_glow(hc[0] + 3, hc[1] + 5, int(max(rect.w, rect.h) * 0.62), (0, 0, 0), 150)
            screen.blit(img, rect)
            pygame.draw.ellipse(screen, GOLD, rect.inflate(6, 6), 2)
        else:
            draw_cell(hx, hy, (250, 246, 240), ox, oy, r=8)

        draw_fx()
        draw_hud()

        if dead:
            msg = serif_big.render("GAME OVER", True, (240, 240, 255))
            screen.blit(msg, msg.get_rect(center=(w // 2, int(h * 0.42))))
            msg2 = serif_mid.render("Enter/Space = retry   ESC = tillbaka", True, (200, 200, 215))
            screen.blit(msg2, msg2.get_rect(center=(w // 2, int(h * 0.50))))

        pygame.display.flip()
