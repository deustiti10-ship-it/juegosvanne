from ursina import *
from panda3d.core import loadPrcFileData, AntialiasAttrib, Point2, Point3
import math, random, os, wave, struct, json

# ------------------------------------------------------------
#  OPCIONES
# ------------------------------------------------------------
FULLSCREEN = False
ANCHO, ALTO = 1280, 720
LUCES_3D = True            # pon False si tu PC va lenta

loadPrcFileData('', 'framebuffer-multisample 1\nmultisamples 4')

try:
    from ursina.shaders import lit_with_shadows_shader
except Exception:
    lit_with_shadows_shader = None

hsv = color.hsv
CARPETA = os.path.dirname(os.path.abspath(__file__))
SR = 22050

# ------------------------------------------------------------
#  SONIDOS (se crean solos la primera vez)
# ------------------------------------------------------------
def guardar(nombre, muestras):
    ruta = os.path.join(CARPETA, nombre)
    with wave.open(ruta, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b''.join(
            struct.pack('<h', int(max(-1.0, min(1.0, m)) * 30000)) for m in muestras))

def sintetizar(nombre, notas, dur, vol=.5, caida=4.0):
    if os.path.exists(os.path.join(CARPETA, nombre)):
        return
    m = []
    for f in notas:
        for i in range(int(SR * dur)):
            t = i / SR
            env = math.exp(-caida * t) * min(1.0, t / 0.01)
            m.append(vol * env * (math.sin(2 * math.pi * f * t) + .3 * math.sin(4 * math.pi * f * t)))
    guardar(nombre, m)

sintetizar('kitty_musica.wav', [523, 587, 659, 784, 880, 784, 659, 587,
                                523, 659, 784, 1047, 880, 784, 659, 587], .4, .25, 2.5)
sintetizar('kitty_item.wav', [988, 1319], .1, .5, 8)
sintetizar('kitty_golpe.wav', [110, 80], .12, .8, 12)
sintetizar('kitty_boing.wav', [330, 440, 550], .06, .6, 6)
sintetizar('kitty_victoria.wav', [523, 659, 784, 1047], .22, .5, 3)

# ------------------------------------------------------------
#  PROGRESO GUARDADO (monedas y recompensas)
# ------------------------------------------------------------
RUTA_PROG = os.path.join(CARPETA, 'kitty_progreso.json')
RECOMPENSAS = [(30, 'LAZO DORADO'), (80, 'AUREOLA'), (150, 'ALAS DE ANGEL')]

def cargar_progreso():
    try:
        with open(RUTA_PROG, 'r') as f:
            d = json.load(f)
        return {'monedas': int(d.get('monedas', 0)), 'mejor': int(d.get('mejor', 1))}
    except Exception:
        return {'monedas': 0, 'mejor': 1}

def guardar_progreso():
    try:
        with open(RUTA_PROG, 'w') as f:
            json.dump(prog, f)
    except Exception:
        pass

prog = cargar_progreso()

def extras():
    return sum(1 for c, _ in RECOMPENSAS if prog['monedas'] >= c)

# ------------------------------------------------------------
#  MOTOR
# ------------------------------------------------------------
app = Ursina(title='MISION GATITA 3D', borderless=False, fullscreen=FULLSCREEN, size=(ANCHO, ALTO))
window.exit_button.visible = False
camera.fov = 60
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
    return Entity(**k)

LIM = 39
obstaculos = []

if SH:
    sol = DirectionalLight(shadows=True, shadow_map_resolution=Vec2(2048, 2048))
    sol.rotation = (55, -35, 0)
    luz_amb = AmbientLight()

AMBIENTES = [200, 330, 160, 270]

def aplicar_ambiente(nivel):
    h = AMBIENTES[(nivel - 1) % len(AMBIENTES)]
    cielo = hsv(h, .28, 1)
    window.color = cielo
    scene.fog_color = cielo
    scene.fog_density = (35, 130)
    if SH:
        sol.color = hsv(40, .15, 1)
        luz_amb.color = hsv(h, .25, .62)

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
#  MUNDO: PUEBLO PASTEL
# ------------------------------------------------------------
def casa(x, z, w, h, col):
    E(model='cube', position=(x, h / 2, z), scale=(w, h, w), color=col)
    E(model='cube', position=(x, h, z), scale=(w * .72, w * .72, w + .8), rotation_z=45,
      color=hsv(350, .45, .95))
    E(model='cube', position=(x, .9, z - w / 2 - .03), scale=(1.0, 1.8, .1), color=hsv(25, .4, .6))
    for sx in (-1, 1):
        G(model='cube', position=(x + sx * w * .3, h * .6, z - w / 2 - .03), scale=(.8, .8, .1),
          color=hsv(48, .5, 1))
    E(model='cube', position=(x + w * .25, h + w * .55, z), scale=(.6, 1.4, .6), color=hsv(20, .3, .7))
    obstaculos.append((x, z, w / 2 + .2, w / 2 + .2))

def cerezo(x, z):
    E(model='cube', position=(x, 1.4, z), scale=(.55, 2.8, .55), color=hsv(25, .5, .38))
    for dx, dy, dz, s in ((0, 3.6, 0, 3.2), (-1.1, 3.1, .3, 2.2), (1.1, 3.2, -.3, 2.3), (0, 4.5, .2, 2.0)):
        E(model='sphere', position=(x + dx, dy, z + dz), scale=s, color=hsv(340, .28, 1))
    obstaculos.append((x, z, .5, .5))

