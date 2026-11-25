#!/usr/bin/env python3
# imu.py — lettura dell'assetto per la bolla live di /jarvis.
#
# Usa il MPU-6050 (0x68) già inizializzato da SpiderG: qui si legge soltanto,
# senza toccare la modalità "Stabilizza", che usa lo stesso sensore.
#
# Gli angoli sono calcolati dal vettore di gravità dell'accelerometro:
#   pitch = atan2(x, sqrt(y² + z²))   muso su / muso giù
#   roll  = atan2(y, sqrt(x² + z²))   inclinazione destra / sinistra
# Con il ragno in piano: x ≈ 0, y ≈ 0, z ≈ 1 g.
#
# Nota: è un accelerometro, non un giroscopio integrato. Va benissimo per una
# bolla statica (mostra l'inclinazione reale rispetto alla gravità), mentre
# durante i movimenti bruschi legge anche l'accelerazione e "balla".

import math

import SpiderG


def disponibile():
    return bool(getattr(SpiderG, 'MPU_connection', 0)) and \
        getattr(SpiderG, 'sensor', None) is not None


def leggi():
    """Ritorna un dizionario pronto per il JSON dell'API."""
    if not disponibile():
        return {'ok': False, 'errore': 'IMU non disponibile'}

    try:
        dati = SpiderG.sensor.get_accel_data()
        x = float(dati['x'])
        y = float(dati['y'])
        z = float(dati['z'])
    except Exception as e:
        return {'ok': False, 'errore': 'lettura fallita: %s' % e}

    # ASSI DI QUESTO MONTAGGIO (verificato sul robot):
    #   x = asse AVANTI/INDIETRO  → muso in su dà x > 0
    #   y = asse SINISTRA/DESTRA  → inclinare a sinistra dà y > 0
    # Quindi il "pitch" (muso su/giù) si ricava da x e il "roll" (lato) da y.
    # Nella prima versione erano invertiti: la bolla si muoveva sull'asse
    # sbagliato.
    pitch = math.degrees(math.atan2(x, math.sqrt(y * y + z * z)))
    roll = math.degrees(math.atan2(y, math.sqrt(x * x + z * z)))
    inclinazione = math.degrees(math.acos(max(-1.0, min(1.0, z / max(0.001, math.sqrt(x*x + y*y + z*z))))))

    return {
        'ok': True,
        'x': round(x, 3),
        'y': round(y, 3),
        'z': round(z, 3),
        'roll': round(roll, 1),
        'pitch': round(pitch, 1),
        'inclinazione': round(inclinazione, 1),
    }


if __name__ == '__main__':
    import json
    print(json.dumps(leggi(), indent=2))
