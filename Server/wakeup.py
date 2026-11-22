#!/usr/bin/env python3
# wakeup.py — esibizione di risveglio del ragno acrilico (≈33 s), sempre sul posto.
#
# 12 servi:
#   M (middle) = corpo: altezza, pitch (avanti/indietro), roll (destra/sinistra)
#   B (base)   = rotazione della zampa (passo, appoggio)
#   E (end)    = articolazione finale (sollevare, allungare, onda)
#
# REGOLA DELLE DIAGONALI: quando una zampa si allunga in avanti, la diagonale
# opposta si allunga all'indietro, nello stesso istante. Così il corpo non
# trasla mai: il ragno "cammina" restando fermo.
#
# Luci: strisce "polizia" per tutta la durata, LED frontale (P2) fisso;
# alla fine LED spento e strisce in respiro lento.
#
# Velocità: 3 unità PWM per passo, 2 ms (~7 ms reali: costa il bus I2C).

import time
import SpiderG

PORTS = {
    'FLB': SpiderG.FLB_port, 'FLM': SpiderG.FLM_port, 'FLE': SpiderG.FLE_port,
    'FRB': SpiderG.FRB_port, 'FRM': SpiderG.FRM_port, 'FRE': SpiderG.FRE_port,
    'HLB': SpiderG.HLB_port, 'HLM': SpiderG.HLM_port, 'HLE': SpiderG.HLE_port,
    'HRB': SpiderG.HRB_port, 'HRM': SpiderG.HRM_port, 'HRE': SpiderG.HRE_port,
}

UNITS = 3
STEP = 0.002
PAUSE = 0.10
MAX_TIME = 3.0
FRONT_LED_PORT = 2

# Ampiezze (unità PWM). Se una mossa va nel verso sbagliato, si cambia il segno.
DIAG_B = 26      # base: allungo diagonale avanti/indietro
DIAG_E = 20      # articolazione finale durante l'allungo diagonale
TILT_E = 34      # sollevamento/estensione zampe per inclinare il corpo

current = {}


# ── motore ──────────────────────────────────────────────────
def _write(name, value):
    try:
        SpiderG.pwm.set_pwm(PORTS[name], 0, value)
    except Exception:
        pass


def _reach(targets):
    t0 = time.time()
    while time.time() - t0 < MAX_TIME:
        moving = False
        for name in PORTS:
            cur = current[name]
            tgt = targets.get(name, cur)
            if cur != tgt:
                gap = tgt - cur
                step = UNITS if gap > 0 else -UNITS
                if abs(gap) <= UNITS:
                    step = gap
                cur += step
                current[name] = cur
                _write(name, cur)
                moving = True
        if not moving:
            return
        time.sleep(STEP)


def _neutral():
    return {n: SpiderG.goal_dict[n] for n in PORTS}


def _init():
    SpiderG.move_init()
    time.sleep(0.25)
    for name in PORTS:
        current[name] = SpiderG.goal_dict[name]


# ── mosse ───────────────────────────────────────────────────
def pose(height=0.0, pitch=0.0, roll=0.0, hold=0.0):
    SpiderG.status_GenOut(height, pitch, roll)
    _reach(dict(SpiderG.goal_dict))
    if hold:
        time.sleep(hold)


def move_map(deltas, hold=0.0, back=True):
    """Muove più servi insieme, ognuno della sua quantità. Un unico movimento."""
    start = {n: current[n] for n in deltas}
    t = dict(current)
    for n, d in deltas.items():
        t[n] = max(100, min(500, start[n] + d))
    _reach(t)
    if hold:
        time.sleep(hold)
    if back:
        _reach(start)


def leg(name, delta, hold=0.10):
    move_map({name: delta}, hold=hold)


def sweep(name, low=100, high=500, hold=0.10):
    """Corsa completa 100 → 500 → 100 (mossa dell'esempio servo)."""
    base = current[name]
    for target in (high, low, base):
        t = dict(current)
        t[name] = target
        _reach(t)
        time.sleep(hold)


def wave(reverse=False):
    order = (('FLE', 26), ('FRE', -26), ('HLE', -26), ('HRE', 26))
    if reverse:
        order = tuple(reversed(order))
    for name, d in order:
        leg(name, d, hold=0.05)


def scuttle(cycles=2):
    """Passo sul posto: diagonali opposte, sempre simultanee."""
    for _ in range(cycles):
        move_map({'FLB': 22, 'HRB': 22, 'FRB': -22, 'HLB': -22}, hold=0.20, back=False)
        move_map({'FLB': -22, 'HRB': -22, 'FRB': 22, 'HLB': 22}, hold=0.20, back=False)
    _reach(_neutral())


def diagonal_extend(front, front_e, back, back_e, hold=0.45):
    """Una zampa avanti e la diagonale opposta indietro, insieme."""
    move_map({front: DIAG_B, front_e: DIAG_E,
              back: -DIAG_B, back_e: -DIAG_E}, hold=hold, back=False)
    time.sleep(PAUSE)
    _reach(_neutral())