def lago(x, z):
    G(model='circle', rotation_x=90, position=(x, .04, z), scale=9, color=hsv(195, .5, 1),
      double_sided=True)
    G(model='circle', rotation_x=90, position=(x, .05, z), scale=7.5, color=hsv(190, .35, 1),
      double_sided=True)
    obstaculos.append((x, z, 3.6, 3.6))

def construir_mundo():
    random.seed(7)
    E(model='plane', scale=(100, 1, 100), color=hsv(110, .32, .86))
    for v in (-20, 0, 20):
        E(model='cube', position=(0, .01, v), scale=(84, .02, 4), color=hsv(38, .22, .98))
        E(model='cube', position=(v, .01, 0), scale=(4, .02, 84), color=hsv(38, .22, .98))
    for s in (-40.5, 40.5):
        E(model='cube', position=(0, .45, s), scale=(82, .9, .4), color=hsv(0, 0, 1))
        E(model='cube', position=(s, .45, 0), scale=(.4, .9, 82), color=hsv(0, 0, 1))
    celdas = [(gx, gz) for gx in (-30, -10, 10, 30) for gz in (-30, -10, 10, 30)]
    random.shuffle(celdas)
    colores = [hsv(340, .22, 1), hsv(200, .25, 1), hsv(55, .3, 1), hsv(270, .2, 1), hsv(150, .22, 1)]
    for i, (gx, gz) in enumerate(celdas):
        if i < 6:
            casa(gx, gz, random.uniform(5, 6.5), random.uniform(3.2, 4.4), random.choice(colores))
        elif i == 6:
            lago(gx, gz)
        elif i < 11:
            cerezo(gx - 2, gz - 1)
            cerezo(gx + 2.5, gz + 1.5)
    for _ in range(90):
        x, z = random.uniform(-38, 38), random.uniform(-38, 38)
        if any(abs(x - ox) < hx + .5 and abs(z - oz) < hz + .5 for ox, oz, hx, hz in obstaculos):
            continue
        col = hsv(random.choice([340, 50, 280, 200, 15]), .5, 1)
        G(model='cube', position=(x, .2, z), scale=(.04, .4, .04), color=hsv(120, .6, .5))
        G(model='sphere', position=(x, .42, z), scale=.22, color=col)
    for _ in range(14):
        cx, cy, cz = random.uniform(-60, 60), random.uniform(22, 34), random.uniform(-30, 70)
        for dx, s in ((0, 7), (-4, 5), (4, 5.5)):
            G(model='sphere', position=(cx + dx, cy, cz), scale=(s * 1.4, s * .6, s), color=hsv(0, 0, 1, .92))
    random.seed()

construir_mundo()
aplicar_ambiente(1)

# ------------------------------------------------------------
#  PERSONAJE: CHICA CON CAPUCHA DE GATO Y PELUCHE
# ------------------------------------------------------------
NEGRO = hsv(0, 0, .06)
BLANCO = hsv(0, 0, .98)
ORO = hsv(45, .8, 1)

PERSONAJES = [
    dict(nombre='MOMO', sudadera=hsv(345, .28, 1), falda=hsv(345, .45, .95), zapato=hsv(345, .5, .9),
         pelo=hsv(20, .35, .18), iris=hsv(350, .5, .85), interior=hsv(345, .45, 1), tono=hsv(345, .6, 1)),
    dict(nombre='NUBI', sudadera=hsv(200, .30, 1), falda=hsv(205, .45, .95), zapato=hsv(205, .5, .9),
         pelo=hsv(240, .30, .20), iris=hsv(200, .5, .9), interior=hsv(200, .4, 1), tono=hsv(200, .6, 1)),
    dict(nombre='LILA', sudadera=hsv(275, .28, 1), falda=hsv(280, .45, .92), zapato=hsv(280, .5, .85),
         pelo=hsv(300, .25, .22), iris=hsv(285, .5, .85), interior=hsv(285, .4, 1), tono=hsv(285, .6, 1)),
    dict(nombre='MENTA', sudadera=hsv(150, .30, .98), falda=hsv(155, .45, .88), zapato=hsv(155, .5, .8),
         pelo=hsv(25, .45, .22), iris=hsv(150, .55, .8), interior=hsv(150, .4, 1), tono=hsv(150, .6, 1)),
]

# arriba, abajo, izquierda, derecha, salto
CONTROLES = [('w', 's', 'a', 'd', 'space'),
             ('up arrow', 'down arrow', 'left arrow', 'right arrow', 'enter'),
             ('i', 'k', 'j', 'l', 'o'),
             ('t', 'g', 'f', 'h', 'y')]
TEXTO_CONTROLES = ['WASD + ESPACIO', 'FLECHAS + ENTER', 'IJKL + O', 'TFGH + Y']

def lazo(padre, pos, col, esc=1.0):
    p = Entity(parent=padre, position=pos)
    for sx in (-1, 1):
        E(parent=p, model='cube', position=(sx * .05 * esc, 0, 0), scale=(.07 * esc, .07 * esc, .03),
          rotation_z=45, color=col)
    E(parent=p, model='sphere', scale=.04 * esc, color=col * .85)
    return p

