# joystick_keys.py
import pygame
import joystick_keys as jk
# ----------------------------
# Button mapping (ändra om dina index skiljer)
# ----------------------------
BTN_K1 = 0   # -> ESC
BTN_K2 = 1   # -> ENTER
BTN_K3 = 2   # -> W
BTN_K4 = 3   # -> A
BTN_K5 = 4   # -> S
BTN_K6 = 5   # -> D
# Action 2 (knappen bredvid Action 1). Kolla numret med: jstest /dev/input/js0
# (tryck Action 2 och se vilken Button som slår om) och ändra här om det inte stämmer.
BTN_ACT2 = 6  # -> Q
BTN_COIN = 7  # Coin: används inte i spelen, visas bara i knapppanelen. Kolla numret med jstest.

# ----------------------------
# Axis config
# ----------------------------
AXIS_X = 0          # ändra om din vänster/höger ligger på annan axel
AXIS_Y = 1          # hos dig såg vi AXIS 1 = -1.0 vid upp, så denna är rätt
DEADZONE = 0.45

_inited = False
_joy = None

_prev = {
    "up": False, "down": False, "left": False, "right": False,
    "esc": False, "enter": False, "act2": False, "coin": False,
    "w": False, "a": False, "s": False, "d": False,
}

def _post_key(key, down: bool):
    evtype = pygame.KEYDOWN if down else pygame.KEYUP
    pygame.event.post(pygame.event.Event(evtype, {"key": key}))

def init(joystick_index=0):
    """Initieras automatiskt första gången update() körs."""
    global _inited, _joy
    if _inited:
        return

    pygame.joystick.init()
    if pygame.joystick.get_count() > 0:
        _joy = pygame.joystick.Joystick(joystick_index)
        _joy.init()
    else:
        _joy = None

    _inited = True

def update():
    """
    Kör EN gång per frame, innan du gör pygame.event.get().
    Skapar KEYDOWN/KEYUP events från joystick:
      - joystick riktning -> piltangenter
      - K1..K6 -> ESC/ENTER/W/A/S/D, Action 2 -> Q
    """
    if not _inited:
        init()

    if _joy is None:
        return

    # VIKTIGT: uppdatera Pygames intern-state för joystick innan get_axis/get_hat
    pygame.event.pump()

    # ----------------------------
    # Read direction
    # ----------------------------
    left = right = up = down = False

    # 1) Hat om den faktiskt ger något (din hat finns men var alltid (0,0))
    use_axes = True
    if _joy.get_numhats() > 0:
        hx, hy = _joy.get_hat(0)
        if (hx, hy) != (0, 0):
            use_axes = False
            left  = (hx == -1)
            right = (hx == 1)
            up    = (hy == 1)
            down  = (hy == -1)

    # 2) Annars: axlar (analog)
    if use_axes:
        try:
            ax = float(_joy.get_axis(AXIS_X))
        except Exception:
            ax = 0.0
        try:
            ay = float(_joy.get_axis(AXIS_Y))
        except Exception:
            ay = 0.0

        left  = ax < -DEADZONE
        right = ax >  DEADZONE
        up    = ay < -DEADZONE
        down  = ay >  DEADZONE

    # ----------------------------
    # Read buttons
    # ----------------------------
    def b(i: int) -> bool:
        try:
            return bool(_joy.get_button(i))
        except Exception:
            return False

    esc   = b(BTN_K1)
    act2  = b(BTN_ACT2)
    coin  = b(BTN_COIN)
    enter = b(BTN_K2)
    w     = b(BTN_K3)
    a     = b(BTN_K4)
    s     = b(BTN_K5)
    d     = b(BTN_K6)

    now = {
        "left": left, "right": right, "up": up, "down": down,
        "esc": esc, "enter": enter, "act2": act2, "coin": coin,
        "w": w, "a": a, "s": s, "d": d,
    }

    # ----------------------------
    # Post events on edges only
    # ----------------------------
    def edge(name: str, key: int):
        if now[name] != _prev[name]:
            _post_key(key, now[name])
            _prev[name] = now[name]

    # Direction -> arrow keys
    edge("left", pygame.K_LEFT)
    edge("right", pygame.K_RIGHT)
    edge("up", pygame.K_UP)
    edge("down", pygame.K_DOWN)

    # Buttons
    edge("esc", pygame.K_ESCAPE)
    edge("enter", pygame.K_RETURN)
    edge("act2", pygame.K_q)

    edge("w", pygame.K_w)
    edge("a", pygame.K_a)
    edge("s", pygame.K_s)
    edge("d", pygame.K_d)

    _prev["coin"] = coin


def pressed():
    """Vilka knappar/riktningar på joysticken som är nedtryckta just nu (för knapppanelen)."""
    return dict(_prev)


def raw_buttons():
    """Numren på alla joystickknappar som hålls in just nu (för felsökning)."""
    if _joy is None:
        return []
    out = []
    for i in range(_joy.get_numbuttons()):
        try:
            if _joy.get_button(i):
                out.append(i)
        except Exception:
            pass
    return out
