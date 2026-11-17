import cairo, math, random, subprocess, sys
import numpy as np

W, H, FPS = 1920, 1080, 30
INK = (0.13, 0.11, 0.13)
PI = math.pi
MARK, BRUSH = 'Permanent Marker', 'Caveat Brush'

# ================================================================ basics
def hx(h):
    h = h.lstrip('#'); return (int(h[0:2], 16)/255, int(h[2:4], 16)/255, int(h[4:6], 16)/255)
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def shade(col, k): return tuple(clamp(v*k) for v in col)
def pr(t, a, b): return clamp((t-a)/(b-a))          # progress 0..1 over a time span
def eio(x): return 4*x*x*x if x < .5 else 1-(-2*x+2)**3/2
def eout(x): return 1-(1-x)**3
def ein(x): return x*x*x
def back(x, s=2.0):
    x = clamp(x)-1; return x*x*((s+1)*x+s)+1
def lerp(a, b, k): return a+(b-a)*k

def rrect(c, x, y, w, h, r):
    r = min(r, w/2, h/2); c.new_sub_path()
    c.arc(x+w-r, y+r, r, -PI/2, 0); c.arc(x+w-r, y+h-r, r, 0, PI/2)
    c.arc(x+r, y+h-r, r, PI/2, PI); c.arc(x+r, y+r, r, PI, 1.5*PI); c.close_path()
def ell(c, x, y, rx, ry):
    c.save(); c.translate(x, y); c.scale(rx, ry); c.new_sub_path(); c.arc(0, 0, 1, 0, 2*PI); c.restore()
def poly(c, pts):
    c.move_to(*pts[0])
    for p in pts[1:]: c.line_to(*p)
    c.close_path()
def fill(c, col, a=1.0): c.set_source_rgba(*col, a); c.fill()
def fs(c, col, lw=7, a=1.0):
    c.set_source_rgba(*col, a); c.fill_preserve(); c.set_source_rgb(*INK); c.set_line_width(lw); c.stroke()
def stroke(c, lw=7, col=INK, a=1.0): c.set_source_rgba(*col, a); c.set_line_width(lw); c.stroke()
def line(c, x0, y0, x1, y1, lw=7, col=INK, a=1.0): c.move_to(x0, y0); c.line_to(x1, y1); stroke(c, lw, col, a)
def R(c, x, y, w, h, r, col, lw=6, a=1.0): rrect(c, x, y, w, h, r); fs(c, col, lw, a)      # outlined box
def E(c, x, y, rx, ry, col, lw=6, a=1.0): ell(c, x, y, rx, ry); fs(c, col, lw, a)           # outlined ellipse
def P_(c, pts, col, lw=6): poly(c, pts); fs(c, col, lw)                                      # outlined polygon
def glow(c, x, y, rx, ry, col, a): ell(c, x, y, rx, ry); fill(c, col, a)                     # flat light pool

def text(c, s, x, y, size, col, font=MARK, outline=0, rot=0, scale=1.0, anchor='c', a=1.0, shadow=0):
    if scale <= 0.001 or a <= 0: return
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(scale, scale)
    c.select_font_face(font); c.set_font_size(size)
    xb, yb, tw, th, xa, _ = c.text_extents(s)
    ox = -tw/2-xb if anchor == 'c' else (-xb if anchor == 'l' else -tw-xb)
    fe = c.font_extents(); oy = (fe[0]-fe[1])/2
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    if shadow:
        c.move_to(ox+shadow, oy+shadow); c.text_path(s)
        c.set_source_rgba(*INK, a); c.set_line_width(outline); c.stroke_preserve(); c.fill()
    c.move_to(ox, oy); c.text_path(s)
    if outline: c.set_source_rgba(*INK, a); c.set_line_width(outline); c.stroke_preserve()
    c.set_source_rgba(*col, a); c.fill(); c.restore()
def text_w(c, s, size, font=MARK):
    c.select_font_face(font); c.set_font_size(size); return c.text_extents(s)[4]

# ================================================================ camera
def camkf(t, keys):
    '''keys: [(time, cx, cy, zoom), ...] -> eased (cx, cy, zoom). Use 2-4 keys per shot.'''
    if t <= keys[0][0]: return keys[0][1:]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            k = eio(pr(t, a[0], b[0])); return tuple(lerp(a[i], b[i], k) for i in (1, 2, 3))
    return keys[-1][1:]
def shake(t, t0, dur=0.35, amp=12):
    if not t0 < t < t0+dur: return (0, 0)
    a = (1-pr(t, t0, t0+dur))*amp; return (a*math.sin(t*95), a*math.cos(t*80))
def cam(c, C, depth=1.0, off=(0, 0)):
    '''Apply camera C=(cx,cy,zoom). depth<1 = far parallax layer (moves/zooms less), >1 = foreground.'''
    cx, cy, z = C
    z = 1+(z-1)*depth; cx = W/2+(cx-W/2)*depth; cy = H/2+(cy-H/2)*depth
    c.translate(W/2+off[0], H/2+off[1]); c.scale(z, z); c.translate(-cx, -cy)
