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

import math
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

# ── le due mosse nuove (ampie e lente, ma non troppo) ───────
# Tutte due alzano e abbassano le articolazioni FINALI (E), quindi non fanno
# camminare il ragno: la punta della zampa sale e scende, il corpo resta fermo.
#
# Il motore scrive UN aggiornamento per frame PWM. Il PCA9685 rigenera le
# uscite a 50 Hz, cioè un frame ogni 20 ms: scrivere più spesso fa cadere le
# scritture a metà frame, vengono accorpate e si vedono degli scatti.
#
# La velocità si regola con STEP, cioè unità di PWM per frame:
#   1 = lento (≈50 unità/s)   2 = medio (≈100/s)   3 = veloce (≈150/s)

SERVO_FRAME = 0.020        # un frame PWM = 20 ms. Non conviene cambiarlo.

# Moltiplicatore globale dell'ampiezza di TUTTA la coreografia: pose, onde,
# allunghi, scuttle, muso su/giù. 1.00 = com'era, 1.20 = 20% più ampia.
# NON tocca le due mosse nuove (hanno la loro ampiezza, già quasi al limite)
# né le corse a fondo scala.
GAIN = 1.35

# Posa di riposo a fine spettacolo: solo il muso verso il basso.
# pitch positivo = muso in giù · roll = inclinazione laterale.
# Il roll è a 0 di proposito: una pendenza laterale così piccola non si nota,
# e se la si alza il peso si scarica su due zampe (instabile + carico
# asimmetrico sui servi per tutta l'ora). Simmetrica è meglio.
FINALE_PITCH = 0.45
FINALE_ROLL = 0.0

# 1) onda "larga": tutte e quattro le zampe, stessa ampiezza, partenza sfalsata.
SWEEP_ALL_NAMES = ('FLE', 'FRE', 'HLE', 'HRE')
SWEEP_ALL_AMP = 200        # 300 ± 200 → 100..500 (fondo scala)
SWEEP_ALL_STEP = 4         # 4 unità per frame (~200 u/s)
SWEEP_ALL_STAGGER = 0.06   # ogni zampa entra 60 ms dopo la precedente

# 2) onda "a cascata": ordine diagonale, ampiezze diverse, sfalsatura più larga.
CASCADE_ORDER = ('FLE', 'HRE', 'FRE', 'HLE')
CASCADE_AMP = 200
CASCADE_STAGGER = 0.10     # ogni zampa entra 100 ms dopo la precedente
CASCADE_STEP = 4
CASCADE_SCALE = {          # ampiezze diverse: niente effetto specchio
    'FLE': 1.00,
    'HRE': 0.85,
    'FRE': 0.92,
    'HLE': 0.78,
}

# ── TEST: passo dimostrativo, solo nella prima mossa ────────
# Ogni voce: (base, punta, verso). Il verso è ricavato dal movimento
# coordinato di scuttle(), dove la diagonale FRB+HLB e la diagonale FLB+HRB
# girano in direzioni opposte.
PASSO_ZAMPE = (
    ('FRB', 'FRE', +1),   # anteriore destra  (guardando frontalmente: sinistra)
    ('HLB', 'HLE', +1),   # posteriore sinistra (guardando frontalmente: destra)
    ('FLB', 'FLE', -1),   # anteriore sinistra
    ('HRB', 'HRE', -1),   # posteriore destra
)
PASSO_E_LIFT = 45         # sollevamento della punta prima di avanzare
PASSO_B_AMP = 80          # quanto avanza la base
PASSO_HOLD = 0.25         # pausa a zampa avanti
PASSO_PAUSA = 0.12        # pausa fra una zampa e l'altra

# Verso di "sollevamento" della punta, ricavato da nose_up():
# davanti sinistra e dietro destra salgono con +, le altre con -.
PUNTA_SU = {'FLE': +1, 'FRE': -1, 'HLE': -1, 'HRE': +1}

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


def posa_finale(pitch=None, roll=None, hold=0.10):
    """Applica SOLO la posa di riposo, senza tornare al centro.

    Serve anche per provarla dal pannello: cambiando `roll` si vede subito
    da che lato pende. Valori di roll oltre ±0.40 diventano instabili.
    """
    pitch = FINALE_PITCH if pitch is None else pitch
    roll = FINALE_ROLL if roll is None else roll
    _init()
    pose(0, pitch, roll, hold=hold)


