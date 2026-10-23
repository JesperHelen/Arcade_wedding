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
    SANS = "dejavusans,liberationsans,arial,sans"
    font_big = pygame.font.SysFont(SANS, 40)
    font_mid = pygame.font.SysFont(SANS, 20)
    font_small = pygame.font.SysFont(SANS, 16, bold=True)

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
        # klipp ut ansiktet med en oval så att fotots mörka bakgrund och hår försvinner
        _mw, _mh = _head.get_size()
        _mask = pygame.Surface((_mw, _mh), pygame.SRCALPHA)
        _mask.fill((255, 255, 255, 0))
        pygame.draw.ellipse(_mask, (255, 255, 255, 255),
                            (int(_mw * 0.08), int(_mh * 0.06), int(_mw * 0.86), int(_mh * 0.88)))
        _head = _head.copy()
        _head.blit(_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

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
    TOP_BAR = 84   # plats för poäng/rekord ovanför spelplanen
    MARGIN = 16

    def grid_size():
        w, h = screen.get_size()
        avail_w = w - 2 * MARGIN
        avail_h = h - TOP_BAR - MARGIN
        cols = avail_w // CELL
        rows = avail_h // CELL
        ox = (w - cols * CELL) // 2
        oy = TOP_BAR + (avail_h - rows * CELL) // 2
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

    # ---- Klassisk stil (gammal mobil-LCD) med ansiktet, ringar och hjärtan ----
    C_BG = (74, 99, 97)          # runt spelplanen
    C_LCD = (172, 178, 160)      # spelplanen
    C_TILE = (160, 166, 148)     # rutmönstret
    C_TILE_EDGE = (182, 188, 170)
    C_INK = (24, 28, 24)         # ormen och konturer
    C_INK_SOFT = (62, 68, 60)
    C_TEXT = (240, 244, 240)
    GOLD = (226, 178, 60)
    GOLD_LIGHT = (255, 232, 150)

    def now():
        return pygame.time.get_ticks() / 1000.0

    def read_best():
        try:
            with open(os.path.join(base_dir(), "Game_2.txt"), "r", encoding="utf-8") as f:
                vals = []
                for line in f:
                    parts = line.strip().split(",")
                    if len(parts) >= 2 and parts[1].strip().isdigit():
                        vals.append(int(parts[1]))
                return max(vals) if vals else 0
        except Exception:
            return 0

    best_score = read_best()

    _bg_cache = {}

    def background(w, h, cols, rows, ox, oy):
        key = (w, h)
        bg = _bg_cache.get(key)
        if bg is not None:
            return bg
        bg = pygame.Surface((w, h))
        bg.fill(C_BG)
        board = pygame.Rect(ox, oy, cols * CELL, rows * CELL)
        pygame.draw.rect(bg, C_LCD, board.inflate(12, 12))
        inset = max(3, CELL // 6)
        for gx in range(cols):
            for gy in range(rows):
                r = pygame.Rect(ox + gx * CELL + inset, oy + gy * CELL + inset, CELL - 2 * inset, CELL - 2 * inset)
                bg.fill(C_TILE, r)
                pygame.draw.rect(bg, C_TILE_EDGE, r, 1)
        _bg_cache[key] = bg
        return bg

    def draw_block(x, y, ox, oy):
        # klassiskt block: svart ram, ljus springa och svart kärna
        r = pygame.Rect(ox + x * CELL + 2, oy + y * CELL + 2, CELL - 4, CELL - 4)
        pygame.draw.rect(screen, C_INK, r, 2)
        gap = max(5, CELL // 6)
        pygame.draw.rect(screen, C_INK, r.inflate(-2 * gap, -2 * gap))

    def draw_ring(x, y, ox, oy):
        # vigselring: guldband i lätt perspektiv med en stor briljant i en fattning ovanpå
        cx, cy = cell_center(x, y, ox, oy)
        cy += CELL // 5 + int(math.sin(now() * 3.0) * CELL * 0.05)
        rw, rh = int(CELL * 0.60), int(CELL * 0.42)
        band = max(4, CELL // 6)
        ring = pygame.Rect(cx - rw, cy - rh, rw * 2, rh * 2)
        pygame.draw.ellipse(screen, C_INK, ring.inflate(4, 4), band + 4)
        pygame.draw.ellipse(screen, GOLD, ring, band)
        pygame.draw.arc(screen, GOLD_LIGHT, ring.inflate(-band, -band), 1.9, 3.0, 2)
        pygame.draw.ellipse(screen, (150, 105, 30), ring.inflate(-2 * band, -2 * band), 1)

        # fattning (två klor) och briljanten
        d = max(6, int(CELL * 0.30))
        girdle = ring.top - d // 3
        pygame.draw.line(screen, C_INK, (cx - d // 2, ring.top + 2), (cx - d // 2 - 2, girdle), 4)
        pygame.draw.line(screen, C_INK, (cx + d // 2, ring.top + 2), (cx + d // 2 + 2, girdle), 4)
        pygame.draw.line(screen, GOLD, (cx - d // 2, ring.top + 2), (cx - d // 2 - 2, girdle), 2)
        pygame.draw.line(screen, GOLD, (cx + d // 2, ring.top + 2), (cx + d // 2 + 2, girdle), 2)
        table = girdle - int(d * 0.6)
        stone = [(cx - d, girdle), (cx - d // 2, table), (cx + d // 2, table), (cx + d, girdle), (cx, girdle + int(d * 0.9))]
        pygame.draw.polygon(screen, (225, 242, 255), stone)
        pygame.draw.polygon(screen, (255, 255, 255), [(cx - d // 2, table), (cx, table), (cx - d // 3, girdle)])
        pygame.draw.line(screen, (150, 190, 220), (cx - d, girdle), (cx + d, girdle), 1)
        pygame.draw.line(screen, (150, 190, 220), (cx + d // 2, table), (cx, girdle + int(d * 0.9)), 1)
        pygame.draw.polygon(screen, C_INK, stone, 2)

        tw = (math.sin(now() * 4.0) + 1) / 2
        if tw > 0.6:
            sz = int(d * 0.9 * (tw - 0.6) / 0.4) + 2
            gx, gy = cx + d, table - 2
            pygame.draw.line(screen, (255, 255, 255), (gx - sz, gy), (gx + sz, gy), 2)
            pygame.draw.line(screen, (255, 255, 255), (gx, gy - sz), (gx, gy + sz), 2)

    def heart_points(cx, cy, r):
        return [(cx - 2 * r, cy - r // 4), (cx + 2 * r, cy - r // 4), (cx, cy + int(r * 2.2))]

    def draw_heart(x, y, ox, oy):
        cx, cy = cell_center(x, y, ox, oy)
        pulse = 1.0 + 0.08 * math.sin(now() * 5.0 + x * 0.7 + y * 1.3)
        r = max(3, int(CELL * 0.18 * pulse))
        # kontur först, sedan fyllning
        for col, grow in ((C_INK, 2), ((214, 40, 60), 0)):
            pygame.draw.circle(screen, col, (cx - r, cy - r // 2), r + grow)
            pygame.draw.circle(screen, col, (cx + r, cy - r // 2), r + grow)
            pts = heart_points(cx, cy, r)
            if grow:
                pts = [(pts[0][0] - grow, pts[0][1]), (pts[1][0] + grow, pts[1][1]), (pts[2][0], pts[2][1] + grow * 2)]
            pygame.draw.polygon(screen, col, pts)
        pygame.draw.circle(screen, (255, 170, 180), (cx - r - r // 3, cy - r), max(1, r // 3))

    def draw_gem(x, y, ox, oy, color, rem):
        # bonus = snedställd ruta som i klassiska Snake, med en ram som krymper när tiden går
        cx, cy = cell_center(x, y, ox, oy)
        r = int(CELL * 0.46)
        diamond = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(screen, color, diamond)
        pygame.draw.polygon(screen, C_INK, diamond, 2)
        k = max(0.0, min(1.0, rem))
        ri = max(2, int(r * 0.45 * k))
        pygame.draw.polygon(screen, C_INK, [(cx, cy - ri), (cx + ri, cy), (cx, cy + ri), (cx - ri, cy)])

    # ---- Små klassiska "pixlar" och "+5" när man äter ----
    particles = []  # [x, y, vx, vy, life, ttl, color]
    floaters = []   # [x, y, life, ttl, text]

    def burst(cx, cy, color):
        for _ in range(14):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(60, 180)
            ttl = random.uniform(0.3, 0.55)
            particles.append([cx, cy, math.cos(ang) * spd, math.sin(ang) * spd, ttl, ttl,
                              random.choice((color, C_INK))])
        floaters.append([cx, cy - CELL // 2, 0.8, 0.8, "+5"])

    def update_fx(dt):
        for p in particles:
            p[4] -= dt
            p[0] += p[2] * dt
            p[1] += p[3] * dt
        particles[:] = [p for p in particles if p[4] > 0]
        for fl in floaters:
            fl[2] -= dt
            fl[1] -= 40 * dt
        floaters[:] = [fl for fl in floaters if fl[2] > 0]

    def draw_fx():
        for x, y, _vx, _vy, life, ttl, col in particles:
            sz = max(2, int(5 * life / ttl))
            screen.fill(col, (int(x) - sz // 2, int(y) - sz // 2, sz, sz))
        for x, y, life, ttl, text in floaters:
            img = font_small.render(text, True, C_INK)
            img.set_alpha(int(255 * life / ttl))
            screen.blit(img, img.get_rect(center=(int(x), int(y))))

    def draw_top_bar(w, ox, cols):
        left = ox
        right = ox + cols * CELL
        val = font_big.render(str(score), True, C_TEXT)
        lab = font_mid.render("Poäng", True, C_TEXT)
        screen.blit(val, (left, 8))
        screen.blit(lab, (left, 8 + val.get_height() - 4))

        best = max(best_score, score)
        bval = font_big.render(str(best), True, C_TEXT)
        blab = font_mid.render("Rekord", True, C_TEXT)
        screen.blit(bval, bval.get_rect(topright=(right, 8)))
        screen.blit(blab, blab.get_rect(topright=(right, 8 + bval.get_height() - 4)))

        # aktiva bonusar i mitten
        effects = []
        if rage_time > 0:
            effects.append((f"RAGE {rage_time:0.0f}s", (226, 178, 60)))
        if slowmo_time > 0:
            effects.append((f"SLOWMO {slowmo_time:0.0f}s", (110, 160, 230)))
        x = w // 2 - (len(effects) * 150 - 10) // 2
        for text, col in effects:
            pill = pygame.Rect(x, 28, 140, 28)
            pygame.draw.rect(screen, col, pill, border_radius=14)
            pygame.draw.rect(screen, C_INK, pill, 2, border_radius=14)
            t_img = font_small.render(text, True, C_INK)
            screen.blit(t_img, t_img.get_rect(center=pill.center))
            x += 150

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

        # bonusar
        if "rage" in powerups:
            x, y = powerups["rage"]["pos"]
            draw_gem(x, y, ox, oy, (226, 178, 60), powerups["rage"]["time"] / POWERUP_LIFETIME)
        if "slowmo" in powerups:
            x, y = powerups["slowmo"]["pos"]
            draw_gem(x, y, ox, oy, (110, 160, 230), powerups["slowmo"]["time"] / POWERUP_LIFETIME)

        # ring (huvudäpplet) och hjärtan (rage-äpplen)
        ax, ay = main_apple
        draw_ring(ax, ay, ox, oy)
        for (ex, ey) in extra_apples:
            draw_heart(ex, ey, ox, oy)

        # kroppen som klassiska block, huvudet som ansiktet
        for (sx, sy) in snake[1:]:
            draw_block(sx, sy, ox, oy)
        hx, hy = snake[0]
        hc = cell_center(hx, hy, ox, oy)
        if head_imgs is not None:
            img = head_imgs.get(direction, head_imgs[(1, 0)])
            rect = img.get_rect(center=hc)
            screen.blit(img, rect)
        else:
            draw_block(hx, hy, ox, oy)

        draw_fx()
        draw_top_bar(w, ox, cols)

        if dead:
            msg = font_big.render("GAME OVER", True, C_INK)
            screen.blit(msg, msg.get_rect(center=(w // 2, int(h * 0.42))))
            msg2 = font_mid.render("Enter/Space = retry   ESC = tillbaka", True, C_INK)
            screen.blit(msg2, msg2.get_rect(center=(w // 2, int(h * 0.50))))

        pygame.display.flip()
