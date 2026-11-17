import sys
from engine import *

GUY = dict(top=hx('#4F79B0'), outfit='hoodie', hair=hx('#4A3226'), hair_style='curly', glasses='round', pants=hx('#3A3F58'))
N = 70
rnd = random.Random(21)
SALT = [(980+rnd.uniform(-1, 1)*430, 770+rnd.uniform(-1, 1)*150, rnd.uniform(0.55, 1.95)) for _ in range(N)]   # x, y, landing time
STARS = [(rnd.uniform(-100, 2020), rnd.uniform(-720, 240)) for _ in range(N)]                                   # world coords in the sky
C_TABLE = lambda t: camkf(t, [(0, 960, 520, 1.0), (2.4, 975, 600, 1.16), (3.4, 975, 640, 1.3)])
C_SKY = lambda t: camkf(t, [(0, 960, -250, 1.0), (0.5, 960, -230, 1.0), (1.7, 960, 600, 1.0), (2.2, 960, 640, 1.25), (3.4, 960, 640, 1.5)])

# ---------------------------------------------------------------- scene 1: kitchen table, a hand sprinkles salt
def table(c, t, grains=True):
    C = C_TABLE(t); c.save(); cam(c, C)
    c.rectangle(-2400, -600, W+4800, 1000); fill(c, hx('#CFE0D8'))                       # tiled wall
    for xx in range(-2400, W+2400, 150):
        for yy in range(-600, 400, 150): rrect(c, xx+6, yy+6, 138, 138, 10); stroke(c, 4, hx('#9DB8AE'))
    R(c, 150, 60, 420, 30, 6, hx('#7A5235'))
    for i, col in enumerate(('#C9584C', '#E0B04A', '#5E8C61', '#4F79B0')): R(c, 190+i*90, -40, 64, 100, 10, hx(col)); R(c, 200+i*90, -62, 44, 26, 6, hx('#3B2A22'), 5)
    for i in range(3): line(c, 1500+i*90, -200, 1500+i*90, 40, 6); E(c, 1500+i*90, 110, 34+i*8, 70+i*10, hx('#9AA3AE'))       # hanging ladles
    c.rectangle(-2400, 380, W+4800, 1400); fill(c, hx('#5A3A26')); line(c, -2400, 380, W+2400, 380, 8)                          # walnut table
    for yy in (560, 760, 960): line(c, -2400, yy, W+2400, yy, 4, INK, 0.35)
    for i in range(40): x = -400+i*83 % 2700; y = 420+(i*137) % 620; line(c, x, y, x+120, y+6, 3, hx('#3B2618'), 0.5)
    R(c, 130, 620, 520, 330, 26, hx('#C99A62')); E(c, 200, 690, 18, 18, hx('#5A3A26'), 5)                                       # cutting board
    for i in range(4): E(c, 330+i*70, 790-i*8, 62, 56, hx('#D8574A')); E(c, 330+i*70, 790-i*8, 40, 36, hx('#F08A7A'), 3)
    P_(c, [(250, 880), (600, 840), (610, 862), (255, 904)], hx('#D9D4C7')); R(c, 150, 872, 110, 36, 10, hx('#2B2730'))          # knife
    soft_shadow(c, 1540, 880, 250, 700); E(c, 1540, 800, 240, 110, hx('#F6EFDD')); E(c, 1540, 786, 196, 84, hx('#E39A4E')); E(c, 1480, 776, 50, 22, hx('#F7C76B'), 3)   # soup bowl
    for i, dx in enumerate((-40, 30)):
        c.move_to(1540+dx, 720)
        for k in range(1, 8): c.line_to(1540+dx+14*math.sin(k*0.9+t*3+i*2)*(k/7), 720-k*22)
        stroke(c, 7, (1, 1, 1), 0.4)
    soft_shadow(c, 1250, 600, 70, 700); R(c, 1200, 440, 100, 160, 22, hx('#EDE6D6')); R(c, 1206, 410, 88, 44, 14, hx('#9AA3AE')); text(c, 'S', 1250, 530, 54, INK)   # salt shaker
    soft_shadow(c, 1400, 560, 60, 700); R(c, 1360, 380, 80, 180, 24, hx('#3B2A22')); E(c, 1400, 372, 30, 24, hx('#5A3A26'))        # pepper mill
    if grains:
        for x, y, tl in SALT:
            k = pr(t, tl-0.42, tl)
            if k <= 0: continue
            gx = lerp(985+12*math.sin(tl*40), x, eout(k)); gy = lerp(470, y, ein(k))
            if k >= 1: ell(c, x+3, y+3, 5, 3); fill(c, (0, 0, 0), 0.35)
            ell(c, gx, gy, 5, 5 if k >= 1 else 8); fill(c, (1, 1, 1))
    hk = eout(pr(t, 0.05, 0.5)); shake_ = 14*math.sin(t*26)*pr(t, 0.5, 0.7)*(1-pr(t, 1.9, 2.1))
    big_hand(c, 985+shake_, lerp(-260, 300, hk)+6*math.sin(t*26), 1.0, -PI/2, curl=0.35, pinch=1.0, sleeve=hx('#4F79B0'))
    lightmap(c, (0.46, 0.40, 0.44), [(820, 430, 1250, (1.0, 0.9, 0.72), 1.0), (1540, 780, 420, (1.0, 0.75, 0.4), 0.35)])
    bloom(c, 820, 300, 700, (1, 0.85, 0.55), 0.10)
    c.restore(); return C

