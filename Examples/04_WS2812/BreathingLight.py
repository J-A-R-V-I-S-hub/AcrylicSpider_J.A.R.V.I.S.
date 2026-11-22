#!/usr/bin/env python3
# BreathingLight.py — esempio WS2812 con rpi_ws281x (GPIO12)
# Adattato al cablaggio del DarkPaw: le strisce sono su GPIO12, non sullo SPI.

import time
import math
from rpi_ws281x import PixelStrip, Color, WS2811_STRIP_GRB

LED_COUNT      = 16
LED_PIN        = 12
LED_FREQ_HZ    = 800000
LED_DMA        = 10
LED_BRIGHTNESS = 255
LED_INVERT     = False
LED_CHANNEL    = 0

strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA,
                   LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL, WS2811_STRIP_GRB)
strip.begin()

R, G, B = 70, 70, 255   # blu del "respiro"

try:
    print("Respiro blu — Ctrl+C per uscire")
    steps = 140
    while True:
        for i in range(steps):
            k = (1 - math.cos(2 * math.pi * i / steps)) / 2
            k = 0.06 + 0.94 * k
            c = Color(int(R * k), int(G * k), int(B * k))
            for p in range(LED_COUNT):
                strip.setPixelColor(p, c)
            strip.show()
            time.sleep(0.043)
except KeyboardInterrupt:
    print("\nSpento")
finally:
    for p in range(LED_COUNT):
        strip.setPixelColor(p, Color(0, 0, 0))
    strip.show()