def chica(raiz, c, nextras=0):
    piel = hsv(22, .16, 1)
    rosa = hsv(345, .4, 1)
    H = 1.48
    piernas = []
    for lado in (-1, 1):
        pv = Entity(parent=raiz, position=(lado * .12, .58, 0))
        E(parent=pv, model='sphere', y=-.25, scale=(.17, .46, .18), color=piel)
        E(parent=pv, model='sphere', y=-.40, scale=(.19, .20, .20), color=BLANCO)
        E(parent=pv, model='sphere', y=-.55, z=.04, scale=(.20, .11, .30), color=c['zapato'])
        piernas.append(pv)
    E(parent=raiz, model='sphere', position=(0, .74, 0), scale=(.56, .40, .44), color=c['falda'])
    E(parent=raiz, model='sphere', position=(0, .98, 0), scale=(.50, .52, .38), color=c['sudadera'])
    E(parent=raiz, model='sphere', position=(0, 1.2, -.02), scale=(.42, .16, .34), color=c['sudadera'])
    # cabeza
    E(parent=raiz, model='sphere', position=(0, H, 0), scale=(.58, .54, .52), color=piel)
    E(parent=raiz, model='sphere', position=(0, H + .04, -.07), scale=(.64, .60, .54), color=c['pelo'])
    for bx in (-.2, -.1, 0, .1, .2):
        E(parent=raiz, model='sphere', position=(bx, H + .11 - abs(bx) * .15, .21),
          scale=(.14, .15, .10), color=c['pelo'])
    for lado in (-1, 1):
        x = lado * .13
        G(parent=raiz, model='sphere', position=(x, H - .07, .235), scale=(.12, .15, .05), color=BLANCO)
        G(parent=raiz, model='sphere', position=(x, H - .075, .245), scale=(.095, .13, .05), color=c['iris'])
        G(parent=raiz, model='sphere', position=(x, H - .075, .256), scale=(.05, .08, .05), color=NEGRO)
        G(parent=raiz, model='sphere', position=(x - .02, H - .03, .266), scale=.03, color=BLANCO)
        G(parent=raiz, model='sphere', position=(lado * .19, H - .17, .21), scale=(.07, .035, .02),
          color=hsv(350, .4, 1))
        E(parent=raiz, model='sphere', position=(lado * .31, H + .02, -.02), scale=(.12, .46, .42), color=BLANCO)
    G(parent=raiz, model='cube', position=(0, H - .22, .245), scale=(.035, .012, .02), color=hsv(350, .6, .7))
    # capucha de gato
    E(parent=raiz, model='sphere', position=(0, H + .26, -.05), scale=(.72, .44, .64), color=BLANCO)
    for lado in (-1, 1):
        E(parent=raiz, model='cube', position=(lado * .24, H + .50, -.03), scale=(.22, .22, .10),
          rotation_z=45 - lado * 12, color=BLANCO)
        E(parent=raiz, model='cube', position=(lado * .24, H + .49, .02), scale=(.12, .12, .06),
          rotation_z=45 - lado * 12, color=c['interior'])
        G(parent=raiz, model='sphere', position=(lado * .11, H + .34, .235), scale=.05, color=NEGRO)
    G(parent=raiz, model='sphere', position=(0, H + .32, .255), scale=(.06, .045, .03), color=hsv(48, .45, 1))
    lazo(raiz, (.27, H + .28, .17), c['interior'], 1.2)
    # trenzas
    for lado in (-1, 1):
        for k, (dy, s) in enumerate(((.28, .2), (.46, .2), (.64, .17))):
            E(parent=raiz, model='sphere', position=(lado * .34, H - dy, -.10), scale=(.11, s, .11), color=c['pelo'])
        lazo(raiz, (lado * .34, H - .78, -.10), rosa, 1.0)
    # brazos que abrazan al peluche
    for lado in (-1, 1):
        br = Entity(parent=raiz, position=(lado * .28, 1.14, 0), rotation_x=-55)
        E(parent=br, model='sphere', y=-.2, scale=(.13, .40, .13), color=c['sudadera'])
        E(parent=br, model='sphere', y=-.43, scale=.11, color=piel)
    # peluche gatito
    pl = Entity(parent=raiz, position=(0, .98, .30))
    E(parent=pl, model='sphere', scale=(.50, .40, .28), color=BLANCO)
    for lado in (-1, 1):
        E(parent=pl, model='cube', position=(lado * .17, .2, 0), scale=(.13, .13, .07), rotation_z=45,
          color=BLANCO)
        E(parent=pl, model='cube', position=(lado * .17, .19, .03), scale=(.07, .07, .04), rotation_z=45,
          color=rosa)
        G(parent=pl, model='sphere', position=(lado * .13, .0, .125), scale=(.04, .06, .03), color=NEGRO)
        G(parent=pl, model='sphere', position=(lado * .17, -.07, .115), scale=(.07, .05, .02),
          color=hsv(350, .35, 1))
        for k in (-1, 0, 1):
            G(parent=pl, model='cube', position=(lado * .27, -.03 + k * .035, .10), scale=(.12, .007, .007),
              rotation_z=lado * k * -10, color=NEGRO)
    G(parent=pl, model='sphere', position=(0, -.04, .135), scale=(.05, .035, .03), color=hsv(48, .5, 1))
    lazo(pl, (.2, .17, .12), hsv(0, .7, .95), .8)
    # recompensas desbloqueadas
    if nextras >= 1:
        lazo(raiz, (-.27, H + .28, .17), ORO, 1.3)
    if nextras >= 2:
        for i in range(10):
            a = i / 10 * 6.2832
            G(parent=raiz, model='sphere', position=(math.cos(a) * .25, H + .72, math.sin(a) * .25),
              scale=.06, color=ORO)
    if nextras >= 3:
        for lado in (-1, 1):
            E(parent=raiz, model='sphere', position=(lado * .34, 1.08, -.30), scale=(.09, .55, .32),
              rotation_z=lado * -22, color=BLANCO)
            E(parent=raiz, model='sphere', position=(lado * .42, 1.0, -.30), scale=(.07, .36, .26),
              rotation_z=lado * -35, color=c['interior'])
    return {'piernas': piernas, 'plush': pl}