def livella(passi=4, tolleranza_gradi=1.5):
    """Riporta il corpo in piano leggendo l'assetto già corretto.

    Usa imu.leggi(), che applica l'offset di montaggio del sensore: senza
    quello, "in piano" significava in realtà inclinato di 5°.

    La correzione è proporzionale all'errore e si ripete, così converge.
    Il fattore 25 viene dalle misure statiche: 1 unità di posa inclina il
    corpo di circa 13-20°, quindi 25 è prudente e converge in 2-3 passi.
    """
    try:
        import imu
    except Exception:
        return
    if not getattr(SpiderG, 'MPU_connection', 0):
        return

    pitch = 0.0
    roll = 0.0
    for _ in range(max(1, passi)):
        d = imu.leggi()
        if not d.get('ok'):
            return
        errore_pitch = d['pitch']     # positivo = muso in su
        errore_roll = d['roll']

        if abs(errore_pitch) < tolleranza_gradi and abs(errore_roll) < tolleranza_gradi:
            break

        # muso in su → serve una posa con pitch positivo (muso in giù)
        pitch = max(-0.6, min(0.6, pitch + errore_pitch / 25.0))
        roll = max(-0.6, min(0.6, roll + errore_roll / 25.0))
        SpiderG.status_GenOut(0, pitch, roll)
        _reach(dict(SpiderG.goal_dict))
        time.sleep(0.12)


def _init():
    SpiderG.move_init()
    time.sleep(0.25)
    for name in PORTS:
        current[name] = SpiderG.goal_dict[name]


# ── mosse ───────────────────────────────────────────────────
def pose(height=0.0, pitch=0.0, roll=0.0, hold=0.0):
    SpiderG.status_GenOut(height * GAIN, pitch * GAIN, roll * GAIN)
    _reach(dict(SpiderG.goal_dict))
    if hold:
        time.sleep(hold)


def move_map(deltas, hold=0.0, back=True):
    """Muove più servi insieme, ognuno della sua quantità. Un unico movimento.
    Le quantità vengono scalate da GAIN, come le pose."""
    start = {n: current[n] for n in deltas}
    t = dict(current)
    for n, d in deltas.items():
        t[n] = max(100, min(500, start[n] + int(round(d * GAIN))))
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


def sweep_all(names=None, amp=None, step=None, stagger=None):
    """Onda larga: le quattro zampe salgono e scendono sfalsate, non insieme.

    Stessa ampiezza per tutte, ma una parte un istante dopo l'altra: il corpo
    ondeggia invece di salire in blocco. Non avanza e non può cadere.
    """
    names = tuple(names) if names else SWEEP_ALL_NAMES
    amp = SWEEP_ALL_AMP if amp is None else amp
    step = SWEEP_ALL_STEP if step is None else step
    stagger = SWEEP_ALL_STAGGER if stagger is None else stagger

    base = {n: current[n] for n in names}
    su = {n: min(500, base[n] + amp) for n in names}
    giu = {n: max(100, base[n] - amp) for n in names}

    _glide_staggered(su, stagger, step)
    time.sleep(0.08)
    _glide_staggered(giu, stagger, step)
    time.sleep(0.08)
    _glide_staggered(base, stagger, step)
    livella(passi=2)


def _una_zampa(base, punta, verso, lift, amp, hold):
    """Solleva una zampa, la porta avanti e la riporta indietro."""
    move_map({punta: -lift}, hold=0.12, back=False)          # solleva
    move_map({base: amp * verso}, hold=hold, back=False)      # avanti
    move_map({base: -amp * verso}, hold=0.12, back=False)     # indietro
    move_map({punta: lift}, hold=0.06, back=False)            # appoggia


def _due_zampe(a, b, lift, amp, hold):
    """Come _una_zampa, ma due zampe insieme (a e b sono terne base/punta/verso)."""
    move_map({a[1]: -lift, b[1]: -lift}, hold=0.12, back=False)
    move_map({a[0]: amp * a[2], b[0]: amp * b[2]}, hold=hold, back=False)
    move_map({a[0]: -amp * a[2], b[0]: -amp * b[2]}, hold=0.12, back=False)
    move_map({a[1]: lift, b[1]: lift}, hold=0.06, back=False)


