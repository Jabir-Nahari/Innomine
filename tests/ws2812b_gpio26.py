import os
import sys
import time
from pathlib import Path


# Allow running via `python tests/ws2812b_gpio26.py` from any cwd.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _clamp_u8(x: float) -> int:
    x = int(round(x))
    if x < 0:
        return 0
    if x > 255:
        return 255
    return x


def _apply_brightness(rgb: tuple[int, int, int], brightness: float) -> tuple[int, int, int]:
    r, g, b = rgb
    return (_clamp_u8(r * brightness), _clamp_u8(g * brightness), _clamp_u8(b * brightness))


def _pack_pixels(
    rgb: tuple[int, int, int],
    num_pixels: int,
    order: str,
) -> bytes:
    r, g, b = rgb
    mapping = {"R": r, "G": g, "B": b}
    try:
        triplet = bytes([mapping[c] for c in order])
    except KeyError as e:
        raise ValueError(f"Invalid LED_ORDER={order!r}; expected permutation of 'RGB' like 'GRB'.") from e
    return triplet * num_pixels


def _try_neopixel_class(num_pixels: int, brightness: float, order: str):
    """Try the high-level NeoPixel class first (fastest/most reliable if supported)."""
    import board
    import neopixel

    # Per Adafruit CircuitPython NeoPixel docs, the exported order constants are:
    # `RGB`, `GRB`, `RGBW`, `GRBW` (not arbitrary permutations like "RBG").
    supported_orders = ["RGB", "GRB", "RGBW", "GRBW"]
    pixel_order = getattr(neopixel, order, None)
    if pixel_order is None or order not in supported_orders:
        raise ValueError(
            f"LED_ORDER={order!r} is not supported by neopixel.NeoPixel on this platform; "
            f"use one of {supported_orders} or rely on the bit-banged fallback."
        )

    # NOTE: On Raspberry Pi, the backend may require specific pins (commonly GPIO18/12/13/19).
    # You requested GPIO26; if the backend rejects it, we'll fall back to bit-banged neopixel_write.
    pixels = neopixel.NeoPixel(
        board.D26,
        num_pixels,
        brightness=brightness,
        auto_write=False,
        pixel_order=pixel_order,
    )
    return pixels


def _try_bitbang_write(num_pixels: int, brightness: float, order: str):
    """Fallback path that can work on arbitrary GPIO pins, but is more timing-sensitive."""
    import board
    import digitalio
    import neopixel_write

    pin = digitalio.DigitalInOut(board.D26)

    def write_all(rgb: tuple[int, int, int]):
        buf = _pack_pixels(rgb, num_pixels=num_pixels, order=order)
        neopixel_write.neopixel_write(pin, buf)

    def deinit():
        try:
            pin.deinit()
        except Exception:
            pass

    return write_all, deinit


def main() -> int:
    print("WS2812B test starting (data: GPIO26).")
    print("Wiring reminders: common GND, 5V power sized for current, and a 3.3V->5V level shifter is recommended.")

    try:
        num_pixels = int(os.getenv("LED_COUNT", "60"))
    except Exception:
        num_pixels = 60

    try:
        brightness = float(os.getenv("LED_BRIGHTNESS", "0.2"))
    except Exception:
        brightness = 0.2

    order = os.getenv("LED_ORDER", "GRB").strip().upper()
    sleep_s = float(os.getenv("SLEEP_S", "1"))

    # Colors are expressed as RGB.
    demo_colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 255),
        (0, 0, 0),
    ]

    # Path A: NeoPixel class (preferred)
    pixels = None
    try:
        pixels = _try_neopixel_class(num_pixels=num_pixels, brightness=brightness, order=order)
        print("Using neopixel.NeoPixel backend.")

        for rgb in demo_colors:
            pixels.fill(rgb)
            pixels.show()
            print(f"Set all pixels to {rgb} (order={order}, brightness={brightness}).")
            time.sleep(sleep_s)

        pixels.fill((0, 0, 0))
        pixels.show()
        print("Done.")
        return 0
    except Exception as e:
        print(f"NeoPixel backend failed to init on GPIO26 ({type(e).__name__}: {e}).")
        print("Falling back to bit-banged neopixel_write (may be less reliable at high pixel counts).")

    # Path B: Bit-banged writer
    try:
        write_all, deinit = _try_bitbang_write(num_pixels=num_pixels, brightness=brightness, order=order)
    except Exception as e:
        print(f"Bit-bang fallback failed to init ({type(e).__name__}: {e}).")
        print("On Raspberry Pi, WS2812 control often requires specific pins via DMA/PWM.")
        print("If this is a hard wiring constraint, consider moving the data line to GPIO18/12/13/19.")
        return 2

    try:
        for rgb in demo_colors:
            rgb2 = _apply_brightness(rgb, brightness)
            write_all(rgb2)
            print(f"Wrote all pixels {rgb} (applied brightness -> {rgb2}, order={order}).")
            time.sleep(sleep_s)

        write_all((0, 0, 0))
        print("Done.")
        return 0
    finally:
        deinit()


if __name__ == "__main__":
    raise SystemExit(main())
