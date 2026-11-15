from ursina import *
from panda3d.core import loadPrcFileData, AntialiasAttrib
import math, random, os, wave, struct

# ------------------------------------------------------------
#  OPCIONES
# ------------------------------------------------------------
FULLSCREEN = False              # ← No se abre en pantalla completa
ANCHO, ALTO = 1280, 720
LUCES_3D = True
MODELO_JUGADORA = 'jugadora.glb'
MODELO_ASESINA = 'asesina.glb'
ESCALA_GLB = 1.0

loadPrcFileData('', 'framebuffer-multisample 1\nmultisamples 4')

try:
    from ursina.shaders import lit_with_shadows_shader, unlit_shader
except Exception:
    lit_with_shadows_shader = None
    unlit_shader = None

hsv = color.hsv

# ------------------------------------------------------------
#  SONIDOS (se generan solos la primera vez)
# ------------------------------------------------------------
CARPETA = os.path.dirname(os.path.abspath(__file__))
SR = 22050

def guardar(nombre, muestras):
    ruta = os.path.join(CARPETA, nombre)
    with wave.open(ruta, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b''.join(
            struct.pack('<h', int(max(-1.0, min(1.0, m)) * 30000)) for m in muestras))

def crear_grito(nombre, base, pico, dur):
    m = []
    fase = 0.0
    for i in range(int(SR * dur)):
        t = i / SR
        f = base + (pico - base) * min(t / 0.25, 1) + 60 * math.sin(2 * math.pi * 9 * t)
        f -= 300 * max(0, t - 0.5)
        fase += 2 * math.pi * f / SR
        env = min(t / 0.03, 1) * math.exp(-1.8 * max(0, t - 0.3))
        env *= min(1, (dur - t) / 0.3)
        v = 0.6 * math.sin(fase) + 0.3 * math.sin(2 * fase) + 0.25 * (random.random() * 2 - 1)
        m.append(v * env * 0.8)
    guardar(nombre, m)