def soft(c, fn, f=10):
    '''Draw fn(ctx) out of focus, in the current camera space (foreground silhouettes = depth).'''
    sm = cairo.ImageSurface(cairo.FORMAT_ARGB32, W//f, H//f); cc = cairo.Context(sm); m = c.get_matrix(); cc.scale(1/f, 1/f); cc.transform(m)
    cc.set_line_join(cairo.LINE_JOIN_ROUND); cc.set_line_cap(cairo.LINE_CAP_ROUND); fn(cc)
    c.save(); c.identity_matrix(); c.scale(f, f); c.set_source_surface(sm, 0, 0)
    c.get_source().set_filter(cairo.FILTER_BILINEAR); c.paint(); c.restore()
def whip(c, k, col=(1, 1, 1)):
    '''Whip-pan streaks, k 0..1 near a cut. Use col=INK on light backgrounds.'''
    if k <= 0: return
    rnd = random.Random(1)
    for i in range(26):
        y = rnd.uniform(0, H); x = rnd.uniform(-200, W)
        line(c, x, y, x+rnd.uniform(300, 900), y, rnd.uniform(4, 16), col, 0.35*k)

# ================================================================ overlays
def tag(c, s, x, y, k, rot=-0.02, size=40):
    if k <= 0: return
    w = text_w(c, s, size)+86
    c.save(); c.translate(x-(x+w+40)*(1-back(k, 1.2)), y); c.rotate(rot)
    rrect(c, 6, 8, w, 76, 5); fill(c, INK, 0.35); R(c, 0, 0, w, 76, 5, hx('#F6EFDD'), 5)
    ell(c, 30, 38, 7, 7); fill(c, INK); text(c, s, 54, 38, size, INK, anchor='l'); c.restore()
def pop_label(c, s, x, y, k, col, size=150, rot=-0.1, t=0):
    if k <= 0: return
    text(c, s, x, y, size, col, outline=size*0.085, rot=rot+0.03*math.sin(t*5), scale=back(k, 2.8), shadow=size*0.03)
def burst(c, x, y, k, r0, r1, n=10, lw=7, col=INK):
    if k <= 0 or k >= 1: return
    for i in range(n):
        a = i*2*PI/n+0.2; ra = lerp(r0, r1, eout(k)); rb = lerp(r0, r1, eout(clamp(k*1.6)))
        line(c, x+math.cos(a)*ra, y+math.sin(a)*ra, x+math.cos(a)*rb, y+math.sin(a)*rb, lw, col, 1-k)
def dust(c, x, y, k, n=5, spread=70, seed=0, col=(0.85, 0.82, 0.78)):
    if k <= 0 or k >= 1: return
    rnd = random.Random(seed)
    for i in range(n):
        a = rnd.uniform(PI, 2*PI); d = rnd.uniform(0.4, 1)*spread*eout(k)
        ell(c, x+math.cos(a)*d*1.4, y+math.sin(a)*d*0.5, 13*(1-k)+3, 13*(1-k)+3); fill(c, col, 0.7*(1-k))
def motes(c, t, x, y, w, h, n=18, seed=2):          # dust motes drifting in a light pool
    rnd = random.Random(seed)
    for i in range(n):
        px = x+rnd.random()*w+20*math.sin(t*0.6+i); py = y+(rnd.random()*h-t*14*(0.5+rnd.random())) % h
        ell(c, px, py, 3, 3); fill(c, (1, 0.95, 0.8), 0.35)
def papers(c, t, n=14, seed=4):                     # sheets of paper flying through the frame
    rnd = random.Random(seed)
    for i in range(n):
        sp = 0.25+rnd.random()*0.3; ph = rnd.random()
        k = (t*sp+ph) % 1; x = rnd.uniform(-100, W+100)+120*math.sin(t*1.5+i); y = -80+k*(H+160)
        c.save(); c.translate(x, y); c.rotate(t*2*(rnd.random()-0.5)*3+i); R(c, -22, -16, 44, 32, 3, hx('#F6EFDD'), 3)
        line(c, -12, -4, 12, -4, 2); line(c, -12, 4, 6, 4, 2); c.restore()
def quote_box(c, s, who, x, y, w, k):               # cream quote box, words appear one by one via k 0..1
    if k <= 0: return
    R(c, x, y, w, 96, 14, hx('#F6EFDD'), 5)
    words = s.split(); n = max(1, int(len(words)*clamp(k*1.15)))
    text(c, ' '.join(words[:n]), x+30, y+48, 46, INK, font=BRUSH, anchor='l')
    text(c, who, x+w-10, y+122, 24, (1, 1, 1), font=BRUSH, anchor='r', a=pr(k, 0.8, 1))
def star(c, x, y, r, col, rot=0.2, label=None):
    if r <= 1: return
    c.save(); c.translate(x, y); c.rotate(rot)
    P_(c, [(math.sin(i*PI/5)*(r if i % 2 == 0 else r*0.45), -math.cos(i*PI/5)*(r if i % 2 == 0 else r*0.45)) for i in range(10)], col, 5)
    if label: text(c, label, 0, 4, r*0.34, INK)
    c.restore()
def hatch_bar(c, x, y0, w, h, col, k=1.0, lw=6):    # hand-drawn bar growing up from baseline y0
    h *= eout(clamp(k))
    if h < 2: return
    c.rectangle(x, y0-h, w, h); fill(c, col)
    c.save(); c.rectangle(x, y0-h, w, h); c.clip()
    for i in range(-int(h), int(w)+20, 22): line(c, x+i, y0, x+i+h, y0-h, 3, INK, 0.75)
    c.restore(); c.rectangle(x, y0-h, w, h); stroke(c, lw)

# ================================================================ character rig
def limb(c, pts, col, w=10):
    '''Sleeve / trouser leg: ink outline + colour core. pts = (x0,y0,cx,cy,x1,y1).'''
    for lw, cc in ((w+8, INK), (w, col)):
        c.move_to(pts[0], pts[1]); c.curve_to(pts[2], pts[3], pts[2], pts[3], pts[4], pts[5]); stroke(c, lw, cc)
def body_path(c):
    c.move_to(-74, -330); c.curve_to(-96, -320, -100, -130, -92, -110)
    c.curve_to(-86, -84, 86, -84, 92, -110); c.curve_to(100, -130, 96, -320, 74, -330); c.close_path()

ARM = 75                                                                       # upper arm = forearm length (reach 148 from the shoulder)
def character(c, x, y, s, P):
    '''Origin at feet, ~510 units tall. Keys in P (all optional):
    skin, hair, hair_style: messy|sidepart|curly|bun|long|bald|cap, top, top2 (accent), pants, sleeve,
    outfit: hoodie|suit|shirt|tee|sweater|apron, tie, glasses: round|rect, mustache,
    view: front|back,
    yaw: -1..1 turn of the whole body (0 = front, ±0.5 = three-quarter, +1 = profile facing screen-right, -1 = facing left),
    head_yaw: turn of the head only (defaults to yaw) - look over the shoulder, turn to camera, follow an object,
    turn: legacy small face shift (= yaw 0.13*turn),
    light: -1..1 side the key light comes from, rim: (r,g,b) rim light on the lit edge (fire, neon, screen glow),
    eyes: dot|half|wide|closed, look=(dx,dy), blink, brow: up|smug|worry|flat|angry,
    mouth: smile|grin|smirk|flat|o|talk|grimace|frown,
    lean, bob, squash, head_tilt, hands=((x,y),(x,y)) local (shoulders at (-80,-292)/(80,-292), reach 148; elbows bend naturally on their own), hand_pose=(l,r), t (finger wiggle),
    walk=(phase,amount), legs: True|False|'sit', held=fn(c) object between body and hands, sweat 0..1, sweat_y.'''
    skin = P.get('skin', hx('#F3C58F')); top = P.get('top', hx('#5E8C61')); top2 = P.get('top2', hx('#D8574A'))
    pants = P.get('pants', hx('#3A3F58')); outfit = P.get('outfit', 'hoodie'); backv = P.get('view') == 'back'
    yaw = clamp(P.get('yaw', 0.13*P.get('turn', 0)), -1, 1); hyaw = clamp(P.get('head_yaw', yaw), -1, 1)
    pb = yaw*PI/2; sb, cb = math.sin(pb), math.cos(pb); fd = 1 if yaw >= 0 else -1
    far = 1 if fd > 0 else 0                                                    # arm/leg on the far side of the body
    lt = P.get('light', -0.6); rim = P.get('rim')
    c.save(); c.translate(x, y); c.scale(s, s); c.rotate(P.get('lean', 0))
    sq = P.get('squash', 1.0); c.scale(1/math.sqrt(sq), sq)
    bob = P.get('bob', 0); ph, wa = P.get('walk', (0, 0)); legs = P.get('legs', True)
    if legs:
        ln = 45 if legs == 'sit' else 100; spx = 34*max(0.3, cb)
        for i in ((far, 1-far) if abs(yaw) > 0.3 else (0, 1)):
            sx = (-spx, spx)[i]
            f = ph+i*PI; fx = sx+34*math.sin(f)*wa; fy = -max(0, math.cos(f))*16*wa-(100-ln)
            pc = shade(pants, 0.75) if (abs(yaw) > 0.3 and i == far) else pants
            limb(c, (sx, -100-bob, (sx+fx)/2, (fy-100)/2, fx, fy-10), pc, 11)
            toe = fd*(8+12*abs(sb)) if abs(yaw) > 0.15 else 8
            c.save(); c.translate(fx+toe, fy); c.scale(1+0.25*abs(sb), 0.62); c.new_sub_path(); c.arc(0, 0, 25, PI, 2*PI); c.close_path(); c.restore()
            fs(c, hx('#2B2730'), 5); line(c, fx+toe-22, fy-1, fx+toe+22, fy-1, 4, hx('#EDE6D6'))
    c.translate(0, -bob)
    bw = 1-0.14*abs(sb)
    def bpath(): c.save(); c.scale(bw, 1); body_path(c); c.restore()
    hands = P.get('hands', ((-108, -150), (108, -150))); bends = P.get('bends', (-26, 26))
    sleeve = P.get('sleeve', shade(top, 0.92)); poses = P.get('hand_pose', ('fist', 'fist'))
    shx = 80*max(0.22, cb)
    def arm(i):
        sx, sy = (-shx, shx)[i]+12*sb, -292; tx, ty = hands[i]
        dx, dy = tx-sx, ty-sy; d = math.hypot(dx, dy)+1e-6; rch = 2*ARM-2
        if d > rch: tx, ty = sx+dx/d*rch, sy+dy/d*rch                           # a hand beyond reach is pulled in (arms never stretch)
        side = -1 if i == 0 else 1; wo = 0.6*cb                                 # elbow always natural: down and outward, never folded up/in
        ex, ey = max((elbow(sx, sy, tx, ty, ARM, ARM, b) for b in (-1, 1)), key=lambda e: e[1]+(wo*side-0.6*abs(sb)*fd)*e[0])   # in profile: elbow goes back
        col = shade(sleeve, 0.78) if (abs(yaw) >= 0.35 and i == far) else sleeve
        for lw, cc in ((19, INK), (11, col)):
            c.move_to(sx, sy); c.line_to(ex, ey); c.line_to(tx, ty); stroke(c, lw, cc)
        hand(c, tx, ty, math.atan2(ty-ey, tx-ex), poses[i], skin, -1 if i == 0 else 1, 1.25, P.get('t', 0))
    back_arm = abs(yaw) >= 0.35 and not backv
    if outfit == 'hoodie': E(c, -40*sb, -322, 96*bw, 46, shade(top, 0.8), 7)
    if P.get('hair_style') == 'long': R(c, -108-40*sb, -440, 216, 190, 60, P.get('hair', hx('#4A3226')), 7)
    if back_arm: arm(far)
    bpath(); fs(c, top)
    c.save(); bpath(); c.clip()
    g = cairo.LinearGradient(-100, 0, 100, 0)
    for o, a in ((0, 0.30*max(0, lt)+0.02), (0.5, 0.05), (1, 0.30*max(0, -lt)+0.02)): g.add_color_stop_rgba(o, 0, 0, 0, a)
    c.rectangle(-110, -340, 220, 270); c.set_source(g); c.fill()                # form shadow on the far side
    if rim:                                                                     # rim light on the lit edge
        ex_ = 100*bw*(1 if lt > 0 else -1); g = cairo.LinearGradient(ex_, 0, ex_-(1 if lt > 0 else -1)*46, 0)
        g.add_color_stop_rgba(0, *rim, 0.55); g.add_color_stop_rgba(1, *rim, 0); c.rectangle(-110, -340, 220, 270); c.set_source(g); c.fill()
    ell(c, -30*sb, -330, 80, 26); fill(c, (0, 0, 0), 0.16)                       # shadow under the head
    c.save(); c.translate(48*sb, 0); c.scale(max(0.3, cb), 1)                     # front details slide round the body when it turns
    if backv:
        line(c, 0, -300, 0, -95, 3, INK, 0.35)
    elif outfit == 'hoodie':
        c.rectangle(-110, -112, 220, 40); fill(c, shade(top, 0.82)); line(c, -110, -112, 110, -112, 4)
        c.move_to(-56, -112); c.line_to(-40, -176); c.line_to(40, -176); c.line_to(56, -112); stroke(c, 5)
        line(c, 0, -300, 0, -176, 3, INK, 0.5)
        for dx in (-18, 18): line(c, dx, -306, dx*0.9, -236, 5, hx('#F2EEE2')); ell(c, dx*0.9, -232, 5, 7); fill(c, hx('#F2EEE2'))
    elif outfit == 'suit':
        P_(c, [(-30, -334), (30, -334), (0, -200)], hx('#F4F1EA'), 4)
        P_(c, [(-9, -322), (9, -322), (13, -240), (0, -214), (-13, -240)], top2, 4)
        P_(c, [(-10, -334), (10, -334), (7, -316), (-7, -316)], shade(top2, 0.8), 4)
        for sg in (-1, 1): P_(c, [(sg*30, -334), (sg*62, -318), (sg*40, -262), (0, -200)], shade(top, 1.18), 5)
        for by in (-176, -140): ell(c, 0, by, 6, 6); fill(c, INK)
        line(c, 0, -200, 0, -90, 4); R(c, 40, -268, 30, 10, 2, hx('#F4F1EA'), 3)
    elif outfit == 'shirt':
        line(c, 0, -322, 0, -90, 4, INK, 0.6)
        for by in (-280, -236, -192, -148): ell(c, 0, by, 5, 5); fill(c, INK, 0.7)
        for sg in (-1, 1): P_(c, [(0, -322), (sg*40, -334), (sg*30, -292)], shade(top, 1.12), 4)
        R(c, 30, -262, 40, 44, 4, top, 4); line(c, 44, -276, 44, -250, 5, top2)
        if P.get('tie'): P_(c, [(-9, -312), (9, -312), (14, -190), (0, -166), (-14, -190)], top2, 4)
    elif outfit == 'tee':
        c.new_sub_path(); c.arc(0, -334, 34, 0, PI); stroke(c, 6, shade(top, 0.75)); E(c, 0, -206, 34, 34, top2, 4)
        star(c, 0, -206, 22, hx('#F7C76B'), 0)
    elif outfit == 'sweater':
        c.new_sub_path(); c.arc(0, -334, 38, 0, PI); stroke(c, 12, shade(top, 0.78))
        for by in (-236, -206): c.rectangle(-110, by, 220, 14); fill(c, top2)
        c.rectangle(-110, -112, 220, 40); fill(c, shade(top, 0.8))
        for xx in range(-90, 100, 14): line(c, xx, -110, xx, -86, 2, INK, 0.4)
    elif outfit == 'apron':
        R(c, -62, -262, 124, 190, 10, top2, 5)
        for sg in (-1, 1): line(c, sg*44, -262, sg*60, -330, 6, top2)
        R(c, 8, -244, 44, 22, 4, hx('#F6EFDD'), 3); line(c, 14, -233, 46, -233, 3); rrect(c, -40, -170, 80, 50, 6); stroke(c, 4)
    c.restore(); c.restore()
    if P.get('held'): P['held'](c)
    for i in (0, 1):
        if not (back_arm and i == far): arm(i)
    # ---- head (a sphere: features ride on it when it turns)
    Rr = 100; hair = P.get('hair', hx('#4A3226')); hs = P.get('hair_style', 'messy'); hl = shade(hair, 1.45)
    php = hyaw*PI/2; sp, cp = math.sin(php), math.cos(php); hd = 1 if hyaw >= 0 else -1; ak = abs(sp)
    c.save(); c.translate(0, -412); c.rotate(P.get('head_tilt', 0))
    E(c, 0, 0, Rr, Rr, skin, 7)
    c.save(); ell(c, 0, 0, Rr-3, Rr-3); c.clip(); g = cairo.RadialGradient(lt*60, -40, 20, lt*30, 0, 165)      # head: lit side / shadow side
    g.add_color_stop_rgba(0, 1, 1, 1, 0.14); g.add_color_stop_rgba(0.55, 0, 0, 0, 0.0); g.add_color_stop_rgba(1, 0, 0, 0, 0.30)
    c.set_source(g); c.paint()
    if rim: c.new_sub_path(); a0 = 0 if lt > 0 else PI; c.arc(0, 0, Rr-7, a0-1.1, a0+1.1); stroke(c, 10, rim, 0.55)
    c.restore()
    if backv:
        if hs != 'bald':
            c.new_sub_path(); c.arc(0, 0, Rr+5, PI*0.72, PI*2.28); c.curve_to(40, 96, -40, 96, (Rr+5)*math.cos(PI*0.72), (Rr+5)*math.sin(PI*0.72)); fs(c, hair)
        c.restore(); c.restore(); return
    fxo = Rr*0.6*sp
    if hs == 'messy':
        c.new_sub_path(); c.arc(0, 0, Rr+6, PI+0.12, 2*PI-0.12)
        for p in ((84, -44), (64, -70), (46, -36), (22, -74), (2, -40), (-22, -70), (-44, -38), (-66, -64), (-86, -30)): c.line_to(clamp(p[0]+fxo*0.5, -88, 88), p[1])
        c.close_path(); fs(c, hair)
        c.move_to(-10, -Rr-2); c.curve_to(-4, -Rr-34, 26, -Rr-36, 36, -Rr-22); c.curve_to(22, -Rr-20, 16, -Rr-10, 16, -Rr+2); c.close_path(); fs(c, hair, 6)
    elif hs == 'sidepart':
        c.new_sub_path(); c.arc(0, 0, Rr+6, PI+0.2, 2*PI-0.05)
        c.curve_to(60+fxo, -30, 10+fxo, -66, -46+fxo, -72); c.curve_to(-60, -56, -76, -40, -(Rr+6)*math.cos(0.2), -(Rr+6)*math.sin(0.2)); c.close_path(); fs(c, hair)
        c.move_to(-46+fxo, -72); c.curve_to(-30, -92, -10, -100, 10, -104); stroke(c, 4)
    elif hs == 'curly':
        c.new_sub_path(); c.arc(0, 0, Rr+4, PI+0.1, 2*PI-0.1); c.curve_to(50, -50, -50, -50, -(Rr+4)*math.cos(0.1), -(Rr+4)*math.sin(0.1)); c.close_path(); fs(c, hair)
        for i in range(11):
            a = PI+0.05+i*(PI-0.1)/10; E(c, math.cos(a)*(Rr+8), math.sin(a)*(Rr+8), 27, 27, hair, 6)
        for i in range(7): ell(c, -66+i*22+fxo*0.4, -52+8*math.sin(i*2.1), 22, 22); fill(c, hair)
        c.new_sub_path(); c.arc(0, 0, Rr-4, PI+0.3, 2*PI-0.3); c.set_source_rgb(*hair); c.set_line_width(40); c.stroke()
    elif hs in ('bun', 'long'):
        if hs == 'bun': E(c, 6-40*sp, -Rr-24, 34*max(0.7, cp), 30, hair, 7)
        c.new_sub_path(); c.arc(0, 0, Rr+5, PI+0.25, 2*PI-0.25)
        c.curve_to(70, -70, 10+fxo, -78, -30+fxo, -52); c.curve_to(-60, -34, -84, -30, -(Rr+5)*math.cos(0.25), -(Rr+5)*math.sin(0.25)); c.close_path(); fs(c, hair)
    elif hs == 'bald':
        for sg in (-1, 1):
            if not (ak > 0.5 and sg == hd): E(c, sg*(Rr-4)*cp-hd*ak*50, -16, 16, 34, hair, 6)
        c.new_sub_path(); c.arc(-30, -40, 40, PI*1.15, PI*1.55); stroke(c, 5, (1, 1, 1), 0.5)
    elif hs == 'cap':
        c.new_sub_path(); c.arc(0, -6, Rr+6, PI, 2*PI); c.close_path(); fs(c, hair)
        bx = -20+fxo*1.6 if ak < 0.5 else (hd*30 if hd > 0 else -150-30)
        R(c, bx, -22, 150, 26, 12, shade(hair, 0.8), 6); E(c, 0, -Rr-8, 10, 7, shade(hair, 0.8), 4)
    ex_ = -hd*(Rr*cp+16*ak)                                                     # ear rides round the head
    if hs not in ('bald', 'cap') and ak > 0.08:                                  # back of the head is hair when it turns
        hb = 95 if hs == 'long' else 14; xb = ex_-hd*16
        c.save(); ell(c, 0, 0, Rr+5, Rr+5); c.clip()
        c.move_to(-hd*(Rr+30), -Rr-30); c.line_to(xb+hd*40*ak, -Rr-30)
        c.curve_to(xb+hd*28*ak, -50, xb, -24, xb-hd*4, hb); c.line_to(-hd*(Rr+30), hb); c.close_path(); fill(c, hair)
        c.move_to(xb+hd*40*ak, -Rr-30); c.curve_to(xb+hd*28*ak, -50, xb, -24, xb-hd*4, hb); stroke(c, 5)
        ell(c, 0, 0, Rr, Rr); stroke(c, 7)
        c.restore()
        if hs == 'curly':
            for i in range(3): E(c, ex_-hd*(34+i*10), -56+i*26, 20, 20, hair, 5)
    if ak > 0.2:
        E(c, ex_, 4, 10+12*ak, 22, skin, 6)
        c.move_to(ex_-hd*4*ak, -8); c.curve_to(ex_+hd*8*ak, -4, ex_+hd*8*ak, 10, ex_-hd*2, 14); stroke(c, 4, INK, 0.6)
    # ---- face
    lkx, lky = P.get('look', (0, 0)); lkx += hd*5*ak; eyes = P.get('eyes', 'dot'); ey = -4
    vis = []                                                                    # cartoon turn: near eye slides to 0.56R, far eye hides
    for sg in (-1, 1):
        near = (sg == hd); dx = lerp(sg*36, hd*56 if near else hd*14, ak); q = 1-0.22*ak if near else 1-1.6*ak
        if q < 0.3: continue
        vis.append((sg, dx, q))
        if P.get('blink') or eyes == 'closed':
            c.move_to(dx-12*q, ey); c.curve_to(dx-6*q, ey+7, dx+6*q, ey+7, dx+12*q, ey); stroke(c, 5)
        elif eyes == 'wide':
            E(c, dx, ey-4, 23*q, 23, (1, 1, 1), 5); ell(c, dx+lkx*0.9*q, ey-4+lky*0.9, 7.5*q, 7.5); fill(c, INK)
        elif eyes == 'half':
            E(c, dx, ey, 17*q, 15, (1, 1, 1), 5); ell(c, dx+lkx*0.6*q, ey+3+lky*0.5, 7*q, 7); fill(c, INK)
            c.save(); c.translate(dx, ey); c.scale(q, 1); c.new_sub_path(); c.arc(0, 0, 17, PI, 2*PI); c.close_path(); c.restore()
            fs(c, skin, 5); line(c, dx-19*q, ey, dx+19*q, ey, 5)
        else:
            ell(c, dx+lkx*q, ey+lky, 8.5*q, 9.5); fill(c, INK); ell(c, dx+lkx*q+3*q, ey+lky-3, 2.5, 2.5); fill(c, (1, 1, 1))
    nx = hd*lerp(30, 90, ak)
    gl = P.get('glasses')
    if gl:
        for sg, dx, q in vis:
            if gl == 'round': ell(c, dx, ey-2, 27*q, 27)
            else: rrect(c, dx-28*q, ey-22, 56*q, 40, 8)
            c.set_source_rgba(1, 1, 1, 0.22); c.fill_preserve(); stroke(c, 5)
        if len(vis) == 2: line(c, vis[0][1]+27*vis[0][2], ey-4, vis[1][1]-27*vis[1][2], ey-4, 5)
        elif vis and ak > 0.4: line(c, vis[0][1]+hd*27*vis[0][2], ey-4, nx, ey-2, 5)
        if ak < 0.25:
            for sg, dx, q in vis: line(c, dx+sg*27*q, ey-6, sg*(Rr-4)*cp+sp*20, ey-12, 5)
        elif vis:
            sg, dx, q = vis[0] if hd > 0 else vis[-1]; line(c, dx-hd*27*q, ey-6, ex_+hd*6, ey-10, 5)
    brow = P.get('brow'); by = ey-(46 if gl else 34)
    for sg, dx, q in vis:
        def bl(x0, y0, x1, y1, w=5): line(c, dx+x0*q, by+y0, dx+x1*q, by+y1, w)
        if brow == 'up': c.move_to(dx-16*q, by-6); c.curve_to(dx-6*q, by-14, dx+6*q, by-14, dx+16*q, by-6); stroke(c, 5)
        elif brow == 'smug':
            if sg < 0: bl(-16, 4, 16, 0)
            else: c.move_to(dx-16*q, by-10); c.curve_to(dx-6*q, by-18, dx+8*q, by-16, dx+16*q, by-8); stroke(c, 5)
        elif brow == 'worry': bl(-14*sg, -16, 18*sg, -2)
        elif brow == 'angry': bl(-16*sg, 2, 18*sg, -14, 6)
        elif brow == 'flat': bl(-16*sg, 4, 18*sg, 4)
    if ak > 0.15:                                                               # nose appears with the turn, sticks out in profile
        c.move_to(nx-hd*3, -2); c.curve_to(nx+hd*30*ak, 2, nx+hd*(14+20*ak), 28, nx-hd*4, 28); c.close_path(); fill(c, skin)
        c.move_to(nx-hd*3, -2); c.curve_to(nx+hd*30*ak, 2, nx+hd*(14+20*ak), 28, nx-hd*4, 28); stroke(c, 6)
    m = P.get('mouth', 'smile'); my = 46; mxx = hd*62*ak; mw = 1-0.42*ak
    c.save(); c.translate(mxx, 0); c.scale(mw, 1); mx = 0
    if P.get('mustache'):
        c.move_to(mx-30, my-8); c.curve_to(mx-16, my-26, mx-4, my-22, mx, my-14); c.curve_to(mx+4, my-22, mx+16, my-26, mx+30, my-8)
        c.curve_to(mx+14, my-4, mx+4, my-6, mx, my-10); c.curve_to(mx-4, my-6, mx-14, my-4, mx-30, my-8); c.close_path(); fs(c, hair, 4); my += 8
    if m == 'smile': c.move_to(mx-26, my-6); c.curve_to(mx-12, my+14, mx+12, my+14, mx+26, my-6); stroke(c, 5)
    elif m == 'grin':
        c.move_to(mx-30, my-8); c.curve_to(mx-20, my+26, mx+20, my+26, mx+30, my-8); c.close_path(); fs(c, (1, 1, 1), 5); line(c, mx-24, my+2, mx+24, my+2, 3)
    elif m == 'smirk': c.move_to(mx-20, my+2); c.curve_to(mx-4, my+10, mx+16, my+6, mx+30, my-10); stroke(c, 5)
    elif m == 'flat': line(c, mx-18, my, mx+18, my, 5)
    elif m == 'o': E(c, mx, my+2, 11, 14, hx('#5A2A2A'), 5)
    elif m == 'talk': c.move_to(mx-20, my-6); c.curve_to(mx-14, my+22, mx+14, my+22, mx+20, my-6); c.close_path(); fs(c, hx('#5A2A2A'), 5)
    elif m == 'grimace':
        R(c, mx-30, my-12, 60, 24, 10, (1, 1, 1), 5); line(c, mx-30, my, mx+30, my, 3)
        for dx in (-15, 0, 15): line(c, mx+dx, my-12, mx+dx, my+12, 3)
    elif m == 'frown': c.move_to(mx-20, my+6); c.curve_to(mx-8, my-6, mx+8, my-6, mx+20, my+6); stroke(c, 5)
    c.restore()
    sw = P.get('sweat', 0)
    if sw > 0:
        side = -hd if ak > 0.3 else 1
        c.save(); c.translate(side*(Rr-14), -46+P.get('sweat_y', 0)); c.scale(back(sw), back(sw))
        c.move_to(0, -28); c.curve_to(17, 0, 15, 17, 0, 17); c.curve_to(-15, 17, -17, 0, 0, -28); c.close_path(); fs(c, hx('#A9DBF3'), 4); c.restore()
    c.restore(); c.restore()

def cast_shadow(c, x, y, w=95, a=0.28): ell(c, x+18, y+4, w, w*0.16); fill(c, (0, 0, 0), a)
def blinking(t, times, d=0.11): return any(b <= t < b+d for b in times)
def crowd(c, y, n, seed=1, s=0.3, x0=-100, x1=W+100, t=0):   # row of tiny background people
    rnd = random.Random(seed); cols = ['#C9584C', '#4F79B0', '#E0B04A', '#5E8C61', '#8A6FB0', '#D9D4C7', '#3A3F58']
    hairs = ['#2B2730', '#4A3226', '#7A3B2E', '#C9A24A', '#9AA3AE']
    for i in range(n):
        px = lerp(x0, x1, (i+rnd.random()*0.6)/n)
        character(c, px, y+rnd.uniform(-6, 6)+3*math.sin(t*2+i), s*rnd.uniform(0.9, 1.1), dict(
            top=hx(rnd.choice(cols)), hair=hx(rnd.choice(hairs)), hair_style=rnd.choice(['messy', 'sidepart', 'bun', 'curly', 'bald']),
            outfit=rnd.choice(['shirt', 'tee', 'suit', 'sweater']), mouth=rnd.choice(['o', 'flat', 'smile']), hands=((-100, -160), (100, -160))))

# ================================================================ props (y = bottom / floor contact unless noted)
def bill(c, x, y, rot=0, s=1.0):
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(s, s)
    R(c, -90, -40, 180, 80, 6, hx('#7DB069'), 5); rrect(c, -78, -30, 156, 60, 4); stroke(c, 3, hx('#2F5E2E'), 0.8)
    E(c, 0, 0, 24, 26, hx('#A3CC8F'), 3); text(c, '$', 0, 0, 34, hx('#2F5E2E')); c.restore()
def money_stack(c, x, y, n=4, s=1.0, vp=(W/2, -600)):    # 3D banded cash bricks, y = bottom
    band = lambda cc, X, Y, Wd, Ht: (cc.rectangle(X+Wd/2-14*s, Y, 28*s, Ht), fs(cc, hx('#F6EFDD'), 3))
    for i in range(n): box3d(c, x-80*s, y-(i+1)*26*s, 160*s, 26*s, 40*s, hx('#7DB069'), vp, 4, band, hx('#8FC47B'))
def mug(c, x, y, s=1.0, t=0, col=hx('#F6EFDD'), steam=True, drink=hx('#6B3E26')):
    c.new_sub_path(); c.arc(x+34*s, y-34*s, 18*s, -PI/2, PI/2); stroke(c, 7)
    cyl3d(c, x, y, 30*s, 64*s, col, tilt=0.24, lw=5, top_col=drink)
    if steam: smoke(c, t, x, y-70*s, 'steam', rate=7, life=1.7, rise=150*s, spread=14*s, size=13*s, wind=8*s, a=0.45, seed=int(x) % 97)
def plant(c, x, y, s=1.0, t=0):
    for i, a in enumerate((-1.0, -0.5, 0.0, 0.5, 1.0)):
        a += 0.04*math.sin(t*1.3+i); L = (150, 190, 210, 190, 150)[i]*s
        tx, ty = x+math.sin(a)*L, y-60*s-math.cos(a)*L
        c.move_to(x, y-60*s); c.curve_to(x+math.sin(a)*L*0.2-30*s, y-60*s-L*0.5, tx-20*s, ty+30*s, tx, ty)
        c.curve_to(tx+10*s, ty+50*s, x+math.sin(a)*L*0.4+30*s, y-60*s-L*0.3, x, y-60*s); c.close_path(); fs(c, hx('#4E8B57') if i % 2 else hx('#3E7548'), 5)
    P_(c, [(x-52*s, y-70*s), (x+52*s, y-70*s), (x+40*s, y), (x-40*s, y)], hx('#C4683F'), 6); R(c, x-58*s, y-84*s, 116*s, 20*s, 5, hx('#D47A4E'), 5)
def floor_lamp(c, x, y, t=0, on=True):
    line(c, x, y-470, x, y, 9); E(c, x, y, 54, 12, hx('#3B2A22'), 5)
    if on: poly(c, [(x-70, y-470), (x+70, y-470), (x+260, y), (x-260, y)]); fill(c, hx('#FFE9A6'), 0.10+0.008*math.sin(t*9))
    P_(c, [(x-78, y-470), (x+78, y-470), (x+50, y-580), (x-50, y-580)], hx('#FBE7B0'), 6)
def frame_pic(c, x, y, w, h, kind=0):               # (x,y) = top-left. kind 0 landscape, 1 chart, 2 portrait
    R(c, x, y, w, h, 5, hx('#5A3A26'), 6); R(c, x+12, y+12, w-24, h-24, 2, hx('#F6EFDD'), 3)
    c.save(); c.rectangle(x+12, y+12, w-24, h-24); c.clip()
    if kind == 0:
        ell(c, x+w*0.68, y+h*0.4, h*0.14, h*0.14); fill(c, hx('#E39A4E'))
        poly(c, [(x, y+h), (x+w*0.35, y+h*0.45), (x+w*0.6, y+h*0.8), (x+w*0.8, y+h*0.6), (x+w, y+h)]); fill(c, hx('#6F9E7A'))
    elif kind == 1:
        c.move_to(x+20, y+h-24)
        for i, v in enumerate((0.3, 0.45, 0.4, 0.62, 0.58, 0.82)): c.line_to(x+24+i*(w-48)/5, y+h-20-v*(h-44))
        stroke(c, 5, hx('#D8574A'))
    else:
        ell(c, x+w/2, y+h*0.45, h*0.2, h*0.2); fill(c, hx('#F3C58F')); ell(c, x+w/2, y+h, h*0.34, h*0.36); fill(c, hx('#4F79B0'))
    c.restore()
def wall_clock(c, x, y, r, t):                      # (x,y) = centre
    E(c, x, y, r, r, hx('#F6EFDD'), 7)
    for i in range(12): a = i*PI/6; line(c, x+math.cos(a)*r*0.78, y+math.sin(a)*r*0.78, x+math.cos(a)*r*0.9, y+math.sin(a)*r*0.9, 3)
    a = -PI/2+2.2; line(c, x, y, x+math.cos(a)*r*0.5, y+math.sin(a)*r*0.5, 6)
    a = -PI/2+0.6; line(c, x, y, x+math.cos(a)*r*0.72, y+math.sin(a)*r*0.72, 4)
    a = -PI/2+int(t*1)*PI/30; line(c, x, y, x+math.cos(a)*r*0.8, y+math.sin(a)*r*0.8, 2.5, hx('#D8574A')); ell(c, x, y, 5, 5); fill(c, INK)
def bookshelf(c, x, y, w, rows=2, seed=5):          # y = first shelf board
    rnd = random.Random(seed); cols = ['#C9584C', '#4F79B0', '#E0B04A', '#5E8C61', '#8A6FB0', '#3A3F58', '#D9D4C7']
    for r in range(rows):
        yy = y+r*120; xx = x+10
        while xx < x+w-40:
            bw = rnd.choice((18, 24, 30)); bh = rnd.randint(70, 100)
            if rnd.random() < 0.12: xx += 26; continue
            R(c, xx, yy-bh, bw, bh, 2, hx(rnd.choice(cols)), 4); line(c, xx+4, yy-bh+14, xx+bw-4, yy-bh+14, 2, INK, 0.5); xx += bw
        R(c, x, yy, w, 14, 3, hx('#7A5235'), 5)
def window(c, x, y, w, h, t=0, night=True, curtains=hx('#C9584C')):   # (x,y) = top-left of the glass
    R(c, x, y, w, h, 4, hx('#2C3557') if night else hx('#9FD0E8'), 7)
    c.save(); c.rectangle(x, y, w, h); c.clip(); rnd = random.Random(9)
    if not night:
        for cx_, cy_ in ((x+w*0.3, y+h*0.3), (x+w*0.75, y+h*0.2)): glow(c, cx_+t*4, cy_, 60, 22, (1, 1, 1), 0.9)
    bx = x-10
    while bx < x+w:
        bw = rnd.randint(50, 90); bh = rnd.randint(int(h*0.25), int(h*0.7))
        c.rectangle(bx, y+h-bh, bw, bh); fill(c, hx('#1B2140') if night else hx('#7FA3BD'))
        for yy in range(int(y+h-bh+14), int(y+h-8), 28):
            for xx in range(int(bx+10), int(bx+bw-12), 22):
                if rnd.random() < 0.5: c.rectangle(xx, yy, 10, 14); fill(c, hx('#F6C866') if night else hx('#DCEBF3'))
        bx += bw+4
    c.restore()
    line(c, x+w/2, y, x+w/2, y+h, 9, hx('#5A3A26')); line(c, x, y+h/2, x+w, y+h/2, 9, hx('#5A3A26'))
    rrect(c, x-6, y-6, w+12, h+12, 5); stroke(c, 14, hx('#5A3A26')); rrect(c, x-13, y-13, w+26, h+26, 6); stroke(c, 5)
    R(c, x-34, y+h+12, w+68, 22, 4, hx('#6B4630'), 5)
    if curtains:
        for sg in (-1, 1):
            sw = 6*math.sin(t*1.1+sg); ex = x+w/2+sg*(w/2+26)
            P_(c, [(ex, y-30), (ex-sg*90, y-30), (ex-sg*(70+sw), y+h*0.55), (ex-sg*(40+sw), y+h+40), (ex, y+h+40)], curtains, 6)
            for k in (25, 50): line(c, ex-sg*k, y-20, ex-sg*(k*0.6+sw), y+h+30, 3, INK, 0.35)
        line(c, x-60, y-32, x+w+60, y-32, 10, hx('#3B2A22'))
def sofa(c, x, y, w=560, col=hx('#7B4B3A')):
    R(c, x, y-250, w, 190, 40, shade(col, 0.9), 7)
    for i in range(1, 3): line(c, x+i*w/3, y-236, x+i*w/3, y-120, 4, INK, 0.5)
    R(c, x-10, y-130, w+20, 100, 26, col, 7); line(c, x+w/2, y-126, x+w/2, y-36, 4, INK, 0.5)
    for ex in (x-40, x+w-40): R(c, ex, y-190, 80, 170, 34, shade(col, 1.12), 7)
    for ex in (x+20, x+w-50): R(c, ex, y-30, 30, 30, 4, hx('#3B2A22'), 5)
    R(c, x+w-190, y-200, 110, 96, 18, hx('#E0B04A'), 6)
def rug(c, x, y, rx, ry, col=hx('#C9584C')):
    E(c, x, y, rx, ry, col, 6); ell(c, x, y, rx*0.82, ry*0.76); stroke(c, 5, hx('#F6EFDD')); ell(c, x, y, rx*0.5, ry*0.42); stroke(c, 4, hx('#F6EFDD'), 0.7)
def tv(c, x, y, t, w=330):
    R(c, x-20, y-110, w+40, 110, 6, hx('#6B4630'), 7); line(c, x+w/2, y-104, x+w/2, y-6, 4)
    for kx in (x+w*0.25, x+w*0.75): ell(c, kx, y-56, 7, 7); fill(c, INK)
    R(c, x+w/2-40, y-128, 80, 20, 3, hx('#2B2730'), 5); R(c, x, y-330, w, 204, 10, hx('#2B2730'), 7)
    fl = 0.85+0.15*math.sin(t*23)*math.sin(t*7); R(c, x+14, y-316, w-28, 176, 4, shade(hx('#3E6FA8'), fl), 4)
    c.move_to(x+30, y-180)
    for i, v in enumerate((0.2, 0.5, 0.35, 0.7, 0.55, 0.9)): c.line_to(x+40+i*(w-80)/5, y-160-v*130)
    stroke(c, 6, hx('#8FE39A')); glow(c, x+w/2, y-10, w*0.8, 30, hx('#7FB0FF'), 0.10*fl)
def phone(c, x, y, w, h, ui=None):                  # (x,y) = top-left; ui(c, sx, sy, sw, sh) draws the screen
    R(c, x, y, w, h, w*0.14, hx('#1F1D24'), 8); R(c, x+w*0.06, y+w*0.1, w*0.88, h-w*0.2, w*0.07, hx('#F7F7F4'), 4)
    R(c, x+w*0.36, y+w*0.035, w*0.28, w*0.035, 6, hx('#3A3840'), 2)
    if ui: c.save(); rrect(c, x+w*0.06, y+w*0.1, w*0.88, h-w*0.2, w*0.07); c.clip(); ui(c, x+w*0.06, y+w*0.1, w*0.88, h-w*0.2); c.restore()
def finger(c, x, y, s=1.0):                          # big finger entering from below, tip at (x,y)
    R(c, x-46*s, y, 92*s, 700*s, 46*s, hx('#F3C58F'), 7); R(c, x-26*s, y+10*s, 52*s, 40*s, 18*s, hx('#F9DDBB'), 4)
def door(c, x, y, w, h, open_k=1.0, beyond=hx('#2B2540')):
    R(c, x-16, y-h-16, w+32, h+16, 4, hx('#5A3A26'), 7); c.rectangle(x, y-h, w, h); fill(c, beyond)
    dw = w*(1-0.82*open_k)
    R(c, x, y-h, dw, h, 2, hx('#8A5A3C'), 6)
    if dw > 60:
        for py in (y-h+30, y-h*0.5+10): R(c, x+16, py, dw-32, h*0.4, 4, hx('#7A4E33'), 4)
    ell(c, x+dw-18, y-h*0.48, 9, 9); fill(c, hx('#E0B04A'))

# ================================================================ sets (drawn with wide margins for camera moves)
def set_void(c, t, wall=hx('#9FB2C2'), floor=hx('#B9C8D4'), horizon=720):
    '''Minimal studio backdrop for explainer beats: curved floor, hill band, light pool. Add props + cast shadows.'''
    c.rectangle(-2400, -600, W+4800, H+1200); fill(c, wall)
    glow(c, W/2, 380, 1100, 520, (1, 1, 1), 0.10)
    c.move_to(-2400, horizon-60); c.curve_to(400, horizon-190, 1300, horizon-170, W+2400, horizon-40); c.line_to(W+2400, H+600); c.line_to(-2400, H+600); c.close_path(); fill(c, shade(wall, 0.88))
    c.move_to(-2400, horizon+70); c.curve_to(500, horizon-40, 1400, horizon-40, W+2400, horizon+70); c.line_to(W+2400, H+600); c.line_to(-2400, H+600); c.close_path(); fill(c, floor)
def set_room(c, t, wall=hx('#E8B27C'), floor=hx('#8C5A3A'), fy=800):
    '''Room shell: striped wallpaper, wainscot panels, baseboard, floorboards. fy = floor line. Furnish with props.'''
    c.rectangle(-2400, -600, W+4800, fy+600); fill(c, wall)
    for xx in range(-2400, W+2400, 110): c.rectangle(xx, -600, 46, fy+600); fill(c, (1, 1, 1), 0.06)
    c.rectangle(-2400, fy-150, W+4800, 150); fill(c, shade(wall, 0.84)); line(c, -2400, fy-150, W+2400, fy-150, 5)
    for xx in range(-2400, W+2400, 170): rrect(c, xx+20, fy-126, 130, 96, 4); stroke(c, 3, INK, 0.3)
    c.rectangle(-2400, fy-22, W+4800, 22); fill(c, shade(wall, 0.6))
    c.rectangle(-2400, fy, W+4800, 900); fill(c, floor); line(c, -2400, fy, W+2400, fy, 7)
    for yy in (fy+50, fy+120, fy+210): line(c, -2400, yy, W+2400, yy, 3, INK, 0.3)
    ao(c, -2400, W+2400, fy, 70, 60, 0.30)                                    # contact shadow wall/floor
    for xx in range(-2400, W+2400, 240): line(c, xx, fy+2, xx-60, fy+50, 3, INK, 0.25); line(c, xx+120, fy+50, xx+40, fy+120, 3, INK, 0.25)
def set_paper(c, t):
    '''Infographic paper backdrop for hand-drawn charts.'''
    c.rectangle(-2400, -600, W+4800, H+1200); fill(c, hx('#D8CEBD')); glow(c, W/2, H/2, 1200, 700, hx('#EFE7D8'), 0.55)
    rnd = random.Random(12)
    for i in range(220): ell(c, rnd.uniform(-200, W+200), rnd.uniform(-100, H+100), rnd.uniform(1, 2.5), rnd.uniform(1, 2.5)); fill(c, hx('#7A6A55'), 0.18)

# ================================================================ light & shadow
def lightmap(c, ambient, lights, f=4):
    '''Lighting pass. Call inside the camera AFTER the scene and characters are drawn, BEFORE labels.
    ambient = (r,g,b) the frame is multiplied by: night (0.26,0.28,0.46), evening (0.60,0.52,0.60), dim room (0.40,0.38,0.58), day (0.80,0.78,0.82).
    lights = [(x, y, radius, (r,g,b), power), ...] in world coords. Smooth falloff + soft highlight roll-off + dither: no rings or bands.'''
    m = c.get_matrix(); sc = math.sqrt(abs(m.xx*m.yy-m.xy*m.yx)); w, h = W//f+1, H//f+1
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32); xs = xs*f+f/2; ys = ys*f+f/2
    L = np.empty((h, w, 3), np.float32); L[:] = ambient
    for x, y, r, col, p in lights:
        dx, dy = c.user_to_device(x, y); rr = max(1.0, r*sc)
        fall = np.clip(1-((xs-dx)**2+(ys-dy)**2)/(rr*rr), 0, 1)**2
        L += fall[..., None]*(np.array(col, np.float32)*p)
    k = 0.8; over = L > k; L[over] = k+(1-k)*(1-np.exp(-(L[over]-k)/(1-k)))
    L = np.clip(L*255+np.random.uniform(-0.6, 0.6, L.shape), 0, 255).astype(np.uint8)
    buf = np.empty((h, w, 4), np.uint8); buf[..., 0] = L[..., 2]; buf[..., 1] = L[..., 1]; buf[..., 2] = L[..., 0]; buf[..., 3] = 255
    sm = cairo.ImageSurface.create_for_data(memoryview(buf), cairo.FORMAT_RGB24, w, h)
    c.save(); c.identity_matrix(); c.scale(f, f); c.set_source_surface(sm, 0, 0); c.get_source().set_filter(cairo.FILTER_BILINEAR)
    c.set_operator(cairo.OPERATOR_MULTIPLY); c.paint(); c.restore(); sm.finish()
