import sys
from engine import *

GUY = dict(top=hx('#4F79B0'), outfit='hoodie', hair=hx('#4A3226'), hair_style='curly', glasses='round', pants=hx('#3A3F58'))
LORD = dict(top=hx('#5B5F6E'), top2=hx('#A8423A'), outfit='suit', hair=hx('#2B2730'), hair_style='sidepart', glasses='rect',
            mustache=True, skin=hx('#E9B98A'), pants=hx('#2E3040'))

def small_phone(c, x, y, lit=1.0):
    R(c, x-24, y-44, 48, 88, 9, hx('#1F1D24'), 5); R(c, x-17, y-34, 34, 66, 4, shade(hx('#BFE3FF'), lit), 2)

def living_room(c, t, C):                 # декорация: 14 предметов, 6 из них двигаются
    c.save(); cam(c, C)
    set_room(c, t)
    window(c, 200, 150, 440, 370, t, night=False)
    glow(c, 520, 880, 420, 90, (1, 1, 1), 0.10)
    frame_pic(c, 760, 150, 200, 150, 1); frame_pic(c, 1000, 210, 130, 170, 2)
    wall_clock(c, 1230, 200, 64, t)
    bookshelf(c, 1380, 300, 420, 1)
    R(c, 1560, 196, 60, 104, 4, hx('#F6EFDD'), 4); text(c, '17', 1590, 262, 40, hx('#D8574A')); c.rectangle(1560, 196, 60, 26); fs(c, hx('#D8574A'), 4)
    rug(c, 940, 950, 620, 86)
    tv(c, 1420, 860, t)
    plant(c, 110, 880, 1.0, t)
    floor_lamp(c, 1850, 870, t, on=False)
    sofa(c, 620, 860)
    R(c, 1240, 770, 120, 16, 4, hx('#7A5235'), 5); line(c, 1300, 786, 1300, 860, 9); E(c, 1300, 862, 44, 9, hx('#5A3A26'), 5); mug(c, 1300, 770, 0.7, t)
    motes(c, t, 240, 200, 420, 600)
    c.restore()

def shot1(c, t):   # отъезд: окно крупно -> вся комната; на 1.95 с приходит уведомление
    C = camkf(t, [(0, 470, 360, 1.9), (1.7, 960, 545, 1.0), (2.8, 975, 560, 1.07)])
    living_room(c, t, C)
    c.save(); cam(c, C)
    ding = t > 1.95
    P = dict(GUY, legs='sit', eyes='wide' if ding else 'half', look=(4, 8), mouth='o' if ding else 'flat', brow='up' if ding else None,
             head_tilt=0.06*(1-pr(t, 1.95, 2.1)), blink=blinking(t, (0.9,)), bob=2*math.sin(t*2.4)-10*math.sin(PI*pr(t, 1.95, 2.25)),
             held=lambda cc: small_phone(cc, 30, -236, 1.4 if ding else 0.8), hands=((-10, -210), (62, -226)), bends=(-46, 40))
    character(c, 880, 868, 0.86, P)
    burst(c, 906, 666, pr(t, 1.95, 2.4), 60, 120, 8, 6, hx('#FFE28A'))
    c.restore()
    c.save(); cam(c, C, depth=1.6)        # размытый лист на переднем плане = глубина
    soft(c, lambda cc: plant(cc, -140, 1420, 2.4, t), 8); c.restore()
    tag(c, 'PAYDAY, 9:00 AM', 60, 64, pr(t, 1.2, 1.7))

