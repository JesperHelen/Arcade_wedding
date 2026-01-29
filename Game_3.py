import os
import random
import pygame
from collections import deque


def run(screen):
    clock = pygame.time.Clock()
    font_big = pygame.font.SysFont("consolas", 40, bold=True)
    font = pygame.font.SysFont("consolas", 22)

    # ----------------------------
    # (valfritt) stoppa ev. bakgrundsmusik i lobby
    # ----------------------------
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except Exception:
        pass

    # ----------------------------
    # Helpers: asset paths
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

    def pacman_asset(name):
        # DINA spökbilder ligger här:
        #   Assets/pac-man/1.png ... 4.png
        candidates = [
            asset_path("Assets", "pac-man", name),
            asset_path("assets", "pac-man", name),

            # om du råkar ha annan casing på Windows ibland:
            asset_path("Assets", "Pac-Man", name),
            asset_path("assets", "Pac-Man", name),
            asset_path("Assets", "PAC-MAN", name),
            asset_path("assets", "PAC-MAN", name),

            # (valfritt) om du vill stödja den gamla också:
            asset_path("Assets", "Pacman", name),
            asset_path("assets", "pacman", name),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return candidates[0]

    def load_img_safe(name):
        try:
            p = pacman_asset(name)
            if os.path.exists(p):
                return pygame.image.load(p).convert_alpha()
        except Exception:
            pass
        return None


    # ----------------------------
    # Base Maze (20x15)
    # Legend: # wall, . pellet, ' ' empty
    # ----------------------------
    BASE = [
        "####################",
        "#........##........#",
        "#.####...##...####.#",
        "#.#  #........#  #.#",
        "#.####.######.####.#",
        "#..................#",
        "#.####.##..##.####.#",
        "#......##..##......#",
        "######.##..##.######",
        "#........##........#",
        "#.####...##...####.#",
        "#...##........##...#",
        "###.##.######.##.###",
        "#........##........#",
        "####################",
    ]

    # Expand requirement: 3x width, 2x height (som du hade)
    TILE_X = 3
    TILE_Y = 2

    # Difficulty tuning
    BASE_PAC_TPS = 5.5
    BASE_GHOST_TPS = 3.2
    GHOST_TPS_RAMP = 0.11
    CHASE_RAMP = 0.006
    MAX_GHOST_TPS = 17.0
    ADD_GHOST_AT = 40.0
    ADD_GHOST_2_AT = 75.0

    # Chili powerup
    CHILI_COUNT = 2
    CHILI_DURATION = 10.0
    CHILI_FREEZE = 10.0

    # Colors
    C_BG = (10, 10, 18)
    C_WALL = (80, 120, 255)
    C_PELLET = (245, 245, 255)
    C_PAC = (255, 230, 140)
    C_PAC_BLINK = (255, 140, 90)
    C_CHILI = (255, 70, 60)
    C_CHILI_STEM = (60, 210, 120)

    # -------------------------------------------------
    # Build bigger maze by tiling BASE (TILE_X x TILE_Y)
    # -------------------------------------------------
    def build_big_maze():
        bh = len(BASE)
        bw = len(BASE[0])
        H = bh * TILE_Y
        W = bw * TILE_X

        grid = []
        for ty in range(TILE_Y):
            for y in range(bh):
                row = []
                for tx in range(TILE_X):
                    row.extend(list(BASE[y]))
                grid.append(row)

        # Carve vertical doors between tiles
        for tx in range(1, TILE_X):
            seam_left = tx * bw - 1
            seam_right = tx * bw
            for ty in range(TILE_Y):
                base_y = ty * bh
                for off in (5, 9):
                    y = base_y + off
                    if 0 <= y < H:
                        grid[y][seam_left] = "."
                        grid[y][seam_right] = "."

        # Carve horizontal doors between tiles
        for ty in range(1, TILE_Y):
            seam_up = ty * bh - 1
            seam_down = ty * bh
            for tx in range(TILE_X):
                base_x = tx * bw
                for off in (6, 13):
                    x = base_x + off
                    if 0 <= x < W:
                        grid[seam_up][x] = "."
                        grid[seam_down][x] = "."

        return ["".join(r) for r in grid]

    MAZE = build_big_maze()
    ROWS = len(MAZE)
    COLS = len(MAZE[0])

    # -------------------------------------------------
    # Layout
    # -------------------------------------------------
    def calc_cell_and_offsets():
        w, h = screen.get_size()
        cell = max(10, min(w // COLS, h // ROWS))
        board_w = COLS * cell
        board_h = ROWS * cell
        ox = (w - board_w) // 2
        oy = (h - board_h) // 2
        return w, h, cell, ox, oy

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------
    def clamp(v, a, b):
        return max(a, min(b, v))

    def in_bounds(x, y):
        return 0 <= x < COLS and 0 <= y < ROWS

    def is_wall(x, y):
        return MAZE[y][x] == "#"

    def neighbors(x, y):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if in_bounds(nx, ny) and not is_wall(nx, ny):
                yield nx, ny

    def bfs_next_step(start, goal):
        if start == goal:
            return start
        q = deque([start])
        prev = {start: None}
        while q:
            cur = q.popleft()
            if cur == goal:
                break
            for nb in neighbors(*cur):
                if nb not in prev:
                    prev[nb] = cur
                    q.append(nb)
        if goal not in prev:
            return start
        cur = goal
        while prev[cur] != start and prev[cur] is not None:
            cur = prev[cur]
        return cur

    def build_pellets():
        pel = set()
        for y in range(ROWS):
            for x in range(COLS):
                if MAZE[y][x] == ".":
                    pel.add((x, y))
        return pel

    def grid_to_center_px(x, y, cell, ox, oy):
        return ox + x * cell + cell // 2, oy + y * cell + cell // 2

    def random_open_cell(exclude=set()):
        for _ in range(2000):
            x = random.randint(1, COLS - 2)
            y = random.randint(1, ROWS - 2)
            if not is_wall(x, y) and (x, y) not in exclude:
                return (x, y)
        for y in range(1, ROWS - 1):
            for x in range(1, COLS - 1):
                if not is_wall(x, y) and (x, y) not in exclude:
                    return (x, y)
        return (1, 1)

    # ----------------------------
    # Ghost PNGs: 1.png..4.png
    # Om fler spöken än 4 -> använd 2.png
    # ----------------------------
    ghost_png_raw = [
        load_img_safe("1.png"),
        load_img_safe("2.png"),
        load_img_safe("3.png"),
        load_img_safe("4.png"),
    ]

    def ghost_img_for_index(i, cell):
        # index: 0..n-1
        # 0->1.png, 1->2.png, 2->3.png, 3->4.png, >=4 -> 2.png
        idx = i if i < 4 else 1
        img = ghost_png_raw[idx]
        if img is None:
            return None

        # skala lite snyggt (lite mindre än cell så det blir luft)
        target = max(8, int(cell * 0.92))
        return pygame.transform.smoothscale(img, (target, target))

    # cache per cell-size så vi inte reskalar varje frame
    ghost_img_cache = {}  # key: (cell, i) -> Surface/None

    def get_ghost_img(i, cell):
        key = (cell, i)
        if key in ghost_img_cache:
            return ghost_img_cache[key]
        ghost_img_cache[key] = ghost_img_for_index(i, cell)
        return ghost_img_cache[key]

    # -------------------------------------------------
    # Chili placement
    # -------------------------------------------------
    def ensure_chilis():
        nonlocal chilis
        needed = CHILI_COUNT - len(chilis)
        if needed <= 0:
            return
        exclude = set(chilis)
        exclude.add(pac_pos)
        for g in ghosts:
            exclude.add(g["pos"])
        for _ in range(needed):
            pos = random_open_cell(exclude)
            chilis.add(pos)
            exclude.add(pos)

    # -------------------------------------------------
    # Drawing
    # -------------------------------------------------
    def draw_board(cell, ox, oy, pellets):
        screen.fill(C_BG)
        for y in range(ROWS):
            for x in range(COLS):
                if is_wall(x, y):
                    r = pygame.Rect(ox + x * cell, oy + y * cell, cell, cell)
                    pygame.draw.rect(screen, C_WALL, r, border_radius=max(4, cell // 6))

        pr = max(2, cell // 9)
        for (x, y) in pellets:
            cx, cy = grid_to_center_px(x, y, cell, ox, oy)
            pygame.draw.circle(screen, C_PELLET, (cx, cy), pr)

    def draw_chili(pos, cell, ox, oy):
        cx, cy = grid_to_center_px(pos[0], pos[1], cell, ox, oy)
        r = max(4, int(cell * 0.20))
        pygame.draw.circle(screen, C_CHILI, (cx, cy), r)
        pygame.draw.circle(screen, C_CHILI_STEM, (cx + r // 2, cy - r // 2), max(2, r // 3))

    def draw_pacman(pos, dirv, cell, ox, oy, t, blink_on, blink_active):
        if blink_active and not blink_on:
            return
        cx, cy = grid_to_center_px(pos[0], pos[1], cell, ox, oy)
        r = int(cell * 0.44)

        phase = (t * 9.0) % 1.0
        openness = 0.5 - 0.5 * (2 * abs(phase - 0.5))
        mouth_deg = 12 + int(38 * openness)

        dx, dy = dirv
        if (dx, dy) == (1, 0):
            base_ang = 0
        elif (dx, dy) == (-1, 0):
            base_ang = 180
        elif (dx, dy) == (0, -1):
            base_ang = 90
        else:
            base_ang = 270

        color = C_PAC_BLINK if blink_active else C_PAC
        if blink_active and blink_on:
            color = (min(255, color[0] + 30), min(255, color[1] + 30), min(255, color[2] + 30))

        pygame.draw.circle(screen, color, (cx, cy), r)

        # mouth wedge
        v1 = pygame.math.Vector2(1, 0).rotate(-(base_ang + mouth_deg))
        v2 = pygame.math.Vector2(1, 0).rotate(-(base_ang - mouth_deg))
        p1 = (cx + int(r * 1.2 * v1.x), cy + int(r * 1.2 * v1.y))
        p2 = (cx + int(r * 1.2 * v2.x), cy + int(r * 1.2 * v2.y))
        pygame.draw.polygon(screen, C_BG, [(cx, cy), p1, p2])

    def draw_ghost_png(pos, cell, ox, oy, img, frozen=False):
        cx, cy = grid_to_center_px(pos[0], pos[1], cell, ox, oy)
        if img is None:
            # fallback om bild saknas
            r = int(cell * 0.42)
            col = (180, 180, 200) if not frozen else (120, 120, 140)
            pygame.draw.circle(screen, col, (cx, cy), r)
            return

        rect = img.get_rect(center=(cx, cy))

        if frozen:
            # tona ner + liten “ice-ring”
            tmp = img.copy()
            tmp.fill((255, 255, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(tmp, rect.topleft)
            pygame.draw.circle(screen, (210, 240, 255), (cx, cy - int(cell * 0.35)), max(2, cell // 10), 1)
        else:
            screen.blit(img, rect.topleft)

    # -------------------------------------------------
    # State
    # -------------------------------------------------
    def find_spawn_open(prefer_x, prefer_y):
        if not is_wall(prefer_x, prefer_y):
            return (prefer_x, prefer_y)
        for rad in range(1, 30):
            for _ in range(80):
                x = clamp(prefer_x + random.randint(-rad, rad), 1, COLS - 2)
                y = clamp(prefer_y + random.randint(-rad, rad), 1, ROWS - 2)
                if not is_wall(x, y):
                    return (x, y)
        for y in range(1, ROWS - 1):
            for x in range(1, COLS - 1):
                if not is_wall(x, y):
                    return (x, y)
        return (1, 1)

    def reset():
        nonlocal pac_pos, pac_dir, pac_next_dir, pellets, ghosts, score, t
        nonlocal pac_tick, ghost_tick
        nonlocal chilis, blink_timer, blink_accum, blink_on

        pellets = build_pellets()
        score = 0
        t = 0.0

        pac_pos = find_spawn_open(1, 1)
        pac_dir = (1, 0)
        pac_next_dir = (1, 0)

        ghosts = []
        ghosts.append({"pos": find_spawn_open(COLS - 2, 1), "dir": (-1, 0), "freeze": 0.0})
        ghosts.append({"pos": find_spawn_open(COLS - 2, ROWS - 2), "dir": (-1, 0), "freeze": 0.0})
        ghosts.append({"pos": find_spawn_open(1, ROWS - 2), "dir": (1, 0), "freeze": 0.0})

        pac_tick = 0.0
        ghost_tick = 0.0

        chilis = set()
        blink_timer = 0.0
        blink_accum = 0.0
        blink_on = True
        ensure_chilis()

    pac_pos = (1, 1)
    pac_dir = (1, 0)
    pac_next_dir = (1, 0)
    pellets = set()
    ghosts = []
    score = 0
    t = 0.0
    pac_tick = 0.0
    ghost_tick = 0.0

    chilis = set()
    blink_timer = 0.0
    blink_accum = 0.0
    blink_on = True

    reset()

    # -------------------------------------------------
    # Main loop
    # -------------------------------------------------
    while True:
        dt = clock.tick(120) / 1000.0
        if dt > 0.05:
            dt = 0.05

        w, h, cell, ox, oy = calc_cell_and_offsets()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {"result": "quit", "score": int(score)}

                if event.key in (pygame.K_UP, pygame.K_w):
                    pac_next_dir = (0, -1)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    pac_next_dir = (0, 1)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    pac_next_dir = (-1, 0)
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    pac_next_dir = (1, 0)

        # timers
        t += dt

        # blink: snabbare och snabbare ju närmare 0
        blink_active = blink_timer > 0.0
        if blink_timer > 0.0:
            blink_timer -= dt
            rem = max(0.0, blink_timer)
            interval = 0.05 + 0.25 * (rem / CHILI_DURATION)
            blink_accum += dt
            while blink_accum >= interval:
                blink_accum -= interval
                blink_on = not blink_on
        else:
            blink_on = True
            blink_accum = 0.0

        # ghost freeze timers
        for g in ghosts:
            if g["freeze"] > 0.0:
                g["freeze"] = max(0.0, g["freeze"] - dt)

        # add ghosts over time
        if t >= ADD_GHOST_AT and len(ghosts) < 4:
            ghosts.append({"pos": find_spawn_open(1, ROWS - 2), "dir": (1, 0), "freeze": 0.0})
        if t >= ADD_GHOST_2_AT and len(ghosts) < 5:
            ghosts.append({"pos": find_spawn_open(COLS // 2, ROWS // 2), "dir": (1, 0), "freeze": 0.0})

        # speed settings
        pac_tps = BASE_PAC_TPS
        ghost_tps = min(MAX_GHOST_TPS, BASE_GHOST_TPS + GHOST_TPS_RAMP * t)
        chase_p = min(0.92, 0.18 + CHASE_RAMP * t)

        # Pac ticks
        pac_tick += dt
        pac_interval = 1.0 / pac_tps
        while pac_tick >= pac_interval:
            pac_tick -= pac_interval

            px, py = pac_pos

            ndx, ndy = pac_next_dir
            tx, ty = px + ndx, py + ndy
            if in_bounds(tx, ty) and not is_wall(tx, ty):
                pac_dir = pac_next_dir

            dx, dy = pac_dir
            nx, ny = px + dx, py + dy
            if in_bounds(nx, ny) and not is_wall(nx, ny):
                pac_pos = (nx, ny)

            # pellets
            if pac_pos in pellets:
                pellets.remove(pac_pos)
                score += 0.5

            # chili pickup
            if pac_pos in chilis:
                chilis.remove(pac_pos)
                blink_timer = CHILI_DURATION
                blink_accum = 0.0
                blink_on = True

            # keep 2 chilis on map
            ensure_chilis()

            # loop pellets
            if not pellets:
                score += 50
                pellets = build_pellets()
                pac_pos = find_spawn_open(1, 1)
                ensure_chilis()

        # Ghost ticks
        ghost_tick += dt
        ghost_interval = 1.0 / ghost_tps
        while ghost_tick >= ghost_interval:
            ghost_tick -= ghost_interval

            for g in ghosts:
                if g["freeze"] > 0.0:
                    continue

                gx, gy = g["pos"]

                possible = []
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = gx + dx, gy + dy
                    if in_bounds(nx, ny) and not is_wall(nx, ny):
                        possible.append((dx, dy))

                cdx, cdy = g["dir"]
                at_intersection = len(possible) >= 3 or (cdx, cdy) not in possible

                if at_intersection and possible:
                    if random.random() < chase_p:
                        step = bfs_next_step(g["pos"], pac_pos)
                        sx, sy = step
                        dx, dy = sx - gx, sy - gy
                        if (dx, dy) in possible:
                            g["dir"] = (dx, dy)
                        else:
                            g["dir"] = random.choice(possible)
                    else:
                        rev = (-cdx, -cdy)
                        opts = [d for d in possible if d != rev]
                        g["dir"] = random.choice(opts if opts else possible)

                dx, dy = g["dir"]
                nx, ny = gx + dx, gy + dy
                if in_bounds(nx, ny) and not is_wall(nx, ny):
                    g["pos"] = (nx, ny)

        # collision handling (efter movement)
        for g in ghosts:
            if g["pos"] == pac_pos:
                if blink_active:
                    # under blink: gå igenom + fryser spöket
                    g["freeze"] = CHILI_FREEZE
                else:
                    return {"result": "game_over", "score": int(score)}

        # Draw
        draw_board(cell, ox, oy, pellets)

        # chilis
        for c in chilis:
            draw_chili(c, cell, ox, oy)

        # pac
        draw_pacman(pac_pos, pac_dir, cell, ox, oy, t, blink_on=blink_on, blink_active=blink_active)

        # ghosts (PNG)
        for i, g in enumerate(ghosts):
            img = get_ghost_img(i, cell)
            draw_ghost_png(g["pos"], cell, ox, oy, img, frozen=(g["freeze"] > 0.0))

        # HUD
        ghost_tps_now = min(MAX_GHOST_TPS, BASE_GHOST_TPS + GHOST_TPS_RAMP * t)
        chase_p_now = min(0.92, 0.18 + CHASE_RAMP * t)

        hud1 = font.render(f"SCORE: {score}", True, (230, 230, 240))
        hud2 = font.render(f"GHOST SPEED: {ghost_tps_now:0.1f} tps", True, (180, 180, 200))
        hud3 = font.render(f"CHASE: {int(chase_p_now * 100)}%", True, (180, 180, 200))
        if blink_active:
            hud4 = font.render(f"CHILI BLINK: {blink_timer:0.1f}s", True, (255, 190, 160))
        else:
            hud4 = font.render("CHILI BLINK: -", True, (180, 180, 200))

        screen.blit(hud1, (24, 18))
        screen.blit(hud2, (24, 44))
        screen.blit(hud3, (24, 70))
        screen.blit(hud4, (24, 96))

        pygame.display.flip()