def bloom(c, x, y, r, col=(1, 0.9, 0.6), a=0.5):          # additive glow: lamps, screens, moon, coins, stars
    g = cairo.RadialGradient(x, y, 0, x, y, r); g.add_color_stop_rgba(0, *col, a); g.add_color_stop_rgba(1, *col, 0)
    c.save(); c.set_operator(cairo.OPERATOR_ADD); c.set_source(g); c.arc(x, y, r, 0, 2*PI); c.fill(); c.restore()
def soft_shadow(c, x, y, w=95, light_x=None, a=0.45):
    '''Soft ground shadow (gradient falloff + dark contact core). Leans and stretches away from a light at light_x.'''
    dx = 0 if light_x is None else clamp((x-light_x)/500, -1, 1)*w*1.1
    for ox, sx, sy, al in ((dx, w*(1+abs(dx)/w*0.7), w*0.2, a*0.75), (dx*0.15, w*0.6, w*0.1, a)):
        c.save(); c.translate(x+ox, y+3); c.scale(sx, sy); g = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
        g.add_color_stop_rgba(0, 0, 0, 0, al); g.add_color_stop_rgba(0.6, 0, 0, 0, al*0.5); g.add_color_stop_rgba(1, 0, 0, 0, 0)
        c.set_source(g); c.arc(0, 0, 1, 0, 2*PI); c.fill(); c.restore()
