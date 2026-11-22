<div align="center">

# Acrylic Spider · J.A.R.V.I.S.

**HRI · Human-Robot Interaction** — ragno quadrupede a scocca acrilica su Raspberry Pi 4.

Fork di [adeept/Adeept_DarkPaw-V3](https://github.com/adeept/Adeept_DarkPaw-V3) · hardware **ADR016** · **Robot HAT V3.2**

![HRI](https://img.shields.io/badge/HRI-Human--Robot_Interaction-4DD8FF?style=for-the-badge&labelColor=05080D)
![Robotics](https://img.shields.io/badge/ROBOTICS-QUADRUPED-FFB347?style=for-the-badge&labelColor=05080D)
![Python](https://img.shields.io/badge/PYTHON-3.13-4DD8FF?style=for-the-badge&labelColor=05080D)
![Arch](https://img.shields.io/badge/AARCH64-DEBIAN_13-FFB347?style=for-the-badge&labelColor=05080D)

</div>

---

## `//` Cos'è

Un ragno robotico a quattro zampe, **12 servi**, telecamera e strisce LED, comandabile dal browser. Il progetto parte dal codice Adeept e aggiunge: routine di risveglio dimostrativa, esibizione automatica ogni ora, pannello web, luci coordinate e una serie di correzioni per questa revisione hardware.

Tutto il movimento avviene **sul posto**: le diagonali lavorano sempre in opposizione (una zampa avanti, l'opposta indietro), così il corpo non trasla mai.

---

## `//` Hardware

| Componente | Dettaglio |
|---|---|
| Robot | Adeept DarkPaw — **ADR016**, scocca acrilica |
| Scheda | Raspberry Pi 4 Model B Rev 1.2 — 4 GB |
| Driver | **Robot HAT V3.2** — PCA9685 @ `0x40`, 12 canali servo |
| Servi | 12 × (Base, Middle, End) × 4 zampe |
| Telecamera | Pi Camera **ov5647** via CSI (libcamera / picamera2) |
| Luci | 2 strisce WS2812 su **GPIO12** (rpi_ws281x) + LED frontale su porta **P2** |
| Sensori | MPU-6050 @ `0x68` (IMU), ADS7830 @ `0x48` (tensione batteria) |

---

## `//` Software

| Livello | Stack |
|---|---|
| Sistema | Debian 13 (trixie) **aarch64**, kernel 6.18 |
| Python | 3.13 |
| Web | Flask (`:5000`) + WebSocket (`:8888`) |
| Camera | picamera2 + libcamera |
| Servi | Adafruit_PCA9685 su I2C-1 |
| Luci | rpi_ws281x (DMA/GPIO12) |

---

## `//` Cosa sa fare

| Sistema | Dettaglio |
|---|---|
| 🕷️ **Locomozione** | 12 servi, passo sul posto, diagonali opposte, inclinazioni, allungo zampe |
| 🎥 **Visione** | Streaming MJPEG dal pannello, inseguimento colore (OpenCV) |
| 🧭 **Sensori** | IMU MPU-6050, PID di stabilità, lettura batteria |
| 🌈 **Luci** | Strisce WS2812 (respiro, polizia, onda) + LED frontale |
| 🌐 **Controllo** | Pannello web da LAN e telefono, comandi via WebSocket |
| 🤖 **HRI** | Routine di risveglio di ~30 s che mostra tutte le capacità, eseguita all'avvio e **ogni ora** |

---

## `//` Routine di risveglio

All'accensione (e allo scatto di ogni ora) il ragno esegue una coreografia di ~30 secondi:

```
dondolio → inclinazione circolare → passo sul posto → onda doppia
→ allungo diagonale (destra avanti / sinistra indietro) → stiramento
→ alzata + respiro meccanico → muso in su → muso in giù
→ inclinazione circolare inversa → allungo diagonale opposto
→ corsa completa del servo → chiusura
```

Durante la sequenza: **strisce in modalità polizia**, **LED frontale fisso accesso**. Alla fine: frontale spento, strisce in respiro lento.

Parametri in `Server/wakeup.py`:

```python
UNITS = 3          # unità PWM per passo (velocità)
PAUSE = 0.10       # pause tra le pose
FRONT_LED_PORT = 2 # porta del LED frontale
DIAG_B, DIAG_E     # ampiezza allungo diagonale
TILT_E             # inclinazione muso su/giù
```

---

## `//` Esibizione oraria

`Server/hourly.py` — thread interno al WebServer: allo scatto dell'ora esegue la routine.

```python
ENABLED = True          # False per disattivare
HOURS = set(range(24))  # es. range(8, 23) = solo 08:00–22:59
EVERY = 1               # 1 = ogni ora
```

> **Nota:** il ragno si muove da solo per 30 s ogni ora. Tienilo lontano dal bordo del tavolo e, se dormi nella stessa stanza, limita `HOURS`.

---

## `//` Avvio rapido

```bash
# servizio (parte al boot e gestisce pannello + routine oraria)
sudo systemctl start Adeept_Robot

# pannello
http://<ip-del-pi>:5000
```

### Provare un singolo esempio

```bash
~/run-example.sh Examples/01_LED/LED.py
~/run-example.sh Examples/04_WS2812/BreathingLight.py
~/run-example.sh Server/wakeup.py
```

Lo script ferma il servizio (libera GPIO/I2C), esegue come root con display attivo e **riavvia il servizio** all'uscita (anche con `Ctrl+C`).

> Perché serve: un pin o il bus possono avere **un solo proprietario**. Con il servizio attivo un esempio dà `GPIO busy`.

---

## `//` Struttura del repo

```
Server/           web server, gestione servi, luci, camera, routine
  wakeup.py       coreografia di risveglio
  hourly.py       timer dell'esibizione oraria
  RobotLight.py   driver WS2812 (rpi_ws281x, GPIO12)
  Switch.py       LED frontale / porte P1-P2-P3 (GPIO 5/6/13)
  SpiderG.py      cinematica delle 12 zampe
Examples/         script di test per ogni componente
Client/           app desktop opzionale
```

---

## `//` Adattamenti per questa revisione hardware

Il codice Adeept V3 è scritto per una revisione più recente della HAT. Su questa scheda (V3.2) sono servite queste modifiche documentate:

| Componente | Adeept V3 | Questa HAT |
|---|---|---|
| PCA9685 | `0x5F` | **`0x40`** |
| Strisce WS2812 | SPI (`spidev`, GPIO10) | **rpi_ws281x su GPIO12** |
| Luci 1/2/3 | GPIO 9, 25, 11 | **GPIO 5, 6, 13** |

Senza questi adattamenti: i servi vanno in `OSError [Errno 5]` all'avvio, le strisce non si accendono e le luci risultano "disabilitate" per conflitto con lo SPI.

---

## `//` Crediti

Codice originale: **Adeept** — [adeept/Adeept_DarkPaw-V3](https://github.com/adeept/Adeept_DarkPaw-V3) (nessuna licenza esplicita: uso personale).

Adattamenti, routine e pannello: **Henry** — [J.A.R.V.I.S. Hub](https://github.com/J-A-R-V-I-S-hub)

<div align="center">

<sub><i>"Sometimes you gotta run before you can walk."</i> — Tony Stark</sub>

</div>
