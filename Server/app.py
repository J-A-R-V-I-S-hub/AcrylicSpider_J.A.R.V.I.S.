#!/usr/bin/env/python3
# File name   : app.py
# Website     : www.adeept.com
# Author      : Adeept
# Date        : 2025/04/25
from importlib import import_module
import os
from flask import (Flask, render_template, Response, send_from_directory,
                   jsonify, request, redirect)
from flask_cors import *
import camera_opencv
from camera_opencv import Camera
import threading
import time
import hmac
import SpiderG
import comandi
import imu
import sistema


app = Flask(__name__)
CORS(app, supports_credentials=True)

# ── protezione del pannello comandi ─────────────────────────
# Protetto SOLO /comandi e /api/comando*: il pannello Vue e lo streaming
# video restano aperti come prima, così non si rompe niente di quello che
# già funziona.
#
# Le credenziali NON stanno nel codice: si leggono da Server/.env
# (che è in .gitignore) oppure dalle variabili d'ambiente. Il file .env
# deve contenere due righe:  COMANDI_USER=...  e  COMANDI_PASS=...


def _load_env(percorso):
    """Lettore .env minimale (CHIAVE=valore, righe # ignorate).

    Volutamente senza dipendenze: python-dotenv non è installato su questo
    sistema e aggiungerlo solo per due variabili non vale il rischio.
    """
    valori = {}
    try:
        with open(percorso, 'r') as f:
            for riga in f:
                riga = riga.strip()
                if not riga or riga.startswith('#') or '=' not in riga:
                    continue
                chiave, valore = riga.split('=', 1)
                valore = valore.strip()
                if len(valore) >= 2 and valore[0] == valore[-1] and valore[0] in '"\'':
                    valore = valore[1:-1]
                valori[chiave.strip()] = valore
    except OSError:
        pass
    return valori


_ENV = _load_env(os.path.join(os.path.dirname(os.path.realpath(__file__)), '.env'))

COMANDI_USER = os.environ.get('COMANDI_USER') or _ENV.get('COMANDI_USER') or ''
COMANDI_PASS = os.environ.get('COMANDI_PASS') or _ENV.get('COMANDI_PASS') or ''

if not COMANDI_USER or not COMANDI_PASS:
    print("app: ATTENZIONE Server/.env mancante o incompleto — "
          "il pannello /comandi resta SENZA password", flush=True)


# ── sessione: cookie firmato con HMAC ───────────────────────
# Il popup del browser (Basic auth) non si può graficare: usiamo una pagina
# di login in stile J.A.R.V.I.S. e un cookie firmato. La Basic resta accettata
# in parallelo, così curl e gli script continuano a funzionare con -u.

import hashlib
import time

_SEGRETO = hashlib.sha256(
    ("%s|%s|jarvis" % (COMANDI_USER, COMANDI_PASS)).encode()).hexdigest()
COOKIE = "jarvis_sess"
DURATA = 30 * 24 * 3600          # 30 giorni
_tentativi = {}                  # ip -> (numero, ultimo tentativo)


def _firma(valore):
    return hmac.new(_SEGRETO.encode(), valore.encode(), hashlib.sha256).hexdigest()


def _sessione_valida():
    valore = request.cookies.get(COOKIE)
    if not valore:
        return False
    parti = valore.split('|')
    if len(parti) != 3:
        return False
    utente, scadenza, firma = parti
    if not hmac.compare_digest(utente, COMANDI_USER):
        return False
    try:
        if int(scadenza) < time.time():
            return False
    except ValueError:
        return False
    return hmac.compare_digest(firma, _firma("%s|%s" % (utente, scadenza)))


def _basic_valida():
    a = request.authorization
    return bool(a and a.type == 'basic'
                and hmac.compare_digest(a.username or '', COMANDI_USER)
                and hmac.compare_digest(a.password or '', COMANDI_PASS))


def _richiede_auth(percorso):
    """False per le poche cose che devono restare raggiungibili senza login."""
    return (percorso not in ('/login', '/logout')
            and not percorso.startswith('/js/')
            and not percorso.startswith('/favicon'))