def light_shaft(c, x0, y0, w0, x1, y1, w1, col=(1, 0.95, 0.75), a=0.22):   # god-ray from a window/lamp to the floor
    g = cairo.LinearGradient(x0, y0, x1, y1); g.add_color_stop_rgba(0, *col, a); g.add_color_stop_rgba(1, *col, 0)
    c.save(); c.set_operator(cairo.OPERATOR_ADD); poly(c, [(x0-w0/2, y0), (x0+w0/2, y0), (x1+w1/2, y1), (x1-w1/2, y1)]); c.set_source(g); c.fill(); c.restore()
def grade(c, col, a=0.18):                                 # colour grade in screen space: warm (1,.75,.45), cold (.45,.6,1)
    c.save(); c.identity_matrix(); c.set_operator(cairo.OPERATOR_SOFT_LIGHT); c.set_source_rgba(*col, a); c.paint(); c.restore()

# ================================================================ motion helpers, arms, hands
def spring(k, bounce=2.2, damp=5.5):                       # 0 -> 1 with overshoot and settle (gestures, pops, landings)
    k = clamp(k); return 1-math.exp(-damp*k)*math.cos(bounce*PI*k)
def kf(t, keys, ease=eio):
    '''Keyframes [(time, value), ...], value = number or tuple. kf(t, [(0, (-108, -150)), (0.4, (-150, -430))], spring) animates a hand.'''
    if t <= keys[0][0]: return keys[0][1]
    for a, b in zip(keys, keys[1:]):
        if t <= b[0]:
            k = ease(pr(t, a[0], b[0]))
            return tuple(lerp(u, v, k) for u, v in zip(a[1], b[1])) if isinstance(a[1], tuple) else lerp(a[1], b[1], k)
    return keys[-1][1]