# ---------------------------------------------------------------- scene 2: night sky -> tilt down to the building
def sky(c, t, stars=True, extra=1.0):
    C = C_SKY(t); c.save(); cam(c, C)
    g = cairo.LinearGradient(0, -900, 0, 1000)
    for o, col in ((0, '#0B1030'), (0.5, '#1B2A5E'), (0.8, '#4A3F7A'), (1, '#8A5A8C')): g.add_color_stop_rgb(o, *hx(col))
    c.rectangle(-2400, -1600, W+4800, 3400); c.set_source(g); c.fill()
    for i in range(160):                                                                # faint background stars
        r_ = random.Random(i); x, y = r_.uniform(-300, 2220), r_.uniform(-900, 380)
        ell(c, x, y, 1.6, 1.6); fill(c, (1, 1, 1), extra*(0.35+0.3*math.sin(t*3+i)))
    if stars:
        for i, (x, y) in enumerate(STARS):
            r = 3*(1+0.25*math.sin(t*7+x)); ell(c, x, y, r, r); fill(c, (1, 1, 0.92)); bloom(c, x, y, 16, (0.8, 0.85, 1), 0.25)
    bloom(c, 1500, -420, 420, (0.75, 0.8, 1.0), 0.28); E(c, 1500, -420, 110, 110, hx('#F4F1DC'))
    for mx, my, mr in ((1460, -450, 22), (1540, -400, 30), (1500, -350, 14)): ell(c, mx, my, mr, mr); fill(c, hx('#D9D4B8'))
    for i, (cx_, cy_, s) in enumerate(((300, -60, 1.2), (1250, 60, 1.0), (1900, -160, 0.8))):
        for dx, dy, r in ((0, 0, 60), (70, -24, 76), (150, 0, 58), (76, 20, 70)): ell(c, cx_+t*12+dx*s, cy_+dy*s, r*s*1.3, r*s*0.6); fill(c, hx('#2A3466'), 0.85)
    r_ = random.Random(3); x = -500                                                      # far skyline
    while x < 2500:
        w = r_.randint(110, 200); h = r_.randint(250, 520); c.rectangle(x, 1010-h, w, h); fill(c, hx('#161A3A'))
        for yy in range(1010-h+20, 990, 40):
            for xx in range(x+16, x+w-20, 34):
                if r_.random() < 0.3: c.rectangle(xx, yy, 14, 20); fill(c, hx('#F7C76B'), 0.9)
        x += w+8
    R(c, 520, 280, 880, 760, 6, hx('#7A4638'), 8)                                        # brick apartment block
    for yy in range(300, 1030, 34):
        for xx in range(530+(17 if (yy//34) % 2 else 0), 1390, 68): line(c, xx, yy, xx+40, yy, 3, hx('#5A2F26'), 0.7)
    R(c, 500, 250, 920, 40, 6, hx('#4A2A22'), 7); R(c, 1290, 170, 60, 86, 4, hx('#4A2A22'), 6)
    for row in range(3):
        for col in range(3):
            wx, wy = 580+col*280, 340+row*250; lit = (row, col) in ((1, 1), (0, 2), (2, 0))
            R(c, wx, wy, 200, 170, 4, hx('#FFD98A') if lit else hx('#1E2748'), 7)
            if lit and (row, col) != (1, 1): ell(c, wx+100, wy+120, 34, 34); fill(c, hx('#B8834F')); ell(c, wx+100, wy+170, 56, 44); fill(c, hx('#B8834F'))
            line(c, wx+100, wy, wx+100, wy+170, 6, hx('#3B2A22')); line(c, wx, wy+85, wx+200, wy+85, 6, hx('#3B2A22'))
            R(c, wx-14, wy+170, 228, 18, 4, hx('#D9D4C7'), 5)
            if lit: bloom(c, wx+100, wy+85, 240, (1, 0.8, 0.4), 0.30)
            if (row, col) == (2, 1): R(c, wx+20, wy+110, 160, 60, 6, hx('#9AA3AE'), 5)
    line(c, 1410, 290, 1410, 1040, 12, hx('#3B3F4A'))
    c.rectangle(-2400, 1040, W+4800, 600); fill(c, hx('#2E2742')); line(c, -2400, 1040, W+2400, 1040, 8)
    line(c, 300, 560, 300, 1040, 14, hx('#1E1A2A')); P_(c, [(250, 540), (350, 540), (336, 570), (264, 570)], hx('#1E1A2A'), 4)   # street lamp
    lightmap(c, (0.42, 0.44, 0.66), [(300, 600, 620, (1.0, 0.85, 0.55), 1.0), (960, 550, 520, (1, 0.9, 0.7), 0.75), (1500, -420, 900, (0.8, 0.85, 1), 0.6),
                                      (960, -300, 1500, (0.7, 0.75, 1), 0.55)])
    bloom(c, 300, 575, 150, (1, 0.9, 0.6), 0.6); light_shaft(c, 300, 575, 60, 300, 1040, 520, a=0.16)
    c.restore(); return C

# ---------------------------------------------------------------- scene 3: the room behind the window
def room(c, t):
    C = camkf(t, [(0, 960, 540, 1.0), (1.5, 1010, 540, 1.08), (3.7, 1120, 520, 1.3)])
    c.save(); cam(c, C)
    set_room(c, t, wall=hx('#D9A877'))
    window(c, 200, 150, 440, 370, t, night=True, curtains=hx('#C9584C'))
    frame_pic(c, 760, 150, 200, 150, 1); frame_pic(c, 1000, 210, 130, 170, 2); wall_clock(c, 1230, 200, 64, t)
    bookshelf(c, 1380, 300, 420, 1); rug(c, 940, 950, 620, 86)
    tv(c, 1420, 860, t); plant(c, 110, 880, 1.0, t); floor_lamp(c, 1850, 870, t, on=True); sofa(c, 620, 860)
    R(c, 1240, 770, 120, 16, 4, hx('#7A5235'), 5); line(c, 1300, 786, 1300, 860, 9); E(c, 1300, 862, 44, 9, hx('#5A3A26'), 5); mug(c, 1300, 770, 0.7, t)
    light_shaft(c, 420, 520, 440, 760, 1000, 760, (0.7, 0.8, 1.0), 0.13)                 # moonlight through the window
    wave, pt, th = spring(pr(t, 0.7, 1.2))*(1-pr(t, 1.5, 1.8)), spring(pr(t, 1.7, 2.2))*(1-pr(t, 2.7, 3.0)), spring(pr(t, 2.9, 3.4))
    hr = (lerp(lerp(62, 170, wave), 205, pt), lerp(lerp(-226, -470, wave), -330, pt)+(10*math.sin(t*16) if wave > 0.5 else 0))
    hl = (lerp(-60, -150, th), lerp(-180, -400, th))
    P = dict(GUY, legs='sit', light=0.8, t=t, turn=0.5*pt, eyes='closed' if th > 0.5 else 'dot', look=(8*pt, 0), brow='up' if (wave > 0.3 or pt > 0.3) else None,
             mouth='grin' if th > 0.5 else ('talk' if (pt > 0.5 and int(t*9) % 2) else 'smile'), blink=blinking(t, (0.4, 2.55)), bob=2*math.sin(t*2.4)-8*math.sin(PI*pr(t, 2.9, 3.2)),
             hands=(hl, hr), bends=(-1, 1), hand_pose=('thumb' if th > 0.3 else 'fist', 'point' if pt > 0.3 else ('open' if wave > 0.2 else 'fist')))
    soft_shadow(c, 880, 868, 120, 1850); character(c, 880, 868, 0.86, P)
    lightmap(c, (0.40, 0.38, 0.58), [(1850, 330, 1500, (1.0, 0.86, 0.6), 1.0), (1585, 640, 700, (0.6, 0.78, 1.0), 0.6), (420, 520, 700, (0.7, 0.8, 1.0), 0.45)])
    bloom(c, 1850, 330, 260, (1, 0.88, 0.6), 0.5); bloom(c, 1585, 640, 300, (0.5, 0.7, 1.0), 0.22+0.05*math.sin(t*20))
    pop_label(c, '+12%', 1585, 420, pr(t, 2.2, 2.45), hx('#8FE39A'), 110, -0.06, t); burst(c, 1585, 420, pr(t, 2.2, 2.6), 150, 230, 10, 6, hx('#EFFFF0'))
    c.restore(); grade(c, (1, 0.8, 0.5), 0.10)

# ---------------------------------------------------------------- timeline
T1, T2 = 2.4, 5.8                                             # start of the two transitions (1.0 s and 1.2 s long)
def shot_table(c, t): table(c, t)
def cut_salt_to_stars(c, t):                                  # particle match cut: salt grains fly up and become the stars
    k = t/1.0; Ca = C_TABLE(T1+t); Cb = C_SKY(0)
    xfade(c, pr(k, 0.15, 0.85), lambda c: table(c, T1+t, grains=False), lambda c: sky(c, 0, stars=False, extra=pr(k, 0.5, 1)))
    morph_points(c, k, [to_screen(Ca, x, y) for x, y, _ in SALT], [to_screen(Cb, x, y) for x, y in STARS], 5*Ca[2], 3, arc=140, t=t, twinkle=0.5)
def shot_sky(c, t): sky(c, t)
def cut_through_window(c, t):                                 # camera flies through the lit window into the room
    k = t/1.2; Cs = C_SKY(2.4+t*0.3)
    push_through(c, k, lambda c: sky(c, 2.4+t*0.3), lambda c: room(c, 0), to_screen(Cs, 960, 675))
def shot_room(c, t): room(c, t)

SHOTS = [(0.0, shot_table), (T1, cut_salt_to_stars), (3.4, shot_sky), (T2, cut_through_window), (7.0, shot_room)]
render(SHOTS, 10.8, sys.argv[1:])