def passo_dimostrativo():
    """TEST: mostra che il ragno sa portare avanti le zampe, una alla volta.

    1. una zampa per volta, girando attorno al corpo
    2. poi le due diagonali opposte, ognuna con le sue due zampe insieme
    Ogni zampa torna sempre esattamente al punto di partenza.
    """
    for zampa in PASSO_ZAMPE:
        _una_zampa(zampa[0], zampa[1], zampa[2],
                   PASSO_E_LIFT, PASSO_B_AMP, PASSO_HOLD)
        time.sleep(PASSO_PAUSA)

    # diagonale 1 insieme: anteriore destra + posteriore sinistra
    _due_zampe(PASSO_ZAMPE[0], PASSO_ZAMPE[1],
               PASSO_E_LIFT, PASSO_B_AMP, PASSO_HOLD)
    time.sleep(PASSO_PAUSA)

    # diagonale 2 insieme: le opposte (anteriore sinistra + posteriore destra)
    _due_zampe(PASSO_ZAMPE[2], PASSO_ZAMPE[3],
               PASSO_E_LIFT, PASSO_B_AMP, PASSO_HOLD)


def marcia(cicli=1, hold=0.28):
    """Marcia sul posto: una diagonale avanti, poi quella opposta.

    Le punte si sollevano prima di avanzare, quindi il ragno non cammina
    davvero: è una camminata a vuoto che però dimostra il passo.
    """
    for _ in range(max(1, cicli)):
        _due_zampe(PASSO_ZAMPE[0], PASSO_ZAMPE[1],
                   PASSO_E_LIFT, PASSO_B_AMP, hold)
        time.sleep(0.10)
        _due_zampe(PASSO_ZAMPE[2], PASSO_ZAMPE[3],
                   PASSO_E_LIFT, PASSO_B_AMP, hold)
        time.sleep(0.10)


def croce(hold=0.30):
    """Inclinazione a croce: avanti, destra, indietro, sinistra."""
    for p, r in ((0.45, 0), (0, 0.45), (-0.45, 0), (0, -0.45)):
        pose(0, p, r, hold=hold)
    pose(0, 0, 0, hold=PAUSE)


def saluto(hold=0.18):
    """Onda lenta delle punte: una zampa per volta, in un senso e nell'altro."""
    onda = (('FLE', 40), ('FRE', -40), ('HLE', -40), ('HRE', 40))
    for name, d in onda:
        leg(name, d, hold=hold)
    for name, d in reversed(onda):
        leg(name, -d, hold=hold)


# ── mosse nuove ─────────────────────────────────────────────
# Tutte lavorano sulle punte o sull'altezza del corpo: nessuna ruota la base
# delle zampe, quindi non possono far avanzare il ragno.


def petalo(hold=0.35, amp=55):
    """Altalena: punte davanti su e dietro giù, poi il contrario.

    Il corpo dondola avanti/indietro restando fermo, come un petalo.
    """
    move_map({n: +amp * s for n, s in PUNTA_SU.items()}, hold=hold, back=False)
    move_map({n: -amp * s for n, s in PUNTA_SU.items()}, hold=hold, back=False)
    _reach(_neutral())


def battito(colpi=2, amp=30, hold=0.06):
    """Colpi secchi delle punte: su-giù ripetuto, a ritmo serrato."""
    for _ in range(max(1, colpi)):
        move_map({n: +amp * s for n, s in PUNTA_SU.items()},
                 hold=hold, back=False)
        move_map({n: -amp * s for n, s in PUNTA_SU.items()},
                 hold=hold, back=False)
    _reach(_neutral())


