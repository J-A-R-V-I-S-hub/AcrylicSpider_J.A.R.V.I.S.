#!/usr/bin/python3
# setup.py — installazione di Acrylic Spider · J.A.R.V.I.S. su Raspberry Pi
#
# COSA FA, IN ORDINE
#   1. controlla di girare come root (serve per apt, systemd e GPIO)
#   2. installa i pacchetti di sistema (apt)
#   3. installa le librerie Python (pip)
#   4. crea il servizio del robot  → Adeept_Robot.service
#   5. crea il watchdog del WiFi   → wifi-watchdog.timer
#   6. prepara Server/.env con le credenziali del pannello
#   7. riavvia la Raspberry
#
# USO
#   sudo python3 setup.py               installazione completa
#   sudo python3 setup.py --dry-run     mostra cosa farebbe, senza toccare nulla
#   sudo python3 setup.py --no-reboot   non riavvia alla fine
#   sudo python3 setup.py --salta-pacchetti   solo servizi e configurazione
#   sudo python3 setup.py --reinstalla  forza l'installazione delle librerie
#
# RILANCIARLO È SICURO: i pacchetti apt già presenti vengono saltati, le
# librerie Python arrivano da requirements.txt con le versioni bloccate (pip
# non aggiorna nulla se sono già quelle), e servizio e Server/.env non vengono
# toccati se esistono già.
#
# TESTATO SU
#   Raspberry Pi 4 Model B · Debian 13 (trixie) aarch64 · Python 3.13
#
# NOTA: i pacchetti pip vengono installati con --break-system-packages da
# Debian 12 in poi, perché il sistema non permette più pip fuori da un venv.
# Qui è voluto: il servizio gira come root con il Python di sistema.

import os
import shutil
import subprocess
import sys
import time

DRY_RUN = "--dry-run" in sys.argv
NO_REBOOT = "--no-reboot" in sys.argv
SALTA_PACCHETTI = "--salta-pacchetti" in sys.argv   # solo servizi e configurazione
REINSTALLA = "--reinstalla" in sys.argv             # forza pip anche se presente

# ── informazioni sull'ambiente ──────────────────────────────
# Percorso del repo, senza la doppia barra che il codice Adeept generava.
thisPath = os.path.dirname(os.path.realpath(__file__))


def utente_reale():
    """Utente che ha lanciato sudo (serve solo per la home, non per i permessi).

    Ordine di tentativi, perché nessuno dei tre da solo è affidabile:
      1. SUDO_USER        → c'è quando si usa sudo (il caso normale)
      2. who -m           → sessione interattiva senza sudo
      3. proprietario del repo → ultimo ripiego sensato
    """
    utente = os.environ.get("SUDO_USER", "").strip()
    if not utente:
        try:
            utente = subprocess.check_output(["who", "-m"], text=True).split()[0]
        except Exception:
            utente = ""
    if not utente or utente == "root":
        try:
            import pwd
            utente = pwd.getpwuid(os.stat(thisPath).st_uid).pw_name
        except Exception:
            utente = "pi"
    return utente


username = utente_reale()
user_home = (os.popen(f"getent passwd {username} | cut -d: -f 6")
             .readline().strip()) or f"/home/{username}"

print(f"repo: {thisPath}")
print(f"home: {user_home}  (utente: {username})")
if DRY_RUN:
    print("modalità DRY-RUN: nessuna modifica verrà applicata\n")


def run_command(cmd=""):
    """Esegue un comando di shell e restituisce (stato, output)."""
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    output = p.stdout.read().decode("utf-8", "replace")
    return p.poll(), output


def esegui(cmd, mostra=True):
    """Esegue (o simula) un comando. In dry-run stampa soltanto."""
    if DRY_RUN:
        if mostra:
            print(f"  [dry-run] {cmd}")
        return 0, ""
    return run_command(cmd)


def check_rpi_model():
    """Ritorna 3, 4 o None secondo il modello di Raspberry Pi."""
    _, result = run_command("cat /proc/device-tree/model | awk '{print $3}'")
    result = result.strip()
    if result == "3":
        return 3
    if result == "4":
        return 4
    return None


def check_raspbain_version():
    """Numero maggiore della versione Debian (11, 12, 13, ...)."""
    _, result = run_command("cat /etc/debian_version | awk -F. '{print $1}'")
    try:
        return int(result.strip())
    except ValueError:
        return 0


def check_python_version():
    return (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)


def check_os_bit():
    """32 o 64 bit reali del sistema (indipendenti dal kernel)."""
    _, os_bit = run_command("getconf LONG_BIT")
    return int(os_bit)


