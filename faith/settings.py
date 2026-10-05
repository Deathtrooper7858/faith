"""Constantes globales del juego (todas las magnitudes de tiempo en milisegundos
o segundos según se indica; las velocidades en píxeles por segundo)."""

TITLE = "Faith of Surviving"
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60

# ── Mundo ────────────────────────────────────────────────────────────────────
TILE = 64
CHUNK_TILES = 8
CHUNK_PX = TILE * CHUNK_TILES
LOAD_RADIUS = 1          # chunks cargados alrededor del jugador (3x3)
KEEP_RADIUS = 2          # chunks que se conservan antes de descartarse
SPAWN_CLEAR_TILES = 7    # radio de pasto garantizado alrededor del inicio

# ── Ciclo día / noche ────────────────────────────────────────────────────────
DAY_LENGTH_MS = 14 * 60 * 1000       # un día completo = 14 minutos reales
START_TIME_FRAC = 0.30               # el juego empieza por la mañana

# ── Jugador ──────────────────────────────────────────────────────────────────
WALK_SPEED = 215.0
RUN_SPEED = 330.0
PLAYER_FOOT_W, PLAYER_FOOT_H = 26, 16
MAX_HEALTH = MAX_FOOD = MAX_THIRST = MAX_STAMINA = 100.0

FOOD_DECAY = 0.11          # por segundo
THIRST_DECAY = 0.17
RUN_DECAY_MULT = 1.8
STAMINA_DRAIN = 22.0       # por segundo corriendo
STAMINA_REGEN = 24.0
STARVE_DAMAGE = 1.2        # vida por segundo con hambre/sed a 0
REGEN_RATE = 0.9           # vida por segundo si estás bien alimentado
INVULN_MS = 650            # invulnerabilidad tras recibir daño
INTERACT_RANGE = 78
REACH = 82                 # alcance de herramientas

HOTBAR_SLOTS = 8
GRID_COLS, GRID_ROWS = 8, 3

# ── Costes / daño ────────────────────────────────────────────────────────────
LAVA_DPS = 14.0
WATER_SLOW = 0.55
DEFENSE_PER_POINT = 0.025  # 2.5 % menos de daño por punto de defensa
DEFENSE_CAP = 0.75
SHIELD_BLOCK = 0.70        # reducción extra con escudo en guardia

# ── Spawns ───────────────────────────────────────────────────────────────────
MAX_ENEMIES_SURFACE = 9
MAX_ENEMIES_CAVE = 12
MAX_ANIMALS = 14

# ── Interfaz (colores) ──────────────────────────────────────────────────────
C_TEXT = (236, 236, 244)
C_DIM = (150, 152, 170)
C_GOLD = (255, 214, 92)
C_PANEL = (18, 20, 30, 225)
C_PANEL_EDGE = (82, 88, 120)
C_SLOT = (44, 48, 64)
C_SLOT_EDGE = (78, 84, 110)
C_SLOT_HOVER = (74, 82, 112)
C_HP = (222, 64, 70)
C_FOOD = (232, 150, 52)
C_WATER = (66, 158, 232)
C_STAMINA = (112, 214, 96)
C_BAD = (230, 90, 90)
C_GOOD = (120, 220, 130)

AUTOSAVE_SECONDS = 75

CAVE_DARK = 188.0
CAVE_AMBIENT = (46, 46, 76)
