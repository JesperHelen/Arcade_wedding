import random
import pygame


def run(screen) -> None:
    clock = pygame.time.Clock()
    w, h = screen.get_size()

    font_big = pygame.font.SysFont("consolas", 40, bold=True)
    font = pygame.font.SysFont("consolas", 22)

    # --- Player ---
    player = pygame.Rect(0, 0, 18, 18)
    player.center = (w // 2, int(h * 0.78))

    # --- Entities (each is dict with rect, kind, speed_mult) ---
    # kind: "red" kills, "green" bonus, "blue" bonus + shield
    orbs: list[dict] = []

    score = 0.0
    best = 0.0

    t = 0.0
    spawn_timer = 0.0
    dead = False

    SPEED_RANDOM_MIN = 0.8
    SPEED_RANDOM_MAX = 1.2

    shield_time = 0.0  # seconds remaining

    def reset():
        nonlocal orbs, score, t, spawn_timer, dead, shield_time
        orbs = []
        score = 0.0
        t = 0.0
        spawn_timer = 0.0
        dead = False
        shield_time = 0.0
        player.center = (w // 2, int(h * 0.78))

    reset()

    # --- Difficulty ---
    base_speed = 280.0          # base fall speed
    base_spawn = 0.52           # seconds between spawns
    min_spawn = 0.11

    # --- Spawn tuning ---
    # Red = common, Green = bonus, Blue = rare bonus+shield
    # Increase spawn feel by allowing extra spawns sometimes.
    p_green = 0.12
    p_blue = 0.06
    p_extra_spawn = 0.22

    # --- Sizes ---
    # "5x larger" vs previous ~14-34 => now ~70-170-ish.
    RED_MIN, RED_MAX = 30, 100
    GREEN_MIN, GREEN_MAX = 70, 150
    BLUE_MIN, BLUE_MAX = 30, 70  # much smaller
    def circle_collide(r1: pygame.Rect, r2: pygame.Rect) -> bool:
        c1x, c1y = r1.center
        c2x, c2y = r2.center

        dx = c1x - c2x
        dy = c1y - c2y
        dist_sq = dx * dx + dy * dy

        r1_rad = r1.w * 0.5
        r2_rad = r2.w * 0.5

        return dist_sq <= (r1_rad + r2_rad) ** 2

    while True:
        dt = clock.tick(60) / 1000.0
        if dt > 0.05:
            dt = 0.05

        # fullscreen can shift sizes on some setups
        new_w, new_h = screen.get_size()
        if new_w != w or new_h != h:
            w, h = new_w, new_h

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {"result": "quit", "score": int(score)}

                if dead and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    reset()

        keys = pygame.key.get_pressed()

        if not dead:
            # --- Movement ---
            speed = 520.0
            dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
            dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])

            player.x += int(dx * speed * dt)
            player.y += int(dy * speed * dt)
            player.x = max(0, min(w - player.w, player.x))
            player.y = max(0, min(h - player.h, player.y))

            # --- Timers ---
            t += dt
            score += dt

            if shield_time > 0:
                shield_time = max(0.0, shield_time - dt)

            # --- Difficulty ramps ---
            fall_speed = base_speed + t * 24.0
            spawn_interval = max(min_spawn, base_spawn - t * 0.010)

            # --- Spawning ---
            spawn_timer += dt
            while spawn_timer >= spawn_interval:
                spawn_timer -= spawn_interval

                def spawn_one():
                    r = random.random()
                    if r < p_blue:
                        kind = "blue"
                        size = random.randint(BLUE_MIN, BLUE_MAX)
                        speed_mult = 1.3  # much faster
                    elif r < p_blue + p_green:
                        kind = "green"
                        size = random.randint(GREEN_MIN, GREEN_MAX)
                        speed_mult = 1.0
                    else:
                        kind = "red"
                        size = random.randint(RED_MIN, RED_MAX)
                        speed_mult = 1.0

                    x = random.randint(0, max(0, w - size))
                    y = -size
                    orbs.append({
                        "rect": pygame.Rect(x, y, size, size),
                        "kind": kind,
                        "speed_mult": speed_mult,
                        "speed_rand": random.uniform(0.8, 1.2), 
                    })


                spawn_one()
                if random.random() < p_extra_spawn:
                    spawn_one()

            # --- Update orbs ---
            for o in orbs:
                o["rect"].y += int(
                    fall_speed * o["speed_mult"] * o["speed_rand"] * dt
                )


            # --- Cleanup ---
            orbs = [o for o in orbs if o["rect"].y < h + 200]

            # --- Collisions ---
            # Iterate over a copy so we can remove safely
            for o in orbs[:]:
                if circle_collide(player, o["rect"]):
                    if o["kind"] == "red":
                        if shield_time <= 0:
                            return {"result": "game_over", "score": int(score)}

                        else:
                            # shield absorbs one hit -> remove orb
                            orbs.remove(o)

                    elif o["kind"] == "green":
                        score += 5.0
                        orbs.remove(o)

                    elif o["kind"] == "blue":
                        score += 10.0
                        shield_time = 3.0
                        orbs.remove(o)

        # --- Draw ---
        screen.fill((10, 10, 18))

        # subtle background grid
        grid_gap = 64
        for x in range(0, w, grid_gap):
            pygame.draw.line(screen, (255, 255, 255), (x, 0), (x, h), 1)
        for y in range(0, h, grid_gap):
            pygame.draw.line(screen, (255, 255, 255), (0, y), (w, y), 1)

        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        screen.blit(overlay, (0, 0))

        # orbs
        for o in orbs:
            r = o["rect"]
            if o["kind"] == "red":
                color = (255, 130, 130)
            elif o["kind"] == "green":
                color = (140, 255, 170)
            else:  # blue
                color = (140, 200, 255)

            # rounded rect makes "orb-ish" without circles
            pygame.draw.rect(screen, color, r, border_radius=999)

            # tiny highlight on big ones
            if r.w >= 60:
                hl = pygame.Rect(r.x + int(r.w * 0.18), r.y + int(r.h * 0.18), max(6, r.w // 6), max(6, r.h // 6))
                pygame.draw.rect(screen, (255, 255, 255), hl, border_radius=999)

        # player
        pygame.draw.rect(screen, (180, 220, 255), player, border_radius=6)

        # shield effect
        if shield_time > 0 and not dead:
            # ring around player
            cx, cy = player.center
            rad = 22
            pygame.draw.circle(screen, (140, 200, 255), (cx, cy), rad, 2)
            pygame.draw.circle(screen, (140, 200, 255), (cx, cy), rad + 6, 1)

        # HUD
        s = font.render(f"SCORE: {score:0.1f}", True, (230, 230, 240))
        b = font.render(f"BEST:  {best:0.1f}", True, (180, 180, 200))
        screen.blit(s, (24, 18))
        screen.blit(b, (24, 44))

        if shield_time > 0 and not dead:
            sh = font.render(f"SHIELD: {shield_time:0.1f}s", True, (160, 210, 255))
            screen.blit(sh, (24, 70))

        if dead:
            msg = font_big.render("GAME OVER", True, (240, 240, 255))
            screen.blit(msg, msg.get_rect(center=(w // 2, int(h * 0.42))))
            msg2 = font.render("Enter/Space = retry   ESC = tillbaka", True, (200, 200, 215))
            screen.blit(msg2, msg2.get_rect(center=(w // 2, int(h * 0.50))))

        pygame.display.flip()