def crear_sonidos():
    p = lambda n: os.path.exists(os.path.join(CARPETA, n))
    if not p('snd_ambiente.wav'):
        m = []
        for i in range(SR * 8):
            t = i / SR
            v = 0.35 * math.sin(2 * math.pi * 55 * t) + 0.25 * math.sin(2 * math.pi * 58 * t)
            v *= 0.6 + 0.4 * math.sin(2 * math.pi * 0.25 * t)
            v += 0.03 * (random.random() * 2 - 1)
            m.append(v * 0.8)
        guardar('snd_ambiente.wav', m)
    if not p('snd_musica.wav'):
        notas = [440, 523.25, 659.25, 523.25, 440, 415.3, 493.88, 659.25,
                 440, 523.25, 622.25, 523.25, 440, 392, 415.3, 329.63]
        m = []
        for f in notas:
            for i in range(SR // 2):
                t = i / SR
                env = math.exp(-4 * t)
                m.append(0.4 * env * (math.sin(2 * math.pi * f * t) +
                                      0.3 * math.sin(2 * math.pi * 2 * f * t)))
        guardar('snd_musica.wav', m)
    if not p('snd_grito.wav'):
        crear_grito('snd_grito.wav', 600, 1800, 1.1)
    if not p('snd_grito2.wav'):
        crear_grito('snd_grito2.wav', 450, 1400, 1.3)
    if not p('snd_golpe.wav'):
        m = []
        for i in range(int(SR * 0.25)):
            t = i / SR
            v = (random.random() * 2 - 1) * math.exp(-20 * t) + 0.7 * math.sin(2 * math.pi * 90 * t) * math.exp(-15 * t)
            m.append(v * 0.8)
        guardar('snd_golpe.wav', m)
    if not p('snd_espada.wav'):
        m = []
        for i in range(int(SR * 0.3)):
            t = i / SR
            env = math.sin(math.pi * t / 0.3) ** 2
            m.append((random.random() * 2 - 1) * env * 0.35 * (1 + math.sin(2 * math.pi * 900 * t * (1 + t))) / 2)
        guardar('snd_espada.wav', m)
    if not p('snd_disparo.wav'):
        m = []
        for i in range(int(SR * 0.35)):
            t = i / SR
            v = (random.random() * 2 - 1) * math.exp(-28 * t) * .9
            v += .8 * math.sin(2 * math.pi * (140 - 100 * t) * t) * math.exp(-16 * t)
            m.append(v)
        guardar('snd_disparo.wav', m)
    if not p('snd_recarga.wav'):
        m = []
        for i in range(int(SR * 0.9)):
            t = i / SR
            v = 0
            for t0 in (0.05, 0.55):
                if t >= t0:
                    v += (random.random() * 2 - 1) * math.exp(-80 * (t - t0)) * .6
            m.append(v)
        guardar('snd_recarga.wav', m)

crear_sonidos()

# ------------------------------------------------------------
#  MOTOR
# ------------------------------------------------------------
app = Ursina(title='MUJERES ASESINAS 3D', borderless=False, fullscreen=FULLSCREEN, size=(ANCHO, ALTO))
window.exit_button.visible = False
camera.fov = 72
try:
    scene.setAntialias(AntialiasAttrib.MAuto)
except Exception:
    pass

SH = lit_with_shadows_shader if (LUCES_3D and lit_with_shadows_shader) else None

def E(**k):
    if SH and 'shader' not in k:
        k['shader'] = SH
    return Entity(**k)

def G(**k):
    if unlit_shader:
        k['shader'] = unlit_shader
    return Entity(**k)

AMBIENTES = [220, 0, 130, 280]
LIM = 43.5
obstaculos = []

if SH:
    sol = DirectionalLight(shadows=True, shadow_map_resolution=Vec2(2048, 2048))
    sol.rotation = (55, -35, 0)
    luz_amb = AmbientLight()

def aplicar_ambiente(nivel):
    h = AMBIENTES[(nivel - 1) % len(AMBIENTES)]
    niebla = hsv(h, .6, .07)
    window.color = niebla
    scene.fog_color = niebla
    scene.fog_density = (10, 65)
    if SH:
        sol.color = hsv(h, .35, .75)
        luz_amb.color = hsv(h, .45, .42)

estado = {'modo': 'menu', 'vida': 100, 'nivel': 1, 'derrotadas': 0, 'ataque': 0,
          'cambiando': False, 'partida': 0, 'vel': Vec3(0, 0, 0), 'prev': Vec3(0, 0, 0),
          'orbita': 0, 'arma': 'principal', 'mun': 12, 'recarga': 0, 'alt': 0, 'recuo': 0}
enemigas = []

Audio('snd_ambiente.wav', loop=True, autoplay=True, volume=0.7)
Audio('snd_musica.wav', loop=True, autoplay=True, volume=0.35)

def angulo_suave(a, b, t):
    d = (b - a + 180) % 360 - 180
    return a + d * min(1, t)

def resolver(x, z, r):
    for ox, oz, hx, hz in obstaculos:
        cx = max(ox - hx, min(x, ox + hx))
        cz = max(oz - hz, min(z, oz + hz))
        dx, dz = x - cx, z - cz
        d2 = dx * dx + dz * dz
        if d2 < r * r:
            if d2 > 1e-8:
                d = math.sqrt(d2)
                x, z = cx + dx / d * r, cz + dz / d * r
            else:
                x = ox + (hx + r) * (1 if x >= ox else -1)
    return clamp(x, -LIM, LIM), clamp(z, -LIM, LIM)

# ------------------------------------------------------------
#  ESCENARIO: CIUDAD REALISTA
# ------------------------------------------------------------
NEGRO_C = hsv(0, 0, .05)

def palmera(x, z):
    for i in range(6):
        E(model='cube', position=(x + i * .08, .5 + i * 1.0, z), scale=(.32 - i * .02, 1.05, .32 - i * .02),
          color=hsv(30, .5, .30))
    copa = Entity(position=(x + .5, 6.6, z))
    E(parent=copa, model='sphere', y=-.2, scale=.5, color=hsv(25, .6, .25))
    for i in range(8):
        piv = Entity(parent=copa, rotation=(28, i * 45, 0))
        E(parent=piv, model='cube', z=1.2, scale=(.55, .06, 2.4), color=hsv(120, .7, random.uniform(.25, .4)))
    obstaculos.append((x + .2, z, .4, .4))

def auto_clasico(x, z, giro, col):
    a = Entity(position=(x, 0, z), rotation_y=giro)
    E(parent=a, model='cube', y=.55, scale=(2, .6, 4.4), color=col)
    E(parent=a, model='cube', y=1.05, z=-.2, scale=(1.74, .42, 2.02), color=hsv(205, .5, .22))
    E(parent=a, model='cube', y=1.28, z=-.2, scale=(1.76, .08, 2.05), color=col)
    for sx in (-1, 1):
        for sz in (-1.4, 1.4):
            E(parent=a, model='sphere', position=(sx * 1.0, .4, sz), scale=(.3, .8, .8), color=NEGRO_C)
    for sz in (-1, 1):
        E(parent=a, model='cube', y=.45, z=sz * 2.25, scale=(2.05, .15, .12), color=hsv(205, .05, .8))
    for sx in (-.7, .7):
        G(parent=a, model='sphere', position=(sx, .65, 2.22), scale=.24, color=hsv(50, .4, 1))
        G(parent=a, model='cube', position=(sx, .65, -2.22), scale=(.25, .12, .05), color=hsv(0, 1, .9))
    if giro % 180 == 0:
        obstaculos.append((x, z, 1.05, 2.25))
    else:
        obstaculos.append((x, z, 2.25, 1.05))

def farola(x, z, giro=0):
    p = Entity(position=(x, 0, z), rotation_y=giro)
    E(parent=p, model='cube', y=2.7, scale=(.13, 5.4, .13), color=hsv(220, .1, .16))
    E(parent=p, model='cube', y=5.3, z=.8, scale=(.11, .11, 1.8), color=hsv(220, .1, .16))
    G(parent=p, model='cube', y=5.22, z=1.6, scale=(.55, .13, .28), color=hsv(48, .45, 1))
    G(parent=p, model='circle', rotation_x=90, position=(0, .06, 1.6), scale=6.5,
      color=hsv(48, 1, 1, .10), double_sided=True)
    obstaculos.append((x, z, .25, .25))

def semaforo(x, z, giro=0):
    p = Entity(position=(x, 0, z), rotation_y=giro)
    E(parent=p, model='cube', y=1.9, scale=(.12, 3.8, .12), color=hsv(220, .1, .15))
    E(parent=p, model='cube', y=3.9, scale=(.22, .65, .22), color=NEGRO_C)
    G(parent=p, model='sphere', y=4.1, z=.12, scale=.07, color=hsv(0, 1, .55))
    G(parent=p, model='sphere', y=3.9, z=.12, scale=.07, color=hsv(45, 1, .55))
    G(parent=p, model='sphere', y=3.7, z=.12, scale=.07, color=hsv(120, 1, .55))
    obstaculos.append((x, z, .25, .25))

def edificio(x, z, w, d, h, col, con_ventanas=True):
    E(model='cube', position=(x, h / 2, z), scale=(w, h, d), color=col)
    for sx in (-1, 1):
        E(model='cube', position=(x + sx * w / 2, h + .15, z), scale=(.3, .3, d + .3), color=col * .8)
        E(model='cube', position=(x, h + .15, z + sx * d / 2), scale=(w + .3, .3, .3), color=col * .8)
    if con_ventanas:
        calidas = [hsv(45, .55, 1), hsv(38, .4, .95), hsv(200, .25, .9), hsv(0, 0, .9)]
        apag = hsv(220, .35, .07)
        def cara(fx, fz, rx, n):
            pisos = int((h - 2.5) // 2.4)
            for i in range(1, pisos + 1):
                for j in range(n):
                    off = (j - (n - 1) / 2) * 2.1
                    if rx:
                        pos = (x + off, i * 2.4 + .9, z + fz)
                        sc = (1.15, 1.5, .06)
                    else:
                        pos = (x + fx, i * 2.4 + .9, z + off)
                        sc = (.06, 1.5, 1.15)
                    if random.random() < .55:
                        G(model='cube', position=pos, scale=sc, color=random.choice(calidas))
                    else:
                        E(model='cube', position=pos, scale=sc, color=apag)
        cara(0, d / 2 + .04, 1, max(1, int(w // 2.4)))
        cara(0, -d / 2 - .04, 1, max(1, int(d // 2.4)))
        cara(w / 2 + .04, 0, 0, max(1, int(d // 2.4)))
        cara(-w / 2 - .04, 0, 0, max(1, int(d // 2.4)))
    else:
        for i in range(int(h // 4)):
            G(model='cube', position=(x + random.uniform(-w / 3, w / 3), 2 + i * 4, z + d / 2 + .05),
              scale=(1.3, .9, .06), color=random.choice([hsv(45, .5, 1), hsv(200, .3, .9), hsv(220, .3, .08)]))
    if random.random() < .75:
        E(model='cube', position=(x + random.uniform(-w / 4, w / 4), h + .7, z + random.uniform(-d / 4, d / 4)),
          scale=(1.3, 1.3, 1.3), color=hsv(220, .1, .25))
    E(model='cube', position=(x, h + .7, z), scale=(.07, 1.4, .07), color=NEGRO_C)
    G(model='sphere', position=(x, h + 1.45, z), scale=.12, color=hsv(0, 1, .6))
    obstaculos.append((x, z, w / 2 + .2, d / 2 + .2))

def construir_mundo():
    random.seed(11)
    E(model='plane', scale=(100, 1, 100), color=hsv(220, .08, .13))
    for v in (-30, -15, 0, 15, 30):
        E(model='cube', position=(0, .012, v), scale=(96, .02, 7.6), color=hsv(220, .12, .085))
        E(model='cube', position=(v, .012, 0), scale=(7.6, .02, 96), color=hsv(220, .12, .085))
        for i in range(-44, 45, 6):
            E(model='cube', position=(i, .025, v), scale=(2.2, .015, .16), color=hsv(45, .7, .85))
            E(model='cube', position=(v, .025, i), scale=(.16, .015, 2.2), color=hsv(45, .7, .85))
    for i in range(6):
        E(model='cube', position=(-2.5 + i * 1.0, .03, 4.2), scale=(.55, .015, 2.4), color=hsv(0, 0, .85, .9))
        E(model='cube', position=(4.2, .03, -2.5 + i * 1.0), scale=(2.4, .015, .55), color=hsv(0, 0, .85, .9))
    lotes = []
    for gx in (-37, -22.5, -7.5, 7.5, 22.5, 37):
        for gz in (-37, -22.5, -7.5, 7.5, 22.5, 37):
            if abs(gx) < 13 and abs(gz) < 13:
                continue
            lotes.append((gx, gz))
    random.shuffle(lotes)
    for gx, gz in lotes:
        if random.random() < .18:
            continue
        edificio(gx + random.uniform(-1, 1), gz + random.uniform(-1, 1),
                 random.uniform(7, 11), random.uniform(7, 11), random.uniform(10, 26),
                 hsv(random.uniform(205, 230), random.uniform(.05, .18), random.uniform(.13, .22)))
    for gx in range(-40, 41, 13):
        edificio(gx, 45.5, random.uniform(9, 12), 6, random.uniform(24, 34),
                 hsv(random.uniform(210, 230), .12, random.uniform(.10, .16)), con_ventanas=False)
        edificio(gx, -45.5, random.uniform(9, 12), 6, random.uniform(24, 34),
                 hsv(random.uniform(210, 230), .12, random.uniform(.10, .16)), con_ventanas=False)
        edificio(45.5, gx, 6, random.uniform(9, 12), random.uniform(24, 34),
                 hsv(random.uniform(210, 230), .12, random.uniform(.10, .16)), con_ventanas=False)
        edificio(-45.5, gx, 6, random.uniform(9, 12), random.uniform(24, 34),
                 hsv(random.uniform(210, 230), .12, random.uniform(.10, .16)), con_ventanas=False)
    pilares = []
    for px in (-30, -15, 0, 15, 30):
        for pz in (-30, -15, 0, 15, 30):
            if abs(px) < 10 and abs(pz) < 10:
                continue
            pilares.append((px, pz))
            E(model='cube', position=(px, 9, pz), scale=(2.6, 18, 2.6), color=hsv(210, .12, .28))
            E(model='cube', position=(px, .4, pz), scale=(3.4, .8, 3.4), color=hsv(210, .10, .20))
            E(model='cube', position=(px, 3, pz), scale=(2.7, .5, 2.7), color=hsv(15, .6, .22))
            obstaculos.append((px, pz, 1.4, 1.4))
    for v in (-30, -15, 0, 15, 30):
        E(model='cube', position=(0, 14, v), scale=(96, .8, .8), color=hsv(215, .15, .13))
        E(model='cube', position=(v, 14, 0), scale=(.8, .8, 96), color=hsv(215, .15, .13))
        E(model='cube', position=(0, 12.5, v + 1.3), scale=(96, .6, .6), color=hsv(8, .75, .28))
    for _ in range(60):
        x = random.uniform(-44, 44)
        z = random.choice([-30, -15, 0, 15, 30]) + random.uniform(-.5, .5)
        largo = random.uniform(2, 6)
        verde = hsv(random.uniform(90, 130), .6, random.uniform(.16, .28))
        E(model='cube', position=(x, 13.4 - largo / 2, z), scale=(.06, largo, .06), color=verde)
        E(model='sphere', position=(x, 13.4 - largo, z), scale=(.4, .28, .4), color=verde)
    for _ in range(16):
        x, z = random.uniform(-40, 40), random.uniform(-40, 40)
        if abs(x) < 13 and abs(z) < 13:
            continue
        s = random.uniform(1.2, 2.2)
        E(model='cube', position=(x, s / 2, z), scale=(s, s, s), color=hsv(30, .32, .18))
        E(model='cube', position=(x, s + .03, z), scale=(s * 1.02, .06, s * 1.02), color=hsv(30, .5, .10))
        obstaculos.append((x, z, s / 2 + .05, s / 2 + .05))
    for _ in range(10):
        x, z = random.uniform(-40, 40), random.uniform(-40, 40)
        if abs(x) < 13 and abs(z) < 13:
            continue
        E(model='sphere', position=(x, .7, z), scale=(1.1, 1.4, 1.1), color=hsv(5, .6, .22))
        G(model='cube', position=(x, 1.35, z), scale=(.6, .04, .6), color=hsv(5, 1, .5))
        obstaculos.append((x, z, .6, .6))
    for _ in range(50):
        E(model='cube', position=(random.uniform(-42, 42), .1, random.uniform(-42, 42)),
          scale=(random.uniform(.2, .6), random.uniform(.1, .3), random.uniform(.2, .6)),
          rotation_y=random.uniform(0, 180), color=hsv(220, .1, .11))
    random.shuffle(pilares)
    for i, (px, pz) in enumerate(pilares[:10]):
        h = 0 if i % 2 == 0 else 200
        G(model='cube', position=(px + 1.5, 4.5, pz), scale=(.3, .3, .3), color=hsv(h, 1, 1))
        G(model='circle', rotation_x=90, position=(px, .06, pz), scale=8,
          color=hsv(h, 1, 1, .13), double_sided=True)
    for z in (-30, -15, 0, 15, 30):
        farola(6.4, z, 0)
        farola(-6.4, z, 180)
    semaforo(6.4, 8, 180)
    semaforo(-6.4, -8, 0)
    semaforo(8, -6.4, 90)
    semaforo(-8, 6.4, -90)
    for px, pz in [(8, 8), (-8, 8), (8, -8), (-8, -8)]:
        palmera(px, pz)
    auto_clasico(11, 3, 0, hsv(175, .8, .75))
    auto_clasico(-11, -3, 0, hsv(0, .85, .70))
    auto_clasico(4, -11, 90, hsv(50, .9, .85))
    auto_clasico(-4, 13, 90, hsv(220, .5, .45))
    random.seed()

construir_mundo()
aplicar_ambiente(1)
if SH:
    try:
        sol.update_bounds(scene)
    except Exception:
        pass

# ------------------------------------------------------------
#  ARMAS
# ------------------------------------------------------------
ORO = hsv(45, .65, .75)
ACERO = hsv(205, .08, .82)
NEGRO = hsv(0, 0, .06)
GRIS = hsv(220, .12, .16)

ARMAS_STATS = {
    'dobles': {'nombre': 'DOS PISTOLAS', 'mun': 24, 'cd': .13, 'dano': 1, 'auto': False, 'pitch': 1.0, 'recuo': 2.2},
    'rifle':  {'nombre': 'RIFLE DE ASALTO', 'mun': 30, 'cd': .11, 'dano': 2, 'auto': True, 'pitch': .85, 'recuo': 3.0},
    'smg':    {'nombre': 'SUBAMETRALLADORA', 'mun': 35, 'cd': .07, 'dano': 1, 'auto': True, 'pitch': 1.25, 'recuo': 1.8},
}

def arma_melee(mano, tipo, acento, hoja_col=None):
    h = Entity(parent=mano, rotation_x=-70)
    if tipo == 'katana':
        E(parent=h, model='cube', y=-.03, scale=(.034, .30, .034), color=NEGRO)
        for i in range(6):
            E(parent=h, model='cube', y=.08 - i * .05, scale=(.040, .022, .040),
              color=acento if i % 2 == 0 else NEGRO, rotation_y=45)
        E(parent=h, model='sphere', y=.125, scale=(.045, .03, .045), color=ORO)
        E(parent=h, model='sphere', y=-.19, scale=(.13, .014, .10), color=ORO)
        E(parent=h, model='cube', y=-.21, scale=(.04, .03, .03), color=ORO)
        if hoja_col is None:
            E(parent=h, model='cube', y=-.45, scale=(.026, .50, .009), color=ACERO)
            E(parent=h, model='cube', y=-.84, z=-.012, scale=(.026, .30, .009), color=ACERO, rotation_x=-4)
            G(parent=h, model='cube', y=-.45, x=.011, scale=(.004, .50, .011), color=hsv(190, .15, 1))
            G(parent=h, model='cube', y=-.84, x=.011, z=-.012, scale=(.004, .30, .011), color=hsv(190, .15, 1))
        else:
            G(parent=h, model='cube', y=-.45, scale=(.028, .50, .010), color=hoja_col)
            G(parent=h, model='cube', y=-.84, z=-.012, scale=(.028, .30, .010), color=hoja_col, rotation_x=-4)
    elif tipo == 'machete':
        E(parent=h, model='cube', y=-.02, scale=(.04, .22, .04), color=NEGRO)
        E(parent=h, model='cube', y=-.35, scale=(.075, .50, .01), color=hsv(30, .2, .45))
        G(parent=h, model='cube', y=-.35, x=-.036, scale=(.006, .50, .012), color=hsv(0, .8, .6))
    else:
        E(parent=h, model='cube', y=-.02, scale=(.035, .18, .035), color=NEGRO)
        E(parent=h, model='cube', y=-.25, scale=(.05, .28, .008), color=ACERO)
        G(parent=h, model='cube', y=-.30, x=.02, scale=(.012, .12, .010), color=hsv(0, 1, .5))
    return h

def arma_pistola(mano, acento):
    g = Entity(parent=mano)
    E(parent=g, model='cube', y=-.14, scale=(.036, .27, .042), color=GRIS)
    E(parent=g, model='cube', y=-.12, z=-.03, scale=(.034, .23, .030), color=NEGRO)
    E(parent=g, model='cube', y=-.295, z=.002, scale=(.016, .04, .016), color=NEGRO)
    E(parent=g, model='cube', y=-.04, z=-.075, scale=(.034, .075, .05), color=hsv(25, .4, .13), rotation_x=-12)
    E(parent=g, model='cube', y=-.09, z=-.055, scale=(.012, .06, .010), color=NEGRO)
    E(parent=g, model='cube', y=-.01, z=.025, scale=(.010, .02, .014), color=NEGRO)
    E(parent=g, model='cube', y=-.27, z=.025, scale=(.008, .02, .014), color=NEGRO)
    E(parent=g, model='cube', y=-.22, z=-.045, scale=(.028, .08, .03), color=NEGRO)
    G(parent=g, model='cube', y=-.14, x=.019, scale=(.004, .20, .007), color=acento)
    G(parent=g, model='sphere', y=-.30, z=-.04, scale=.012, color=color.red)
    flash = G(parent=g, model='sphere', y=-.36, scale=.13, color=hsv(48, .7, 1))
    flash.enabled = False
    return g, flash

def arma_rifle(mano, acento):
    g = Entity(parent=mano, scale=.8)
    E(parent=g, model='cube', y=-.20, scale=(.05, .40, .07), color=GRIS)
    E(parent=g, model='cube', y=.17, scale=(.045, .28, .07), color=NEGRO)
    E(parent=g, model='cube', y=.32, scale=(.05, .04, .09), color=hsv(0, 0, .1))
    E(parent=g, model='cube', y=-.55, scale=(.058, .30, .062), color=GRIS)
    G(parent=g, model='cube', y=-.55, x=.030, scale=(.004, .26, .008), color=acento)
    E(parent=g, model='cube', y=-.85, scale=(.018, .40, .018), color=NEGRO)
    E(parent=g, model='cube', y=-1.06, scale=(.032, .07, .032), color=NEGRO)
    E(parent=g, model='cube', y=-.31, z=-.12, scale=(.042, .12, .15), color=NEGRO, rotation_x=-10)
    E(parent=g, model='cube', y=-.02, z=-.08, scale=(.04, .08, .05), color=NEGRO, rotation_x=-12)
    E(parent=g, model='cube', y=-.25, z=.052, scale=(.03, .32, .02), color=NEGRO)
    E(parent=g, model='cube', y=-.25, z=.09, scale=(.04, .12, .04), color=NEGRO)
    G(parent=g, model='sphere', y=-.315, z=.09, scale=.022, color=hsv(185, .9, 1))
    E(parent=g, model='cube', y=-.72, z=.04, scale=(.01, .02, .03), color=NEGRO)
    flash = G(parent=g, model='sphere', y=-1.14, scale=.18, color=hsv(48, .7, 1))
    flash.enabled = False
    return g, flash

def arma_smg(mano, acento):
    g = Entity(parent=mano)
    E(parent=g, model='cube', y=-.16, scale=(.05, .30, .06), color=GRIS)
    E(parent=g, model='cube', y=-.38, scale=(.04, .18, .04), color=NEGRO)
    E(parent=g, model='cube', y=-.50, scale=(.028, .07, .028), color=NEGRO)
    E(parent=g, model='cube', y=-.14, z=-.15, scale=(.03, .05, .22), color=NEGRO)
    E(parent=g, model='cube', y=-.01, z=-.07, scale=(.036, .07, .05), color=NEGRO, rotation_x=-10)
    E(parent=g, model='cube', y=.13, scale=(.02, .22, .02), color=NEGRO)
    E(parent=g, model='cube', y=.24, scale=(.04, .02, .05), color=NEGRO)
    E(parent=g, model='cube', y=-.12, z=.04, scale=(.012, .03, .02), color=NEGRO)
    E(parent=g, model='cube', y=-.30, z=.035, scale=(.01, .02, .02), color=NEGRO)
    G(parent=g, model='cube', y=-.16, x=.026, scale=(.004, .22, .008), color=acento)
    flash = G(parent=g, model='sphere', y=-.58, scale=.14, color=hsv(48, .7, 1))
    flash.enabled = False
    return g, flash

# ------------------------------------------------------------
#  PERSONAJE FEMENINO (estilo anime con proporciones humanas)
# ------------------------------------------------------------
def mujer(raiz, piel, top, pantalon, pelo, acento, iris, calzado=None, chaqueta=None, manga=None,
          guante=None, crop=False, falda=False, botas_altas=True, cargo=False, gafas=False,
          bandana=None, peinado='coletas', malvada=False, glb=None, melee='katana',
          hoja_col=None, principal=None, espalda=False):
    if glb and os.path.exists(os.path.join(CARPETA, glb)):
        E(parent=raiz, model=glb, scale=ESCALA_GLB)
        return {'piernas': [Entity(parent=raiz), Entity(parent=raiz)], 'shins': [],
                'brazo': Entity(parent=raiz), 'brazo_izq': Entity(parent=raiz),
                'cola': Entity(parent=raiz),
                'armas': {'katana': [Entity(parent=raiz)], 'principal': [Entity(parent=raiz)]},
                'flashes': [], 'izq_pose': None}
    c = Entity(parent=raiz)
    if calzado is None:
        calzado = hsv(0, 0, .07)
    piernas, shins = [], []
    for lado in (-1, 1):
        pv = Entity(parent=c, position=(lado * .095, .97, 0))
        E(parent=pv, model='sphere', y=-.21, scale=(.148, .38, .163), color=piel if falda else pantalon)
        if botas_altas:
            E(parent=pv, model='sphere', y=-.46, scale=(.135, .30, .15), color=calzado)
            E(parent=pv, model='sphere', y=-.33, scale=(.15, .11, .16), color=calzado)
            G(parent=pv, model='cube', y=-.285, scale=(.152, .014, .162), color=acento)
        rod = Entity(parent=pv, y=-.45)
        E(parent=rod, model='sphere', y=-.19, scale=(.115, .40, .125),
          color=calzado if botas_altas else pantalon)
        E(parent=rod, model='sphere', y=-.43, z=.05, scale=(.115, .10, .245), color=calzado)
        E(parent=rod, model='cube', y=-.475, z=-.04, scale=(.08, .05, .07), color=calzado)
        if cargo:
            E(parent=rod, model='cube', position=(lado * .075, -.16, 0), scale=(.035, .13, .12),
              color=pantalon * .8)
            E(parent=rod, model='cube', position=(lado * .095, -.16, 0), scale=(.010, .018, .11), color=NEGRO)
        piernas.append(pv)
        shins.append(rod)
    E(parent=c, model='sphere', y=1.00, scale=(.34, .22, .24), color=pantalon)
    E(parent=c, model='sphere', y=1.10, scale=(.245, .15, .185), color=piel if crop else top)
    if crop:
        E(parent=c, model='sphere', y=1.29, scale=(.265, .21, .185), color=piel)
        E(parent=c, model='sphere', y=1.44, scale=(.30, .19, .205), color=top)
    else:
        E(parent=c, model='sphere', y=1.29, scale=(.265, .25, .185), color=top)
        E(parent=c, model='sphere', y=1.45, scale=(.30, .16, .205), color=top)
    if falda:
        E(parent=c, model='sphere', y=.94, scale=(.40, .12, .30), color=chaqueta or top)
        G(parent=c, model='cube', y=.87, scale=(.37, .010, .28), color=acento)
    E(parent=c, model='cube', y=1.15, scale=(.24, .04, .17), color=calzado)
    G(parent=c, model='cube', y=1.15, z=.088, scale=(.045, .035, .012), color=ORO)
    for lado in (-1, 1):
        if chaqueta:
            E(parent=c, model='sphere', position=(lado * .15, 1.40, -.01), scale=(.09, .24, .18), color=chaqueta)
            G(parent=c, model='cube', position=(lado * .055, 1.44, .095), scale=(.010, .24, .012), color=acento)
        E(parent=c, model='sphere', position=(lado * .185, 1.52, 0), scale=(.10, .13, .13),
          color=manga or chaqueta or piel)
    E(parent=c, model='sphere', y=1.595, scale=(.055, .09, .055), color=piel)
    if chaqueta:
        E(parent=c, model='sphere', y=1.545, scale=(.135, .05, .12), color=chaqueta)
    E(parent=c, model='sphere', y=1.79, scale=(.235, .245, .225), color=piel)
    E(parent=c, model='sphere', y=1.72, z=.055, scale=(.185, .095, .165), color=piel)
    E(parent=c, model='sphere', position=(0, 1.795, .118), scale=(.018, .030, .022), color=piel * .88)
    for lado in (-1, 1):
        E(parent=c, model='sphere', position=(lado * .115, 1.765, .075), scale=(.055, .07, .05), color=piel * .96)
        x = lado * .062
        G(parent=c, model='sphere', position=(x, 1.80, .101), scale=(.072, .088, .028), color=color.white)
        G(parent=c, model='sphere', position=(x, 1.795, .111), scale=(.052, .078, .028), color=iris)
        G(parent=c, model='sphere', position=(x, 1.795, .118), scale=(.022, .046, .020), color=NEGRO)
        G(parent=c, model='sphere', position=(x - .011, 1.82, .123), scale=.016, color=color.white)
        G(parent=c, model='cube', position=(x, 1.845, .106), scale=(.088, .012, .020), color=NEGRO,
          rotation_z=lado * -10)
        G(parent=c, model='cube', position=(x, 1.878, .100), scale=(.075, .010, .020),
          color=pelo, rotation_z=lado * (12 if malvada else -6))
        G(parent=c, model='sphere', position=(lado * .088, 1.755, .10), scale=(.038, .018, .012),
          color=hsv(0, .4, .95, .5))
    G(parent=c, model='cube', y=1.725, z=.108, scale=(.034 if not malvada else .058, .008, .010),
      color=hsv(350, .7, .55))
    if malvada:
        G(parent=c, model='cube', position=(.082, 1.73, .102), scale=(.011, .055, .010), color=hsv(0, 1, .5))
        G(parent=c, model='cube', position=(-.048, 1.858, .102), scale=(.009, .045, .010), color=hsv(0, 1, .5))
    if gafas:
        for lado in (-1, 1):
            G(parent=c, model='cube', position=(lado * .062, 1.80, .126), scale=(.095, .072, .014),
              color=hsv(220, .3, .06))
            G(parent=c, model='cube', position=(lado * .08, 1.82, .134), scale=(.028, .011, .006),
              color=hsv(200, .2, .9))
            G(parent=c, model='cube', position=(lado * .118, 1.80, .055), scale=(.010, .014, .13), color=NEGRO)
        G(parent=c, model='cube', position=(0, 1.807, .126), scale=(.028, .011, .012), color=ORO)
    E(parent=c, model='sphere', y=1.845, z=-.03, scale=(.265, .29, .265), color=pelo)
    E(parent=c, model='sphere', y=1.93, z=.005, scale=(.255, .12, .245), color=pelo)
    for bx in (-.10, -.05, 0, .05, .10):
        E(parent=c, model='sphere', position=(bx, 1.905 - abs(bx) * .22, .10), scale=(.07, .13, .05),
          color=pelo, rotation_z=bx * -160)
    for lado in (-1, 1):
        E(parent=c, model='sphere', position=(lado * .135, 1.76, .03), scale=(.045, .20, .06), color=pelo)
    if bandana is not None:
        E(parent=c, model='sphere', y=1.915, z=-.01, scale=(.275, .07, .27), color=bandana)
        E(parent=c, model='sphere', position=(0, 1.91, -.155), scale=.065, color=bandana)
        for lado in (-1, 1):
            E(parent=c, model='cube', position=(lado * .04, 1.845, -.18), scale=(.04, .15, .015),
              color=bandana, rotation_z=lado * 14)
        for bx in (-.09, -.025, .045, .10):
            G(parent=c, model='sphere', position=(bx, 1.92, .108), scale=.011, color=color.white)
    elif not gafas:
        G(parent=c, model='sphere', position=(.115, 1.935, .015), scale=(.04, .04, .028), color=acento)
    cola = Entity(parent=c, position=(0, 1.90, -.05))
    if peinado == 'coletas':
        for lado in (-1, 1):
            E(parent=cola, model='sphere', position=(lado * .155, -.11, -.02), scale=(.08, .28, .08), color=pelo)
            E(parent=cola, model='sphere', position=(lado * .175, -.37, -.03), scale=(.07, .32, .07), color=pelo)
            E(parent=cola, model='sphere', position=(lado * .185, -.61, -.04), scale=(.045, .26, .045), color=pelo)
    elif peinado == 'cola':
        E(parent=cola, model='sphere', position=(0, -.07, -.13), scale=.095, color=pelo)
        E(parent=cola, model='sphere', position=(0, -.31, -.15), scale=(.09, .40, .09), color=pelo)
        E(parent=cola, model='sphere', position=(0, -.60, -.16), scale=(.065, .32, .065), color=pelo)
    else:
        E(parent=cola, model='sphere', position=(0, -.22, -.11), scale=(.28, .52, .095), color=pelo)
        E(parent=cola, model='sphere', position=(0, -.57, -.12), scale=(.24, .47, .085), color=pelo)
        E(parent=cola, model='sphere', position=(0, -.83, -.12), scale=(.18, .28, .075), color=pelo)
    brazos = []
    for lado in (-1, 1):
        br = Entity(parent=c, position=(lado * .205, 1.50, 0), rotation_x=-15)
        E(parent=br, model='sphere', y=-.13, scale=(.068, .28, .073), color=manga or piel)
        cod = Entity(parent=br, y=-.28)
        E(parent=cod, model='sphere', y=-.11, scale=(.058, .23, .062), color=manga or guante or piel)
        if not manga and not guante:
            G(parent=cod, model='cube', y=-.02, scale=(.065, .012, .070), color=acento)
        else:
            G(parent=cod, model='cube', y=-.045, scale=(.065, .012, .070), color=acento)
        E(parent=cod, model='sphere', y=-.26, scale=(.058, .09, .040), color=guante or piel)
        E(parent=cod, model='sphere', position=(lado * .045, -.295, .012), scale=(.02, .05, .025),
          color=guante or piel)
        brazos.append((br, cod))
    manoD = Entity(parent=brazos[1][1], y=-.285)
    manoI = Entity(parent=brazos[0][1], y=-.285)
    armas = {'katana': [arma_melee(manoD, melee, acento, hoja_col)], 'principal': []}
    flashes = []
    if principal == 'dobles':
        g1, f1 = arma_pistola(manoD, acento)
        g2, f2 = arma_pistola(manoI, acento)
        armas['principal'] = [g1, g2]
        flashes = [f1, f2]
    elif principal in ('rifle', 'smg'):
        g, f = (arma_rifle if principal == 'rifle' else arma_smg)(manoD, acento)
        armas['principal'] = [g]
        flashes = [f]
    for g in armas['principal']:
        g.enabled = False
    if espalda:
        sb = Entity(parent=c, position=(0, 1.22, -.16), rotation_z=42)
        E(parent=sb, model='cube', y=0, scale=(.045, .95, .05), color=NEGRO)
        G(parent=sb, model='cube', y=-.2, z=.026, scale=(.01, .48, .006), color=acento)
        E(parent=sb, model='sphere', y=.48, scale=(.055, .035, .055), color=ORO)
        E(parent=sb, model='cube', y=.63, scale=(.034, .28, .038), color=NEGRO)
        for i in range(5):
            E(parent=sb, model='cube', y=.73 - i * .05, scale=(.04, .018, .042),
              color=acento if i % 2 == 0 else NEGRO)
        E(parent=sb, model='sphere', y=.56, scale=(.095, .013, .075), color=ORO)
    return {'piernas': piernas, 'shins': shins, 'brazo': brazos[1][0], 'brazo_izq': brazos[0][0],
            'cola': cola, 'armas': armas, 'flashes': flashes, 'izq_pose': None}

# ------------------------------------------------------------
#  LOS 3 PERSONAJES JUGABLES
# ------------------------------------------------------------
PERSONAJES = [
    dict(nombre='CALLE', desc='Top corto, cargo y gafas. Dos pistolas.',
         piel=hsv(25, .28, .88), top=hsv(50, .95, .95), pantalon=hsv(85, .40, .30),
         pelo=hsv(20, .65, .24), acento=hsv(50, 1, 1), iris=hsv(25, .7, .4),
         calzado=hsv(30, .4, .16), crop=True, cargo=True, gafas=True, botas_altas=False,
         peinado='cola', principal='dobles'),
    dict(nombre='TACTICA', desc='Chaqueta de cuero y botas altas. Rifle de asalto.',
         piel=hsv(20, .20, .92), top=hsv(0, 0, .14), pantalon=hsv(0, 0, .08),
         pelo=hsv(35, .55, .26), acento=hsv(190, .9, 1), iris=hsv(190, .9, 1),
         calzado=hsv(0, 0, .06), chaqueta=hsv(15, .35, .16), manga=hsv(15, .35, .16),
         guante=hsv(0, 0, .06), botas_altas=True, peinado='cola', principal='rifle'),
    dict(nombre='PANDILLERA', desc='Camiseta sin mangas, jeans y panuelo. Submetralladora.',
         piel=hsv(22, .42, .78), top=hsv(0, 0, .95), pantalon=hsv(215, .65, .45),
         pelo=hsv(0, 0, .04), acento=hsv(0, 1, 1), iris=hsv(20, .8, .25),
         calzado=hsv(0, 0, .88), bandana=hsv(0, .9, .70), botas_altas=False,
         peinado='suelto', principal='smg'),
]

jugadora = Entity(position=(0, 0, 0))
jugadora.modelo = None
jugadora.p = {}
jugadora.tipo = 'dobles'
jugadora.indice = 0
jugadora.yaw = 0
jugadora.pitch = 18
jugadora.t = 0

def construir_jugadora(i):
    if jugadora.modelo is not None:
        destroy(jugadora.modelo)
    d = PERSONAJES[i]
    datos = {k: v for k, v in d.items() if k not in ('nombre', 'desc')}
    jugadora.modelo = Entity(parent=jugadora)
    jugadora.p = mujer(jugadora.modelo, glb=MODELO_JUGADORA, melee='katana', espalda=True, **datos)
    jugadora.tipo = d['principal']
    jugadora.indice = i

def cargador():
    return ARMAS_STATS[jugadora.tipo]['mun']

def equipar(nombre):
    estado['arma'] = nombre
    for k, lst in jugadora.p['armas'].items():
        for a in lst:
            a.enabled = (k == nombre)
    if nombre == 'katana':
        jugadora.p['brazo'].rotation_x = -15
        jugadora.p['izq_pose'] = None
        jugadora.p['brazo_izq'].rotation_y = 0
    else:
        jugadora.p['brazo'].rotation_x = -88
        if jugadora.tipo == 'dobles':
            jugadora.p['izq_pose'] = -88
            jugadora.p['brazo_izq'].rotation_y = 0
        else:
            jugadora.p['izq_pose'] = -80
            jugadora.p['brazo_izq'].rotation_y = 22
    mira.enabled = (nombre != 'katana')

def animar_caminar(p, t, mover):
    sn = math.sin(t)
    if mover:
        p['piernas'][0].rotation_x = sn * 46
        p['piernas'][1].rotation_x = -sn * 46
        for i, sh in enumerate(p.get('shins', [])):
            ph = sn if i == 0 else -sn
            sh.rotation_x = max(0, ph) * 38 - 5
    else:
        for pv in p['piernas']:
            pv.rotation_x = lerp(pv.rotation_x, 0, .2)
        for sh in p.get('shins', []):
            sh.rotation_x = lerp(sh.rotation_x, -4, .2)
    if p.get('izq_pose') is not None:
        p['brazo_izq'].rotation_x = p['izq_pose']
    elif mover:
        p['brazo_izq'].rotation_x = -15 - sn * 28
    else:
        p['brazo_izq'].rotation_x = lerp(p['brazo_izq'].rotation_x, -15, .2)
    p['cola'].rotation_x = 12 + (math.sin(t * .5) * 10 if mover else math.sin(time.time() * 1.5) * 2)

def mover_jugadora(dt):
    j = jugadora
    j.yaw += mouse.velocity[0] * 40
    j.pitch = clamp(j.pitch - mouse.velocity[1] * 40, -8, 40)
    fy = math.radians(j.yaw)
    fwd = Vec3(math.sin(fy), 0, math.cos(fy))
    der = Vec3(math.cos(fy), 0, -math.sin(fy))
    mx = held_keys['d'] - held_keys['a']
    mz = held_keys['w'] - held_keys['s']
    mov = fwd * mz + der * mx
    movil = mov.length() > 0
    if movil:
        mov = mov.normalized()
        v = 12.0 if held_keys['left shift'] else 7.0
        j.x, j.z = resolver(j.x + mov.x * v * dt, j.z + mov.z * v * dt, .5)
        j.t += dt * (17 if held_keys['left shift'] else 12)
    if estado['arma'] != 'katana':
        j.modelo.rotation_y = angulo_suave(j.modelo.rotation_y, j.yaw, 15 * dt)
    elif movil:
        j.modelo.rotation_y = angulo_suave(j.modelo.rotation_y, math.degrees(math.atan2(mov.x, mov.z)), 12 * dt)
    elif estado['ataque'] > 0:
        j.modelo.rotation_y = angulo_suave(j.modelo.rotation_y, j.yaw, 15 * dt)
    animar_caminar(j.p, j.t, movil)
    pr = math.radians(j.pitch + estado['recuo'])
    objetivo = j.position + Vec3(0, 1.6, 0) + der * .9
    pos = objetivo - fwd * (math.cos(pr) * 4.6) + Vec3(0, math.sin(pr) * 4.6, 0)
    camera.position = Vec3(clamp(pos.x, -44, 44), max(.6, pos.y), clamp(pos.z, -44, 44))
    camera.look_at(objetivo)

# ------------------------------------------------------------
#  ENEMIGA
# ------------------------------------------------------------
TRAJES = [(hsv(355, .85, .30), hsv(0, 0, .10), hsv(0, 1, 1)),
          (hsv(0, 0, .08), hsv(350, .8, .35), hsv(330, 1, 1)),
          (hsv(280, .6, .20), hsv(285, .5, .35), hsv(290, 1, 1)),
          (hsv(25, .6, .22), hsv(30, .4, .30), hsv(40, 1, 1))]
PELOS = [hsv(0, 0, .04), hsv(0, 0, .85), hsv(350, .8, .35), hsv(30, .4, .18)]

class Asesina(Entity):
    def __init__(self, posicion, velocidad, vida):
        super().__init__(position=posicion)
        self.velocidad = velocidad
        self.vida = vida
        self.cd = 0
        self.t = random.uniform(0, 6)
        self.fase = random.uniform(0, 6.28)
        self.muerta = False
        self.modelo = Entity(parent=self)
        tr, ch, ac = random.choice(TRAJES)
        tipo = random.choice(['katana', 'machete', 'cuchillo'])
        self.p = mujer(self.modelo, piel=hsv(15, .08, .88), top=tr, pantalon=tr, chaqueta=ch,
                       pelo=random.choice(PELOS), acento=ac, iris=hsv(0, 1, 1), guante=hsv(0, 0, .07),
                       falda=True, botas_altas=True, malvada=True, glb=MODELO_ASESINA, melee=tipo,
                       hoja_col=hsv(0, .8, .8) if tipo == 'katana' else None,
                       peinado='coletas' if random.random() < .5 else 'suelto')
        self.p['brazo'].rotation_x = -80

    def update(self):
        if self.muerta or estado['modo'] != 'juego':
            return
        dt = time.dt
        self.t += dt * 10
        self.cd -= dt
        pos = jugadora.position
        d = distance_xz(self.position, pos)
        objetivo = Vec3(pos.x, 0, pos.z)
        if d > 6:
            objetivo += Vec3(estado['vel'].x, 0, estado['vel'].z) * .6
            objetivo += Vec3(math.sin(self.fase), 0, math.cos(self.fase)) * 3
        dx, dz = objetivo.x - self.x, objetivo.z - self.z
        if math.hypot(dx, dz) > .1:
            self.rotation_y = angulo_suave(self.rotation_y, math.degrees(math.atan2(dx, dz)), 10 * dt)
        mover = d > 1.4
        if mover:
            v = self.velocidad * (1.7 if d < 6 else 1)
            r = math.radians(self.rotation_y)
            self.x, self.z = resolver(self.x + math.sin(r) * v * dt, self.z + math.cos(r) * v * dt, .5)
            self.modelo.y = abs(math.sin(self.t)) * .05
        for o in enemigas:
            if o is not self:
                ex, ez = self.x - o.x, self.z - o.z
                dd = math.hypot(ex, ez)
                if 0 < dd < 1.0:
                    self.x += ex / dd * dt * 2
                    self.z += ez / dd * dt * 2
        sn = math.sin(self.t)
        for i, pv in enumerate(self.p['piernas']):
            pv.rotation_x = (sn * 42 if mover else 0) * (1 if i == 0 else -1)
        for i, sh in enumerate(self.p.get('shins', [])):
            if mover:
                ph = sn if i == 0 else -sn
                sh.rotation_x = max(0, ph) * 34 - 5
            else:
                sh.rotation_x = lerp(sh.rotation_x, -4, .2)
        self.p['cola'].rotation_x = 15 + math.sin(self.t * .5) * 10
        if d <= 1.8 and self.cd <= 0:
            self.cd = 1.1
            self.p['brazo'].rotation_x = -150
            self.p['brazo'].animate('rotation_x', -80, duration=.3)
            herir_jugadora(10 + estado['nivel'])

    def recibir_golpe(self, dano=1):
        if self.muerta:
            return
        self.vida -= dano
        ax, az = self.x - jugadora.x, self.z - jugadora.z
        n = math.hypot(ax, az) or 1
        self.x, self.z = resolver(self.x + ax / n * 1.2, self.z + az / n * 1.2, .5)
        self.modelo.scale = 1.1
        self.modelo.animate_scale(1, .15)
        if self.vida <= 0:
            self.morir()

    def morir(self):
        self.muerta = True
        if self in enemigas:
            enemigas.remove(self)
        estado['derrotadas'] += 1
        Audio(random.choice(['snd_grito.wav', 'snd_grito2.wav']),
              pitch=random.uniform(.85, 1.2), auto_destroy=True)
        self.modelo.animate('rotation_x', -90, duration=.45)
        destroy(self, delay=1.6)

# ------------------------------------------------------------
#  LOGICA DEL JUEGO
# ------------------------------------------------------------
def herir_jugadora(dano):
    estado['vida'] -= dano
    Audio('snd_golpe.wav', auto_destroy=True)
    pantalla.color = hsv(0, 1, .8, .5)
    pantalla.animate_color(hsv(0, 1, .8, 0), duration=.5)

def punto_spawn():
    for _ in range(60):
        p = Vec3(random.uniform(-40, 40), 0, random.uniform(-40, 40))
        x, z = resolver(p.x, p.z, .6)
        if distance_xz(Vec3(x, 0, z), jugadora.position) > 22:
            return Vec3(x, 0, z)
    return Vec3(0, 0, -40)

def empezar_nivel(partida):
    if partida != estado['partida'] or estado['modo'] != 'juego':
        return
    estado['cambiando'] = False
    n = estado['nivel']
    aplicar_ambiente(n)
    estado['mun'] = cargador()
    for _ in range(min(2 + n, 10)):
        enemigas.append(Asesina(punto_spawn(), min(3.4 + .45 * n, 7.5), 2 + n // 3))
    t = Text(text=f'NIVEL {n}', origin=(0, 0), scale=4, y=.2, color=color.red, parent=camera.ui)
    destroy(t, delay=2.5)

def iniciar_juego():
    for e in list(enemigas):
        destroy(e)
    enemigas.clear()
    estado.update(modo='juego', vida=100, nivel=1, derrotadas=0, ataque=0, cambiando=False,
                  mun=cargador(), recarga=0, alt=0, recuo=0)
    estado['partida'] += 1
    jugadora.position = Vec3(0, 0, 0)
    jugadora.yaw = 0
    jugadora.pitch = 18
    jugadora.modelo.rotation_y = 0
    estado['prev'] = Vec3(jugadora.position)
    menu.enabled = False
    hud.enabled = True
    equipar('principal')
    mouse.locked = True
    empezar_nivel(estado['partida'])

def mostrar_menu(mensaje=None):
    estado['modo'] = 'menu'
    menu.enabled = True
    hud.enabled = False
    mouse.locked = False
    mouse.visible = True
    equipar('principal')
    if mensaje:
        subtitulo.text = mensaje
        boton_jugar.text = 'JUGAR DE NUEVO'

def terminar_juego():
    for e in list(enemigas):
        destroy(e)
    enemigas.clear()
    mostrar_menu(f'Te atraparon. Nivel {estado["nivel"]} | Derrotadas: {estado["derrotadas"]}')

def trazador(a, b):
    largo = (b - a).length()
    if largo < .1:
        return
    t = G(model='cube', position=(a + b) / 2, scale=(.035, .035, largo), color=hsv(48, .4, 1))
    t.look_at(b)
    destroy(t, delay=.07)

def impacto(pos):
    fl = G(model='sphere', position=pos, scale=.13, color=hsv(48, .5, 1))
    destroy(fl, delay=.07)
    for i in range(5):
        d = G(model='sphere', position=pos, scale=.05, color=hsv(45, .7, 1))
        d.animate_position(pos + Vec3(random.uniform(-.6, .6), random.uniform(.2, .9),
                                      random.uniform(-.6, .6)), duration=.22)
        destroy(d, delay=.22)

def recargar():
    if estado['arma'] != 'principal' or estado['recarga'] > 0 or estado['mun'] >= cargador():
        return
    estado['recarga'] = 1.1
    Audio('snd_recarga.wav', auto_destroy=True, volume=.6)

def atacar():
    if estado['modo'] != 'juego' or estado['ataque'] > 0 or estado['recarga'] > 0:
        return
    fy = math.radians(jugadora.yaw)
    f = Vec3(math.sin(fy), 0, math.cos(fy))
    brazo = jugadora.p['brazo']
    if estado['arma'] == 'katana':
        estado['ataque'] = .5
        brazo.rotation_x = -150
        brazo.animate('rotation_x', -15, duration=.35)
        Audio('snd_espada.wav', auto_destroy=True, volume=.6, pitch=random.uniform(.9, 1.2))
        for e in list(enemigas):
            dx = Vec3(e.x - jugadora.x, 0, e.z - jugadora.z)
            dist = dx.length()
            if 0 < dist < 3.6 and dx.normalized().dot(f) > .35:
                Audio('snd_golpe.wav', auto_destroy=True, volume=.4, pitch=1.2)
                e.recibir_golpe(2)
        return
    st = ARMAS_STATS[jugadora.tipo]
    if estado['mun'] <= 0:
        recargar()
        return
    estado['ataque'] = st['cd']
    estado['mun'] -= 1
    estado['recuo'] += st['recuo']
    brazo.rotation_x = -98
    brazo.animate('rotation_x', -88, duration=min(.12, st['cd']))
    Audio('snd_disparo.wav', auto_destroy=True, volume=.7, pitch=st['pitch'] * random.uniform(.95, 1.08))
    fls = jugadora.p['flashes']
    origen = jugadora.position + Vec3(0, 1.3, 0) + f
    if fls:
        fl = fls[estado['alt'] % len(fls)]
        estado['alt'] += 1
        origen = fl.world_position
        fl.enabled = True
        invoke(setattr, fl, 'enabled', False, delay=.05)
    mejor, md = None, 999
    for e in enemigas:
        dx = Vec3(e.x - jugadora.x, 0, e.z - jugadora.z)
        dist = dx.length()
        if 0 < dist < 40 and dx.normalized().dot(f) > .985 and dist < md:
            mejor, md = e, dist
    if mejor:
        trazador(origen, Vec3(mejor.x, 1.4, mejor.z))
        impacto(Vec3(mejor.x, 1.3, mejor.z))
        mejor.recibir_golpe(st['dano'])
    else:
        pt = origen + f * random.uniform(10, 22)
        trazador(origen, pt)
        impacto(pt)
    if estado['mun'] <= 0:
        recargar()

def input(key):
    if estado['modo'] == 'menu':
        if key in ('1', '2', '3'):
            elegir(int(key) - 1)
        return
    if key in ('left mouse down', 'f'):
        atacar()
    if key == '1':
        equipar('katana')
    if key == '2':
        equipar('principal')
    if key == 'r':
        recargar()
    if key == 'escape':
        mostrar_menu('Partida en pausa (JUGAR empieza de nuevo)')

def update():
    dt = time.dt
    if estado['modo'] != 'juego':
        estado['orbita'] += dt * .25
        a = estado['orbita']
        camera.position = Vec3(math.sin(a) * 5.2, 1.9, math.cos(a) * 5.2)
        camera.look_at(Vec3(0, 1.15, 0))
        animar_caminar(jugadora.p, 0, False)
        return
    mover_jugadora(dt)
    if dt > 0:
        estado['vel'] = (jugadora.position - estado['prev']) / dt
        estado['prev'] = Vec3(jugadora.position)
    estado['ataque'] -= dt
    estado['recuo'] = lerp(estado['recuo'], 0, 10 * dt)
    if estado['arma'] == 'principal' and ARMAS_STATS[jugadora.tipo]['auto'] and held_keys['left mouse']:
        atacar()
    if estado['recarga'] > 0:
        estado['recarga'] -= dt
        if estado['recarga'] <= 0:
            estado['mun'] = cargador()
    texto_vida.text = f'VIDA: {max(0, int(estado["vida"]))}'
    texto_nivel.text = f'NIVEL: {estado["nivel"]}'
    texto_enemigas.text = f'ASESINAS: {len(enemigas)}'
    if estado['arma'] == 'katana':
        texto_arma.text = '[1] KATANA'
    else:
        st = ARMAS_STATS[jugadora.tipo]
        texto_arma.text = f'[2] {st["nombre"]}  ' + ('RECARGANDO...' if estado['recarga'] > 0 else f'{estado["mun"]}/{st["mun"]}')
    barra_vida.scale_x = max(0.001, .4 * estado['vida'] / 100)
    mira.scale = 2.2 + estado['recuo'] * .35
    if estado['vida'] <= 0:
        terminar_juego()
        return
    if not enemigas and not estado['cambiando']:
        estado['cambiando'] = True
        estado['nivel'] += 1
        estado['vida'] = min(100, estado['vida'] + 25)
        invoke(empezar_nivel, estado['partida'], delay=3)

# ------------------------------------------------------------
#  INTERFAZ
# ------------------------------------------------------------
pantalla = Entity(parent=camera.ui, model='quad', scale=(3, 2), color=hsv(0, 1, .8, 0), z=1)

hud = Entity(parent=camera.ui)
texto_vida = Text(parent=hud, text='', position=(-.85, .46), scale=1.6, color=color.red)
Entity(parent=hud, model='quad', origin=(-.5, 0), position=(-.85, .41), scale=(.4, .02), color=hsv(0, 0, .15))
barra_vida = Entity(parent=hud, model='quad', origin=(-.5, 0), position=(-.85, .41), scale=(.4, .02),
                    color=hsv(0, 1, .8))
texto_nivel = Text(parent=hud, text='', position=(-.85, .37), scale=1.3, color=color.white)
texto_enemigas = Text(parent=hud, text='', position=(-.85, .33), scale=1.3, color=color.orange)
texto_arma = Text(parent=hud, text='', position=(-.85, .29), scale=1.3, color=color.cyan)
mira = Text(parent=hud, text='+', origin=(0, 0), position=(0.03, 0.03), scale=2.2, color=color.white)
Text(parent=hud, text='1: katana | 2: arma de fuego (mantener clic = rafaga) | R: recargar',
     origin=(0, 0), position=(0, -.46), scale=1.0, color=color.gray)

menu = Entity(parent=camera.ui)
Entity(parent=menu, model='quad', scale=(3, 2), color=hsv(0, 0, 0, .22), z=1)
Entity(parent=menu, model='quad', scale=(3, .2), y=.38, color=hsv(28, .95, .95, .88), z=.5)
Entity(parent=menu, model='quad', scale=(3, .012), y=.275, color=hsv(52, 1, 1), z=.4)
Entity(parent=menu, model='quad', scale=(3, .012), y=.485, color=hsv(52, 1, 1), z=.4)
Text(parent=menu, text='MUJERES ASESINAS 3D', origin=(0, 0), position=(.005, .375), scale=3.2,
     color=color.black, z=.1)
Text(parent=menu, text='MUJERES ASESINAS 3D', origin=(0, 0), position=(0, .38), scale=3.2,
     color=hsv(55, .15, 1), z=0)
subtitulo = Text(parent=menu, text='Sobrevive a la ciudad del terror', origin=(0, 0),
                 position=(0, .22), scale=1.4, color=color.light_gray)
boton_jugar = Button(parent=menu, text='JUGAR', color=hsv(0, 1, .5),
                     scale=(.3, .09), position=(-.55, -.05), on_click=iniciar_juego)
boton_salir = Button(parent=menu, text='SALIR', color=hsv(0, 0, .2),
                     scale=(.3, .09), position=(-.55, -.18), on_click=application.quit)
Text(parent=menu, text='ELIGE PERSONAJE (o teclas 1, 2, 3)', origin=(0, 0), position=(.55, .15),
     scale=1.2, color=hsv(52, 1, 1))
pers_botones = []
for _i, _d in enumerate(PERSONAJES):
    _b = Button(parent=menu, text=f'{_i + 1}. {_d["nombre"]}', scale=(.34, .08), position=(.55, .06 - _i * .11),
                color=hsv(0, 0, .2), on_click=(lambda i=_i: elegir(i)))
    pers_botones.append(_b)
texto_pers = Text(parent=menu, text='', origin=(0, 0), position=(.55, -.30), scale=1.0, color=color.light_gray)
Text(parent=menu, text='WASD mover | SHIFT correr | CLIC o F atacar | 1 katana | 2 arma | R recargar | ESC menu',
     origin=(0, 0), position=(0, -.44), scale=1.0, color=color.gray)

def elegir(i):
    construir_jugadora(i)
    for k, b in enumerate(pers_botones):
        b.color = hsv(30, .9, .7) if k == i else hsv(0, 0, .2)
    texto_pers.text = PERSONAJES[i]['desc']
    equipar('principal')

elegir(0)
mostrar_menu()
app.run()