# ------------------------------------------------------------
#  JUGADORAS
# ------------------------------------------------------------
estado = {'modo': 'menu', 'nivel': 1, 'vida': 100, 'n': 2, 'partida': 0, 'cambiando': False,
          'est': 0, 'cor': 0, 'nub': 0, 'meta_e': 0, 'meta_c': 0, 'meta_n': 0,
          'orbita': 0, 'aviso_t': 0,
          'cam_yaw': 0, 'cam_pitch': 32, 'yaw_obj': 0, 'pitch_obj': 32, 'zoom': 1.0, 'cam_snap': True,
          'vista': 0, 'mouse_t': 0}
VISTAS = [(0, 32, 'ATRAS'), (0, 55, 'ALTA'), (180, 28, 'DE FRENTE')]
jugadoras = []
items = []
nubes = []
casita = {'ent': None, 'puerta': None, 'glow': None, 'pos': Vec3(0, 0, 30), 'abierta': False, 'obs': None}

class Jugadora(Entity):
    def __init__(self, idx):
        super().__init__()
        self.idx = idx
        self.cfg = PERSONAJES[idx]
        self.teclas = CONTROLES[idx]
        self.vy = 0.0
        self.suelo = True
        self.t = 0.0
        self.giro = 180
        self.puntos = 0
        self.inmune = 0.0
        self.modelo = Entity(parent=self)
        self.modelo.rotation_y = self.giro
        self.partes = chica(self.modelo, self.cfg, extras())

    def reconstruir(self):
        destroy(self.modelo)
        self.modelo = Entity(parent=self)
        self.modelo.rotation_y = self.giro
        self.partes = chica(self.modelo, self.cfg, extras())

    def dir_mouse(self, fw, rt):
        pt = punto_mouse()
        if pt is not None:
            d = Vec3(pt.x - self.x, 0, pt.z - self.z)
        else:
            d = rt * mouse.x + fw * mouse.y
            return d if d.length() > .08 else Vec3(0, 0, 0)
        return d if d.length() > .5 else Vec3(0, 0, 0)

    def saltar(self):
        if self.suelo:
            self.vy = 9.5
            self.suelo = False

    def update(self):
        dt = time.dt
        mover = False
        if estado['modo'] == 'juego':
            t = self.teclas
            yaw = math.radians(estado['cam_yaw'])
            fw = Vec3(math.sin(yaw), 0, math.cos(yaw))
            rt = Vec3(math.cos(yaw), 0, -math.sin(yaw))
            mx = held_keys[t[3]] - held_keys[t[2]]
            mz = held_keys[t[0]] - held_keys[t[1]]
            v = rt * mx + fw * mz
            if v.length() == 0 and self.idx == 0 and estado['mouse_t'] <= 0 and held_keys['left mouse']:
                v = self.dir_mouse(fw, rt)
            if v.length() > 0:
                mover = True
                v = v.normalized()
                self.x, self.z = resolver(self.x + v.x * 7 * dt, self.z + v.z * 7 * dt, .5)
                self.giro = angulo_suave(self.giro, math.degrees(math.atan2(v.x, v.z)), 14 * dt)
                self.modelo.rotation_y = self.giro
                self.t += dt * 12
            self.vy -= 26 * dt
            self.y += self.vy * dt
            if self.y <= 0:
                self.y = 0
                self.vy = 0
                self.suelo = True
            if self.inmune > 0:
                self.inmune -= dt
                self.modelo.enabled = int(self.inmune * 12) % 2 == 0
            else:
                self.modelo.enabled = True
        sn = math.sin(self.t)
        p = self.partes
        if mover and self.suelo:
            p['piernas'][0].rotation_x = sn * 42
            p['piernas'][1].rotation_x = -sn * 42
            self.modelo.y = abs(sn) * .05
        else:
            for pv in p['piernas']:
                pv.rotation_x = lerp(pv.rotation_x, 0, .2)
            self.modelo.y = lerp(self.modelo.y, 0, .2)
        p['plush'].y = .98 + (math.sin(self.t * 2) * .015 if mover else math.sin(time.dt * 0) * 0)

def punto_mouse():
    try:
        lens = base.camLens
        cerca, lejos = Point3(), Point3()
        if not lens.extrude(Point2(mouse.x * 2 / window.aspect_ratio, mouse.y * 2), cerca, lejos):
            return None
        a = scene.getRelativePoint(camera, cerca)
        b = scene.getRelativePoint(camera, lejos)
        dy = b.y - a.y
        if dy >= -1e-6:
            return None
        t = -a.y / dy
        return Vec3(a.x + (b.x - a.x) * t, 0, a.z + (b.z - a.z) * t)
    except Exception:
        return None