def elbow(sx, sy, tx, ty, l1=118, l2=118, bend=1):         # two-bone IK: returns the elbow point
    d = math.hypot(tx-sx, ty-sy)+1e-6
    if d > l1+l2-1: l1 = l2 = d/2+0.5
    a = math.acos(clamp((l1*l1+d*d-l2*l2)/(2*l1*d), -1, 1)); base = math.atan2(ty-sy, tx-sx)+(a if bend < 0 else -a)
    return sx+math.cos(base)*l1, sy+math.sin(base)*l1
def _finger(c, x0, y0, ang, ln, skin, w=7):
    x1, y1 = x0+math.cos(ang)*ln, y0+math.sin(ang)*ln
    for lw, col in ((w+6, INK), (w, skin)): line(c, x0, y0, x1, y1, lw, col)
def hand(c, x, y, ang, pose='fist', skin=(0.95, 0.77, 0.56), flip=1, s=1.0, t=0):
    '''Small character hand at the wrist (x,y), pointing along ang. pose: fist|open|point|thumb|flat|grip.'''
    c.save(); c.translate(x, y); c.rotate(ang); c.scale(s, s*flip)
    if pose == 'open':
        for i, a in enumerate((-0.55, -0.2, 0.15, 0.5)): _finger(c, 14, a*10, a+0.05*math.sin(t*9+i), 25, skin)
        _finger(c, 4, -8, -1.25, 18, skin, 8)
    elif pose == 'point':
        _finger(c, 14, -4, -0.06, 32, skin, 8); _finger(c, 4, -8, -1.2, 15, skin, 8)
    elif pose == 'thumb':
        _finger(c, 6, -8, -1.5, 26, skin, 9)
    elif pose == 'flat':
        for a in (-0.12, 0.0, 0.12): _finger(c, 14, a*30, a*0.3, 24, skin)
        _finger(c, 6, -8, -0.9, 16, skin, 8)
    E(c, 8, 0, 17, 15 if pose != 'flat' else 11, skin, 5)
    if pose in ('fist', 'thumb', 'point', 'grip'):
        for i in range(3 if pose != 'point' else 2): line(c, 15, 1+i*5-(0 if pose != 'point' else -3), 23, 1+i*5-(0 if pose != 'point' else -3), 2.5, INK, 0.55)
        if pose in ('fist', 'grip'): E(c, 10, -11, 8, 6, skin, 4)
    c.restore()
