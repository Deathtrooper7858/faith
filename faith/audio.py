"""Efectos de sonido sintetizados proceduralmente (no requiere archivos de audio).
Si no hay dispositivo de audio el módulo se desactiva en silencio."""
import array
import math
import random
import pygame

_enabled = False
_sounds = {}
_volume = 0.55
_muted = False
_rng = random.Random(7)
RATE = 22050


def _synth(duration, freq=None, noise=0.0, decay=6.0, vibrato=0.0, sweep=0.0,
           wave="sine", attack=0.004):
    n = int(RATE * duration)
    buf = array.array("h")
    phase = 0.0
    for i in range(n):
        t = i / RATE
        f = (freq or 0) * (1.0 + sweep * t / max(duration, 1e-6))
        if vibrato:
            f *= 1.0 + 0.04 * math.sin(2 * math.pi * vibrato * t)
        phase += 2 * math.pi * f / RATE
        if wave == "square":
            tone = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave == "saw":
            tone = ((phase / math.pi) % 2.0) - 1.0
        else:
            tone = math.sin(phase)
        v = (tone if freq else 0.0) * (1.0 - noise) + (_rng.uniform(-1, 1) * noise)
        env = math.exp(-decay * t / max(duration, 1e-6) * 1.0)
        if t < attack:
            env *= t / attack
        buf.append(int(max(-1.0, min(1.0, v * env)) * 20000))
    return buf


def _cat(*parts):
    out = array.array("h")
    for p in parts:
        out.extend(p)
    return out


def _make_sound(data):
    import io
    import wave
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(data.tobytes())
    bio.seek(0)
    return pygame.mixer.Sound(bio)


def init():
    global _enabled
    import sys
    is_web = sys.platform == "emscripten" or "pygbag" in sys.modules
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
        elif not is_web:
            # En desktop reiniciamos con el formato exacto de las muestras (mono, 22 kHz)
            pygame.mixer.quit()
            pygame.mixer.init(frequency=RATE, size=-16, channels=1, buffer=512)
        _enabled = bool(pygame.mixer.get_init())
    except Exception:
        _enabled = False
        return False
    try:
        defs = {
            "swing": _synth(0.14, noise=0.85, decay=5, ),
            "hit": _cat(_synth(0.10, 150, 0.55, 9), _synth(0.04, 90, 0.2, 9)),
            "chop": _cat(_synth(0.09, 190, 0.45, 8), _synth(0.05, 120, 0.3, 8)),
            "mine": _cat(_synth(0.05, 1250, 0.25, 9), _synth(0.10, 820, 0.12, 8)),
            "pickup": _cat(_synth(0.05, 780, 0, 6), _synth(0.08, 1170, 0, 6)),
            "craft": _cat(_synth(0.06, 520, 0, 5), _synth(0.06, 660, 0, 5), _synth(0.10, 880, 0, 5)),
            "hurt": _synth(0.28, 210, 0.25, 5, sweep=-0.6, wave="saw"),
            "eat": _cat(_synth(0.04, 0, 1.0, 9), _synth(0.04, 0, 1.0, 9), _synth(0.05, 0, 1.0, 9)),
            "drink": _synth(0.30, 420, 0, 3, vibrato=14, sweep=0.5),
            "step": _synth(0.05, 0, 1.0, 12),
            "place": _synth(0.10, 110, 0.35, 8),
            "door": _synth(0.22, 140, 0.15, 4, sweep=0.8, wave="saw"),
            "click": _synth(0.03, 900, 0, 8),
            "arrow": _synth(0.18, 520, 0.1, 6, sweep=-0.7),
            "die": _synth(0.55, 260, 0.2, 3, sweep=-0.85, wave="saw"),
            "enemy_die": _synth(0.30, 330, 0.3, 4, sweep=-0.7, wave="square"),
            "levelup": _cat(_synth(0.08, 523, 0, 4), _synth(0.08, 659, 0, 4), _synth(0.14, 784, 0, 4)),
            "splash": _synth(0.14, 0, 0.9, 6),
            "sleep": _cat(_synth(0.2, 392, 0, 3), _synth(0.3, 294, 0, 3)),
        }
        for name, data in defs.items():
            try:
                _sounds[name] = _make_sound(data)
            except Exception:
                try:
                    _sounds[name] = pygame.mixer.Sound(buffer=data.tobytes())
                except Exception:
                    pass
    except Exception:
        _enabled = False
        _sounds.clear()
    return _enabled


def play(name, volume=1.0):
    if not _enabled or _muted:
        return
    s = _sounds.get(name)
    if s is not None:
        try:
            s.set_volume(max(0.0, min(1.0, _volume * volume)))
            s.play()
        except Exception:
            pass


def toggle_mute():
    global _muted
    _muted = not _muted
    return _muted


def is_muted():
    return _muted


def set_volume(v):
    global _volume
    _volume = max(0.0, min(1.0, v))
