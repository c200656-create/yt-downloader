import sys
from engine import *

BOSS = dict(top=hx('#5B5F6E'), top2=hx('#A8423A'), outfit='suit', hair=hx('#2B2730'), hair_style='sidepart', glasses='rect',
            mustache=True, skin=hx('#E9B98A'), pants=hx('#2E3040'))
GUY = dict(top=hx('#4F79B0'), outfit='hoodie', hair=hx('#4A3226'), hair_style='curly', glasses='round', pants=hx('#3A3F58'))
GIRL = dict(top=hx('#EDE6D6'), top2=hx('#2F6F5E'), outfit='apron', hair=hx('#7A3B2E'), hair_style='bun', skin=hx('#E9B98A'), pants=hx('#4A3F5A'))

# ---------------------------------------------------------------- A: back room, swinging lamp - every shadow moves with it
C_A = lambda t: camkf(t, [(0, 960, 560, 1.04), (3.4, 985, 520, 1.22)])
def boss_P(t, lamp_x):
    hy = kf(t, [(0, 0.0), (1.5, 0.0), (1.85, 1.0), (2.6, 1.0), (3.0, 0.0)], eio)          # turns his head to the door and back
    pt = spring(pr(t, 0.55, 0.95))*(1-pr(t, 1.3, 1.55))                                   # points at the money
    return dict(BOSS, legs=False, t=t, yaw=0.3*hy, head_yaw=clamp(hy+0.12*math.sin(t*1.8), -1, 1), light=clamp((lamp_x-960)/120, -1, 1),
                eyes='wide' if 1.85 < t < 2.6 else 'half', brow='up' if 1.85 < t < 2.6 else 'smug', mouth='o' if 1.85 < t < 2.6 else 'smirk',
                look=(6, 0) if 1.85 < t < 2.6 else (-4*pt, 6*pt), blink=blinking(t, (0.4, 3.2)),
                hands=((-34, -252), (lerp(34, -150, pt), lerp(-252, -300, pt))), bends=(-1, 1), hand_pose=('flat', 'point' if pt > 0.3 else 'flat'))
def room_A(c, t):
    C = C_A(t); ang = 0.30*math.sin(t*1.8+0.6); c.save(); cam(c, C)
    set_room(c, t, wall=hx('#6E7A84'), floor=hx('#3B2E2A'), fy=760)
    frame_pic(c, 230, 170, 230, 170, 1); wall_clock(c, 1640, 210, 66, t); bookshelf(c, 90, 440, 330, 2, seed=8)
    bx, by = 960+math.sin(ang)*374, -200+math.cos(ang)*374                                  # bulb position (pendant_lamp returns the same)
    P = boss_P(t, bx)
    wall_shadow(c, lambda cc: character(cc, 960, 820, 1.0, P), (bx, by), k=1.32, a=0.34, clip=(-2400, -600, W+4800, 1360))
    safe_front = lambda cc, X, Y, Wd, Ht: (E(cc, X+Wd/2, Y+Ht/2, 44, 44, hx('#9AA3AE'), 5), line(cc, X+Wd/2, Y+Ht/2, X+Wd/2+30*math.cos(t), Y+Ht/2+30*math.sin(t), 5))
    box3d(c, 1560, 540, 220, 220, 70, hx('#3F454E'), vp=(960, -900), front=safe_front)
    character(c, 960, 820, 1.0, P)
    tbl = lambda cc, X, Y, Wd, Ht: [line(cc, X+40, Y+30+i*110, X+Wd-40, Y+30+i*110, 4, INK, 0.4) for i in range(3)]
    box3d(c, 330, 700, 1260, 380, 120, hx('#5A3A26'), vp=(960, -900), front=tbl, top_col=hx('#6E4A32'))
    ao(c, 330, 1590, 700, 0, 40, 0.35)
    items = [(lambda cc: money_stack(cc, 700, 680, 5, 0.9), 700, 680), (lambda cc: money_stack(cc, 860, 668, 3, 0.9), 860, 668),
             (lambda cc: box3d(cc, 1090, 600, 250, 76, 50, hx('#2B2730'), vp=(960, -900), front=lambda c2, X, Y, Wd, Ht: R(c2, X+Wd/2-40, Y-14, 80, 18, 6, hx('#9AA3AE'), 4)), 1215, 676),
             (lambda cc: mug(cc, 1420, 684, 1.2, t, steam=False), 1420, 684)]
    for fn, x0, fy in items: object_shadow(c, fn, x0, fy, (bx, by), a=0.5, blur=5, squash=0.45, fade_h=260)
    for fn, x0, fy in items: fn(c)
    smoke(c, t, 1420, 600, 'steam', rate=10, life=2.2, rise=230, spread=22, size=20, wind=12, a=0.5, seed=4)
    pendant_lamp(c, 960, -200, 330, ang, cone=0.16)
    lightmap(c, (0.22, 0.22, 0.30), [(bx, by+160, 1150, (1.0, 0.86, 0.62), 1.25), (-200, 300, 900, (0.5, 0.6, 1.0), 0.25)])
    bloom(c, bx, by, 220, (1, 0.9, 0.6), 0.55); motes(c, t, bx-260, by+40, 520, 520, 24)
    pop_label(c, '$2.4M', 540, 520, pr(t, 0.75, 1.0), hx('#FFD54A'), 110, -0.08, t)
    c.restore()
    c.save(); cam(c, C, depth=1.5); soft(c, lambda cc: (R(cc, -260, 860, 520, 700, 90, hx('#1E1A22')), R(cc, -240, 760, 480, 160, 60, hx('#1E1A22'))), 8); c.restore()
    tag(c, 'BACK ROOM, 2:00 AM', 60, 64, pr(t, 0.2, 0.7)); return C