def big_hand(c, x, y, s=1.0, rot=0.0, curl=0.0, pinch=0.0, sleeve=(0.93, 0.9, 0.84), skin=(0.95, 0.77, 0.56)):
    '''Close-up hand for inserts. (x,y) = centre of the palm; the forearm leaves to the right before rotation (rot=-PI/2: comes from the top).
    curl 0..1 closes the fingers, pinch 0..1 brings thumb and index together (sprinkling, holding a coin/card).'''
    c.save(); c.translate(x, y); c.rotate(rot); c.scale(s, s)
    R(c, 70, -62, 1500, 124, 30, sleeve, 7); R(c, 52, -72, 60, 144, 14, shade(sleeve, 1.06), 7)
    for i, oy in enumerate((-48, -17, 14, 44)):
        a0 = PI+0.12*(i-1.5)-(curl*1.1+pinch*(0.9 if i == 0 else 0.25)); ln = (62, 70, 66, 54)[i]
        kx, ky = -62+math.cos(a0)*ln, oy+math.sin(a0)*ln*-1
        a1 = a0-(curl*1.4+pinch*(1.0 if i == 0 else 0.3)); tx, ty = kx+math.cos(a1)*ln*0.8, ky-math.sin(a1)*ln*0.8
        for lw, col in ((36, INK), (24, skin)):
            c.move_to(-56, oy); c.line_to(kx, ky); c.line_to(tx, ty); stroke(c, lw, col)
    R(c, -82, -74, 150, 148, 44, skin, 7)
    a0 = PI*0.72-pinch*0.55; kx, ky = -30+math.cos(a0)*74, 62+math.sin(a0)*74; a1 = a0+0.5+pinch*0.9; tx, ty = kx+math.cos(a1)*52, ky+math.sin(a1)*52*0.6
    for lw, col in ((40, INK), (28, skin)):
        c.move_to(-20, 54); c.line_to(kx, ky); c.line_to(tx, ty); stroke(c, lw, col)
    c.move_to(-40, -30); c.curve_to(-10, -14, -4, 20, -30, 40); stroke(c, 4, INK, 0.35)
    c.restore()

# ================================================================ transitions (k = 0..1; fa / fb draw a whole frame: fa = lambda c: shotA(c, time))
def to_screen(C, x, y): return ((x-C[0])*C[2]+W/2, (y-C[1])*C[2]+H/2)      # world point -> screen point for camera C
def layer(c, fn, alpha=1.0):                               # draw fn(c) as its own layer with opacity (dissolves)
    if alpha <= 0.003: return
    c.push_group(); fn(c); c.pop_group_to_source(); c.paint_with_alpha(clamp(alpha))
def xfade(c, k, fa, fb):                                   # dissolve A -> B
    if k < 0.997: fa(c)
    layer(c, fb, eio(k))
def zoom_streaks(c, k, cx=W/2, cy=H/2, col=(1, 1, 1), n=40):   # radial speed lines for pushes through things
    if k <= 0: return
    rnd = random.Random(5)
    for i in range(n):
        a = rnd.uniform(0, 2*PI); r0 = rnd.uniform(260, 700); r1 = r0+rnd.uniform(200, 700)
        line(c, cx+math.cos(a)*r0, cy+math.sin(a)*r0, cx+math.cos(a)*r1, cy+math.sin(a)*r1, rnd.uniform(3, 12), col, 0.3*k)
def push_through(c, k, fa, fb, focus, layers=('#F6EFDD', '#C4683F', '#E0B04A', '#8A5A3C')):
    '''Camera flies from scene A into `focus` (screen point: a window, door, screen, eye, keyhole), passes through the wall -
    its cut layers (plaster, brick, insulation, wood) sweep past as growing frames - and lands in scene B, which settles from a slight zoom.'''
    fx, fy = focus; za = 1+ein(pr(k, 0, 0.62))*11; zb = 1+(1-eout(pr(k, 0.4, 1)))*1.3
    def A(c): c.save(); c.translate(fx, fy); c.scale(za, za); c.translate(-fx, -fy); fa(c); c.restore()
    def B(c): c.save(); c.translate(W/2, H/2); c.scale(zb, zb); c.translate(-W/2, -H/2); fb(c); c.restore()
    if k < 0.6: A(c)
    layer(c, B, pr(k, 0.44, 0.6))
    cx, cy = lerp(fx, W/2, eio(pr(k, 0.2, 0.6))), lerp(fy, H/2, eio(pr(k, 0.2, 0.6)))
    for i, col in enumerate(layers):
        sz = math.exp((k-0.40-i*0.04)*17)*0.35
        if 0.3 < sz < 3.2:
            c.save(); c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            for q in (1.34, 1.0): c.rectangle(cx-W/2*sz*q, cy-H/2*sz*q, W*sz*q, H*sz*q)
            c.set_source_rgb(*hx(col)); c.fill_preserve(); stroke(c, 7); c.restore()
    zoom_streaks(c, 1-abs(k-0.5)/0.3, cx, cy)
def match_zoom(c, k, fa, fb, oa, ob, big=1300):
    '''Shape match cut: zoom into a round object of A, oa=(x,y,r) on screen, until it fills the frame; dissolve into B zoomed on ITS round
    object ob=(x,y,r); pull back. Coin -> moon, plate -> clock, eye -> planet, button -> wheel.'''
    def part(c, fn, o, kk):
        z = (big/o[2])**kk; c.save(); c.translate(lerp(o[0], W/2, kk), lerp(o[1], H/2, kk)); c.scale(z, z); c.translate(-o[0], -o[1]); fn(c); c.restore()
    if k < 0.6: part(c, fa, oa, ein(pr(k, 0, 0.6)))
    layer(c, lambda c: part(c, fb, ob, 1-eout(pr(k, 0.4, 1))), pr(k, 0.4, 0.6))
def morph_points(c, k, A, B, ra=4, rb=3, cola=(1, 1, 1), colb=(1, 1, 0.92), arc=90, t=0, twinkle=0.0):
    '''Particle match cut: point i travels from A[i] to B[i] (screen coords) on an arc while size and colour change.
    Draw it on top of xfade(c, k, fa, fb). Salt -> stars, coins -> city lights, rain -> numbers, sparks -> fireflies.'''
    rnd = random.Random(7)
    for (ax, ay), (bx, by) in zip(A, B):
        d = rnd.random()*0.25; kk = eio(pr(k, d, d+0.75)); wob = math.sin(kk*PI)
        x = lerp(ax, bx, kk)+wob*arc*(rnd.random()-0.5)*2; y = lerp(ay, by, kk)-wob*arc*rnd.random()
        r = lerp(ra, rb, kk)*(1+twinkle*kk*0.5*math.sin(t*7+ax))
        ell(c, x, y, r, r); fill(c, tuple(lerp(u, v, kk) for u, v in zip(cola, colb)))
def wipe_by(c, k, fa, fb, draw_obj, w=600):
    '''Object wipe: something big crosses the frame left -> right (a bus, a hand, a door, a banknote) and scene B is revealed behind it.
    draw_obj(c, x) draws the object with its centre at screen x.'''
    x = lerp(-w, W+w, eio(k)); fa(c)
    c.save(); c.rectangle(0, 0, max(0, x), H); c.clip(); fb(c); c.restore(); draw_obj(c, x)

