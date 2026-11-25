#!/usr/bin/env python3
# comandi.py — comandi manuali per il pannello /comandi.
#
# Modalità loop: schiacciare una mossa la fa ripetere senza sosta finché non
# la schiacci di nuovo (o non premi STOP). È pensata per guardare le mosse
# con calma: molte durano 1-2 secondi, da sole finiscono prima che tu le veda.
#
# Perché un lucchetto: la sequenza oraria (hourly.py) e i comandi manuali
# scrivono sugli stessi 12 canali PWM del PCA9685. Se partono insieme il
# ragno trema e le posizioni si corrompono. LOCK serializza: una sola
# mossa alla volta, in qualunque modo venga avviata.

import threading
import time

import SpiderG
import wakeup

# Lucchetto unico, condiviso con hourly.py.
LOCK = threading.Lock()

_led = None
_esito_lock = threading.Lock()
_esito = {"nome": None, "esito": None, "quando": 0.0}

# Stato del loop: nome della mossa che sta ripetendo, o None.
_loop_lock = threading.Lock()
_loop_nome = None
_loop_thread = None


def set_led(led):
    """Registra l'oggetto luci del WebServer (può essere None)."""
    global _led
    _led = led


def stato():
    """Stato per il pannello: ultima mossa, esito, occupato, loop attivo."""
    with _esito_lock:
        d = dict(_esito)
    d["occupato"] = LOCK.locked()
    with _loop_lock:
        d["loop"] = _loop_nome
    return d


def _registra(nome, esito):
    with _esito_lock:
        _esito["nome"] = nome
        _esito["esito"] = esito
        _esito["quando"] = time.time()


# ── movimenti ───────────────────────────────────────────────
def _servo(fn):
    """Avvolge una mossa che usa i servi: pausa, init, mossa, ritorno."""
    def esegui():
        try:
            # Il thread di camminata (se mai attivato) non deve scrivere
            # mentre la mossa manuale muove gli stessi servi.
            SpiderG.Servo.pause()
        except Exception:
            pass
        wakeup._init()
        fn()
        wakeup.pose(0, 0, 0)
    return esegui


def _luci(fn):
    """Mosse che toccano solo LED: nessun servo, quindi nessun init."""
    def esegui():
        fn()
        time.sleep(0.15)
    return esegui


def _posa(fn):
    """Esegue una posa e CE LA LASCIA: nessun ritorno al centro.

    Diverso da _servo: quello chiude sempre con pose(0,0,0), che annullerebbe
    la posa di riposo.
    """
    def esegui():
        try:
            SpiderG.Servo.pause()
        except Exception:
            pass
        fn()
        time.sleep(0.15)
    return esegui


def _risveglio():
    try:
        SpiderG.Servo.pause()
    except Exception:
        pass
    wakeup.run(_led)


def _dondolio():
    wakeup.pose(0, 0, 0.55, hold=wakeup.PAUSE)
    wakeup.pose(0, 0, -0.55, hold=wakeup.PAUSE)


def _polizia():
    if _led is not None:
        _led.police()


def _riposo_luci():
    if _led is not None:
        _led.breath(70, 70, 255)


