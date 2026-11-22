#!/usr/bin/env python3
# FlowingLights.py — esempio WS2812 con rpi_ws281x (GPIO12)
# Effetto "inseguimento" sulle due strisce del DarkPaw.

import time
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


def wipe(color, wait=0.06):
    for i in range(LED_COUNT):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait)
    time.sleep(0.2)
    for i in range(LED_COUNT):
        strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()
        time.sleep(wait)


try:
    print("Inseguimento colori — Ctrl+C per uscire")
    while True:
        wipe(Color(255, 0, 0))
        wipe(Color(0, 255, 0))
        wipe(Color(0, 0, 255))
        wipe(Color(255, 255, 0))
        wipe(Color(0, 255, 255))
        wipe(Color(255, 0, 255))
except KeyboardInterrupt:
    print("\nSpento")
finally:
    for i in range(LED_COUNT):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()