# ================================================================ atmosphere: smoke, steam, fire, sparks
SMOKE_KINDS = {   # (colour when born, colour when old, opacity) - pass kind='...' or cols=((r,g,b),(r,g,b)) for your own
    'steam': ((1.0, 1.0, 1.0), (0.86, 0.9, 1.0), 0.55),      # kettle, coffee, shower, hot food
    'smoke': ((0.62, 0.62, 0.66), (0.80, 0.80, 0.83), 0.50),  # chimney, exhaust, candle out
    'dark':  ((0.10, 0.09, 0.10), (0.36, 0.35, 0.38), 0.75),  # burnt toast, tyre fire, explosion, crash
    'fire':  ((0.30, 0.20, 0.16), (0.52, 0.50, 0.53), 0.65),  # smoke above flames (warm at the base)
    'toxic': ((0.55, 0.92, 0.35), (0.32, 0.62, 0.30), 0.45),  # poison, scam, "toxic debt"
    'magic': ((0.85, 0.62, 1.00), (0.48, 0.72, 1.00), 0.50),  # transformation, idea, dream
    'money': ((0.62, 0.88, 0.55), (0.45, 0.72, 0.45), 0.42),  # cash vapour, "money evaporates"
    'dust':  ((0.84, 0.74, 0.58), (0.76, 0.69, 0.58), 0.45),  # car skid, falling building, desert
}
def smoke(c, t, x, y, kind='steam', rate=16, life=2.4, rise=260, spread=60, size=44, wind=30, a=None, seed=1,
          style='soft', cols=None, start=-99, stop=1e9):
    '''Rising plume of puffs from (x,y), deterministic in t. rise = px climbed over a puff's life, spread = sideways wander,
    size = radius at birth (grows ~2x), wind = sideways drift (px, +right). Puffs are born only between start and stop (bursts).
    style 'soft' = realistic gradient puffs; 'toon' = flat cartoon cloud with one merged ink outline.'''
    c0, c1, a0 = SMOKE_KINDS.get(kind, SMOKE_KINDS['steam'])
    if cols: c0, c1 = cols
    if a is not None: a0 = a
    i0 = max(0, int(math.floor((max(t-life, start)+99)*rate))); i1 = int(math.floor((min(t, stop)+99)*rate))
    P = []
    for i in range(i0, i1+1):
        b = i/rate-99
        if b < start or b > stop or b > t: continue
        age = t-b; u = age/life
        if u >= 1: continue
        r_ = random.Random(seed*100003+i); sw = r_.uniform(1.4, 3.0); ph = r_.uniform(0, 6.3)
        px = x+r_.uniform(-1, 1)*spread*0.25+wind*u*u+spread*u*math.sin(age*sw+ph)
        py = y-rise*(1.4*u-0.4*u*u)
        rr = size*(0.35+1.4*u)*r_.uniform(0.8, 1.2)
        al = a0*min(1, u/0.1)*(1-u)**1.2
        P.append((px, py, rr, u, al))
    if style == 'toon':
        for px, py, rr, u, al in P: ell(c, px, py, rr*(1-u**3)+5, rr*(1-u**3)+5); fill(c, INK)
        for px, py, rr, u, al in P: ell(c, px, py, rr*(1-u**3), rr*(1-u**3)); fill(c, tuple(lerp(p, q, u) for p, q in zip(c0, c1)))
        for px, py, rr, u, al in P: ell(c, px-rr*0.3, py-rr*0.3, rr*0.35*(1-u**3), rr*0.25*(1-u**3)); fill(c, (1, 1, 1), 0.25)
        return
    for px, py, rr, u, al in P:                                                 # volumetric puff: lit top, denser darker underside
        col = tuple(lerp(p, q, u) for p, q in zip(c0, c1))
        g = cairo.RadialGradient(px-rr*0.25, py-rr*0.35, 0, px, py, rr)
        g.add_color_stop_rgba(0, *shade(col, 1.18), al); g.add_color_stop_rgba(0.5, *col, al*0.8); g.add_color_stop_rgba(0.8, *shade(col, 0.82), al*0.35)
        g.add_color_stop_rgba(1, *shade(col, 0.8), 0)
        c.set_source(g); c.arc(px, py, rr, 0, 2*PI); c.fill()
def fire(c, t, x, y, w=90, h=170, seed=0, embers=True, glow_a=0.35):
    '''Flames standing on (x,y): three nested flickering layers + embers + glow. Put smoke(kind='fire') above it.'''
    rnd = random.Random(seed); phs = [rnd.uniform(0, 10) for _ in range(5)]
    bloom(c, x, y-h*0.35, h*1.7, (1, 0.55, 0.2), glow_a)
    for k, col in ((1.0, hx('#D9442B')), (0.72, hx('#F28A2E')), (0.45, hx('#FFD866'))):
        for j in range(5):
            ph = phs[j]; fx = x+(j-2)*w*0.22*k
            fl = 0.68+0.22*math.sin(t*9+ph)+0.12*math.sin(t*23+ph*2)
            hh = h*k*fl*(1.0, 0.72, 0.5, 0.78, 0.55)[(j+2) % 5]; ww = w*0.32*k; sway = 0.18*hh*math.sin(t*6+ph)
            c.move_to(fx-ww, y); c.curve_to(fx-ww, y-hh*0.5, fx+sway-ww*0.2, y-hh*0.7, fx+sway, y-hh)
            c.curve_to(fx+sway+ww*0.2, y-hh*0.7, fx+ww, y-hh*0.5, fx+ww, y); c.close_path(); fill(c, col)
    if embers:
        c.save(); c.set_operator(cairo.OPERATOR_ADD)
        for i in range(int((t+50)*9)-16, int((t+50)*9)+1):
            b = i/9-50; age = t-b
            if not 0 <= age < 1.6: continue
            r_ = random.Random(seed*7919+i); u = age/1.6
            ex = x+r_.uniform(-w*0.5, w*0.5)+40*math.sin(age*3+r_.random()*6)*u; ey = y-h*0.4-age*r_.uniform(150, 260)
            ell(c, ex, ey, 3.2*(1-u)+1, 3.2*(1-u)+1); fill(c, (1, 0.6+0.3*(1-u), 0.25), 0.9*(1-u))
        c.restore()
def sparks(c, t, x, y, t0, n=26, speed=700, grav=1500, life=0.8, col=(1, 0.85, 0.4), seed=3, up=True):
    '''Burst of sparks at time t0 from (x,y): short streaks with gravity (welding, coin hit, short circuit, explosion).'''
    age = t-t0
    if not 0 < age < life: return
    c.save(); c.set_operator(cairo.OPERATOR_ADD)
    for i in range(n):
        r_ = random.Random(seed*31+i); a = r_.uniform(-PI*0.95, -PI*0.05) if up else r_.uniform(0, 2*PI); v = speed*r_.uniform(0.4, 1)
        vx, vy = math.cos(a)*v, math.sin(a)*v; px, py = x+vx*age, y+vy*age+0.5*grav*age*age
        tx, ty = vx, vy+grav*age; L = math.hypot(tx, ty)+1e-6; ln = 0.035*L
        line(c, px, py, px-tx/L*ln, py-ty/L*ln, 4, col, 1-age/life)
    c.restore()
def smoke_wipe(c, k, fa, fb, col=(0.93, 0.93, 0.96), seed=9):
    '''Transition: a wall of soft smoke/steam swells up from the bottom, covers the frame, then thins out over scene B.'''
    fa(c) if k < 0.5 else fb(c)
    cover = math.sin(PI*clamp(k))
    rnd = random.Random(seed)
    for i in range(48):
        gx, gy = rnd.uniform(-100, W+100), rnd.uniform(-100, H+150); delay = (gy/H)*0.25
        kk = clamp((cover-(0.25-delay))/0.75) if k < 0.5 else cover
        if kk <= 0: continue
        rr = 520*kk*rnd.uniform(0.7, 1.2); py = gy+(1-kk)*500-k*260
        g = cairo.RadialGradient(gx, py, 0, gx, py, rr)
        g.add_color_stop_rgba(0, *col, 0.95); g.add_color_stop_rgba(0.6, *col, 0.7); g.add_color_stop_rgba(1, *col, 0)
        c.set_source(g); c.arc(gx, py, rr, 0, 2*PI); c.fill()
    full = clamp((cover-0.82)/0.18)
    if full > 0: c.set_source_rgba(*col, full); c.paint()

# ================================================================ depth: 3D props, cast shadows, ambient occlusion, haze
def box3d(c, x, y, w, h, d, col, vp=(W/2, -400), lw=6, front=None, top_col=None):
    '''Solid box. Front face: top-left (x,y), size w x h. Extruded d px toward the vanishing point vp (world coords):
    vp above -> top face shows, vp to the right -> right side shows. Same vp for all boxes in a scene = consistent perspective.
    front(c, x, y, w, h) decorates the front face (drawers, labels, windows). Returns (ox, oy) depth offset.'''
    cx, cy = x+w/2, y+h/2; L = math.hypot(vp[0]-cx, vp[1]-cy)+1e-6; ox, oy = (vp[0]-cx)/L*d, (vp[1]-cy)/L*d
    if oy < 0: P_(c, [(x, y), (x+w, y), (x+w+ox, y+oy), (x+ox, y+oy)], top_col or shade(col, 1.16), lw)
    else: P_(c, [(x, y+h), (x+w, y+h), (x+w+ox, y+h+oy), (x+ox, y+h+oy)], shade(col, 0.6), lw)
    if ox > 0.5: P_(c, [(x+w, y), (x+w+ox, y+oy), (x+w+ox, y+h+oy), (x+w, y+h)], shade(col, 0.72), lw)
    elif ox < -0.5: P_(c, [(x, y), (x+ox, y+oy), (x+ox, y+h+oy), (x, y+h)], shade(col, 0.72), lw)
    c.rectangle(x, y, w, h); g = cairo.LinearGradient(0, y, 0, y+h); g.add_color_stop_rgb(0, *shade(col, 1.04)); g.add_color_stop_rgb(1, *shade(col, 0.9))
    c.set_source(g); c.fill_preserve(); stroke(c, lw)
    if front: front(c, x, y, w, h)
    return ox, oy
def cyl3d(c, x, y, r, h, col, tilt=0.28, lt=-0.6, lw=6, top_col=None):
    '''Upright cylinder (mug, can, barrel, chimney, jar, coin): (x,y) = centre of the bottom. tilt = how much of the top is seen.
    Shaded round (dark on the side away from the light lt, specular stripe on the lit side). top_col = liquid / contents.'''
    ry = r*tilt
    def body():
        c.move_to(x-r, y-h); c.line_to(x-r, y); c.save(); c.translate(x, y); c.scale(r, ry); c.arc_negative(0, 0, 1, PI, 0); c.restore()
        c.line_to(x+r, y-h); c.save(); c.translate(x, y-h); c.scale(r, ry); c.arc_negative(0, 0, 1, 0, -PI); c.restore(); c.close_path()
    body(); fill(c, col)
    c.save(); body(); c.clip(); g = cairo.LinearGradient(x-r, 0, x+r, 0); s_ = 1 if lt > 0 else -1
    for o, a_ in ((0, 0.38), (0.5, 0.06), (1, 0.0)): g.add_color_stop_rgba(o if s_ > 0 else 1-o, 0, 0, 0, a_)
    c.rectangle(x-r, y-h-ry, 2*r, h+2*ry); c.set_source(g); c.fill()
    c.rectangle(x+s_*r*0.45-r*0.08, y-h, r*0.16, h); fill(c, (1, 1, 1), 0.28)
    c.restore(); body(); stroke(c, lw)
    if top_col: E(c, x, y-h, r, ry, shade(col, 1.12), lw); E(c, x, y-h, r*0.82, ry*0.76, top_col, max(2, lw-2))
    else: E(c, x, y-h, r, ry, shade(col, 1.15), lw)