@app.before_request
def _auth_pannello():
    if not _richiede_auth(request.path):
        return None
    if not COMANDI_USER or not COMANDI_PASS:
        return None
    if _sessione_valida() or _basic_valida():
        return None
    if request.path.startswith('/api/'):
        return jsonify({'ok': False, 'errore': 'autenticazione richiesta'}), 401
    return redirect('/login?next=' + request.path.lstrip('/'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return send_from_directory(dir_path + '/dist', 'login.html')

    ip = request.remote_addr or '?'
    numero, ultimo = _tentativi.get(ip, (0, 0))
    if numero >= 5 and time.time() - ultimo < 30:
        return redirect('/login?errore=attendi')

    utente = request.form.get('utente', '')
    password = request.form.get('password', '')
    if (hmac.compare_digest(utente, COMANDI_USER)
            and hmac.compare_digest(password, COMANDI_PASS)):
        _tentativi.pop(ip, None)
        scadenza = int(time.time()) + DURATA
        valore = "%s|%d" % (COMANDI_USER, scadenza)
        risposta = redirect('/' + request.form.get('next', '').lstrip('/'))
        risposta.set_cookie(COOKIE, valore + '|' + _firma(valore),
                            max_age=DURATA, httponly=True, samesite='Lax')
        return risposta

    _tentativi[ip] = (numero + 1, time.time())
    return redirect('/login?errore=1')


@app.route('/logout')
def logout():
    risposta = redirect('/login')
    risposta.delete_cookie(COOKIE)
    return risposta

# La telecamera NON deve bloccare l'avvio del pannello: il suo flat è
# tollerante e a volte la pipeline va in timeout per minuti.
# Viene quindi aperta in un thread; fino a quando non è pronta (o se
# fallisce) lo stream serve un fotogramma segnaposto.
camera = None
_camera_lock = threading.Lock()
RETRY_SECONDS = 15      # ogni quanto ritentare se la camera non parte


def _camera_worker():
    """Apre la camera; se fallisce riprova ogni RETRY_SECONDS.
    Il pannello resta sempre disponibile: prima o poi il flat fa contatto."""
    global camera
    while True:
        with _camera_lock:
            already = camera is not None
        if already:
            time.sleep(10)
            continue
        try:
            c = Camera()
            with _camera_lock:
                camera = c
            print("camera: pronta", flush=True)
        except Exception as e:
            print("camera: non disponibile (%s) — riprovo fra %ds"
                  % (e, RETRY_SECONDS), flush=True)
            time.sleep(RETRY_SECONDS)


threading.Thread(target=_camera_worker, daemon=True).start()


def _placeholder_frame():
    try:
        from PIL import Image, ImageDraw
        import io
        img = Image.new("RGB", (640, 480), (10, 12, 18))
        d = ImageDraw.Draw(img)
        d.text((30, 215), "CAMERA OFFLINE", fill=(255, 179, 71))
        d.text((30, 240), "in attesa del flat CSI...", fill=(120, 130, 150))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=70)
        return buf.getvalue()
    except Exception:
        return b""


PLACEHOLDER = _placeholder_frame()


def gen(_camera=None):
    """Video streaming generator function."""
    global camera
    errors = 0
    while True:
        with _camera_lock:
            cam = camera
        if cam is None:
            frame = PLACEHOLDER
            time.sleep(0.5)
        else:
            try:
                frame = cam.get_frame()
                errors = 0
            except Exception:
                errors += 1
                frame = PLACEHOLDER
                # dopo 20 errori consecutivi considero la camera caduta
                # e lascio che il worker la riapra
                if errors >= 20:
                    with _camera_lock:
                        camera = None
                    errors = 0
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
    return Response(gen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

dir_path = os.path.dirname(os.path.realpath(__file__))

@app.route('/api/img/<path:filename>')
def sendimg(filename):
    return send_from_directory(dir_path+'/dist/img', filename)

@app.route('/js/<path:filename>')
def sendjs(filename):
    return send_from_directory(dir_path+'/dist/js', filename)

@app.route('/css/<path:filename>')
def sendcss(filename):
    return send_from_directory(dir_path+'/dist/css', filename)

@app.route('/api/img/icon/<path:filename>')
def sendicon(filename):
    return send_from_directory(dir_path+'/dist/img/icon', filename)

@app.route('/fonts/<path:filename>')
def sendfonts(filename):
    return send_from_directory(dir_path+'/dist/fonts', filename)

@app.route('/jarvis')
def jarvis_page():
    """Control center J.A.R.V.I.S.: mosse nostre + comandi del pannello originale."""
    return send_from_directory(dir_path + '/dist', 'jarvis.html')


@app.route('/comandi')
def comandi_page():
    """/comandi è stato rinominato in /jarvis: redirect per i vecchi segnalibri."""
    return redirect('/jarvis')


@app.route('/api/comandi')
def api_comandi_stato():
    """Stato corrente: occupato / ultima mossa / esito."""
    return jsonify(comandi.stato())


@app.route('/api/livella', methods=['POST'])
def api_livella():
    """Mette il corpo in piano muovendo i servi centrali (livella() di wakeup).

    È un'azione, non un comando in loop: prende il lucchetto, livella e lo
    rilascia. Se una mossa è in corso risponde 409 invece di accavallarsi.
    """
    import comandi
    import wakeup
    if not comandi.LOCK.acquire(blocking=False):
        return jsonify({'ok': False, 'messaggio': 'una mossa è in corso'}), 409
    try:
        SpiderG.Servo.pause()
        wakeup.livella(passi=5)
        esito = wakeup.throttled()
        return jsonify({'ok': True, 'tensione': esito == 0})
    except Exception as e:
        return jsonify({'ok': False, 'messaggio': str(e)}), 500
    finally:
        comandi.LOCK.release()


@app.route('/api/imu')
def api_imu():
    """Assetto corrente per la bolla live: roll, pitch e inclinazione."""
    try:
        return jsonify(imu.leggi())
    except Exception as e:
        return jsonify({'ok': False, 'errore': str(e)}), 500


@app.route('/api/sistema')
def api_sistema():
    """Dati di sistema per la scheda 'Sistema' (neofetch dinamico)."""
    try:
        gruppi, misure, telemetria = sistema.raccogli()
    except Exception as e:
        return jsonify({'gruppi': [{'titolo': 'Errore', 'righe': [['Errore', str(e)]]}],
                        'misure': [], 'telemetria': {}}), 500
    return jsonify({'gruppi': gruppi, 'misure': misure, 'telemetria': telemetria})


@app.route('/api/comando/stop', methods=['POST'])
def api_comando_stop():
    """Ferma qualsiasi loop in corso."""
    ok, messaggio = comandi.ferma()
    return jsonify({'ok': ok, 'messaggio': messaggio})


@app.route('/api/comando/<nome>', methods=['POST'])
def api_comando(nome):
    """Interruttore: avvia la mossa in loop, o la ferma se è già in corso."""
    ok, messaggio = comandi.avvia(nome)
    return jsonify({'ok': ok, 'messaggio': messaggio}), (200 if ok else 409)


@app.route('/<path:filename>')
def sendgen(filename):
    return send_from_directory(dir_path+'/dist', filename)

@app.route('/')
def index():
    return send_from_directory(dir_path+'/dist', 'index.html')

class webapp:
    def __init__(self):
        self.camera = camera

    def modeselect(self, modeInput):
        Camera.modeSelect = modeInput

    def modeselectApp(self, modeInput):
        camera_opencv.APPMode = modeInput

    def colorFindSet(self, H, S, V):
        camera.colorFindSet(H, S, V)

    def colorFindSetApp(self, H, S, V):
        camera.colorFindSetApp(H, S, V)

    def thread(self):
        app.run(host='0.0.0.0', threaded=True)

    def startthread(self):
        fps_threading=threading.Thread(target=self.thread)         #Define a thread for FPV and OpenCV
        fps_threading.setDaemon(False)                             #'True' means it is a front thread,it would close when the mainloop() closes
        fps_threading.start()                                     #Thread starts


