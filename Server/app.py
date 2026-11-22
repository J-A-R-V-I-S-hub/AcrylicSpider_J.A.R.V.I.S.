#!/usr/bin/env/python3
# File name   : app.py
# Website     : www.adeept.com
# Author      : Adeept
# Date        : 2025/04/25
from importlib import import_module
import os
from flask import Flask, render_template, Response, send_from_directory
from flask_cors import *
import camera_opencv
from camera_opencv import Camera
import threading
import time


app = Flask(__name__)
CORS(app, supports_credentials=True)

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