def servizio_installato(nome):
    """True se l'unità esiste già, anche se è ferma.

    Prima si controllava solo 'is-active': un servizio installato ma spento
    veniva riscritto, perdendo eventuali personalizzazioni.
    """
    return os.path.exists(f"/etc/systemd/system/{nome}")


def pacchetto_apt_presente(nome):
    """True se il pacchetto apt risulta già installato."""
    r = subprocess.run(["dpkg-query", "-W", "-f=${Status}", nome],
                       capture_output=True, text=True)
    return "install ok installed" in r.stdout


def modulo_pip_presente(nome):
    """True se il modulo Python si importa già."""
    r = subprocess.run([sys.executable, "-c", f"import {nome}"],
                       capture_output=True)
    return r.returncode == 0


def scrivi_file(percorso, contenuto, modo=0o644, etichetta=""):
    """Scrive un file di sistema (o lo simula in dry-run)."""
    if DRY_RUN:
        print(f"  [dry-run] scriverei {percorso} ({len(contenuto)} byte)")
        return
    try:
        with open(percorso, "w") as f:
            f.write(contenuto)
        os.chmod(percorso, modo)
        print(f"  creato {percorso}{(' — ' + etichetta) if etichetta else ''}")
    except Exception as e:
        print(f"  ERRORE scrivendo {percorso}: {e}")


# ── 0 · root ────────────────────────────────────────────────
# apt, systemd e la creazione degli unit file richiedono i privilegi.
if os.geteuid() != 0 and not DRY_RUN:
    print("\nQuesto script va eseguito come root:")
    print("   sudo python3 setup.py\n")
    sys.exit(1)

# ── 1 · pacchetti di sistema ────────────────────────────────
# picamera2 e opencv vanno da apt: le versioni pip non sono compatibili
# con il libcamera di Raspberry Pi OS.
# Ogni pacchetto viene saltato se è già installato: così rilanciare lo
# script non aggiorna nulla e non cambia il comportamento del robot.
print("\n[1/6] pacchetti di sistema")

PACCHETTI_APT = [
    ("python3-picamera2", "camera (libcamera)"),
    ("python3-opencv", "cv2, riconoscimento colore"),
    ("opencv-data", "dati di opencv"),
    ("python3-smbus", "I2C: PCA9685, IMU, ADC"),
    ("i2c-tools", "diagnostica I2C"),
    ("python3-gpiozero", "GPIO"),
    ("python3-pigpio", "demone pigpio"),
    ("python3-pyqt5", "finestra grafica (opzionale)"),
    ("python3-opengl", "rendering (opzionale)"),
]

if SALTA_PACCHETTI:
    print("  saltati (--salta-pacchetti)")
else:
    esegui("apt-get update", mostra=False)
    for pacchetto, nota in PACCHETTI_APT:
        if pacchetto_apt_presente(pacchetto):
            print(f"  {pacchetto}: già installato")
            continue
        stato = 0
        for tentativo in range(3):
            stato = esegui(f"apt-get install -y {pacchetto}", mostra=False)[0]
            if stato == 0:
                break
        print(f"  {pacchetto}: {'installato' if stato == 0 else 'ERRORE'}  ({nota})")

# ── 2 · librerie Python ─────────────────────────────────────
# Si installa da requirements.txt, dove ogni versione è bloccata con ==.
# È l'unico modo per avere ESATTAMENTE l'ambiente che funziona: un
# `pip3 install X` senza versione prenderebbe l'ultima e potrebbe rompere
# il robot (es. websockets: il WebServer usa l'API legacy, dalla 14 non
# più garantita).
print("\n[2/6] librerie Python")

REQUISITI = os.path.join(thisPath, "requirements.txt")
BREAK = " --break-system-packages" if check_raspbain_version() >= 12 else ""

if SALTA_PACCHETTI:
    print("  saltati (--salta-pacchetti)")
elif not os.path.exists(REQUISITI):
    print(f"  {REQUISITI} non trovato: librerie non installate")
else:
    comando = f"pip3 install -r {REQUISITI}{BREAK}"
    if DRY_RUN:
        print(f"  [dry-run] {comando}")
        print("  (con le versioni bloccate, se sono già queste non cambia nulla)")
    elif modulo_pip_presente("websockets") and not REINSTALLA:
        # già tutto installato: pip conferma e non tocca niente
        stato = esegui(comando, mostra=False)[0]
        print(f"  versioni bloccate: {'già allineate' if stato == 0 else 'ERRORE'}")
        if stato != 0:
            print("  ecco il dettaglio di pip:")
            esegui(comando)
    else:
        stato = 1
        for tentativo in range(3):
            stato = esegui(comando, mostra=False)[0]
            if stato == 0:
                break
        if stato == 0:
            print("  installate le versioni di requirements.txt")
        else:
            print("  ERRORE, ecco il dettaglio di pip:")
            esegui(comando)