def shot3(c, t):   # через плечо: арендодатель в дверях, наезд, в конце whip
    wk = eio(pr(t, 1.62, 1.8))
    C = camkf(t, [(0, 960, 540, 1.0), (1.7, 1180, 450, 1.38)]); C = (C[0]+900*wk, C[1], C[2])
    c.save(); cam(c, C)
    set_room(c, t, wall=hx('#D9A877'))
    frame_pic(c, 300, 180, 220, 160, 0); frame_pic(c, 560, 230, 120, 150, 2)
    line(c, 760, 250, 760, 800, 10, hx('#3B2A22')); E(c, 760, 804, 60, 12, hx('#3B2A22'), 5)      # вешалка с курткой
    for sg in (-1, 1): line(c, 760, 290, 760+sg*46, 256, 8, hx('#3B2A22'))
    P_(c, [(760, 290), (826, 330), (812, 520), (748, 520)], hx('#C9584C'), 6)
    plant(c, 1620, 820, 0.8, t); wall_clock(c, 1640, 230, 54, t)
    R(c, 1020, 806, 400, 34, 8, hx('#6F9E7A'), 5); text(c, 'HOME', 1220, 824, 22, INK)
    ok = eout(pr(t, 0.05, 0.45))
    door(c, 1050, 800, 340, 640, ok)
    c.save(); c.rectangle(1050+340*(1-0.82*ok), 160, 340, 640); c.clip()                          # персонаж обрезан проёмом
    glow(c, 1300, 300, 150, 200, hx('#FFD98A'), 0.25); R(c, 1280, 230, 40, 60, 8, hx('#FBE7B0'), 4)
    def clipboard(cc):
        R(cc, -70, -290, 120, 150, 6, hx('#B8834F'), 5); R(cc, -60, -272, 100, 124, 3, hx('#F6EFDD'), 3)
        text(cc, 'RENT', -10, -236, 30, hx('#A8423A')); R(cc, -34, -300, 48, 18, 4, hx('#9AA3AE'), 3)
        for i in range(3): line(cc, -48, -206+i*18, 28, -206+i*18, 3, INK, 0.6)
    P = dict(LORD, eyes='half', mouth='flat', brow='flat', look=(-8, 2), blink=blinking(t, (1.2,)), bob=2*math.sin(t*2), held=clipboard,
             hands=((-76, -196), (lerp(108, 150, ok), lerp(-150, -250, back(pr(t, 0.5, 0.8))))), bends=(-30, -36))
    cast_shadow(c, 1250, 800, 90); character(c, 1250, 800, 0.9, P)
    c.restore()
    for i in range(3):                                                                            # стук в дверь
        k = pr(t, i*0.07, 0.25+i*0.07)
        if 0 < k < 1: line(c, 1010-i*26, 420+i*40, 960-i*26, 400+i*40, 7, INK, 1-k)
    pop_label(c, '$2,350', 1560, 420, pr(t, 0.85, 1.1), hx('#F0564A'), 120, 0.08, t)
    c.restore()
    c.save(); cam(c, C, depth=1.5)                                                                # наш герой со спины, не в фокусе
    soft(c, lambda cc: character(cc, 400, 1830, 2.5, dict(GUY, view='back', legs=False, hands=((-120, -150), (120, -150)))), 6)
    c.restore()
    whip(c, wk)

def shot4(c, t):   # бумажный график: whip-вход, панорама вдоль столбиков, наезд на крошечный остаток
    wk = 1-eio(pr(t, 0.0, 0.18))
    C = camkf(t, [(0, 640, 560, 1.3), (1.0, 1050, 560, 1.15), (1.7, 1500, 730, 2.3)]); C = (C[0]-900*wk, C[1], C[2])
    c.save(); cam(c, C, off=shake(t, 1.7, 0.3, 8))
    set_paper(c, t)
    text(c, 'THIS MONTH', 960, 130, 96, INK, font=BRUSH)
    line(c, 250, 880, 1750, 880, 14, hx('#3A3D3A')); line(c, 250, 250, 250, 886, 14, hx('#3A3D3A'))
    hatch_bar(c, 380, 873, 260, 560, hx('#4E8B57'), pr(t, 0.15, 0.6))
    hatch_bar(c, 880, 873, 260, 546, hx('#D8574A'), pr(t, 0.55, 1.0))
    hatch_bar(c, 1420, 873, 200, 16, hx('#4F79B0'), pr(t, 1.0, 1.2))
    c.set_dash([16, 12]); line(c, 640, 313, 880, 313, 4, INK, pr(t, 0.6, 0.8)); line(c, 1140, 857, 1420, 857, 4, INK, pr(t, 1.0, 1.2)); c.set_dash([])
    text(c, '+$2,400', 510, 270, 60, hx('#2F6F3A'), font=BRUSH, a=pr(t, 0.5, 0.65)); text(c, '-$2,350', 1010, 284, 60, hx('#A8423A'), font=BRUSH, a=pr(t, 0.9, 1.05))
    for s_, x_ in (('Salary', 510), ('Rent', 1010), ('Left over', 1520)): text(c, s_, x_, 940, 46, INK, font=BRUSH)
    k = pr(t, 1.25, 1.5)
    if k > 0:
        cast_shadow(c, 1700, 873, 34, 0.2)
        character(c, 1700, 873, 0.3*back(k, 1.5), dict(GUY, eyes='dot', mouth='frown', brow='worry', look=(-8, 6), head_tilt=-0.1))
    pop_label(c, '$50', 1520, 760, pr(t, 1.7, 1.92), hx('#FFD54A'), 80, -0.08, t)
    burst(c, 1520, 760, pr(t, 1.7, 2.0), 90, 140, 10, 5)
    star(c, 1340, 690, 60*back(pr(t, 1.8, 2.0), 2), hx('#E0B04A'), 0.2+0.05*math.sin(t*4), 'OOF')
    c.restore(); whip(c, wk, INK)

SHOTS = [(0.0, shot1), (2.8, shot3), (4.6, shot4)]
render(SHOTS, 6.8, sys.argv[1:])