def colocar_jugadoras():
    n = len(jugadoras)
    for i, p in enumerate(jugadoras):
        p.position = Vec3((i - (n - 1) / 2) * 2.0, 0, -2)
        p.vy = 0
        p.giro = 180
        p.modelo.rotation_y = 180
        p.modelo.enabled = True
        p.inmune = 0

def crear_jugadoras(n):
    for p in jugadoras:
        destroy(p)
    jugadoras.clear()
    estado['n'] = n
    for i in range(n):
        jugadoras.append(Jugadora(i))
    colocar_jugadoras()

# ------------------------------------------------------------
#  OBJETOS, NUBES Y CASITA
# ------------------------------------------------------------
class Item(Entity):
    def __init__(self, tipo, pos):
        super().__init__(position=pos)
        self.tipo = tipo
        self.base = pos.y
        self.t = random.uniform(0, 6)
        if tipo == 'estrella':
            for r in (0, 45):
                G(parent=self, model='cube', scale=(.55, .55, .12), rotation_z=r, color=hsv(48, .85, 1))
            G(parent=self, model='sphere', scale=.3, color=hsv(48, .35, 1))
        elif tipo == 'corazon':
            rosa = hsv(345, .6, 1)
            G(parent=self, model='cube', scale=.34, rotation_z=45, color=rosa)
            for sx in (-1, 1):
                G(parent=self, model='sphere', position=(sx * .12, .12, 0), scale=.34, color=rosa)
        else:
            G(parent=self, model='sphere', scale=(.42, .42, .08), color=hsv(45, .8, 1))
            G(parent=self, model='sphere', scale=(.28, .28, .1), color=hsv(48, .5, 1))

class Nube(Entity):
    def __init__(self, pos, vel):
        super().__init__(position=pos)
        self.vel = vel
        self.viva = True
        self.t = random.uniform(0, 6)
        self.cuerpo = Entity(parent=self)
        for dx, dy, s in ((0, 0, 1.1), (-.6, -.1, .8), (.6, -.1, .85), (0, .4, .8)):
            E(parent=self.cuerpo, model='sphere', position=(dx, dy + .9, 0), scale=s, color=hsv(225, .15, .62))
        for sx in (-1, 1):
            G(parent=self.cuerpo, model='sphere', position=(sx * .25, 1.0, -.5), scale=(.2, .24, .1), color=BLANCO)
            G(parent=self.cuerpo, model='sphere', position=(sx * .25, 1.0, -.56), scale=.1, color=NEGRO)
            G(parent=self.cuerpo, model='cube', position=(sx * .25, 1.2, -.54), scale=(.28, .05, .05),
              rotation_z=sx * 18, color=NEGRO)

    def update(self):
        if not self.viva or estado['modo'] != 'juego' or not jugadoras:
            return
        dt = time.dt
        self.t += dt * 3
        objetivo = min(jugadoras, key=lambda p: distance_xz(self.position, p.position))
        dx, dz = objetivo.x - self.x, objetivo.z - self.z
        d = math.hypot(dx, dz) or 1
        self.rotation_y = angulo_suave(self.rotation_y, math.degrees(math.atan2(-dx, -dz)) + 180, 6 * dt)
        self.x, self.z = resolver(self.x + dx / d * self.vel * dt, self.z + dz / d * self.vel * dt, .8)
        self.cuerpo.y = math.sin(self.t) * .12
        for p in jugadoras:
            if distance_xz(self.position, p.position) < 1.25:
                if p.y > .5 and p.vy < 0:
                    self.aplastar(p)
                    return
                herir(p, self)

    def aplastar(self, p):
        self.viva = False
        if self in nubes:
            nubes.remove(self)
        estado['nub'] += 1
        p.puntos += 3
        p.vy = 9
        Audio('kitty_boing.wav', auto_destroy=True, volume=.7)
        self.animate_scale(Vec3(1.5, .1, 1.5), .15)
        destroy(self, delay=.3)

def herir(p, nube):
    if p.inmune > 0:
        return
    estado['vida'] -= 12
    p.inmune = 1.3
    ax, az = p.x - nube.x, p.z - nube.z
    n = math.hypot(ax, az) or 1
    p.x, p.z = resolver(p.x + ax / n * 1.8, p.z + az / n * 1.8, .5)
    Audio('kitty_golpe.wav', auto_destroy=True, volume=.6)
    pantalla.color = hsv(350, .8, 1, .35)
    pantalla.animate_color(hsv(350, .8, 1, 0), duration=.4)

def punto_libre(margen=1.5, min_origen=0):
    for _ in range(80):
        x, z = random.uniform(-LIM + 2, LIM - 2), random.uniform(-LIM + 2, LIM - 2)
        if math.hypot(x, z) < min_origen:
            continue
        if any(abs(x - ox) < hx + margen and abs(z - oz) < hz + margen for ox, oz, hx, hz in obstaculos):
            continue
        return Vec3(x, 0, z)
    return Vec3(random.choice([-20, 20]), 0, random.uniform(-30, 30))