def onda_lenta(amp=70, periodi=2.0, durata=2.5, fps=20, ordine=None):
    """Onda fluida: le quattro punte seguono una sinusoide sfasata.

    Non è una sequenza di scatti: ogni zampa è a un punto diverso della stessa
    onda, quindi il movimento gira attorno al corpo in modo continuo — come
    cerchio e torsione, ma sulle punte invece che sul corpo.

    Una zampa alla volta è al massimo, quindi la corrente resta bassa.
    """
    ordine = ordine or ('FLE', 'HRE', 'FRE', 'HLE')
    base = {n: current[n] for n in ordine}
    fase = {n: i / float(len(ordine)) for i, n in enumerate(ordine)}
    t0 = time.time()
    passo = 1.0 / max(1, fps)

    while True:
        trascorso = time.time() - t0
        if trascorso >= durata:
            break
        giro = (trascorso / durata) * periodi
        for n in ordine:
            valore = base[n] + amp * math.sin(2 * math.pi * (giro - fase[n]))
            valore = max(100, min(500, int(valore)))
            if valore != current[n]:
                current[n] = valore
                _write(n, valore)
        time.sleep(passo)

    _reach(base)


def respiro(cicli=2, su=120, giu=-58, hold=0.28, passi=5, passo=0.075):
    """Respiro naturale: sale piano, pausa, scende piano, pausa, ripete.

    Non sono tre pose staccate: ogni salita e ogni discesa è una rampa di
    piccoli passi, così il movimento è continuo e sembra davvero un respiro.
    """
    def rampa(da, a):
        for i in range(1, passi + 1):
            pose(da + (a - da) * i / float(passi), 0, 0)
            time.sleep(passo)

    attuale = 0.0
    for _ in range(max(1, cicli)):
        rampa(attuale, su)
        attuale = su
        time.sleep(hold)
        rampa(attuale, giu)
        attuale = giu
        time.sleep(hold)
    rampa(attuale, 0.0)


def torsione(hold=0.30):
    """Torsione in diagonale: avanti-destra, indietro-sinistra e incroci."""
    for p, r in ((0.40, 0.40), (-0.40, -0.40),
                 (0.40, -0.40), (-0.40, 0.40)):
        pose(0, p, r, hold=hold)
    pose(0, 0, 0, hold=PAUSE)


def scalini(hold=0.28):
    """Salita a gradini: il corpo sale tre volte, poi scende tutto d'un fiato."""
    for h in (45, 90, 130):
        pose(h, 0, 0, hold=hold)
    pose(70, 0, 0, hold=0.20)
    pose(0, 0, 0, hold=PAUSE)


def ventaglio(hold=0.30, amp=60):
    """Apre e chiude le punte in diagonale: le due coppie opposte si scambiano.

    Solo articolazioni finali: è un'apertura "a forbice" che non sposta nulla.
    """
    move_map({'FLE': -amp, 'HRE': -amp, 'FRE': +amp, 'HLE': +amp},
             hold=hold, back=False)
    move_map({'FLE': +amp, 'HRE': +amp, 'FRE': -amp, 'HLE': -amp},
             hold=hold, back=False)
    _reach(_neutral())


def _glide(targets, step=None, frame=None):
    """Porta più servi al valore indicato, `step` unità di PWM per frame.

    Un solo aggiornamento ogni 20 ms, cioè alla frequenza con cui il PCA9685
    rigenera le uscite: così il movimento è fluido e il bus I2C resta leggero.
    """
    frame = SERVO_FRAME if frame is None else frame
    step = 1 if step is None else max(1, int(step))
    names = list(targets)
    if not names:
        return
    while True:
        attivo = False
        for n in names:
            cur, tgt = current[n], targets[n]
            if cur == tgt:
                continue
            cur = min(tgt, cur + step) if tgt > cur else max(tgt, cur - step)
            current[n] = cur
            _write(n, cur)
            attivo = True
        if not attivo:
            return
        time.sleep(frame)


def _glide_staggered(targets, stagger, step=None, frame=None):
    """Come _glide, ma ogni servo entra sfalsato di `stagger` secondi."""
    frame = SERVO_FRAME if frame is None else frame
    step = 1 if step is None else max(1, int(step))
    names = list(targets)
    if not names:
        return
    starts = {n: current[n] for n in names}
    passi = {n: int(round(abs(targets[n] - starts[n]) / float(step))) for n in names}
    offsets = {n: int((i * stagger) / frame) for i, n in enumerate(names)}
    total = max(passi[n] + offsets[n] for n in names)
    for k in range(total):
        for n in names:
            done = k - offsets[n]
            if done <= 0:
                continue
            delta = min(done, passi[n]) * step
            if targets[n] > starts[n]:
                want = min(starts[n] + delta, targets[n])
            else:
                want = max(starts[n] - delta, targets[n])
            if want != current[n]:
                current[n] = want
                _write(n, want)
        time.sleep(frame)


