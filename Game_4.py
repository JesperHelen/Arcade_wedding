import os
import random
import pygame
import joystick_keys as jk

def run(screen):
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont("consolas", 42, bold=True)
    font = pygame.font.SysFont("consolas", 22)




    # ----------------------------
    # Helpers: asset paths (sounds)
    # ----------------------------
    def base_dir():
        return os.path.dirname(os.path.abspath(__file__))

    def asset_path(*parts):
        candidates = [
            os.path.join(base_dir(), *parts),
            os.path.join(base_dir(), *[p.lower() for p in parts]),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return candidates[0]

    def sfx_path(name):
        # Lägg dina ljudfiler här (valfritt):
        #   Assets/Tetris/rad_1.wav ... rad_4.wav
        # eller Assets/SFX/rad_1.wav ... rad_4.wav
        # eller assets/sfx/...
        candidates = [
            asset_path("Assets", "Tetris", name),
            asset_path("Assets", "SFX", name),
            asset_path("assets", "tetris", name),
            asset_path("assets", "sfx", name),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return candidates[0]

    def load_sound(filename):
        try:
            if pygame.mixer.get_init():
                p = sfx_path(filename)
                if os.path.exists(p):
                    return pygame.mixer.Sound(p)
        except Exception:
            pass
        return None

    # Ljud: rad_1..rad_4 (wav/ogg funkar)

    snd_line = {
        1: [load_sound("rad_1.wav"), load_sound("rad_1.ogg"), load_sound("rad_1.mp3")],
        2: [load_sound("rad_2.wav"), load_sound("rad_2.ogg"), load_sound("rad_2.mp3")],
        3: [load_sound("rad_3.wav"), load_sound("rad_3.ogg"), load_sound("rad_3.mp3")],
        4: [
            load_sound("rad_4.wav"), load_sound("rad_4.ogg"), load_sound("rad_4.mp3"),
            load_sound("rad_4_2.wav"), load_sound("rad_4_2.ogg"), load_sound("rad_4_2.mp3"),
        ],
    }

    # Ta bort None
    for k in list(snd_line.keys()):
        snd_line[k] = [s for s in snd_line[k] if s is not None]

    # -----------------------
    # Board / layout
    # -----------------------
    COLS, ROWS = 10, 20
    PANEL_W = 240  # right info panel width

    # Tetris scoring (classic-ish)
    SCORE_PER_LINE = {1: 10, 2: 25, 3: 50, 4: 100}

    # Difficulty: target ~2 minutes survival at average play
    START_DROP_SEC = 0.78
    MIN_DROP_SEC = 0.12
    RAMP_PER_SEC = 0.0048  # higher = faster difficulty ramp

    # Input repeat (movement)
    MOVE_DAS = 0.13  # delay until repeat
    MOVE_ARR = 0.045  # repeat rate
    SOFT_DROP_MULT = 0.09  # drop interval multiplier when holding DOWN

    # Colors
    BG = (10, 10, 18)
    PANEL_BG = (14, 14, 24)
    TEXT = (235, 235, 245)

    COLORS = {
        "I": (140, 200, 255),
        "O": (255, 230, 140),
        "T": (220, 180, 255),
        "S": (140, 255, 170),
        "Z": (255, 120, 140),
        "J": (140, 200, 255),
        "L": (255, 170, 120),
    }

    # -----------------------
    # Tetromino definitions
    # -----------------------
    PIECES = {
        "I": [
            [(0, 1), (1, 1), (2, 1), (3, 1)],
            [(2, 0), (2, 1), (2, 2), (2, 3)],
        ],
        "O": [
            [(1, 1), (2, 1), (1, 2), (2, 2)],
        ],
        "T": [
            [(1, 1), (0, 2), (1, 2), (2, 2)],
            [(1, 1), (1, 2), (2, 2), (1, 3)],
            [(0, 2), (1, 2), (2, 2), (1, 3)],
            [(1, 1), (0, 2), (1, 2), (1, 3)],
        ],
        "S": [
            [(1, 1), (2, 1), (0, 2), (1, 2)],
            [(1, 1), (1, 2), (2, 2), (2, 3)],
        ],
        "Z": [
            [(0, 1), (1, 1), (1, 2), (2, 2)],
            [(2, 1), (1, 2), (2, 2), (1, 3)],
        ],
        "J": [
            [(0, 1), (0, 2), (1, 2), (2, 2)],
            [(1, 1), (2, 1), (1, 2), (1, 3)],
            [(0, 2), (1, 2), (2, 2), (2, 3)],
            [(1, 1), (1, 2), (0, 3), (1, 3)],
        ],
        "L": [
            [(2, 1), (0, 2), (1, 2), (2, 2)],
            [(1, 1), (1, 2), (1, 3), (2, 3)],
            [(0, 2), (1, 2), (2, 2), (0, 3)],
            [(0, 1), (1, 1), (1, 2), (1, 3)],
        ],
    }

    # 7-bag randomizer
    def new_bag():
        bag = list(PIECES.keys())
        random.shuffle(bag)
        return bag

    # -----------------------
    # Geometry / UI scaling
    # -----------------------
    def compute_layout():
        w, h = screen.get_size()
        max_cell_w = (w - PANEL_W - 60) // COLS
        max_cell_h = (h - 60) // ROWS
        cell = max(14, min(max_cell_w, max_cell_h))
        board_w = COLS * cell
        board_h = ROWS * cell
        ox = (w - (board_w + PANEL_W)) // 2
        oy = (h - board_h) // 2
        return w, h, cell, board_w, board_h, ox, oy

    def rect_for_cell(x, y, cell, ox, oy):
        return pygame.Rect(ox + x * cell, oy + y * cell, cell, cell)

    # -----------------------
    # Line clear "explosion" particles
    # -----------------------
    class Particle:
        __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "r", "col")

        def __init__(self, x, y, vx, vy, life, r, col):
            self.x = x
            self.y = y
            self.vx = vx
            self.vy = vy
            self.life = life
            self.max_life = life
            self.r = r
            self.col = col

        def update(self, dt):
            self.life -= dt
            if self.life <= 0:
                return False
            # lite "fall"
            self.vy += 900.0 * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            return True

        def draw(self, surf):
            a = max(0, min(255, int(255 * (self.life / self.max_life))))
            r = max(1, int(self.r * (0.6 + 0.4 * (self.life / self.max_life))))
            pygame.draw.circle(surf, (*self.col, a), (int(self.x), int(self.y)), r)

    particles = []

    def spawn_line_explosion(cleared_rows, cell, ox, oy):
        # Burst längs hela raden (cool men billig)
        for row_y in cleared_rows:
            y0 = oy + row_y * cell + cell // 2
            for x in range(COLS):
                x0 = ox + x * cell + cell // 2
                # färg: ta från block om finns, annars vit-ish
                c = board[row_y][x] if 0 <= row_y < ROWS else None
                col = c if c is not None else (245, 245, 255)

                # lite fler partiklar per cell
                for _ in range(6):
                    vx = random.uniform(-420, 420)
                    vy = random.uniform(-520, -120)
                    life = random.uniform(0.25, 0.55)
                    r = random.uniform(2.0, 4.5)
                    particles.append(Particle(x0, y0, vx, vy, life, r, col))

    # -----------------------
    # Game state
    # -----------------------
    board = [[None for _ in range(COLS)] for _ in range(ROWS)]
    bag = new_bag()
    next_piece = bag.pop()

    score = 0
    lines = 0
    t = 0.0

    # active piece
    cur_type = None
    cur_rot = 0
    cur_x = 3
    cur_y = 0

    # tick timers
    drop_acc = 0.0

    # input repeat state
    move_left = False
    move_right = False
    das_timer = 0.0
    arr_timer = 0.0
    last_dir = 0  # -1 left, +1 right

    def get_blocks(ptype, rot):
        rots = PIECES[ptype]
        r = rot % len(rots)
        return rots[r]

    def can_place(ptype, rot, x, y):
        blocks = get_blocks(ptype, rot)
        for bx, by in blocks:
            gx = x + bx
            gy = y + by
            if gx < 0 or gx >= COLS or gy < 0 or gy >= ROWS:
                return False
            if board[gy][gx] is not None:
                return False
        return True

    def clear_lines_and_get_rows():
        """
        Tar bort fulla rader.
        Returnerar (antal_cleared, lista_med_cleared_row_indices_innan_shift)
        """
        nonlocal board, lines
        cleared_rows = []
        new_rows = []

        for y, row in enumerate(board):
            if all(cell is not None for cell in row):
                cleared_rows.append(y)
            else:
                new_rows.append(row)

        cleared = len(cleared_rows)

        while len(new_rows) < ROWS:
            new_rows.insert(0, [None for _ in range(COLS)])

        board = new_rows
        lines += cleared
        return cleared, cleared_rows

    def spawn_piece():
        """
        Returns True if spawned successfully, False if game over (can't place).
        """
        nonlocal cur_type, cur_rot, cur_x, cur_y, next_piece, bag
        cur_type = next_piece
        cur_rot = 0
        cur_x = 3
        cur_y = 0

        if not bag:
            bag = new_bag()
        next_piece = bag.pop()

        return can_place(cur_type, cur_rot, cur_x, cur_y)

    def lock_piece(cell, ox, oy):
        """
        Locks current piece. Returns True if next piece spawns, False => game over.
        """
        nonlocal score

        blocks = get_blocks(cur_type, cur_rot)
        for bx, by in blocks:
            gx = cur_x + bx
            gy = cur_y + by
            if 0 <= gy < ROWS and 0 <= gx < COLS:
                board[gy][gx] = COLORS[cur_type]

        cleared, cleared_rows = clear_lines_and_get_rows()

        if cleared:
            # score
            score += SCORE_PER_LINE.get(cleared, 0)

            # play correct sound rad_1..rad_4
            sounds = snd_line.get(min(4, cleared), [])
            if sounds:
                try:
                    random.choice(sounds).play()
                except Exception:
                    pass


            # explosion effect (spawn AFTER clear_lines removed them? -> vi vill effekten på gamla rader)
            # Vi använder cleared_rows från "innan shift" men board är nu shufflad.
            # För att effekten ska hamna rätt visuellt ändå: vi spawna på de y-indexen direkt när clear sker.
            spawn_line_explosion(cleared_rows, cell, ox, oy)

        return spawn_piece()

    def rotate():
        nonlocal cur_rot, cur_x, cur_y
        nr = cur_rot + 1
        for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (-2, 0), (2, 0)]:
            if can_place(cur_type, nr, cur_x + dx, cur_y + dy):
                cur_rot = nr
                cur_x += dx
                cur_y += dy
                return

    def hard_drop(cell, ox, oy):
        nonlocal cur_y, score
        while can_place(cur_type, cur_rot, cur_x, cur_y + 1):
            cur_y += 1

        score += 1  # exakt 1 poäng per hard drop
        ok = lock_piece(cell, ox, oy)
        return ok

    # start first piece
    if not spawn_piece():
        return {"result": "game_over", "score": int(score)}

    # -----------------------
    # Drawing helpers
    # -----------------------
    def draw_block(r, color, cell):
        pygame.draw.rect(screen, color, r, border_radius=max(3, cell // 6))
        hi = pygame.Rect(r.x + 2, r.y + 2, r.w - 4, r.h - 4)
        pygame.draw.rect(screen, (255, 255, 255), hi, width=1, border_radius=max(3, cell // 6))

    def draw_piece(ptype, rot, x, y, cell, ox, oy, alpha=255):
        blocks = get_blocks(ptype, rot)
        col = COLORS[ptype]
        for bx, by in blocks:
            gx = x + bx
            gy = y + by
            rr = rect_for_cell(gx, gy, cell, ox, oy)
            if alpha != 255:
                surf = pygame.Surface((rr.w, rr.h), pygame.SRCALPHA)
                pygame.draw.rect(
                    surf,
                    (*col, alpha),
                    pygame.Rect(0, 0, rr.w, rr.h),
                    border_radius=max(3, cell // 6),
                )
                screen.blit(surf, (rr.x, rr.y))
            else:
                draw_block(rr, col, cell)

    def draw_ghost_piece(cell, ox, oy):
        gy = cur_y
        while can_place(cur_type, cur_rot, cur_x, gy + 1):
            gy += 1
        draw_piece(cur_type, cur_rot, cur_x, gy, cell, ox, oy, alpha=70)

    # -----------------------
    # Main loop
    # -----------------------
    while True:
        dt = clock.tick(120) / 1000.0
        jk.update()
        if dt > 0.05:
            dt = 0.05

        w, h, cell, board_w, board_h, ox, oy = compute_layout()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {"result": "quit", "score": int(score)}

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {"result": "quit", "score": int(score)}

                if event.key == pygame.K_LEFT:
                    move_left = True
                    last_dir = -1
                    das_timer = 0.0
                    arr_timer = 0.0
                    if can_place(cur_type, cur_rot, cur_x - 1, cur_y):
                        cur_x -= 1

                elif event.key == pygame.K_RIGHT:
                    move_right = True
                    last_dir = 1
                    das_timer = 0.0
                    arr_timer = 0.0
                    if can_place(cur_type, cur_rot, cur_x + 1, cur_y):
                        cur_x += 1

                elif event.key == pygame.K_UP:
                    rotate()

                elif event.key == pygame.K_SPACE or event.key == pygame.K_RETURN:
                    ok = hard_drop(cell, ox, oy)
                    if not ok:
                        return {"result": "game_over", "score": int(score)}

            if event.type == pygame.KEYUP:
                if event.key == pygame.K_LEFT:
                    move_left = False
                    if last_dir == -1:
                        das_timer = 0.0
                        arr_timer = 0.0
                elif event.key == pygame.K_RIGHT:
                    move_right = False
                    if last_dir == 1:
                        das_timer = 0.0
                        arr_timer = 0.0

        # update
        t += dt

        # update particles
        if particles:
            particles[:] = [p for p in particles if p.update(dt)]

        # horizontal auto-repeat
        held_dir = 0
        if move_left and not move_right:
            held_dir = -1
        elif move_right and not move_left:
            held_dir = 1

        if held_dir != 0:
            if held_dir != last_dir:
                last_dir = held_dir
                das_timer = 0.0
                arr_timer = 0.0
            else:
                das_timer += dt
                if das_timer >= MOVE_DAS:
                    arr_timer += dt
                    while arr_timer >= MOVE_ARR:
                        arr_timer -= MOVE_ARR
                        if can_place(cur_type, cur_rot, cur_x + held_dir, cur_y):
                            cur_x += held_dir
                        else:
                            break
        else:
            last_dir = 0
            das_timer = 0.0
            arr_timer = 0.0

        # drop speed ramp
        drop_sec = max(MIN_DROP_SEC, START_DROP_SEC - RAMP_PER_SEC * t)

        # soft drop
        keys = pygame.key.get_pressed()
        if keys[pygame.K_DOWN]:
            drop_sec *= SOFT_DROP_MULT

        drop_acc += dt
        while drop_acc >= drop_sec:
            drop_acc -= drop_sec
            if can_place(cur_type, cur_rot, cur_x, cur_y + 1):
                cur_y += 1
            else:
                ok = lock_piece(cell, ox, oy)
                if not ok:
                    return {"result": "game_over", "score": int(score)}

        # -----------------------
        # Draw
        # -----------------------
        screen.fill(BG)

        # board background panel
        board_rect = pygame.Rect(ox - 10, oy - 10, board_w + 20, board_h + 20)
        pygame.draw.rect(screen, (18, 18, 30), board_rect, border_radius=18)

        # grid / cells
        for y in range(ROWS):
            for x in range(COLS):
                r = rect_for_cell(x, y, cell, ox, oy)
                pygame.draw.rect(screen, (255, 255, 255), r, width=1, border_radius=max(3, cell // 7))
                c = board[y][x]
                if c is not None:
                    draw_block(r, c, cell)

        # pieces
        draw_ghost_piece(cell, ox, oy)
        draw_piece(cur_type, cur_rot, cur_x, cur_y, cell, ox, oy)

        # particles overlay (explosions)
        if particles:
            fx = pygame.Surface((w, h), pygame.SRCALPHA)
            for p in particles:
                p.draw(fx)
            screen.blit(fx, (0, 0))

        # right panel
        panel_x = ox + board_w + 30
        panel = pygame.Rect(panel_x, oy - 10, PANEL_W, board_h + 20)
        pygame.draw.rect(screen, PANEL_BG, panel, border_radius=18)

        # HUD text
        drop_sec_now = max(MIN_DROP_SEC, START_DROP_SEC - RAMP_PER_SEC * t)
        level_like = 1 + int((START_DROP_SEC - drop_sec_now) / 0.08)

        text_y = oy + 10

        def blit_label(label, value):
            nonlocal text_y
            a = font.render(label, True, (200, 200, 220))
            b = font.render(str(value), True, TEXT)
            screen.blit(a, (panel_x + 18, text_y))
            screen.blit(b, (panel_x + 18, text_y + 24))
            text_y += 62

        blit_label("SCORE", score)
        blit_label("LINES", lines)
        blit_label("LVL", level_like)
        blit_label("TIME", f"{t:0.0f}s")

        # next piece preview
        label = font.render("NEXT", True, (200, 200, 220))
        screen.blit(label, (panel_x + 18, text_y))
        preview_box = pygame.Rect(panel_x + 18, text_y + 32, 120, 120)
        pygame.draw.rect(screen, (22, 22, 36), preview_box, border_radius=14)

        px0, py0 = preview_box.x + 20, preview_box.y + 20
        mini = max(12, cell // 2)
        for bx, by in get_blocks(next_piece, 0):
            rr = pygame.Rect(px0 + bx * mini, py0 + by * mini, mini, mini)
            pygame.draw.rect(screen, COLORS[next_piece], rr, border_radius=max(3, mini // 6))
            pygame.draw.rect(screen, (255, 255, 255), rr, width=1, border_radius=max(3, mini // 6))

        # Controls hint
        hint = [
            "← → flytta",
            "↑ rotera",
            "↓ soft drop",
            "SPACE hard drop",
            "ESC tillbaka",
        ]
        hy = oy + board_h - 10 - len(hint) * 22
        for s in hint:
            tx = font.render(s, True, (170, 170, 195))
            screen.blit(tx, (panel_x + 18, hy))
            hy += 22


        pygame.display.flip()