# ── 3 · servizio del robot ─────────────────────────────────
print("\n[3/6] servizio del robot")
robot_service = "Adeept_Robot.service"

if servizio_installato(robot_service):
    print(f"  {robot_service} già presente: non lo tocco")
else:
    # L'avvio diretto di python (senza startup.sh) fa sì che systemd sorvegli
    # il processo vero: se muore, lo riavvia davvero.
    unit = f"""[Unit]
Description=Adeept DarkPaw - robot control (WebServer)
After=wifi-hotspot-manager.service network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=root
WorkingDirectory={user_home}
ExecStart=/usr/bin/python3 {thisPath}/Server/WebServer.py
Restart=on-failure
RestartSec=5
KillMode=mixed
TimeoutStopSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    scrivi_file(f"/etc/systemd/system/{robot_service}", unit, etichetta="servizio robot")
    esegui("systemctl daemon-reload", mostra=False)
    esegui(f"systemctl enable {robot_service}", mostra=False)

# ── 4 · watchdog del WiFi ──────────────────────────────────
# Se all'avvio il modem è lento, il gestore apre l'hotspot di emergenza e il
# Pi resta lì. Questo timer, ogni minuto, prova a riportarlo sulla rete vera.
print("\n[4/6] watchdog del WiFi")
watchdog = "wifi-watchdog"
sorgente = f"{thisPath}/wifi-watchdog.sh"
destinazione = f"/usr/local/bin/{watchdog}.sh"

if os.path.exists(sorgente):
    if DRY_RUN:
        print(f"  [dry-run] copierei {sorgente} → {destinazione}")
    else:
        shutil.copyfile(sorgente, destinazione)
        os.chmod(destinazione, 0o755)
        print(f"  installato {destinazione}")

    unit_servizio = f"""[Unit]
Description=Mantiene il Pi agganciato al WiFi configurato
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=oneshot
ExecStart={destinazione}
"""
    unit_timer = f"""[Unit]
Description=Esegue il WiFi watchdog ogni minuto

[Timer]
OnBootSec=40
OnUnitActiveSec=60
AccuracySec=5

[Install]
WantedBy=timers.target
"""
    scrivi_file(f"/etc/systemd/system/{watchdog}.service", unit_servizio)
    scrivi_file(f"/etc/systemd/system/{watchdog}.timer", unit_timer)
    esegui("systemctl daemon-reload", mostra=False)
    esegui(f"systemctl enable --now {watchdog}.timer", mostra=False)
else:
    print(f"  {sorgente} non trovato: watchdog saltato")

# ── 5 · credenziali del pannello ───────────────────────────
# Il pannello /jarvis richiede una password. Le credenziali stanno in
# Server/.env, che non va committato. Se manca lo creiamo dal modello.
print("\n[5/6] credenziali del pannello")
env_reale = f"{thisPath}/Server/.env"
env_modello = f"{thisPath}/Server/.env.example"

if os.path.exists(env_reale):
    print("  Server/.env già presente: non lo tocco")
elif os.path.exists(env_modello):
    if DRY_RUN:
        print("  [dry-run] creerei Server/.env da .env.example")
    else:
        shutil.copyfile(env_modello, env_reale)
        os.chmod(env_reale, 0o600)
        print("  creato Server/.env con la password di esempio")
        print("     ATTENZIONE: cambia COMANDI_PASS prima di esporre il pannello")
else:
    print("  Server/.env.example non trovato: credenziali non configurate")

# ── 6 · riepilogo ──────────────────────────────────────────
print("\n[6/6] fatto")
print("""
Il robot è installato.

   servizio    sudo systemctl status Adeept_Robot
   pannello    http://<ip-del-pi>:5000/jarvis
   credenziali in Server/.env

Se la telecamera non è ancora montata, spegni la Raspberry e collegala
prima del primo avvio: la routine di risveglio muove subito i servi.
""")

if NO_REBOOT or DRY_RUN:
    print("riavvio saltato.\n")
else:
    print("riavvio tra 5 secondi… (Ctrl+C per annullare)")
    try:
        time.sleep(5)
        os.system("reboot")
    except KeyboardInterrupt:
        print("riavvio annullato.")