def sweep_cascade(order=None, amp=None, stagger=None, step=None, frame=None,
                  scale=None):
    """Onda a cascata: le quattro zampe salgono e scendono sfalsate.

    Ampia e lenta: ogni zampa entra un attimo dopo la precedente e con
    un'ampiezza leggermente diversa, così il movimento gira attorno al corpo e
    non è speculare. Alza e abbassa le punte: il ragno resta sul posto.
    """
    order = tuple(order) if order else CASCADE_ORDER
    amp = CASCADE_AMP if amp is None else amp
    stagger = CASCADE_STAGGER if stagger is None else stagger
    step = CASCADE_STEP if step is None else step
    frame = SERVO_FRAME if frame is None else frame
    scale = scale or CASCADE_SCALE

    base = {n: current[n] for n in order}
    su = {n: min(500, base[n] + int(amp * scale.get(n, 1.0))) for n in order}
    giu = {n: max(100, base[n] - int(amp * scale.get(n, 1.0))) for n in order}

    _glide_staggered(su, stagger, step, frame)
    _glide_staggered(giu, stagger, step, frame)
    _glide_staggered(base, stagger, step, frame)
    livella(passi=2)


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
def throttled():
    """Bitmask di `vcgencmd get_throttled`: 0 = alimentazione sana.
    bit 0  = sottotensione in corso
    bit 16 = sottotensione rilevata dall'accensione in poi"""
    try:
        import subprocess
        out = subprocess.check_output(['vcgencmd', 'get_throttled'],
                                      text=True, timeout=2).strip()
        return int(out.split('=')[1], 16)
    except Exception:
        return 0


def avviso_tensione(prima, dopo):
    """True se la sottotensione è COMPARSA durante la mossa (non se c'era già)."""
    if (dopo & 0x10000) and not (prima & 0x10000):
        print("wakeup: ATTENZIONE calo di tensione durante il movimento — "
              "l'alimentazione non regge i servi", flush=True)
        return True
    return False


def run(led=None):
    _tensione_prima = throttled()
    if led is not None:
        try:
            led.police()
        except Exception:
            pass
    front_led(True)

    _init()

    # ══ 1 · apertura ═════════════════════════════════════════
    pose(0, 0, 0.55, hold=0.14)
    pose(0, 0, -0.55, hold=0.14)
    pose(0, 0, 0, hold=0.06)

    # ══ 2 · onda larga a quattro punte, fondo scala ══════════
    sweep_all()

    # ══ 3 · altalena e scatto sul posto ══════════════════════
    petalo(hold=0.20, amp=55)
    scuttle(cycles=1)

    # ══ 4 · onde veloci, poi onda lenta che gira attorno al corpo ══
    wave()
    wave(reverse=True)
    time.sleep(0.05)
    onda_lenta()

    # ══ 5 · muso su e giù ════════════════════════════════════
    nose_up(hold=0.30)
    nose_down(hold=0.30)

    # ══ 5b · scalini: il corpo sale a tre gradini e scende ══
    scalini(hold=0.26)

    # ══ 6 · cascata, fondo scala ═════════════════════════════
    sweep_cascade()

    # ══ 7 · chiusura ═════════════════════════════════════════
    pose(0, 0, 0.45, hold=0.16)
    pose(0, 0, -0.45, hold=0.16)
    # posa di riposo: muso in giù, leggermente inclinato di lato.
    # Niente livella() qui: raddrizzerebbe la posa appena impostata.
    pose(0, FINALE_PITCH, FINALE_ROLL, hold=0.12)

    front_led(False)
    if led is not None:
        try:
            led.breath(70, 70, 255)
        except Exception:
            pass

    avviso_tensione(_tensione_prima, throttled())


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
