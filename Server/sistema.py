#!/usr/bin/env python3
# sistema.py — raccoglie le informazioni di sistema per la scheda "Sistema"
# di /jarvis, in stile neofetch.
#
# Tutto è letto al momento della richiesta: uptime, memoria, disco, IP e
# temperatura cambiano di continuo, quindi non ha senso tenerli fissi.

import os
import platform
import shutil
import subprocess
import time

# il conteggio dei pacchetti è lento (~0.5 s): lo tengo in cache per un minuto
_cache_pkg = {"quando": 0.0, "valore": 0}


def _leggi(percorso, predefinito=""):
    try:
        with open(percorso) as f:
            return f.read().strip()
    except OSError:
        return predefinito


def _byte(n):
    for unita in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unita == "TiB":
            if unita == "B":
                return "%d B" % n
            return "%.2f %s" % (n, unita)
        n /= 1024.0


def _os_release():
    dati = {}
    for riga in _leggi("/etc/os-release").splitlines():
        if "=" in riga:
            chiave, valore = riga.split("=", 1)
            dati[chiave] = valore.strip().strip('"')
    return dati


def _pacchetti():
    ora = time.time()
    if ora - _cache_pkg["quando"] < 60:
        return _cache_pkg["valore"]
    try:
        r = subprocess.run(["dpkg-query", "-f", "${binary:Package}\n", "-W"],
                           capture_output=True, text=True, timeout=6)
        n = len([x for x in r.stdout.splitlines() if x.strip()])
    except Exception:
        n = 0
    _cache_pkg.update(quando=ora, valore=n)
    return n