MOSSE = {
    # sequenza completa
    'risveglio':   _risveglio,
    # servi
    'servo':       _servo(lambda: wakeup.sweep_all()),
    'cascata':     _servo(lambda: wakeup.sweep_cascade()),
    'passotest':   _servo(lambda: wakeup.passo_dimostrativo()),
    'marcia':      _servo(lambda: wakeup.marcia(2)),
    'saluto':      _servo(lambda: wakeup.wave()),
    'saluto_rev':  _servo(lambda: wakeup.wave(reverse=True)),
    'saluto_lento': _servo(lambda: wakeup.saluto()),
    'passo':       _servo(lambda: wakeup.scuttle(2)),
    'allungo_dx':  _servo(lambda: wakeup.diagonal_extend('FRB', 'FRE', 'HLB', 'HLE')),
    'allungo_sx':  _servo(lambda: wakeup.diagonal_extend('FLB', 'FLE', 'HRB', 'HRE')),
    'muso_su':     _servo(lambda: wakeup.nose_up()),
    'muso_giu':    _servo(lambda: wakeup.nose_down()),
    'cerchio':     _servo(lambda: wakeup.circle_tilt()),
    'dondolio':    _servo(_dondolio),
    'petalo':      _servo(lambda: wakeup.petalo()),
    'battito':     _servo(lambda: wakeup.battito(2)),
    'torsione':    _servo(lambda: wakeup.torsione()),
    'scalini':     _servo(lambda: wakeup.scalini()),
    'ventaglio':   _servo(lambda: wakeup.ventaglio()),
    # posa
    'finale':      _posa(lambda: wakeup.posa_finale()),
    # luci
    'polizia':     _luci(_polizia),
    'polizia_off': _luci(_riposo_luci),
    'led_on':      _luci(lambda: wakeup.front_led(True)),
    'led_off':     _luci(lambda: wakeup.front_led(False)),
}


# ── loop ────────────────────────────────────────────────────
_PAUSA_FRA_CICLI = 0.30     # secondi di respiro fra una ripetizione e l'altra


def _ciclo(nome):
    """Esegue una singola ripetizione della mossa, con il lucchetto preso."""
    tensione_prima = wakeup.throttled()
    try:
        _registra(nome, "in corso")
        MOSSE[nome]()
        esito = "ok"
        if wakeup.avviso_tensione(tensione_prima, wakeup.throttled()):
            esito = "ok ma calo di tensione"
        _registra(nome, esito)
    except Exception as e:
        _registra(nome, "errore: %s" % e)
        print("comandi: errore in %s: %s" % (nome, e), flush=True)
    finally:
        LOCK.release()


def _loop_worker():
    """Ripete la mossa richiesta finché _loop_nome resta quella."""
    while True:
        with _loop_lock:
            nome = _loop_nome
        if nome is None:
            return

        # Il lucchetto è condiviso con la sequenza oraria: se è occupato
        # aspetto un attimo invece di accavallarmi.
        if not LOCK.acquire(timeout=2):
            time.sleep(0.1)
            continue
        try:
            with _loop_lock:
                if _loop_nome != nome:
                    # cambiata la richiesta mentre aspettavamo
                    raise _Cambio()
            _ciclo(nome)
        except _Cambio:
            LOCK.release()
        # pausa breve, interrompibile subito
        for _ in range(int(_PAUSA_FRA_CICLI / 0.05)):
            with _loop_lock:
                if _loop_nome != nome:
                    break
            time.sleep(0.05)


class _Cambio(Exception):
    """Segnale interno: la mossa richiesta è cambiata."""


def avvia(nome):
    """Interruttore: avvia la mossa in loop, o la ferma se è già in corso."""
    global _loop_nome, _loop_thread
    if nome not in MOSSE:
        return False, "comando sconosciuto: %s" % nome

    with _loop_lock:
        if _loop_nome == nome:
            _loop_nome = None
            return True, "fermato: " + nome
        _loop_nome = nome
        if _loop_thread is None or not _loop_thread.is_alive():
            _loop_thread = threading.Thread(target=_loop_worker, daemon=True,
                                            name="loop-comandi")
            _loop_thread.start()
    return True, "loop: " + nome


def ferma():
    """Ferma qualsiasi loop in corso."""
    global _loop_nome
    with _loop_lock:
        _loop_nome = None
    return True, "fermato"


def elenco():
    """Nomi delle mosse disponibili (per il pannello e per i test)."""
    return sorted(MOSSE)


if __name__ == "__main__":
    # Prova a secco: mostra le mosse, non muove nulla.
    print("comandi disponibili:", len(MOSSE))
    for n in elenco():
        print("  -", n)