def construir_casita(pos):
    c = Entity(position=pos)
    E(parent=c, model='cube', y=1.3, scale=(4, 2.6, 4), color=hsv(340, .25, 1))
    E(parent=c, model='cube', y=2.6, scale=(3.2, 3.2, 4.4), rotation_z=45, color=hsv(350, .5, .95))
    puerta = E(parent=c, model='cube', position=(0, .9, -2.03), scale=(1.1, 1.8, .1), color=hsv(0, 0, .45))
    for sx in (-1, 1):
        G(parent=c, model='cube', position=(sx * 1.3, 1.5, -2.03), scale=(.7, .7, .1), color=hsv(48, .5, 1))
    glow = G(parent=c, model='circle', rotation_x=90, y=.06, scale=11, color=hsv(130, .6, 1, .35),
             double_sided=True)
    glow.enabled = False
    casita.update(ent=c, puerta=puerta, glow=glow, pos=Vec3(pos), abierta=False)
    casita['obs'] = (pos.x, pos.z, 2.2, 2.2)
    obstaculos.append(casita['obs'])

def limpiar_nivel():
    for it in items:
        destroy(it)
    items.clear()
    for n in nubes:
        destroy(n)
    nubes.clear()
    if casita['ent'] is not None:
        destroy(casita['ent'])
        casita['ent'] = None
    if casita['obs'] in obstaculos:
        obstaculos.remove(casita['obs'])
    casita['obs'] = None

# ------------------------------------------------------------
#  INTERFAZ
# ------------------------------------------------------------
pantalla = Entity(parent=camera.ui, model='quad', scale=(3, 2), color=hsv(0, 1, .8, 0), z=1)

hud = Entity(parent=camera.ui)
filas = [Text(parent=hud, text='', position=(-.86, .46 - i * .045), scale=1.2, color=PERSONAJES[i]['tono'])
         for i in range(4)]
Entity(parent=hud, model='quad', origin=(-.5, 0), position=(-.86, .255), scale=(.4, .018), color=hsv(0, 0, .2))
barra_vida = Entity(parent=hud, model='quad', origin=(-.5, 0), position=(-.86, .255), scale=(.4, .018),
                    color=hsv(345, .7, 1))
t_vida = Text(parent=hud, text='', position=(-.86, .235), scale=1.1, color=hsv(345, .5, .4))
t_nivel = Text(parent=hud, text='', position=(-.86, .195), scale=1.2, color=hsv(0, 0, .25))
t_monedas = Text(parent=hud, text='', position=(-.86, .155), scale=1.2, color=hsv(40, .9, .7))
t_mis = [Text(parent=hud, text='', position=(.40, .46 - i * .05), scale=1.2, color=hsv(0, 0, .2))
         for i in range(5)]
Text(parent=hud, text='MOUSE (MOMO): clic izq = caminar, clic der = saltar  |  C: camara  |  Q/E: girar  |  rueda: zoom  |  ESC: menu',
     origin=(0, 0), position=(0, -.46), scale=1.0, color=hsv(0, 0, .3))

aviso = Text(parent=camera.ui, text='', origin=(0, 0), position=(0, .22), scale=2.4, color=color.white)
aviso.enabled = False

def poner(t, s):
    if t.text != s:
        t.text = s

def mostrar_aviso(texto, seg=2.5, col=None):
    aviso.text = texto
    aviso.color = col if col is not None else hsv(345, .7, 1)
    aviso.enabled = True
    estado['aviso_t'] = seg

menu = Entity(parent=camera.ui)
Entity(parent=menu, model='quad', scale=(3, 2), color=hsv(330, .25, 1, .38), z=1)
Entity(parent=menu, model='quad', scale=(3, .22), y=.38, color=hsv(340, .5, 1, .92), z=.5)
Text(parent=menu, text='MISION GATITA 3D', origin=(0, 0), position=(.005, .375), scale=3.2,
     color=hsv(345, .8, .5))
Text(parent=menu, text='MISION GATITA 3D', origin=(0, 0), position=(0, .38), scale=3.2, color=BLANCO)
subtitulo = Text(parent=menu, text='Recojan estrellas y corazones, y entren juntas a la casita',
                 origin=(0, 0), position=(0, .24), scale=1.3, color=hsv(0, 0, .2))
info = Text(parent=menu, text='', position=(-.85, .13), scale=1.1, color=hsv(0, 0, .15))
Text(parent=menu, text='CUANTAS JUGADORAS? (o teclas 1 a 4)', origin=(0, 0), position=(.45, .17),
     scale=1.1, color=hsv(345, .8, .5))
botones_n = []

def elegir_jugadores(n):
    crear_jugadoras(n)
    for k, b in enumerate(botones_n):
        b.color = hsv(345, .6, .95) if k + 1 == n else hsv(0, 0, .35)
    if SH:
        try:
            sol.update_bounds(scene)
        except Exception:
            pass

for _i in range(4):
    _b = Button(parent=menu, text=f'{_i + 1} JUGADORA' + ('S' if _i else ''), scale=(.34, .075),
                position=(.45, .09 - _i * .095), color=hsv(0, 0, .35),
                on_click=(lambda i=_i: elegir_jugadores(i + 1)))
    botones_n.append(_b)

def iniciar_juego():
    estado.update(modo='juego', nivel=1, vida=100, cambiando=False, mouse_t=.4, vista=0, zoom=1.0,
                  cam_yaw=0, cam_pitch=32, yaw_obj=0, pitch_obj=32, cam_snap=True)
    estado['partida'] += 1
    for p in jugadoras:
        p.puntos = 0
    menu.enabled = False
    hud.enabled = True
    empezar_nivel(estado['partida'])

