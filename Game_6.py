import math
import random
import pygame
import joystick_keys as jk


def clamp(x, a, b):
    return max(a, min(b, x))


def _get_font(size=24):
    # Använd systemfont här inne för att spelet ska vara fristående.
    # (Din launcher har egen font-cache i menyn.)
    f = pygame.font.SysFont("consolas", size)
    f.set_bold(True)
    return f


def run(screen):
    """
    Pong VS (2 players)
    - Vänster spelare: W/S (eller joystick upp/ner via jk)
    - Höger spelare: Pil upp/ner (eller joystick upp/ner via jk)
    - Först till 3 vinner
    - Hastighet ökar efter varje poäng
    Returnerar dict som dina andra spel: {"result": "done"/"quit", "score": 0}
    """
    clock = pygame.time.Clock()
    W, H = screen.get_size()

    font_big = _get_font(44)
    font = _get_font(22)
    font_small = _get_font(16)

    # --- Colors (match-ish din stil) ---
    BG = (10, 10, 18)
    FG = (235, 235, 255)
    MID = (60, 60, 80)
    ACCENT = (255, 230, 140)
    WIN = (120, 240, 170)

    # --- Game constants ---
    WIN_SCORE = 3

    PADDLE_W = 14
    PADDLE_H = 110
    PADDLE_SPEED = 520.0  # px/s

    BALL_SIZE = 14
    base_ball_speed = 360.0
    speed_growth = 1.12      # blir snabbare efter varje poäng
    speed_growth_hit = 1.02  # lite snabbare efter paddle-hit
    max_ball_speed = 1100.0

    # --- Entities ---
    left = pygame.Rect(40, H // 2 - PADDLE_H // 2, PADDLE_W, PADDLE_H)
    right = pygame.Rect(W - 40 - PADDLE_W, H // 2 - PADDLE_H // 2, PADDLE_W, PADDLE_H)
    ball = pygame.Rect(W // 2 - BALL_SIZE // 2, H // 2 - BALL_SIZE // 2, BALL_SIZE, BALL_SIZE)

    left_score = 0
    right_score = 0

    current_speed = base_ball_speed
    paused = False
    game_over = False
    winner_text = ""

    def reset_round(serving_dir=None):
        nonlocal current_speed
        ball.center = (W // 2, H // 2)

        # lite slumpad vinkel men mest horisontellt
        ang = random.uniform(-0.60, 0.60)  # ~ -35°..+35°
        dirx = serving_dir if serving_dir in (-1, 1) else random.choice([-1, 1])

        vx = math.cos(ang) * dirx
        vy = math.sin(ang)

        # undvik helt rak
        if abs(vy) < 0.15:
            vy = 0.15 * (1 if random.random() < 0.5 else -1)

        # normalisera
        ln = math.sqrt(vx * vx + vy * vy)
        vx, vy = vx / ln, vy / ln
        return [vx * current_speed, vy * current_speed]

    ball_vel = reset_round()

    def bounce_from_paddle(paddle_rect, incoming_vx, incoming_vy, is_left):
        # träffpunkt: -1..+1
        rel = (ball.centery - paddle_rect.centery) / (paddle_rect.height / 2)
        rel = clamp(rel, -1.0, 1.0)

        max_angle = math.radians(60)
        angle = rel * max_angle

        speed = math.sqrt(incoming_vx * incoming_vx + incoming_vy * incoming_vy)
        speed = min(max_ball_speed, speed * speed_growth_hit)

        dirx = 1 if is_left else -1
        vx = math.cos(angle) * dirx
        vy = math.sin(angle)
        return vx * speed, vy * speed

    def draw_center_text(txt, y, col=FG, big=False):
        f = font_big if big else font
        s = f.render(txt, True, col)
        screen.blit(s, s.get_rect(center=(W // 2, y)))

    def draw():
        screen.fill(BG)

        # mid line
        for y in range(0, H, 22):
            pygame.draw.rect(screen, MID, (W // 2 - 2, y, 4, 12))

        # paddles + ball
        pygame.draw.rect(screen, FG, left, border_radius=6)
        pygame.draw.rect(screen, FG, right, border_radius=6)
        pygame.draw.rect(screen, FG, ball, border_radius=6)

        # score
        sc = font_big.render(f"{left_score}  {right_score}", True, FG)
        screen.blit(sc, sc.get_rect(center=(W // 2, 56)))

        # hint
        hint = font_small.render("Vänster: W/S  •  Höger: ↑/↓  •  P=paus  •  ESC=till menyn", True, (170, 170, 190))
        screen.blit(hint, (18, H - 30))

        spd = font_small.render(f"Hastighet: {int(current_speed)}", True, (140, 140, 160))
        screen.blit(spd, (W - spd.get_width() - 18, H - 30))

        if paused and not game_over:
            draw_center_text("PAUS", H // 2 - 30, ACCENT, big=True)
            draw_center_text("Tryck P för att fortsätta", H // 2 + 18, (200, 200, 220))

        if game_over:
            draw_center_text(winner_text, H // 2 - 44, WIN, big=True)
            draw_center_text("Tryck R för rematch", H // 2 + 10, (200, 200, 220))
            draw_center_text("ESC för att avsluta", H // 2 + 40, (200, 200, 220))

        pygame.display.flip()

    # -------------------------------------------------------
    # Input helpers: både keyboard + jk (joystick map)
    # -------------------------------------------------------
    def left_input(keys):
        """
        Vänster: W/S + jk (t.ex. joystick upp/ner)
        """
        move = 0.0
        if keys[pygame.K_w]:
            move -= 1.0
        if keys[pygame.K_s]:
            move += 1.0

        # jk (om du mappat upp/ner där)
        # Vi försöker vara kompatibla med flera namn:
        # - jk.up / jk.down kan vara bool
        # - jk.pressed("UP") / etc kan finnas
        try:
            if getattr(jk, "up", False):
                move -= 1.0
            if getattr(jk, "down", False):
                move += 1.0
        except Exception:
            pass

        return clamp(move, -1.0, 1.0)

    def right_input(keys):
        """
        Höger: pil upp/ner + jk också (så båda kan köra joystick om du vill)
        """
        move = 0.0
        if keys[pygame.K_UP]:
            move -= 1.0
        if keys[pygame.K_DOWN]:
            move += 1.0

        try:
            if getattr(jk, "up2", False):
                move -= 1.0
            if getattr(jk, "down2", False):
                move += 1.0
        except Exception:
            # om du inte har up2/down2 så gör inget
            pass

        return clamp(move, -1.0, 1.0)

    # -------------------------------------------------------
    # Main loop
    # -------------------------------------------------------
    while True:
        jk.update()
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {"result": "quit", "score": 0}

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {"result": "quit", "score": 0}

                if event.key == pygame.K_p and not game_over:
                    paused = not paused

                if event.key == pygame.K_r and game_over:
                    left_score = 0
                    right_score = 0
                    current_speed = base_ball_speed
                    game_over = False
                    winner_text = ""
                    ball_vel = reset_round()

        keys = pygame.key.get_pressed()

        if not paused and not game_over:
            # paddles
            lm = left_input(keys)
            rm = right_input(keys)

            left.y += int(lm * PADDLE_SPEED * dt)
            right.y += int(rm * PADDLE_SPEED * dt)

            left.y = clamp(left.y, 0, H - left.height)
            right.y = clamp(right.y, 0, H - right.height)

            # ball move
            ball.x += int(ball_vel[0] * dt)
            ball.y += int(ball_vel[1] * dt)

            # wall bounce
            if ball.top <= 0:
                ball.top = 0
                ball_vel[1] *= -1
            elif ball.bottom >= H:
                ball.bottom = H
                ball_vel[1] *= -1

            # paddle collide
            if ball.colliderect(left) and ball_vel[0] < 0:
                ball.left = left.right
                ball_vel[0], ball_vel[1] = bounce_from_paddle(left, ball_vel[0], ball_vel[1], is_left=True)

            if ball.colliderect(right) and ball_vel[0] > 0:
                ball.right = right.left
                ball_vel[0], ball_vel[1] = bounce_from_paddle(right, ball_vel[0], ball_vel[1], is_left=False)

            # score
            scored = False
            if ball.right < 0:
                right_score += 1
                scored = True
                serving_dir = -1
            elif ball.left > W:
                left_score += 1
                scored = True
                serving_dir = 1

            if scored:
                current_speed = min(max_ball_speed, current_speed * speed_growth)

                if left_score >= WIN_SCORE or right_score >= WIN_SCORE:
                    game_over = True
                    winner_text = "VÄNSTER VANN!" if left_score > right_score else "HÖGER VANN!"
                else:
                    ball_vel = reset_round(serving_dir=serving_dir)

        draw()
