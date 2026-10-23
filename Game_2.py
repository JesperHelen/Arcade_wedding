import os
import glob
import random
import pygame
import joystick_keys as jk
import controls
from typing import Set, Tuple

def run(screen):
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont("consolas", 40, bold=True)
    font = pygame.font.SysFont("consolas", 22)

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
        # Röster: eat_1.mp3, eat_2.mp3 ... och gameover.mp3 (wav/ogg funkar också)
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
    snd_gameover = load_sounds("gameover")

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

    def draw_ring(x, y, ox, oy):
        cx, cy = cell_center(x, y, ox, oy)
        cy += CELL // 10
        r = int(CELL * 0.36)
        pygame.draw.circle(screen, (240, 200, 80), (cx, cy), r, max(2, CELL // 7))
        d = max(3, CELL // 6)
        top = cy - r - d // 2
        stone = [(cx, top - d), (cx + d, top), (cx, top + d), (cx - d, top)]
        pygame.draw.polygon(screen, (190, 230, 255), stone)
        pygame.draw.polygon(screen, (255, 255, 255), stone, 1)

    def draw_heart(x, y, ox, oy):
        cx, cy = cell_center(x, y, ox, oy)
        r = max(3, int(CELL * 0.18))
        col = (230, 60, 90)
        pygame.draw.circle(screen, col, (cx - r, cy - r // 2), r)
        pygame.draw.circle(screen, col, (cx + r, cy - r // 2), r)
        pygame.draw.polygon(screen, col, [(cx - 2 * r, cy - r // 4), (cx + 2 * r, cy - r // 4), (cx, cy + int(r * 2.2))])

    def draw_veil(body, ox, oy, w, h):
        # Kroppen som ett vitt brudslöjesläp som tunnar ut mot svansen
        if not body:
            return
        layer = pygame.Surface((w, h), pygame.SRCALPHA)
        n = len(body)
        pad = max(2, CELL // 10)
        for i, (sx, sy) in enumerate(body):
            f = i / max(1, n - 1)
            col = (int(245 - 100 * f), int(245 - 100 * f), int(255 - 90 * f))
            rect = pygame.Rect(ox + sx * CELL + pad, oy + sy * CELL + pad, CELL - 2 * pad, CELL - 2 * pad)
            pygame.draw.rect(layer, col, rect, border_radius=CELL // 3)
            if i + 1 < n:
                c1 = cell_center(sx, sy, ox, oy)
                c2 = cell_center(*body[i + 1], ox, oy)
                link = pygame.Rect(min(c1[0], c2[0]) - CELL // 2 + pad, min(c1[1], c2[1]) - CELL // 2 + pad,
                                   abs(c1[0] - c2[0]) + CELL - 2 * pad, abs(c1[1] - c2[1]) + CELL - 2 * pad)
                pygame.draw.rect(layer, col, link, border_radius=CELL // 3)
            # spets
            cx, cy = rect.center
            dot = (col[0] - 45, col[1] - 45, col[2] - 40)
            pygame.draw.circle(layer, dot, (cx - CELL // 5, cy - CELL // 5), 2)
            pygame.draw.circle(layer, dot, (cx + CELL // 5, cy + CELL // 5), 2)
            pygame.draw.circle(layer, dot, (cx + CELL // 5, cy - CELL // 5), 1)
            pygame.draw.circle(layer, dot, (cx - CELL // 5, cy + CELL // 5), 1)
        screen.blit(layer, (0, 0))

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
                    play(snd_gameover)
                    return {"result": "game_over", "score": int(score)}

                new_head = (nx, ny)

                if new_head in set(snake[:-1]):
                    play(snd_gameover)
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

        # ---- Draw ----
        screen.fill((10, 10, 18))

        for x in range(cols + 1):
            px = ox + x * CELL
            pygame.draw.line(screen, (255, 255, 255), (px, oy), (px, oy + rows * CELL), 1)
        for y in range(rows + 1):
            py = oy + y * CELL
            pygame.draw.line(screen, (255, 255, 255), (ox, py), (ox + cols * CELL, py), 1)

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        screen.blit(overlay, (0, 0))

        border = pygame.Rect(ox, oy, cols * CELL, rows * CELL)
        pygame.draw.rect(screen, (255, 170, 170, 100), border, width=2, border_radius=14)

        # ring (huvudäpplet)
        ax, ay = main_apple
        draw_ring(ax, ay, ox, oy)

        # rage-äpplen = hjärtan
        for (ex, ey) in extra_apples:
            draw_heart(ex, ey, ox, oy)

        # powerups on map (dim over time)
        if "rage" in powerups:
            (x, y) = powerups["rage"]["pos"]
            rem = powerups["rage"]["time"] / POWERUP_LIFETIME
            c = 120 + int(135 * rem)
            draw_cell(x, y, (255, c, 140), ox, oy, r=6)

        if "slowmo" in powerups:
            (x, y) = powerups["slowmo"]["pos"]
            rem = powerups["slowmo"]["time"] / POWERUP_LIFETIME
            c = 120 + int(135 * rem)
            draw_cell(x, y, (140, c, 255), ox, oy, r=6)

        # slöjan (kroppen) och huvudet
        draw_veil(snake[1:], ox, oy, w, h)
        hx, hy = snake[0]
        if head_imgs is not None:
            img = head_imgs.get(direction, head_imgs[(1, 0)])
            screen.blit(img, img.get_rect(center=cell_center(hx, hy, ox, oy)))
        else:
            draw_cell(hx, hy, (180, 220, 255), ox, oy, r=8)

        # HUD
        base_tps = min(MAX_TPS, BASE_TPS + TPS_RAMP * t)
        speed_mult = (RAGE_SPEED_MULT if rage_time > 0 else 1.0) * (SLOWMO_SPEED_MULT if slowmo_time > 0 else 1.0)
        shown_tps = min(MAX_TPS * 1.5, base_tps * speed_mult)

        hud1 = font.render(f"SCORE: {score}", True, (230, 230, 240))
        hud2 = font.render(f"SPEED: {shown_tps:0.1f} tps", True, (180, 180, 200))
        lock = max(0.0, POWERUPS_LOCK_SECONDS - t)
        hud3 = font.render(f"POWERUPS LOCK: {lock:0.0f}s" if lock > 0 else "POWERUPS: ON", True, (160, 160, 190))

        screen.blit(hud1, (24, 18))
        screen.blit(hud2, (24, 44))
        screen.blit(hud3, (24, 70))

        yline = 96
        if rage_time > 0:
            rr = font.render(f"RAGE: {rage_time:0.1f}s  (var {RAGE_EVERY_N_TICKS}:e ruta -> vitt äpple)", True, (255, 230, 140))
            screen.blit(rr, (24, yline))
            yline += 24
        if slowmo_time > 0:
            sm = font.render(f"SLOWMO: {slowmo_time:0.1f}s", True, (140, 200, 255))
            screen.blit(sm, (24, yline))
            yline += 24

        if dead:
            msg = font_big.render("GAME OVER", True, (240, 240, 255))
            screen.blit(msg, msg.get_rect(center=(w // 2, int(h * 0.42))))
            msg2 = font.render("Enter/Space = retry   ESC = tillbaka", True, (200, 200, 215))
            screen.blit(msg2, msg2.get_rect(center=(w // 2, int(h * 0.50))))

        pygame.display.flip()