# ---------------------------------------------------------------- B: kitchen, two people in profile, kettle + burning toast
C_B = lambda t: camkf(t, [(0, 880, 560, 1.12), (2.8, 1050, 545, 1.2)])
WIN_B = (1010, 270)
def kettle(c, x, y, col=hx('#C9584C')):
    P_(c, [(x+52, y-60), (x+108, y-112), (x+116, y-100), (x+66, y-36)], shade(col, 0.9), 5)              # spout
    c.new_sub_path(); c.arc(x, y-110, 58, PI*1.1, PI*1.9); stroke(c, 16); c.new_sub_path(); c.arc(x, y-110, 58, PI*1.1, PI*1.9); stroke(c, 8, hx('#2B2730'))
    cyl3d(c, x, y, 70, 100, col, tilt=0.26, lw=6); E(c, x, y-108, 16, 8, hx('#2B2730'), 4)
def kitchen_B(c, t):
    C = C_B(t); c.save(); cam(c, C)
    set_room(c, t, wall=hx('#EBC9A0'), floor=hx('#8A6A50'), fy=880)
    window(c, 820, 110, 380, 300, t, night=False, curtains=hx('#5E8C61'))
    handles = lambda cc, X, Y, Wd, Ht: (line(cc, X+Wd/2, Y+8, X+Wd/2, Y+Ht-8, 3, INK, 0.5), R(cc, X+Wd/2-30, Y+Ht-36, 18, 10, 4, hx('#9AA3AE'), 3), R(cc, X+Wd/2+12, Y+Ht-36, 18, 10, 4, hx('#9AA3AE'), 3))
    for i in range(3): box3d(c, 90+i*230, 100, 210, 200, 40, hx('#CFE0D8'), vp=(960, 600), front=handles)
    for i in range(3): box3d(c, 1300+i*230, 100, 210, 200, 40, hx('#CFE0D8'), vp=(960, 600), front=handles)
    drawers = lambda cc, X, Y, Wd, Ht: [(rrect(cc, X+20+k*215, Y+24, 190, Ht-48, 6), stroke(cc, 4, INK, 0.5), R(cc, X+95+k*215, Y+40, 40, 10, 4, hx('#D9D4C7'), 3)) for k in range(int(Wd//215))]
    box3d(c, 100, 640, 1720, 240, 60, hx('#5E8C61'), vp=(960, 300), front=drawers, top_col=hx('#ECE7DD'))
    ao(c, 100, 1820, 640, 0, 30, 0.25)
    whistle = 0.9 < t < 1.7
    items = [(lambda cc: kettle(cc, 600, 625), 600, 625), (lambda cc: box3d(cc, 1180, 540, 170, 86, 50, hx('#BFC6CC'), vp=(960, 300),
             front=lambda c2, X, Y, Wd, Ht: R(c2, X+Wd-34, Y+30, 18, 30, 4, hx('#2B2730'), 3)), 1265, 626),
             (lambda cc: cyl3d(cc, 1520, 626, 40, 92, hx('#E0B04A'), top_col=hx('#C99A62')), 1520, 626),
             (lambda cc: plant(cc, 300, 628, 0.55, t), 300, 628)]
    for fn, x0, fy in items: object_shadow(c, fn, x0, fy, WIN_B, a=0.32, blur=6, squash=0.3, fade_h=200)
    for fn, x0, fy in items: fn(c)
    for k in (0, 1): R(c, 1230+k*40, 530, 18, 14, 3, hx('#7A4E33'), 3)                     # burnt toast in the slots
    smoke(c, t, 1265, 520, 'dark', style='toon', rate=9, life=1.8, rise=320, spread=40, size=26, wind=70, start=0.8, seed=6)
    smoke(c, t, 712, 505, 'steam', rate=12, life=1.6, rise=160, spread=20, size=18, wind=30, a=0.45, seed=2)
    smoke(c, t, 712, 505, 'steam', rate=38, life=1.4, rise=420, spread=60, size=40, wind=160, a=0.6, start=0.9, stop=1.7, seed=3)
    g = spring(pr(t, 0.2, 0.55))*(1-pr(t, 2.0, 2.3)); talk = 'talk' if (t < 2.0 and int(t*9) % 2) else 'smile'
    PG = dict(GUY, yaw=1.0, t=t, light=0.4, mouth=talk if t < 1.0 else 'o', eyes='dot' if t < 1.0 else 'wide', brow='up',
              hands=((lerp(70, 190, g), lerp(-160, -330, g)), (80, -170)), bends=(1, 1), hand_pose=('open', 'fist'), blink=blinking(t, (0.6,)))
    hy = lerp(-1, 0, spring(pr(t, 1.55, 1.95)))                                             # she turns her head to camera: deadpan
    PW = dict(GIRL, yaw=-1.0, head_yaw=hy, t=t, light=-0.3, eyes='half', mouth='flat', brow='flat', blink=blinking(t, (2.35,)),
              hands=((-70, -210), (-130, -230)), bends=(-1, -1), hand_pose=('grip', 'grip'),
              held=lambda cc: mug(cc, -110, -205, 0.8, t, steam=False, col=hx('#C9584C')))
    for x0, PP in ((430, PG), (1540, PW)):
        object_shadow(c, lambda cc: character(cc, x0, 1010, 0.98, PP), x0, 1010, WIN_B, a=0.34, blur=6, squash=0.3)
        soft_shadow(c, x0, 1010, 90, WIN_B[0], 0.35)
    character(c, 430, 1010, 0.98, PG); character(c, 1540, 1010, 0.98, PW)
    light_shaft(c, 1010, 420, 380, 1010, 1100, 900, (1, 0.97, 0.85), 0.12)
    lightmap(c, (0.80, 0.78, 0.82), [(1010, 300, 1300, (1, 0.97, 0.88), 0.3)])
    burst(c, 712, 470, pr(t, 0.9, 1.3), 60, 140, 10, 6)
    c.restore()
    c.save(); cam(c, C, depth=1.6); soft(c, lambda cc: plant(cc, 1960, 1330, 2.3, t), 8); c.restore()
    tag(c, 'MONDAY, 8:15 AM', 60, 64, pr(t, 0.1, 0.6)); return C

# ---------------------------------------------------------------- C: dusk street, burning cash, 3D buildings, long fire shadow
C_C = lambda t: camkf(t, [(0, 1050, 380, 1.12), (1.5, 960, 560, 1.0), (2.8, 900, 640, 1.2)])
SUN = (1250, 330)
def street_C(c, t):
    C = C_C(t); c.save(); cam(c, C)
    g = cairo.LinearGradient(0, -400, 0, 900)
    for o, col in ((0, '#2B2350'), (0.45, '#6A3B77'), (0.75, '#D0596B'), (1, '#F4A35E')): g.add_color_stop_rgb(o, *hx(col))
    c.rectangle(-2400, -1200, W+4800, 3000); c.set_source(g); c.fill()
    bloom(c, *SUN, 520, (1, 0.75, 0.45), 0.45); E(c, *SUN, 120, 120, hx('#FFD9A0'), 0)
    c.restore()
    c.save(); cam(c, C, depth=0.55)                                                          # far factory layer: slower parallax
    for i, (fx, fh) in enumerate(((100, 300), (520, 380), (1500, 340), (1900, 260))):
        c.rectangle(fx, 900-fh, 360, fh+300); fill(c, hx('#4A3560'))
        cyl3d(c, fx+120, 900-fh, 34, 220, hx('#3E2D52'), lw=0)
        smoke(c, t+i*0.7, fx+120, 900-fh-220, 'smoke', rate=8, life=4, rise=320, spread=50, size=40, wind=260, a=0.4, seed=10+i)
    c.restore(); haze(c, (0.96, 0.62, 0.55), 0.14)
    c.save(); cam(c, C)
    def facade(cc, X, Y, Wd, Ht):
        for r in range(int(Ht//150)):
            for k in range(int(Wd//150)):
                lit = (r*7+k*3) % 5 == 0; R(cc, X+40+k*150, Y+40+r*150, 80, 100, 4, hx('#FFD98A') if lit else hx('#2C2440'), 4)
    box3d(c, -520, 140, 760, 820, 260, hx('#7A4638'), vp=(960, 560), front=facade)
    box3d(c, 1700, 200, 700, 760, 260, hx('#5E4A6E'), vp=(960, 560), front=facade)
    poly(c, [(-2400, 960), (W+2400, 960), (W+2400, 2000), (-2400, 2000)]); fill(c, hx('#6A5E78'))
    for k in range(-6, 7): line(c, 960+k*60, 980, 960+k*420, 1600, 4, INK, 0.25)
    line(c, -2400, 960, W+2400, 960, 7)
    ao(c, -2400, W+2400, 960, 50, 40, 0.3)
    fire_l = (960, 760); fl = 1.2+0.12*math.sin(t*17)+0.08*math.sin(t*7)
    PG = dict(GUY, yaw=0.55, t=t, light=1, rim=(1, 0.6, 0.3), eyes='half', brow='worry', mouth='frown', head_tilt=0.06,
              hands=((150, -230), (200, -180)), bends=(1, 1), hand_pose=('open', 'open'), blink=blinking(t, (1.1,)), bob=2*math.sin(t*2))
    object_shadow(c, lambda cc: character(cc, 640, 980, 1.0, PG), 640, 980, fire_l, a=0.5, blur=5, squash=0.35, fade_h=520)
    object_shadow(c, lambda cc: cyl3d(cc, 960, 980, 85, 180, hx('#7A4A35')), 960, 980, (960, 400), a=0.3)
    soft_shadow(c, 640, 980, 90, 960, 0.4)
    cyl3d(c, 960, 980, 85, 180, hx('#7A4A35'), lt=0.2)
    for k in (0.3, 0.55, 0.8): c.save(); c.translate(960, 980-180*k); c.scale(85, 22); c.new_sub_path(); c.arc_negative(0, 0, 1, PI, 0); c.restore(); stroke(c, 4, INK, 0.5)
    character(c, 640, 980, 1.0, PG)
    for j, t0 in enumerate((0.2, 0.8, 1.4, 2.0)):                                            # banknotes flutter into the fire and burn
        u = pr(t, t0, t0+0.9)
        if 0 < u < 1:
            bx = lerp(700+j*120, 960+(j-1.5)*30, eio(u))+60*math.sin(u*9+j); byy = lerp(250, 780, u*u)
            bill(c, bx, byy, math.sin(u*7+j)*0.8, 0.8*(1-pr(u, 0.85, 1)))
        sparks(c, t, 960, 790, t0+0.9, n=18, speed=520, seed=j)
    fire(c, t, 960, 800, 130, 230, seed=2)
    smoke(c, t, 960, 600, 'fire', rate=14, life=3.0, rise=640, spread=90, size=60, wind=180, seed=5)
    lightmap(c, (0.38, 0.32, 0.48), [(fire_l[0], fire_l[1], 1150, (1, 0.62, 0.32), fl), (SUN[0], SUN[1], 1300, (1, 0.7, 0.5), 0.55)])
    bloom(c, 960, 720, 260, (1, 0.6, 0.25), 0.35)
    pop_label(c, '-$2,400', 1330, 640, pr(t, 1.7, 1.95), hx('#F0564A'), 110, 0.06, t)
    c.restore(); grade(c, (1, 0.72, 0.45), 0.12); return C

# ---------------------------------------------------------------- timeline: smoke wipe A->B, shape match kettle lid -> sun B->C
def tA(c, t): room_A(c, t)
def tAB(c, t): smoke_wipe(c, t/1.0, lambda c: room_A(c, 3.4+t), lambda c: kitchen_B(c, 0), col=(0.92, 0.92, 0.95))
def tB(c, t): kitchen_B(c, t)
def tBC(c, t):
    Cb, Cc = C_B(2.8), C_C(0); (ax, ay), (sx, sy) = to_screen(Cb, 600, 517), to_screen(Cc, *SUN)
    match_zoom(c, t/1.0, lambda c: kitchen_B(c, 2.8+t*0.2), lambda c: street_C(c, 0), (ax, ay, 70*Cb[2]), (sx, sy, 120*Cc[2]))
def tC(c, t): street_C(c, t)
SHOTS = [(0.0, tA), (3.4, tAB), (4.4, tB), (7.2, tBC), (8.2, tC)]
render(SHOTS, 11.0, sys.argv[1:])