boton_jugar = Button(parent=menu, text='JUGAR', color=hsv(345, .6, .95), scale=(.3, .09),
                     position=(-.55, .02), on_click=iniciar_juego)
Button(parent=menu, text='SALIR', color=hsv(0, 0, .35), scale=(.3, .09), position=(-.55, -.10),
       on_click=application.quit)
texto_ctrl = Text(parent=menu, text='', position=(-.85, -.22), scale=1.0, color=hsv(0, 0, .15))
Text(parent=menu, text='MOUSE (MOMO): clic izq = caminar, clic der = saltar  |  C: camara  |  Q/E: girar  |  rueda: zoom',
     origin=(0, 0), position=(0, -.46), scale=1.0, color=hsv(0, 0, .25))

def actualizar_info():
    lineas = [f'Monedas: {prog["monedas"]}     Mejor nivel: {prog["mejor"]}', 'Recompensas:']
    for c, nombre in RECOMPENSAS:
        lineas.append(('  [X] ' if prog['monedas'] >= c else '  [ ] ') + f'{nombre} ({c} monedas)')
    info.text = '\n'.join(lineas)
    texto_ctrl.text = '\n'.join(f'{PERSONAJES[i]["nombre"]}: {TEXTO_CONTROLES[i]}'
                                for i in range(estado['n']))

def mostrar_menu(mensaje=None):
    estado['modo'] = 'menu'
    limpiar_nivel()
    colocar_jugadoras()
    menu.enabled = True
    hud.enabled = False
    aviso.enabled = False
    actualizar_info()
    if mensaje:
        subtitulo.text = mensaje
        boton_jugar.text = 'JUGAR DE NUEVO'

