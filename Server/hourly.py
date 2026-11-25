#!/usr/bin/env python3
# hourly.py — esegue la routine di risveglio ogni ora, allo scatto (:00).
#
# Gira come thread DENTRO il processo del WebServer: così condivide la stessa
# istanza PCA9685 e lo stesso oggetto luci. Un processo separato andrebbe in
# conflitto (DMA delle strisce, bus I2C, thread dei servi).
#
# Parametri in cima: accensione, ore consentite, intervallo.

import datetime
import threading
import time

import comandi
import wakeup

ENABLED = True

# Ore in cui è consentito esibirsi (0-23). Di default tutte e 24.
# Esempio: range(8, 23) → solo dalle 08:00 alle 22:59, silenzio di notte.
HOURS = set(range(24))

# Ogni quante ore (1 = ogni ora, 2 = una volta ogni due ore, ecc.)
EVERY = 1


def _seconds_to_next_hour(now=None):
    now = now or datetime.datetime.now()
    nxt = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    return max(1.0, (nxt - now).total_seconds())


def _loop(led):
    while True:
        wait = _seconds_to_next_hour()
        time.sleep(wait)

        now = datetime.datetime.now()
        if now.hour not in HOURS:
            continue
        if now.hour % EVERY != 0:
            continue

        # Stesso lucchetto dei comandi manuali: se qualcuno sta muovendo il
        # ragno dal pannello, aspetto (max 2 min) invece di scontrarmi.
        if not comandi.LOCK.acquire(timeout=120):
            print("hourly: sequenza saltata, un comando manuale è in corso",
                  flush=True)
            continue

        try:
            wakeup.run(led)
        except Exception as e:
            print("hourly: errore durante la sequenza:", e)
        finally:
            comandi.LOCK.release()


def start(led=None):
    """Avvia il timer. Silenzioso se ENABLED è False."""
    if not ENABLED:
        print("hourly: disabilitato", flush=True)
        return None
    t = threading.Thread(target=_loop, args=(led,), daemon=True, name="hourly")
    t.start()
    # marcatore su disco: prova che il timer è partito (utile per i log)
    try:
        with open("/tmp/hourly.started", "w") as f:
            f.write(datetime.datetime.now().isoformat() + "\n")
    except Exception:
        pass
    print("hourly: attivo (ogni %dh, ore %s)" % (
        EVERY, "tutte" if HOURS == set(range(24)) else sorted(HOURS)), flush=True)
    return t


if __name__ == "__main__":
    # Prova a secco: mostra quando partirebbe, senza muovere nulla.
    now = datetime.datetime.now()
    print("ora attuale:        ", now.strftime("%H:%M:%S"))
    print("attesa al prossimo :00:", int(_seconds_to_next_hour(now)), "secondi")
    print("ore abilitate:      ", "tutte" if HOURS == set(range(24)) else sorted(HOURS))
    print("ogni                ", EVERY, "ora/e")
