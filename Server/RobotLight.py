#!/usr/bin/env python3
# RobotLight.py — backend WS2812 via rpi_ws281x su GPIO12
# Adattato per l'hardware DarkPaw con cablaggio "vecchia revisione"
# (strisce collegate a GPIO12, non allo SPI). API identica a quella attesa
# dal codice V3: classe Adeept_SPI_LedPixel con breath/police/flowing/rainbow.

import time
import threading
from rpi_ws281x import PixelStrip, Color, WS2811_STRIP_GRB

LED_PIN      = 12        # GPIO12 (PWM0) — cablaggio del ragno
LED_FREQ_HZ  = 800000
LED_DMA      = 10
LED_INVERT   = False
LED_CHANNEL  = 0


class Adeept_SPI_LedPixel(threading.Thread):
    def __init__(self, count=16, bright=255, sequence='GRB', bus=0, device=0, *args, **kwargs):
        super(Adeept_SPI_LedPixel, self).__init__(*args, **kwargs)
        self.daemon = True
        self.led_count = count
        self.led_brightness = bright
        self.led_init_state = 0
        self.lightMode = 'none'
        self.pixels = [(0, 0, 0) for _ in range(count)]

        self.colorBreathR = 0
        self.colorBreathG = 0
        self.colorBreathB = 0
        self.colorFlowingR = 0
        self.colorFlowingG = 0
        self.colorFlowingB = 0

        self.led_begin(bus, device)
        self.__flag = threading.Event()
        self.__flag.set()
        self.__running = threading.Event()
        self.__running.set()

    # ── init ─────────────────────────────────────────────────
    def led_begin(self, bus=0, device=0):
        try:
            self.strip = PixelStrip(self.led_count, LED_PIN, LED_FREQ_HZ,
                                    LED_DMA, LED_INVERT, self.led_brightness,
                                    LED_CHANNEL, WS2811_STRIP_GRB)
            self.strip.begin()
            self.set_all_led_color(0, 0, 0)
            self.show()
            self.led_init_state = 1
        except Exception as e:
            print("WS2812 init error:", e)
            self.led_init_state = 0

    def check_spi_state(self):
        return self.led_init_state

    def spi_gpio_info(self):
        print("WS2812: GPIO%d (PWM0, rpi_ws281x) — %d pixel" % (LED_PIN, self.led_count))

    def led_close(self):
        try:
            self.pause()
            self.set_all_led_color(0, 0, 0)
            self.show()
        except Exception:
            pass

    # ── buffer ───────────────────────────────────────────────
    def set_led_count(self, count):
        self.led_count = count
        self.pixels = [(0, 0, 0) for _ in range(count)]

    def set_led_type(self, rgb_type):
        pass

    def set_led_brightness(self, brightness):
        self.led_brightness = max(0, min(255, int(brightness)))
        try:
            self.strip.setBrightness(self.led_brightness)
        except Exception:
            pass

    def _clamp(self, v):
        return max(0, min(255, int(v)))

    def set_ledpixel(self, index, r, g, b):
        if 0 <= index < self.led_count:
            self.pixels[index] = (self._clamp(r), self._clamp(g), self._clamp(b))

    def set_led_color_data(self, index, r, g, b):
        self.set_ledpixel(index, r, g, b)

    def set_led_color(self, index, r, g, b):
        self.set_ledpixel(index, r, g, b)

    def set_led_rgb_data(self, index, color):
        self.set_ledpixel(index, color[0], color[1], color[2])

    def set_led_rgb(self, index, color):
        self.set_ledpixel(index, color[0], color[1], color[2])

    def set_all_led_color_data(self, r, g, b):
        for i in range(self.led_count):
            self.pixels[i] = (self._clamp(r), self._clamp(g), self._clamp(b))

    def set_all_led_color(self, r, g, b):
        self.set_all_led_color_data(r, g, b)

    def set_all_led_rgb_data(self, color):
        self.set_all_led_color_data(color[0], color[1], color[2])

    def set_all_led_rgb(self, color):
        self.set_all_led_color_data(color[0], color[1], color[2])

    def show(self):
        try:
            for i, (r, g, b) in enumerate(self.pixels):
                self.strip.setPixelColor(i, Color(r, g, b))
            self.strip.show()
        except Exception as e:
            print("WS2812 show error:", e)

    # ── modalità ─────────────────────────────────────────────
    def pause(self):
        self.lightMode = 'none'

    def resume(self):
        self.__flag.set()

    def suspend(self):
        self.__flag.clear()

    def breath(self, R_input, G_input, B_input):
        self.colorBreathR, self.colorBreathG, self.colorBreathB = R_input, G_input, B_input
        self.lightMode = 'breath'
        self.resume()

    def police(self):
        self.lightMode = 'police'
        self.resume()

    def flowing(self, R_input, G_input, B_input):
        self.colorFlowingR, self.colorFlowingG, self.colorFlowingB = R_input, G_input, B_input
        self.lightMode = 'flowing'
        self.resume()

    def rainbow(self, R_input=0, G_input=0, B_input=0):
        self.lightMode = 'rainbow'
        self.resume()

    # ── loop ─────────────────────────────────────────────────
    def breathProcessing(self):
        # Respiro lento e naturale: easing sinusoidale, ~6 s per ciclo completo.
        import math
        r, g, b = self.colorBreathR, self.colorBreathG, self.colorBreathB
        steps = 140
        while self.lightMode == 'breath':
            for i in range(steps):
                if self.lightMode != 'breath':
                    break
                k = (1 - math.cos(2 * math.pi * i / steps)) / 2   # 0 → 1 → 0
                k = 0.06 + 0.94 * k                              # non si spegne del tutto
                self.set_all_led_color(int(r * k), int(g * k), int(b * k))
                self.show()
                time.sleep(0.043)

    def policeProcessing(self):
        half = max(1, self.led_count // 2)
        while self.lightMode == 'police':
            for _ in range(3):
                if self.lightMode != 'police':
                    break
                for i in range(self.led_count):
                    self.pixels[i] = (255, 0, 0) if i < half else (0, 0, 0)
                self.show()
                time.sleep(0.12)
                for i in range(self.led_count):
                    self.pixels[i] = (0, 0, 255) if i < half else (255, 0, 0)
                self.show()
                time.sleep(0.12)

    def flowingProcessing(self):
        r, g, b = self.colorFlowingR, self.colorFlowingG, self.colorFlowingB
        pos = 0
        while self.lightMode == 'flowing':
            for i in range(self.led_count):
                if self.lightMode != 'flowing':
                    break
                self.pixels[i] = (r, g, b) if i == pos else (0, 0, 0)
                self.show()
                time.sleep(0.06)
            pos = (pos + 1) % self.led_count

    def rainbowProcessing(self):
        offset = 0
        while self.lightMode == 'rainbow':
            for i in range(self.led_count):
                if self.lightMode != 'rainbow':
                    break
                h = (i * 256 // self.led_count + offset) % 256
                if h < 85:
                    self.pixels[i] = (255 - h * 3, h * 3, 0)
                elif h < 170:
                    h -= 85
                    self.pixels[i] = (0, 255 - h * 3, h * 3)
                else:
                    h -= 170
                    self.pixels[i] = (h * 3, 0, 255 - h * 3)
            self.show()
            offset = (offset + 4) % 256
            time.sleep(0.05)

    def run(self):
        while self.__running.isSet():
            self.__flag.wait()
            mode = self.lightMode
            if mode == 'breath':
                self.breathProcessing()
            elif mode == 'police':
                self.policeProcessing()
            elif mode == 'flowing':
                self.flowingProcessing()
            elif mode == 'rainbow':
                self.rainbowProcessing()
            else:
                time.sleep(0.1)
