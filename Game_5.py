# Game_5.py — Space Invaders (Arcade-style)
# Assets:
#   Assets/Space/Skett.png    (player ship)
#   Assets/Space/kula.png     (player bullet)
#   Assets/Space/Fielnde.png  (enemy base sprite)
#
# Saves highscores to: game_5.txt (same folder as this file)

import os
import math
import random
import pygame
import joystick_keys as jk


def run(screen):
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont("consolas", 46, bold=True)
    font = pygame.font.SysFont("consolas", 22)

    # ----------------------------
    # Helpers: asset paths
    # ----------------------------
    def base_dir():
        return os.path.dirname(os.path.abspath(__file__))

    def asset_path(*parts):
        # tolerant to case
        candidates = [
            os.path.join(base_dir(), *parts),
            os.path.join(base_dir(), *[p.lower() for p in parts]),
            os.path.join(base_dir(), *[p.capitalize() for p in parts]),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return candidates[0]

    ASSET_DIR = asset_path("Assets", "Space")

    def load_img(name, alpha=True):
        p = asset_path("Assets", "Space", name)
        try:
            img = pygame.image.load(p)
            return img.convert_alpha() if alpha else img.convert()
        except Exception as e:
            # fallback: make a placeholder
            surf = pygame.Surface((48, 48), pygame.SRCALPHA)
            pygame.draw.rect(surf, (255, 80, 80), surf.get_rect(), width=3)
            pygame.draw.line(surf, (255, 80, 80), (0, 0), (47, 47), 3)
            pygame.draw.line(surf, (255, 80, 80), (47, 0), (0, 47), 3)
            return surf

    def tint_surface(src, rgb):
        """Multiplicative tint (keeps alpha)."""
        s = src.copy()
        s.fill(rgb + (255,), special_flags=pygame.BLEND_RGBA_MULT)
        return s

    # ----------------------------
    # Highscore file
    # ----------------------------
    SCORE_FILE = os.path.join(base_dir(), "game_5.txt")

    def read_scores():
        if not os.path.exists(SCORE_FILE):
            return []
        out = []
        try:
            with open(SCORE_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(int(line))
                    except Exception:
                        pass
        except Exception:
            return []
        out = [s for s in out if isinstance(s, int)]
        out.sort(reverse=True)
        return out[:10]

    def write_scores(scores):
        try:
            with open(SCORE_FILE, "w", encoding="utf-8") as f:
                for s in scores[:10]:
                    f.write(str(int(s)) + "\n")
        except Exception:
            pass

    def submit_score(score):
        scores = read_scores()
        scores.append(int(score))
        scores.sort(reverse=True)
        scores = scores[:10]
        write_scores(scores)
        return scores

    # ----------------------------
    # Config
    # ----------------------------
    W, H = screen.get_size()

    BG = (8, 8, 14)
    HUD = (230, 230, 245)
    SUB = (175, 175, 200)

    # Abilities caps / starts
    MAX_BULLETS_CAP = 9
    max_bullets = 1          # ability: extra shots increases this up to 9
    bullet_damage = 1        # ability: extra damage
    fire_cd = 0.28           # ability: extra attack speed lowers this
    FIRE_CD_MIN = 0.08

    homing_bonus = 0         # ability: +2 homing bullets (red) => set to 2 when collected

    # Player
    PLAYER_SPEED = 520.0
    PLAYER_PAD_BOTTOM = 38
    PLAYER_HP = 5

    # Bullets
    BULLET_SPEED = 920.0
    ENEMY_BULLET_SPEED = 520.0

    # Enemy formation
    COLS = 10
    ROWS = 5
    ENEMY_GAP_X = 18
    ENEMY_GAP_Y = 16
    ENEMY_STEP_DOWN = 22
    ENEMY_MOVE_SPEED = 70.0  # will ramp
    ENEMY_SHOOT_BASE = 0.55  # baseline chance factor

    # Powerups
    POWERUP_DROP_CHANCE = 0.14
    POWERUP_FALL_SPEED = 180.0
    POWERUP_LIFE = 14.0  # seconds until despawn if not collected

    # Waves
    wave = 1
    score = 0

    # Input state (joystick via jk.update() -> KEYDOWN/KEYUP)
    move_left = False
    move_right = False
    firing = False

    # ----------------------------
    # Load & prep sprites
    # ----------------------------
    img_ship = load_img("Skett.png", alpha=True)
    img_bullet = load_img("kula.png", alpha=True)
    img_enemy_base = load_img("Fielnde.png", alpha=True)

    # Scale a bit for consistent look
    def fit_width(img, target_w):
        w, h = img.get_size()
        if w <= 0:
            return img
        s = target_w / float(w)
        return pygame.transform.smoothscale(img, (int(w * s), int(h * s)))

    img_ship = fit_width(img_ship, 72)
    img_bullet = fit_width(img_bullet, 14)
    img_enemy_base = fit_width(img_enemy_base, 52)

    # Enemy variants by color+hp
    ENEMY_TYPES = [
        {"name": "green", "hp": 5, "tint": (110, 255, 140), "score": 10},
        {"name": "blue",  "hp": 10, "tint": (120, 170, 255), "score": 18},
        {"name": "red",   "hp": 50, "tint": (255, 90, 110), "score": 70},
    ]

    enemy_imgs = {
        t["name"]: tint_surface(img_enemy_base, t["tint"])
        for t in ENEMY_TYPES
    }

    bullet_player_img = tint_surface(img_bullet, (140, 240, 255))  # cyan-ish
    bullet_homing_img = tint_surface(img_bullet, (255, 90, 90))    # red-ish (homing)
    bullet_enemy_img = tint_surface(img_bullet, (255, 80, 80))     # red always

    # ----------------------------
    # Small UI helpers
    # ----------------------------
    def draw_center(text, y, col=HUD, fnt=None):
        f = fnt or font_big
        s = f.render(text, True, col)
        screen.blit(s, s.get_rect(center=(W // 2, y)))

    def draw_shadow_text(text, pos, col=HUD, fnt=None):
        f = fnt or font
        s = f.render(text, True, col)
        sh = f.render(text, True, (20, 20, 28))
        screen.blit(sh, (pos[0] + 2, pos[1] + 2))
        screen.blit(s, pos)

    # ----------------------------
    # Entities
    # ----------------------------
    class Bullet:
        __slots__ = ("x", "y", "vx", "vy", "from_enemy", "damage", "homing", "img", "w", "h")

        def __init__(self, x, y, vx, vy, from_enemy, damage=1, homing=False, img=None):
            self.x = float(x)
            self.y = float(y)
            self.vx = float(vx)
            self.vy = float(vy)
            self.from_enemy = bool(from_enemy)
            self.damage = int(damage)
            self.homing = bool(homing)
            self.img = img
            self.w, self.h = self.img.get_size() if self.img else (8, 16)

        def rect(self):
            return pygame.Rect(int(self.x - self.w // 2), int(self.y - self.h // 2), self.w, self.h)

        def update(self, dt, enemies):
            # Homing: steer gently towards nearest enemy
            if self.homing and enemies:
                target = None
                best = 1e18
                for e in enemies:
                    if not e.alive:
                        continue
                    dx = (e.x - self.x)
                    dy = (e.y - self.y)
                    d2 = dx * dx + dy * dy
                    if d2 < best:
                        best = d2
                        target = e
                if target is not None:
                    dx = target.x - self.x
                    dy = target.y - self.y
                    dist = math.hypot(dx, dy) + 1e-6
                    ux, uy = dx / dist, dy / dist
                    # Blend current velocity direction toward target
                    speed = math.hypot(self.vx, self.vy)
                    steer = 10.0 * dt  # higher = snappier
                    nx = (self.vx / (speed + 1e-6)) * (1.0 - steer) + ux * steer
                    ny = (self.vy / (speed + 1e-6)) * (1.0 - steer) + uy * steer
                    nd = math.hypot(nx, ny) + 1e-6
                    self.vx = (nx / nd) * speed
                    self.vy = (ny / nd) * speed

            self.x += self.vx * dt
            self.y += self.vy * dt

            # out of bounds?
            if self.y < -50 or self.y > H + 50 or self.x < -60 or self.x > W + 60:
                return False
            return True

        def draw(self, surf):
            r = self.rect()
            surf.blit(self.img, (r.x, r.y))

    class Enemy:
        __slots__ = ("x", "y", "hp", "max_hp", "kind", "img", "alive", "w", "h")

        def __init__(self, x, y, kind):
            self.x = float(x)
            self.y = float(y)
            self.kind = kind  # dict from ENEMY_TYPES
            self.hp = int(kind["hp"])
            self.max_hp = int(kind["hp"])
            self.img = enemy_imgs[kind["name"]]
            self.alive = True
            self.w, self.h = self.img.get_size()

        def rect(self):
            return pygame.Rect(int(self.x - self.w // 2), int(self.y - self.h // 2), self.w, self.h)

        def hit(self, dmg):
            if not self.alive:
                return False
            self.hp -= int(dmg)
            if self.hp <= 0:
                self.alive = False
                return True
            return False

        def draw(self, surf):
            if not self.alive:
                return
            r = self.rect()
            surf.blit(self.img, (r.x, r.y))

            # HP bar for red (bossy) or if damaged
            if self.max_hp >= 50 or self.hp < self.max_hp:
                bar_w = self.w
                bar_h = 6
                x0 = r.x
                y0 = r.y - 10
                pygame.draw.rect(surf, (30, 30, 45), (x0, y0, bar_w, bar_h), border_radius=3)
                frac = max(0.0, min(1.0, self.hp / float(self.max_hp)))
                pygame.draw.rect(surf, (255, 120, 120), (x0, y0, int(bar_w * frac), bar_h), border_radius=3)

    class Powerup:
        # type: "shots" | "damage" | "rate" | "homing"
        __slots__ = ("x", "y", "typ", "vy", "life", "w", "h")

        def __init__(self, x, y, typ):
            self.x = float(x)
            self.y = float(y)
            self.typ = typ
            self.vy = POWERUP_FALL_SPEED
            self.life = POWERUP_LIFE
            self.w = 28
            self.h = 28

        def rect(self):
            return pygame.Rect(int(self.x - self.w // 2), int(self.y - self.h // 2), self.w, self.h)

        def update(self, dt):
            self.y += self.vy * dt
            self.life -= dt
            if self.y > H + 40 or self.life <= 0:
                return False
            return True

        def draw(self, surf):
            r = self.rect()
            # simple icon: colored gem + letter
            if self.typ == "shots":
                col = (255, 230, 120); ch = "S"   # Shots
            elif self.typ == "damage":
                col = (255, 140, 140); ch = "D"   # Damage
            elif self.typ == "rate":
                col = (170, 255, 170); ch = "R"   # Rate
            else:
                col = (255, 100, 100); ch = "H"   # Homing

            pygame.draw.rect(surf, (18, 18, 30), r, border_radius=10)
            pygame.draw.rect(surf, col, r.inflate(-6, -6), border_radius=9)
            txt = font.render(ch, True, (10, 10, 18))
            surf.blit(txt, txt.get_rect(center=r.center))

    # ----------------------------
    # Game setup
    # ----------------------------
    def make_wave(wave_idx):
        enemies = []
        # More reds later, but keep it fair
        # rows: top -> tougher (blue/red), bottom -> green
        for ry in range(ROWS):
            for cx in range(COLS):
                px = 120 + cx * (img_enemy_base.get_width() + ENEMY_GAP_X)
                py = 90 + ry * (img_enemy_base.get_height() + ENEMY_GAP_Y)

                # choose kind
                if ry == 0 and wave_idx >= 3:
                    kind = ENEMY_TYPES[2]  # red
                elif ry <= 1:
                    kind = ENEMY_TYPES[1]  # blue
                else:
                    kind = ENEMY_TYPES[0]  # green

                enemies.append(Enemy(px, py, kind))
        return enemies

    enemies = make_wave(wave)
    enemy_dir = 1  # 1 right, -1 left
    enemy_speed = ENEMY_MOVE_SPEED

    # Player state
    ship_rect = img_ship.get_rect()
    player_x = W * 0.5
    player_y = H - PLAYER_PAD_BOTTOM
    player_hp = PLAYER_HP

    bullets = []
    enemy_bullets = []
    powerups = []

    fire_timer = 0.0

    # stars
    stars = []
    for _ in range(90):
        stars.append([random.uniform(0, W), random.uniform(0, H), random.uniform(60, 160)])

    def alive_enemies():
        return [e for e in enemies if e.alive]

    # ----------------------------
    # Shooting
    # ----------------------------
    def try_fire():
        nonlocal fire_timer
        if fire_timer > 0:
            return

        # limit normal bullets by max_bullets (homing bullets are extra)
        active_player_bullets = sum(1 for b in bullets if not b.from_enemy and not b.homing)
        if active_player_bullets >= max_bullets:
            return

        # spawn normal bullet
        bx = player_x
        by = player_y - ship_rect.height // 2 - 6
        bullets.append(Bullet(bx, by, 0.0, -BULLET_SPEED, from_enemy=False, damage=bullet_damage, homing=False, img=bullet_player_img))

        # spawn homing bonus bullets (+2) if enabled
        if homing_bonus >= 2:
            # slight angle spread
            bullets.append(Bullet(bx - 8, by, -120.0, -BULLET_SPEED * 0.92, from_enemy=False, damage=bullet_damage, homing=True, img=bullet_homing_img))
            bullets.append(Bullet(bx + 8, by, 120.0, -BULLET_SPEED * 0.92, from_enemy=False, damage=bullet_damage, homing=True, img=bullet_homing_img))

        fire_timer = fire_cd

    # ----------------------------
    # Enemy shooting
    # ----------------------------
    def enemy_shoot(dt):
        # pick random shooters among bottom-most in each column
        live = alive_enemies()
        if not live:
            return

        # build bottom-most per column (based on x bucket)
        cols = {}
        for e in live:
            # bucket by nearest column index
            idx = int((e.x - 80) // (img_enemy_base.get_width() + ENEMY_GAP_X))
            if idx not in cols or e.y > cols[idx].y:
                cols[idx] = e
        shooters = list(cols.values())
        if not shooters:
            return

        # chance scales with wave and remaining enemies
        remain = len(live)
        base = ENEMY_SHOOT_BASE + 0.05 * (wave - 1)
        intensity = base * (dt * 60.0) * (1.2 + (COLS * ROWS - remain) / 25.0)
        # clamp
        intensity = max(0.05, min(0.95, intensity))

        # shoot a few times randomly
        # (very small probability per frame)
        if random.random() < intensity * 0.15:
            shooter = random.choice(shooters)
            bx = shooter.x
            by = shooter.y + shooter.h // 2 + 8
            enemy_bullets.append(Bullet(bx, by, 0.0, ENEMY_BULLET_SPEED, from_enemy=True, damage=1, homing=False, img=bullet_enemy_img))

    # ----------------------------
    # Powerups
    # ----------------------------
    def maybe_drop_powerup(x, y):
        if random.random() > POWERUP_DROP_CHANCE:
            return
        # weight the drops slightly:
        # if already max bullets, reduce "shots" chance
        choices = ["damage", "rate", "homing", "shots"]
        weights = [1.0, 1.0, 0.9, 1.0]
        if max_bullets >= MAX_BULLETS_CAP:
            weights[3] = 0.2
        if homing_bonus >= 2:
            weights[2] = 0.25
        typ = random.choices(choices, weights=weights, k=1)[0]
        powerups.append(Powerup(x, y, typ))

    def apply_powerup(typ):
        nonlocal max_bullets, bullet_damage, fire_cd, homing_bonus, score
        if typ == "shots":
            if max_bullets < MAX_BULLETS_CAP:
                max_bullets += 1
                score += 5
        elif typ == "damage":
            bullet_damage += 1
            score += 6
        elif typ == "rate":
            fire_cd = max(FIRE_CD_MIN, fire_cd - 0.03)
            score += 6
        elif typ == "homing":
            homing_bonus = 2
            score += 8

    # ----------------------------
    # Intro / instructions
    # ----------------------------
    intro_t = 0.0
    while intro_t < 0.75:
        dt = clock.tick(120) / 1000.0
        intro_t += dt
        jk.update()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {"result": "quit", "score": 0}
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE,):
                    return {"result": "quit", "score": 0}
                # any key starts
                intro_t = 999

        screen.fill(BG)
        draw_center("SPACE INVADER", H // 2 - 70, col=HUD, fnt=font_big)
        draw_center("Press any button", H // 2 - 10, col=SUB, fnt=font)
        draw_center("← → move   SPACE shoot   ESC back", H // 2 + 26, col=SUB, fnt=font)
        pygame.display.flip()

    # ----------------------------
    # Main loop
    # ----------------------------
    game_over = False
    over_timer = 0.0

    while True:
        dt = clock.tick(120) / 1000.0
        if dt > 0.05:
            dt = 0.05

        jk.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {"result": "quit", "score": int(score)}

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {"result": "quit", "score": int(score)}

                elif event.key == pygame.K_LEFT:
                    move_left = True
                elif event.key == pygame.K_RIGHT:
                    move_right = True

                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    firing = True
                    # instant shot on press
                    try_fire()

            elif event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT:
                    move_left = False
                elif event.key == pygame.K_RIGHT:
                    move_right = False
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    firing = False

        # Game over screen timing
        if game_over:
            over_timer += dt
            if over_timer >= 2.2:
                submit_score(score)
                return {"result": "game_over", "score": int(score)}

            # draw game over
            screen.fill(BG)
            draw_center("GAME OVER", H // 2 - 50, col=(255, 120, 120), fnt=font_big)
            draw_center(f"SCORE: {int(score)}", H // 2 + 10, col=HUD, fnt=font)
            draw_center("Returning...", H // 2 + 44, col=SUB, fnt=font)
            pygame.display.flip()
            continue

        # ----------------------------
        # Update world
        # ----------------------------

        # background stars
        for s in stars:
            s[1] += s[2] * dt
            if s[1] > H + 5:
                s[0] = random.uniform(0, W)
                s[1] = -5
                s[2] = random.uniform(60, 160)

        # player move
        dx = 0.0
        if move_left and not move_right:
            dx = -PLAYER_SPEED
        elif move_right and not move_left:
            dx = PLAYER_SPEED

        player_x += dx * dt
        pad = 30
        player_x = max(pad, min(W - pad, player_x))

        # fire hold
        if fire_timer > 0:
            fire_timer -= dt
        if firing:
            try_fire()

        # enemy move: compute bounds
        live = alive_enemies()

        # ramp difficulty as wave grows
        enemy_speed = ENEMY_MOVE_SPEED + (wave - 1) * 14.0

        if live:
            minx = min(e.x - e.w / 2 for e in live)
            maxx = max(e.x + e.w / 2 for e in live)

            # step
            step = enemy_dir * enemy_speed * dt
            # if would hit wall, reverse and move down
            if maxx + step > W - 30 or minx + step < 30:
                enemy_dir *= -1
                for e in live:
                    e.y += ENEMY_STEP_DOWN
            else:
                for e in live:
                    e.x += step

            # lose if reach player line
            if max(e.y + e.h / 2 for e in live) >= (player_y - 40):
                game_over = True
                over_timer = 0.0

        # enemy shooting
        enemy_shoot(dt)

        # update bullets
        if bullets:
            bullets[:] = [b for b in bullets if b.update(dt, live)]
        if enemy_bullets:
            enemy_bullets[:] = [b for b in enemy_bullets if b.update(dt, live)]

        # update powerups
        if powerups:
            powerups[:] = [p for p in powerups if p.update(dt)]

        # collisions: player bullets vs enemies
        if bullets and live:
            for b in list(bullets):
                if b.from_enemy:
                    continue
                br = b.rect()
                hit_any = False
                for e in live:
                    if not e.alive:
                        continue
                    if br.colliderect(e.rect()):
                        died = e.hit(b.damage)
                        hit_any = True
                        if died:
                            score += e.kind["score"]
                            maybe_drop_powerup(e.x, e.y)
                        else:
                            score += 1  # chip points
                        break
                if hit_any:
                    try:
                        bullets.remove(b)
                    except ValueError:
                        pass

        # collisions: enemy bullets vs player
        ship_r = img_ship.get_rect(center=(int(player_x), int(player_y)))
        if enemy_bullets:
            for b in list(enemy_bullets):
                if not b.from_enemy:
                    continue
                if b.rect().colliderect(ship_r):
                    player_hp -= 1
                    try:
                        enemy_bullets.remove(b)
                    except ValueError:
                        pass
                    if player_hp <= 0:
                        game_over = True
                        over_timer = 0.0
                        break

        # collisions: player collects powerups
        if powerups:
            for p in list(powerups):
                if p.rect().colliderect(ship_r):
                    apply_powerup(p.typ)
                    try:
                        powerups.remove(p)
                    except ValueError:
                        pass

        # next wave if all dead
        if not alive_enemies():
            wave += 1
            enemies = make_wave(wave)
            enemy_dir = 1
            # small reward
            score += 25 + 10 * (wave - 1)
            # clear bullets/powerups so it feels clean
            bullets.clear()
            enemy_bullets.clear()
            powerups.clear()
            # heal a bit (but not full)
            player_hp = min(PLAYER_HP, player_hp + 1)

        # ----------------------------
        # Draw
        # ----------------------------
        screen.fill(BG)

        # stars
        for sx, sy, spd in stars:
            r = 1 if spd < 110 else 2
            pygame.draw.circle(screen, (120, 120, 155), (int(sx), int(sy)), r)

        # HUD panel top
        pygame.draw.rect(screen, (14, 14, 24), (18, 14, W - 36, 44), border_radius=14)

        # HUD text
        draw_shadow_text(f"SCORE {int(score)}", (32, 26), col=HUD, fnt=font)
        draw_shadow_text(f"WAVE {wave}", (240, 26), col=HUD, fnt=font)
        draw_shadow_text(f"HP {player_hp}", (390, 26), col=HUD, fnt=font)

        # Abilities state
        draw_shadow_text(f"SHOTS {max_bullets}/{MAX_BULLETS_CAP}", (500, 26), col=SUB, fnt=font)
        draw_shadow_text(f"DMG {bullet_damage}", (700, 26), col=SUB, fnt=font)
        draw_shadow_text(f"RATE {max(0.01, fire_cd):.2f}s", (820, 26), col=SUB, fnt=font)
        if homing_bonus >= 2:
            draw_shadow_text("+HOMING", (980, 26), col=(255, 120, 120), fnt=font)

        # enemies
        for e in enemies:
            e.draw(screen)

        # bullets
        for b in bullets:
            b.draw(screen)
        for b in enemy_bullets:
            b.draw(screen)

        # powerups
        for p in powerups:
            p.draw(screen)

        # player
        ship_r = img_ship.get_rect(center=(int(player_x), int(player_y)))
        screen.blit(img_ship, (ship_r.x, ship_r.y))

        # bottom hint
        hint = "← → move   SPACE shoot   ESC back"
        ht = font.render(hint, True, SUB)
        screen.blit(ht, (W // 2 - ht.get_width() // 2, H - 32))

        pygame.display.flip()