# ------------------------------------------------------------
#  LOGICA DEL JUEGO
# ------------------------------------------------------------
def empezar_nivel(partida):
    if partida != estado['partida'] or estado['modo'] != 'juego':
        return
    limpiar_nivel()
    n = estado['nivel']
    estado.update(cambiando=False, est=0, cor=0, nub=0, meta_e=min(4 + 2 * n, 20),
                  meta_c=min(2 + n, 12), meta_n=min(1 + n // 2, 4))
    aplicar_ambiente(n)
    colocar_jugadoras()
    construir_casita(punto_libre(3.5, 24))
    def lugar():
        p = punto_libre(1.2, 4)
        p.y = 2.6 if random.random() < .25 else 1.0
        return p
    for _ in range(estado['meta_e'] + 2):
        items.append(Item('estrella', lugar()))
    for _ in range(estado['meta_c'] + 1):
        items.append(Item('corazon', lugar()))
    for _ in range(4 + n // 2):
        items.append(Item('moneda', lugar()))
    for _ in range(min(estado['meta_n'] + 1 + n // 3, 7)):
        nubes.append(Nube(punto_libre(1.5, 14), min(1.8 + .25 * n, 4.2)))
    mostrar_aviso(f'NIVEL {n}', 2.5)

def recoger(it, p):
    if it.tipo == 'estrella':
        estado['est'] += 1
        p.puntos += 1
    elif it.tipo == 'corazon':
        estado['cor'] += 1
        p.puntos += 2
        estado['vida'] = min(100, estado['vida'] + 4)
    else:
        p.puntos += 1
        prog['monedas'] += 1
        guardar_progreso()
        revisar_recompensas(prog['monedas'] - 1)
    Audio('kitty_item.wav', auto_destroy=True, volume=.6, pitch=random.uniform(.95, 1.15))
    if it in items:
        items.remove(it)
    destroy(it)

def revisar_recompensas(antes):
    for c, nombre in RECOMPENSAS:
        if antes < c <= prog['monedas']:
            for p in jugadoras:
                p.reconstruir()
            mostrar_aviso(f'RECOMPENSA: {nombre}!', 3.5, hsv(48, .9, 1))

def abrir_casita():
    casita['abierta'] = True
    casita['puerta'].color = hsv(130, .6, .9)
    casita['glow'].enabled = True
    mostrar_aviso('Misiones listas! Vayan juntas a la casita', 3, hsv(130, .7, .8))

def completar_nivel():
    estado['cambiando'] = True
    n = estado['nivel']
    ganadas = 10 + 5 * n + int(estado['vida'] // 10)
    antes = prog['monedas']
    prog['monedas'] += ganadas
    prog['mejor'] = max(prog['mejor'], n + 1)
    guardar_progreso()
    Audio('kitty_victoria.wav', auto_destroy=True, volume=.7)
    mostrar_aviso(f'NIVEL {n} COMPLETADO!  +{ganadas} monedas', 3.2, hsv(48, .9, 1))
    revisar_recompensas(antes)
    estado['nivel'] += 1
    estado['vida'] = min(100, estado['vida'] + 25)
    invoke(empezar_nivel, estado['partida'], delay=3.5)

def terminar_juego():
    mejor = max(jugadoras, key=lambda p: p.puntos)
    msg = f'Fin del juego. Nivel {estado["nivel"]}. Mas puntos: {mejor.cfg["nombre"]} ({mejor.puntos})'
    mostrar_menu(msg)

def atar_jugadoras():
    n = len(jugadoras)
    if n < 2:
        return
    cx = sum(p.x for p in jugadoras) / n
    cz = sum(p.z for p in jugadoras) / n
    for p in jugadoras:
        dx, dz = p.x - cx, p.z - cz
        d = math.hypot(dx, dz)
        if d > 13:
            k = 13 / d
            p.x, p.z = cx + dx * k, cz + dz * k

def mover_camara(dt):
    n = len(jugadoras)
    xs = [p.x for p in jugadoras]
    zs = [p.z for p in jugadoras]
    cx, cz = sum(xs) / n, sum(zs) / n
    sep = max(max(xs) - min(xs), max(zs) - min(zs))
    estado['cam_yaw'] = angulo_suave(estado['cam_yaw'], estado['yaw_obj'], 5 * dt)
    estado['cam_pitch'] = lerp(estado['cam_pitch'], estado['pitch_obj'], min(1, 5 * dt))
    dist = (15 + sep * .8) * estado['zoom']
    y = math.radians(estado['cam_yaw'])
    p = math.radians(estado['cam_pitch'])
    fw = Vec3(math.sin(y), 0, math.cos(y))
    obj = Vec3(cx, 1.1, cz)
    pos = obj - fw * (dist * math.cos(p)) + Vec3(0, dist * math.sin(p), 0)
    if estado['cam_snap']:
        camera.position = pos
        estado['cam_snap'] = False
    else:
        camera.position += (pos - camera.position) * min(1, 8 * dt)
    camera.rotation = Vec3(estado['cam_pitch'], estado['cam_yaw'], 0)

def cambiar_vista():
    estado['vista'] = (estado['vista'] + 1) % len(VISTAS)
    yaw, pitch, nombre = VISTAS[estado['vista']]
    estado['yaw_obj'] = yaw
    estado['pitch_obj'] = pitch
    mostrar_aviso(f'CAMARA: {nombre}', 1.2, hsv(345, .6, 1))

def input(key):
    if estado['modo'] == 'menu':
        if key in ('1', '2', '3', '4'):
            elegir_jugadores(int(key))
            actualizar_info()
        if key in ('enter', 'space'):
            iniciar_juego()
        return
    for p in jugadoras:
        if key == p.teclas[4]:
            p.saltar()
    if key == 'right mouse down' and jugadoras:
        jugadoras[0].saltar()
    if key == 'c':
        cambiar_vista()
    if key == 'scroll up':
        estado['zoom'] = max(.5, estado['zoom'] * .9)
    if key == 'scroll down':
        estado['zoom'] = min(2.2, estado['zoom'] * 1.1)
    if key == 'escape':
        mostrar_menu('Partida en pausa (JUGAR empieza de nuevo)')

def update():
    dt = time.dt
    if estado['modo'] != 'juego':
        estado['orbita'] += dt * .25
        a = estado['orbita']
        r = 4 + len(jugadoras) * 1.6
        camera.position = Vec3(math.sin(a) * r, 2.6, -2 + math.cos(a) * r)
        camera.rotation = Vec3(math.degrees(math.atan2(1.5, r)), math.degrees(a) + 180, 0)
        return
    estado['mouse_t'] -= dt
    estado['yaw_obj'] += (held_keys['e'] - held_keys['q']) * 100 * dt
    atar_jugadoras()
    mover_camara(dt)
    for it in list(items):
        it.t += dt * 3
        it.rotation_y += 120 * dt
        it.y = it.base + math.sin(it.t) * .15
        for p in jugadoras:
            if distance_xz(it.position, p.position) < 1.15 and abs(it.base - (p.y + .9)) < 1.0:
                recoger(it, p)
                break
    if casita['ent'] is not None and not estado['cambiando']:
        if not casita['abierta']:
            if (estado['est'] >= estado['meta_e'] and estado['cor'] >= estado['meta_c']
                    and estado['nub'] >= estado['meta_n']):
                abrir_casita()
        elif all(distance_xz(p.position, casita['pos']) < 4.6 for p in jugadoras):
            completar_nivel()
    if estado['aviso_t'] > 0:
        estado['aviso_t'] -= dt
        if estado['aviso_t'] <= 0:
            aviso.enabled = False
    for i, f in enumerate(filas):
        if i < len(jugadoras):
            f.enabled = True
            poner(f, f'{jugadoras[i].cfg["nombre"]}: {jugadoras[i].puntos} pts')
        else:
            f.enabled = False
    barra_vida.scale_x = max(0.001, .4 * estado['vida'] / 100)
    poner(t_vida, f'VIDA DEL EQUIPO: {max(0, int(estado["vida"]))}')
    poner(t_nivel, f'NIVEL: {estado["nivel"]}')
    poner(t_monedas, f'MONEDAS: {prog["monedas"]}')
    poner(t_mis[0], 'MISIONES')
    poner(t_mis[1], f'Estrellas: {estado["est"]}/{estado["meta_e"]}')
    poner(t_mis[2], f'Corazones: {estado["cor"]}/{estado["meta_c"]}')
    poner(t_mis[3], f'Nubes aplastadas: {estado["nub"]}/{estado["meta_n"]}')
    poner(t_mis[4], 'Casita: ABIERTA, entren juntas' if casita['abierta'] else 'Casita: cerrada')
    if estado['vida'] <= 0:
        terminar_juego()

# ------------------------------------------------------------
#  ARRANQUE
# ------------------------------------------------------------
Audio('kitty_musica.wav', loop=True, autoplay=True, volume=.35)
elegir_jugadores(2)
mostrar_menu()
app.run()