def nose_up(hold=0.55):
    """Anteriori sollevate, posteriori che spingono: il corpo pende in su."""
    move_map({'FLE': TILT_E, 'FRE': -TILT_E,
              'HLE': -TILT_E, 'HRE': TILT_E}, hold=hold, back=False)
    pose(0, -0.30, 0, hold=0.25)
    _reach(_neutral())
    SpiderG.status_GenOut(0, 0, 0)


def nose_down(hold=0.55):
    """Inverse: posteriori sollevate, anteriori che spingono: muso in giù."""
    move_map({'FLE': -TILT_E, 'FRE': TILT_E,
              'HLE': TILT_E, 'HRE': -TILT_E}, hold=hold, back=False)
    pose(0, 0.30, 0, hold=0.25)
    _reach(_neutral())
    SpiderG.status_GenOut(0, 0, 0)


def circle_tilt(hold=0.20):
    """Inclinazione circolare: il corpo gira attorno senza spostarsi."""
    for p, r in ((0.45, 0.40), (0, 0.55), (-0.45, 0.40), (-0.55, 0),
                 (-0.45, -0.40), (0, -0.55), (0.45, -0.40), (0.55, 0)):
        pose(0, p, r, hold=hold)


def front_led(on):
    # Switch.switch() si inizializza da sé (idempotente): non chiamare
    # switchSetup() qui, altrimenti si rischia una doppia creazione dei LED.
    try:
        import Switch
        Switch.switch(FRONT_LED_PORT, 1 if on else 0)
    except Exception:
        pass


# ── coreografia ─────────────────────────────────────────────
def run(led=None):
    if led is not None:
        try:
            led.police()
        except Exception:
            pass
    front_led(True)

    _init()

    # 1. dondolio laterale
    pose(0, 0, 0.55, hold=PAUSE)
    pose(0, 0, -0.55, hold=PAUSE)
    pose(0, 0, 0, hold=PAUSE)

    # 2. inclinazione circolare
    circle_tilt()
    pose(0, 0, 0, hold=PAUSE)

    # 3. passo sul posto (diagonali simultanee e opposte)
    scuttle(cycles=2)
    time.sleep(PAUSE)

    # 4. onda, avanti e indietro
    wave()
    time.sleep(0.06)
    wave(reverse=True)
    time.sleep(PAUSE)

    # 5. allungo diagonale: anteriore DESTRA avanti, posteriore SINISTRA indietro
    diagonal_extend('FRB', 'FRE', 'HLB', 'HLE')
    pose(0, 0.30, 0.30, hold=0.30)
    pose(0, 0, 0, hold=PAUSE)

    # 6. stiramento avanti / indietro
    pose(0, 0.55, 0, hold=PAUSE)
    pose(0, -0.55, 0, hold=PAUSE)

    # 7. alzata + respiro meccanico
    pose(0, 0, 0, hold=PAUSE)
    pose(95, 0, 0, hold=PAUSE)
    pose(120, 0, 0, hold=0.55)
    pose(60, 0, 0, hold=0.45)
    pose(0, 0, 0, hold=PAUSE)

    # 8. muso in su: posteriori spingono, anteriori sollevate
    nose_up()
    time.sleep(PAUSE)

    # 9. muso in giù: anteriori spingono, posteriori sollevate
    nose_down()
    time.sleep(PAUSE)

    # 10. inclinazione circolare al contrario
    for p, r in ((0.55, 0), (0.45, -0.40), (0, -0.55), (-0.45, -0.40),
                 (-0.55, 0), (-0.45, 0.40), (0, 0.55), (0.45, 0.40)):
        pose(0, p, r, hold=0.18)
    pose(0, 0, 0, hold=PAUSE)

    # 11. allungo diagonale opposto: anteriore SINISTRA avanti, posteriore DESTRA indietro
    diagonal_extend('FLB', 'FLE', 'HRB', 'HRE')
    pose(0, 0.30, -0.30, hold=0.30)
    pose(0, 0, 0, hold=PAUSE)

    # 12. corsa completa del servo (mossa dell'esempio)
    sweep('FRB')

    # 13. chiusura: dondolio lento e riposo
    pose(0, 0, 0.45, hold=PAUSE * 2)
    pose(0, 0, -0.45, hold=PAUSE * 2)
    pose(0, 0, 0)

    front_led(False)
    if led is not None:
        try:
            led.breath(70, 70, 255)
        except Exception:
            pass


if __name__ == "__main__":
    # Esecuzione manuale: crea l'oggetto luci, così polizia e respiro funzionano
    # anche fuori dal WebServer.
    _led = None
    try:
        import RobotLight as robotLight
        _led = robotLight.Adeept_SPI_LedPixel(16, 255)
        if _led.check_spi_state() != 0:
            _led.start()
        else:
            _led = None
    except Exception:
        _led = None

    run(_led)
    import os
    os._exit(0)
