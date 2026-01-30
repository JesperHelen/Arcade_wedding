import os
import random
import pygame
import math
import joystick_keys as jk

def run(screen):
    # ----------------------------
    # Helpers: asset paths
    # ----------------------------
    def base_dir():
        return os.path.dirname(os.path.abspath(__file__))

    def asset_path(name):
        candidates = [
            os.path.join(base_dir(), "Assets", "Flappy-bird", name),
            os.path.join(base_dir(), "assets", "Flappy-bird", name),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return candidates[0]

    # ----------------------------
    # Init
    # ----------------------------
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 26, bold=True)

    W, H = screen.get_size()

    # ----------------------------
    # Load images
    # ----------------------------
    def load_img(name):
        return pygame.image.load(asset_path(name)).convert_alpha()

    # bird variants
    bird_base_img = load_img("bird_base.png")
    bird_power_img = load_img("bird.png")

    pipe_img = load_img("pipe.png")
    base_img = load_img("base.png")
    bg_img = load_img("bg.png")

    # ----------------------------
    # Scale
    # ----------------------------
    def scale_to_height(img, target_h):
        w = int(img.get_width() * (target_h / img.get_height()))
        return pygame.transform.smoothscale(img, (w, int(target_h)))

    base_h = int(H * 0.15)
    base_img = scale_to_height(base_img, base_h)

    bg_img = scale_to_height(bg_img, H)

    pipe_h = int(H * 0.88)
    pipe_img = scale_to_height(pipe_img, pipe_h)

    bird_h = int(H * 0.055)
    bird_base_img = scale_to_height(bird_base_img, bird_h)
    bird_power_img = scale_to_height(bird_power_img, bird_h)

    # ----------------------------
    # Game constants
    # ----------------------------
    GROUND_Y = H - base_img.get_height()

    # 30% higher gravity + 30% higher jump
    GRAVITY = 2200.0 * 1.30
    JUMP_VEL = -720.0 * 1.30

    # speed ramp
    BASE_SCROLL = 340.0
    SCROLL_RAMP = 10.5
    MAX_SCROLL = 780.0

    PIPE_GAP = int(H * 0.26)

    # pipes farther apart (~30%)
    PIPE_SPAWN_SEC = 1.35 * 1.30

    # scoring rules
    SCORE_PER_PIPE_BEFORE_150 = 10
    SCORE_PER_PIPE_AFTER_150 = 5

    # pipe sway after score
    SWAY_START_SCORE = 50
    SWAY_AMPLITUDE = int(H * 0.06)
    SWAY_SPEED = 1.5  # rad/s

    # ----------------------------
    # Tiling scroll
    # ----------------------------
    bg_x = 0.0
    base_x = 0.0

    def draw_tiled(img, x_offset, y):
        iw = img.get_width()
        x = int(x_offset) % iw
        x -= iw
        while x < W:
            screen.blit(img, (x, y))
            x += iw

    # ----------------------------
    # FX: simple "explosion" on bird swap
    # ----------------------------
    particles = []  # each: {x,y,vx,vy,life,ttl,size}
    swap_fx_time = 0.0  # ring/flash timer

    def spawn_swap_explosion(cx, cy):
        nonlocal swap_fx_time
        swap_fx_time = 0.35  # ring duration

        for _ in range(28):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(220.0, 520.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            ttl = random.uniform(0.25, 0.55)
            particles.append({
                "x": float(cx),
                "y": float(cy),
                "vx": vx,
                "vy": vy,
                "life": ttl,
                "ttl": ttl,
                "size": random.uniform(2.0, 5.0),
            })

    def update_fx(dt):
        nonlocal swap_fx_time, particles
        if swap_fx_time > 0:
            swap_fx_time = max(0.0, swap_fx_time - dt)

        newp = []
        for p in particles:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            # slight drag
            p["vx"] *= (1.0 - 0.9 * dt)
            p["vy"] *= (1.0 - 0.9 * dt)
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            newp.append(p)
        particles = newp

    def draw_fx():
        # particles
        for p in particles:
            a = p["life"] / max(0.0001, p["ttl"])
            alpha = int(255 * a)
            r = int(p["size"])
            surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 230, 140, alpha), (r + 1, r + 1), r)
            screen.blit(surf, (int(p["x"]) - r - 1, int(p["y"]) - r - 1))

        # ring pulse
        if swap_fx_time > 0:
            a = swap_fx_time / 0.35
            radius = int((1.0 - a) * 60) + 10
            alpha = int(220 * a)
            ring = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 230, 140, alpha), (radius + 2, radius + 2), radius, width=3)
            screen.blit(ring, (bird_x - radius - 2, int(bird_y) - radius - 2))

            # quick flash
            flash = pygame.Surface((W, H), pygame.SRCALPHA)
            flash.fill((255, 230, 140, int(70 * a)))
            screen.blit(flash, (0, 0))

    # ----------------------------
    # Bird
    # ----------------------------
    bird_x = int(W * 0.28)
    bird_y = int(H * 0.40)
    bird_vy = 0.0
    bird_rot = 0.0

    bird_using_power = False  # False => bird_base.png, True => bird.png
    bird_img = bird_base_img

    def bird_rect():
        return bird_img.get_rect(center=(bird_x, int(bird_y)))

    # ----------------------------
    # Pipes
    # Each pipe: {x, gap_y, scored, phase, sway}
    # sway is decided AT SPAWN so only new pipes after threshold move
    # ----------------------------
    pipes = []
    spawn_timer = 0.0

    def spawn_pipe(current_score):
        margin = int(H * 0.12)
        gap_center_min = margin + PIPE_GAP // 2
        gap_center_max = GROUND_Y - margin - PIPE_GAP // 2
        gap_y = random.randint(gap_center_min, gap_center_max)

        sway_flag = (current_score >= SWAY_START_SCORE)

        pipes.append({
            "x": float(W + 60),
            "gap_y": gap_y,
            "scored": False,
            "phase": random.uniform(0.0, math.tau),
            "sway": sway_flag,
        })

        return sway_flag

    def current_gap_y(p, time_s):
        gy = p["gap_y"]
        if p.get("sway", False):
            gy += int(SWAY_AMPLITUDE * math.sin((time_s * SWAY_SPEED) + p["phase"]))

        # clamp så gapet aldrig hamnar i mark/tak
        min_gy = PIPE_GAP // 2 + int(H * 0.08)
        max_gy = GROUND_Y - PIPE_GAP // 2 - int(H * 0.08)
        return max(min_gy, min(max_gy, gy))

    def pipe_rects(p, time_s):
        x = int(p["x"])
        gap_y = current_gap_y(p, time_s)
        pw = pipe_img.get_width()

        top_img = pygame.transform.flip(pipe_img, False, True)
        top_rect = top_img.get_rect()
        top_rect.midbottom = (x + pw // 2, gap_y - PIPE_GAP // 2)

        bot_rect = pipe_img.get_rect()
        bot_rect.midtop = (x + pw // 2, gap_y + PIPE_GAP // 2)

        return top_img, top_rect, pipe_img, bot_rect

    # ----------------------------
    # State
    # ----------------------------
    score = 0
    t = 0.0
    alive = True

    # ----------------------------
    # Main loop
    # ----------------------------
    while True:
        dt = clock.tick(120) / 1000.0
        jk.update()
        if dt > 0.05:
            dt = 0.05

        t += dt
        scroll = min(MAX_SCROLL, BASE_SCROLL + SCROLL_RAMP * t)

        # scoring per pipe changes after 150 score
        score_per_pipe = SCORE_PER_PIPE_AFTER_150 if score >= 150 else SCORE_PER_PIPE_BEFORE_150

        # ----- events -----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {"result": "quit", "score": int(score)}

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {"result": "quit", "score": int(score)}

                if alive and event.key in (pygame.K_SPACE, pygame.K_UP, pygame.K_w):
                    bird_vy = JUMP_VEL

        # ----- update -----
        if alive:
            bg_x -= scroll * 0.35 * dt
            base_x -= scroll * dt

            bird_vy += GRAVITY * dt
            bird_y += bird_vy * dt

            bird_rot = max(-25.0, min(70.0, bird_vy * 0.06))

            # spawn pipes
            spawn_timer += dt
            if spawn_timer >= PIPE_SPAWN_SEC:
                spawn_timer -= PIPE_SPAWN_SEC
                new_pipe_has_sway = spawn_pipe(score)

                # ---- BIRD SWAP TRIGGER ----
                # When the FIRST sway pipe is spawned, swap bird image + explode once
                if new_pipe_has_sway and not bird_using_power:
                    bird_using_power = True
                    bird_img = bird_power_img
                    spawn_swap_explosion(bird_x, int(bird_y))

            for p in pipes:
                p["x"] -= scroll * dt

            pipes = [p for p in pipes if p["x"] > -pipe_img.get_width() - 120]

            # scoring: passerar pipe centerline
            brect = bird_rect()
            for p in pipes:
                pipe_mid_x = int(p["x"]) + pipe_img.get_width() // 2
                if (not p["scored"]) and (brect.centerx > pipe_mid_x):
                    p["scored"] = True
                    score += score_per_pipe

            # collisions
            brect = bird_rect()

            if brect.bottom >= GROUND_Y:
                alive = False
            if brect.top <= 0:
                alive = False

            if alive:
                for p in pipes:
                    top_img, top_rect, bot_img, bot_rect = pipe_rects(p, t)
                    if brect.colliderect(top_rect) or brect.colliderect(bot_rect):
                        alive = False
                        break

            if not alive:
                return {"result": "game_over", "score": int(score)}

        # FX update always (so explosion continues even if you die next frame)
        update_fx(dt)

        # ----- draw -----
        screen.fill((0, 0, 0))
        draw_tiled(bg_img, bg_x, 0)

        for p in pipes:
            top_img, top_rect, bot_img, bot_rect = pipe_rects(p, t)
            screen.blit(top_img, top_rect.topleft)
            screen.blit(bot_img, bot_rect.topleft)

        # bird
        b = pygame.transform.rotate(bird_img, -bird_rot)
        br = b.get_rect(center=(bird_x, int(bird_y)))
        screen.blit(b, br.topleft)

        draw_tiled(base_img, base_x, GROUND_Y)

        # FX on top
        draw_fx()

        hud = font.render(f"SCORE: {score}", True, (245, 245, 255))
        spd = font.render(f"SPEED: {scroll:0.0f}", True, (180, 180, 210))
        rule = font.render(f"PIPE SCORE: {score_per_pipe}", True, (180, 180, 210))
        mode = font.render("BIRD: POWER" if bird_using_power else "BIRD: BASE", True, (180, 180, 210))

        screen.blit(hud, (24, 18))
        screen.blit(spd, (24, 46))
        screen.blit(rule, (24, 74))
        screen.blit(mode, (24, 102))

        pygame.display.flip()