def silhouette(c, fn, M=None, a=0.4, blur=5, fade=None, col=(0, 0, 0), clip=None):
    '''Flat soft shadow of whatever fn(c) draws (a character, a prop), transformed by cairo.Matrix M in the current space.
    fade = ((x0, y0, a0), (x1, y1, a1)) world points: opacity gradient. clip = (x, y, w, h) world rect to keep it on a wall/floor.'''
    f = max(1, int(blur)); sm = cairo.ImageSurface(cairo.FORMAT_ARGB32, W//f+2, H//f+2); cc = cairo.Context(sm)
    cc.scale(1/f, 1/f); cc.transform(c.get_matrix())
    if M is not None: cc.transform(M)
    cc.set_line_join(cairo.LINE_JOIN_ROUND); cc.set_line_cap(cairo.LINE_CAP_ROUND); fn(cc)
    pat = cairo.SurfacePattern(sm); pat.set_filter(cairo.FILTER_BILINEAR); pat.set_matrix(cairo.Matrix(1/f, 0, 0, 1/f, 0, 0))
    c.save()
    if clip: c.rectangle(*clip); c.clip()
    if fade:
        (x0, y0, a0), (x1, y1, a1) = fade; d0, d1 = c.user_to_device(x0, y0), c.user_to_device(x1, y1)
        src = cairo.LinearGradient(*d0, *d1); src.add_color_stop_rgba(0, *col, a0); src.add_color_stop_rgba(1, *col, a1)
    else: src = cairo.SolidPattern(*col, a)
    c.identity_matrix(); c.set_source(src); c.mask(pat); c.restore()
def object_shadow(c, fn, x0, floor_y, light, a=0.42, blur=6, squash=0.32, side='back', fade_h=420, clip=None):
    '''Real cast shadow on the floor/table plane at floor_y: the drawing fn is projected away from the point light (lx, ly).
    x0 = the object's centre x. The lower the light, the longer and more slanted the shadow. side='back' (shadow falls away
    from camera, light in front) or 'front' (light behind the object, shadow comes toward camera). Draw BEFORE the object.'''
    lx, ly = light; sx = clamp((x0-lx)/max(60, floor_y-ly), -2.5, 2.5); q = squash if side == 'back' else -squash
    M = cairo.Matrix(1, 0, -sx, q, sx*floor_y, floor_y*(1-q))
    silhouette(c, fn, M, a, blur, ((x0, floor_y, a), (x0+sx*fade_h, floor_y-q*fade_h, a*0.12)), clip=clip)
def wall_shadow(c, fn, light, k=1.4, dy=0, a=0.3, blur=8, clip=None):
    '''Shadow on the wall behind: fn is scaled k times away from the light point (bigger and softer, moves opposite to the light).
    Draw right after the wall, before furniture and characters. clip = wall rect so it does not spill onto the floor.'''
    lx, ly = light; silhouette(c, fn, cairo.Matrix(k, 0, 0, k, lx*(1-k), ly*(1-k)+dy), a, blur, clip=clip)
def ao(c, x0, x1, y, up=60, down=45, a=0.32):
    '''Ambient occlusion: darkening where two surfaces meet (wall/floor, object/table, box/box). Instant depth.'''
    for y1, aa in ((y-up, a), (y+down, a*0.8)):
        g = cairo.LinearGradient(0, y, 0, y1); g.add_color_stop_rgba(0, 0, 0, 0, aa); g.add_color_stop_rgba(1, 0, 0, 0, 0)
        c.rectangle(x0, min(y, y1), x1-x0, abs(y1-y)); c.set_source(g); c.fill()
def haze(c, col=(0.75, 0.8, 0.95), a=0.18):
    '''Aerial perspective: call between far layers and near layers - everything drawn before gets pushed back into the air.'''
    c.save(); c.identity_matrix(); c.set_source_rgba(*col, a); c.paint(); c.restore()
def pendant_lamp(c, x, y, length, ang, on=True, col=hx('#2F3B3A'), cone=0.22):
    '''Hanging lamp from the ceiling point (x, y), swinging by ang (rad, e.g. 0.3*sin(t*1.7)). Returns the bulb position
    in world coords -> feed it to lightmap, object_shadow and wall_shadow so every shadow swings with the lamp.'''
    bx, by = x+math.sin(ang)*length, y+math.cos(ang)*length
    line(c, x, y, bx, by, 4); c.save(); c.translate(bx, by); c.rotate(-ang)
    if on and cone > 0:
        g = cairo.LinearGradient(0, 44, 0, 1000); g.add_color_stop_rgba(0, 1, 0.92, 0.7, cone); g.add_color_stop_rgba(1, 1, 0.92, 0.7, 0)
        c.save(); c.set_operator(cairo.OPERATOR_ADD); poly(c, [(-70, 44), (70, 44), (520, 1000), (-520, 1000)]); c.set_source(g); c.fill(); c.restore()
    E(c, 0, 44, 24, 15, hx('#FFF3C4') if on else hx('#9AA3AE'), 5)
    P_(c, [(-24, -34), (24, -34), (96, 40), (-96, 40)], col, 6); R(c, -12, -46, 24, 16, 4, shade(col, 0.8), 4)
    c.restore(); return bx+44*math.sin(ang), by+44*math.cos(ang)

# ================================================================ post / render
rng = np.random.default_rng(3)
def _grain():
    buf = np.zeros((H, W, 4), np.uint8); buf[..., 3] = (rng.random((H, W))**3*46).astype(np.uint8)
    return cairo.ImageSurface.create_for_data(memoryview(buf), cairo.FORMAT_ARGB32, W, H), buf
GRAINS = [_grain() for _ in range(3)]
def post(c, i, dark=False):
    if not dark:
        g = cairo.RadialGradient(W/2, H/2, H*0.42, W/2, H/2, H*1.08)
        g.add_color_stop_rgba(0, 0, 0, 0, 0); g.add_color_stop_rgba(1, 0.05, 0.02, 0.08, 0.62)
        c.rectangle(0, 0, W, H); c.set_source(g); c.fill()
    c.set_source_surface(GRAINS[(i//2) % 3][0], 0, 0); c.paint_with_alpha(0.55)

def render(SHOTS, DUR, argv, dark=()):
    '''SHOTS = [(start_time, fn(c, local_t)), ...]. argv: ['stills', t1, t2...] or [out.mp4]. dark = shot fns without vignette.'''
    def frame(i):
        t = i/FPS; surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H); c = cairo.Context(surf)
        c.set_line_join(cairo.LINE_JOIN_ROUND); c.set_line_cap(cairo.LINE_CAP_ROUND)
        st, fn = [s for s in SHOTS if s[0] <= t+1e-6][-1]
        c.save(); fn(c, t-st); c.restore(); c.identity_matrix(); post(c, i, fn in dark)
        return surf
    if argv[0] == 'sheet':                                                     # one small contact sheet = cheap visual check
        ts = list(map(float, argv[1:])); cols = 3 if len(ts) > 4 else 2; tw = 480; th = tw*9//16; rows = -(-len(ts)//cols)
        S = cairo.ImageSurface(cairo.FORMAT_RGB24, tw*cols, th*rows); sc = cairo.Context(S)
        for k, tt in enumerate(ts):
            fr = frame(round(tt*FPS)); sc.save(); sc.translate((k % cols)*tw, (k//cols)*th); sc.scale(tw/W, tw/W)
            sc.set_source_surface(fr, 0, 0); sc.paint(); sc.restore()
            text(sc, f'{tt:.1f}s', (k % cols)*tw+10, (k//cols)*th+18, 20, (1, 1, 1), font=BRUSH, anchor='l', outline=4)
        S.write_to_png('sheet.png'); print('sheet.png'); return
    if argv[0] == 'stills':
        for tt in map(float, argv[1:]): frame(round(tt*FPS)).write_to_png(f's_{tt:05.2f}.png')
        return
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', argv[0]], stdin=subprocess.PIPE)
    for i in range(int(FPS*DUR)): ff.stdin.write(bytes(frame(i).get_data()))
    ff.stdin.close(); ff.wait(); print('done', argv[0])

# ================================================================ ready-made beats (call inside a camera; P = character dict)
def walk_in(c, t, P, x0=-180, x1=800, ground=880, s=0.86, light_x=None):
    '''Character walks in (7 half-steps, eases out), stops with a lean back and dust, then waves and talks (t > 1.6).'''
    xk = eout(pr(t, 0.0, 1.45)); gx = lerp(x0, x1, xk); wa = 1-pr(t, 1.3, 1.5); phs = xk*PI*7; d = 1 if x1 >= x0 else -1
    stop = pr(t, 1.45, 1.75); wave = spring(pr(t, 1.6, 1.9))
    Q = dict(P, yaw=P.get('yaw', 0.35*d*wa), t=t, mouth='talk' if (t > 1.7 and int(t*9) % 2) else P.get('mouth', 'smile'),
             walk=(phs, wa), bob=abs(math.sin(phs))*12*wa, lean=d*(0.07*wa-0.07*math.sin(stop*PI)*(1-stop)),
             hands=((-100+30*math.sin(phs)*wa, -150), (lerp(100-30*math.sin(phs)*wa, 130, wave), lerp(-150, -420+14*math.sin(t*22), wave))),
             hand_pose=('fist', 'open' if wave > 0.3 else 'fist'))
    soft_shadow(c, gx, ground, 80*s/0.86, light_x); character(c, gx, ground, s, Q)
    dust(c, x1, ground+4, pr(t, 1.42, 1.9), seed=3)
    return gx
def slide_out(c, t, P, x0=800, ground=880, t0=0.62, dist=760, s=0.86):
    '''Panic for t0 s, then the character silently slides out sideways (feet frozen) with speed lines and dust.'''
    sl = ein(pr(t, t0, t0+0.8)); gx = x0-dist*sl
    Q = dict(P, eyes='wide', mouth='grimace', brow='worry', look=(9, 0), lean=-0.05*pr(t, t0-0.1, t0+0.2), sweat=pr(t, 0.1, 0.35), sweat_y=30*pr(t, 0.4, 1.5))
    soft_shadow(c, gx, ground, 80*s/0.86); character(c, gx, ground, s, Q)
    if sl > 0:
        for j in range(3): line(c, gx+90+j*14, ground-320+j*90, gx+90+160*sl+j*30, ground-320+j*90, 6, (1, 1, 1), 0.5*(1-sl*0.5))
        dust(c, gx+60, ground+4, pr(t, t0, t0+0.6), 6, 90, seed=8)
    return gx
def black_card(c, t, words=('Three', 'dollars.'), x=700, y=600, size=110):
    '''Black punchline card: white handwritten words appear one by one. Pass the shot fn to render(..., dark=(...)).'''
    c.rectangle(0, 0, W, H); fill(c, (0, 0, 0))
    for i, wd in enumerate(words):
        k = pr(t, 0.08+i*0.34, 0.20+i*0.34)
        if k > 0: text(c, wd, x, y+10*(1-eout(k)), size, (1, 1, 1), font=BRUSH, anchor='l', a=k)
        x += text_w(c, wd+' ', size, BRUSH)