def _uptime():
    try:
        secondi = float(_leggi("/proc/uptime").split()[0])
    except Exception:
        return "?"
    g = int(secondi // 86400)
    o = int(secondi % 86400 // 3600)
    m = int(secondi % 3600 // 60)
    if g:
        return "%dg %dh %dm" % (g, o, m)
    if o:
        return "%dh %dm" % (o, m)
    return "%dm" % m


def _memoria():
    info = {}
    for riga in _leggi("/proc/meminfo").splitlines():
        chiave, _, resto = riga.partition(":")
        parti = resto.split()
        if parti:
            info[chiave] = int(parti[0]) * 1024
    tot = info.get("MemTotal", 0)
    disp = info.get("MemAvailable", info.get("MemFree", 0))
    usata = max(0, tot - disp)
    swap_tot = info.get("SwapTotal", 0)
    swap_usata = max(0, swap_tot - info.get("SwapFree", 0))
    return usata, tot, swap_usata, swap_tot


def _percentuale(usato, totale):
    return (usato * 100 // totale) if totale else 0


def _disco():
    try:
        u = shutil.disk_usage("/")
        return u.used, u.total
    except Exception:
        return 0, 0


def _indirizzi():
    esito = []
    try:
        r = subprocess.run(["ip", "-4", "-o", "addr", "show"],
                           capture_output=True, text=True, timeout=3)
        for riga in r.stdout.splitlines():
            parti = riga.split()
            if len(parti) < 4:
                continue
            iface = parti[1]
            if iface not in ("eth0", "wlan0"):
                continue
            if "inet" in parti:
                cidr = parti[parti.index("inet") + 1]
                esito.append("%s %s" % (iface, cidr))
    except Exception:
        pass
    return ", ".join(esito) if esito else "nessun indirizzo"


def _wifi():
    """SSID e qualità del segnale (dBm → %)."""
    # 'iw' sta in /usr/sbin, che non è sempre nel PATH (es. utente pi)
    r = None
    for eseguibile in ("iw", "/usr/sbin/iw", "/sbin/iw"):
        try:
            r = subprocess.run([eseguibile, "dev", "wlan0", "link"],
                               capture_output=True, text=True, timeout=3)
            break
        except FileNotFoundError:
            continue
        except Exception:
            return ""
    if r is None:
        return ""
    try:
        ssid, dbm = "", None
        for riga in r.stdout.splitlines():
            if riga.strip().startswith("SSID:"):
                ssid = riga.split(":", 1)[1].strip()
            elif "signal:" in riga:
                try:
                    dbm = int(riga.split("signal:")[1].split()[0])
                except Exception:
                    pass
        if not ssid:
            return ""
        if dbm is None:
            return ssid
        qualita = max(0, min(100, 2 * (dbm + 100)))
        return "%s · %d dBm (%d%%)" % (ssid, dbm, qualita)
    except Exception:
        return ""


def _tailscale():
    try:
        r = subprocess.run(["ip", "-4", "-o", "addr", "show", "tailscale0"],
                           capture_output=True, text=True, timeout=3)
        for parte in r.stdout.split():
            if parte and parte[0].isdigit() and "/" in parte:
                return parte.split("/")[0]
    except Exception:
        pass
    return ""


def _temperatura():
    try:
        milli = int(_leggi("/sys/class/thermal/thermal_zone0/temp"))
        return "%.1f°C" % (milli / 1000.0)
    except Exception:
        return "n/d"


def _soc():
    """Legge il SoC dal device-tree: 'brcm,bcm2711' → BCM2711."""
    compat = _leggi("/proc/device-tree/compatible")
    for parte in compat.split("\x00"):
        if parte.startswith("brcm,bcm"):
            return parte.split(",", 1)[1].upper()
    return ""


def _cpu():
    modello = _soc()
    if not modello:
        for riga in _leggi("/proc/cpuinfo").splitlines():
            if riga.lower().startswith(("model name", "hardware")):
                modello = riga.split(":", 1)[1].strip()
                if modello:
                    break
    if not modello:
        modello = platform.processor() or "?"
    nuclei = os.cpu_count() or 1
    freq = ""
    try:
        k = int(_leggi("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"))
        freq = " @ %.2f GHz" % (k / 1000000.0)
    except Exception:
        pass
    return "%s (%d)%s" % (modello, nuclei, freq)


def _wm():
    """Window manager attivo (solo se c'è una sessione X)."""
    for processo, etichetta in (("openbox", "Openbox"), ("xfwm4", "Xfwm4"),
                                ("metacity", "Metacity"), ("mutter", "Mutter"),
                                ("fluxbox", "Fluxbox")):
        try:
            if subprocess.run(["pgrep", "-x", processo],
                              capture_output=True, timeout=2).returncode == 0:
                return etichetta + " (X11)"
        except Exception:
            continue
    return ""


def _cursore():
    """Tema del cursore dal display :0 (xrdb)."""
    # Il servizio gira come root: per leggere il display della sessione X
    # serve anche l'XAUTHORITY usato da lightdm.
    for authority in ("/var/run/lightdm/root/:0", "/home/pi/.Xauthority", ""):
        ambiente = {"DISPLAY": ":0", "PATH": "/usr/bin:/bin"}
        if authority:
            ambiente["XAUTHORITY"] = authority
        try:
            r = subprocess.run(["xrdb", "-query"], capture_output=True, text=True,
                               timeout=3, env=ambiente)
            for riga in r.stdout.splitlines():
                if riga.lower().startswith("xcursor.theme:"):
                    return riga.split(":", 1)[1].strip()
        except Exception:
            continue
    return ""


_GPU = {
    "BCM2712": "Broadcom bcm2712-v3d [Integrated]",
    "BCM2711": "Broadcom bcm2711-vc5 [Integrated]",
    "BCM2837": "Broadcom bcm2837-vc4 [Integrated]",
    "BCM2835": "Broadcom bcm2835-vc4 [Integrated]",
}


def _gpu():
    soc = _soc()
    if not soc:
        return ""
    return _GPU.get(soc, "Broadcom %s [Integrated]" % soc.lower())


def _filesystem():
    try:
        r = subprocess.run(["df", "-T", "/"], capture_output=True, text=True, timeout=3)
        parti = r.stdout.strip().splitlines()[-1].split()
        if len(parti) >= 2:
            return parti[1]
    except Exception:
        pass
    return ""


def _host():
    modello = _leggi("/proc/device-tree/model")
    if modello:
        return modello.replace("\x00", "").strip()
    return platform.node() or "?"


def _shell():
    try:
        r = subprocess.run(["bash", "-c", "echo $BASH_VERSION"],
                           capture_output=True, text=True, timeout=3)
        versione = (r.stdout or "").strip()
        if versione:
            return "bash %s" % versione.split("(")[0]
    except Exception:
        pass
    return os.environ.get("SHELL", "?")


def raccogli():
    """Ritorna gruppi di righe, misure con barra, telemetria per la HUD."""
    osr = _os_release()
    usata, tot, swap_u, swap_t = _memoria()
    disco_u, disco_t = _disco()
    pct_ram = _percentuale(usata, tot)
    pct_disco = _percentuale(disco_u, disco_t)

    # temperatura numerica anche per la barra
    temp_val = None
    try:
        temp_val = int(_leggi("/sys/class/thermal/thermal_zone0/temp")) / 1000.0
    except Exception:
        pass
    pct_temp = 0 if temp_val is None else max(0, min(100, int(temp_val * 100 / 85)))

    hardware = [
        ["Host", _host()],
        ["CPU", _cpu()],
        ["GPU", _gpu()],
    ]
    sistema = [
        ["OS", "%s %s" % (osr.get("PRETTY_NAME", "?"), platform.machine())],
        ["Kernel", "%s %s" % (platform.system(), platform.release())],
        ["Uptime", _uptime()],
        ["Pacchetti", "%d (dpkg)" % _pacchetti()],
        ["Shell", _shell()],
    ]
    for etichetta, valore in (("WM", _wm()), ("Cursore", _cursore())):
        if valore:
            sistema.append([etichetta, valore])
    sistema += [
        ["Locale", os.environ.get("LANG", "?")],
        ["Carico", "%.2f  %.2f  %.2f" % os.getloadavg()],
    ]

    rete = [
        ["WLAN", _wifi() or "n/d"],
        ["Indirizzo", _indirizzi()],
    ]
    ts = _tailscale()
    if ts:
        rete.append(["Tailscale", ts])

    gruppi = [
        {"titolo": "Hardware", "righe": [r for r in hardware if r[1]]},
        {"titolo": "Sistema", "righe": sistema},
        {"titolo": "Rete", "righe": rete},
    ]

    misure = [
        {"etichetta": "RAM", "valore": pct_ram,
         "testo": "%s / %s" % (_byte(usata), _byte(tot))},
        {"etichetta": "Disco", "valore": pct_disco,
         "testo": "%s / %s · %s" % (_byte(disco_u), _byte(disco_t), _filesystem())},
        {"etichetta": "Temp", "valore": pct_temp,
         "testo": ("%.1f °C" % temp_val) if temp_val is not None else "n/d"},
        {"etichetta": "Swap", "valore": _percentuale(swap_u, swap_t),
         "testo": "%s / %s" % (_byte(swap_u), _byte(swap_t))},
    ]

    carico = os.getloadavg()
    nuclei = max(1, os.cpu_count() or 1)
    telemetria = {
        "temp": ("%.0f°" % temp_val) if temp_val is not None else "n/d",
        "cpu": "%d%%" % min(100, int(carico[0] * 100 / nuclei)),
        "ram": "%d%%" % pct_ram,
    }
    return gruppi, misure, telemetria


if __name__ == "__main__":
    gruppi, misure, tel = raccogli()
    for g in gruppi:
        print("\n[%s]" % g["titolo"])
        larg = max(len(k) for k, _ in g["righe"]) if g["righe"] else 0
        for k, v in g["righe"]:
            print("  %-*s : %s" % (larg, k, v))
    print("\n[barre]")
    for m in misure:
        print("  %-6s %3d%%  %s" % (m["etichetta"], m["valore"], m["testo"]))
    print("\ntelemetria:", tel)
