import sys, math
from PIL import Image, ImageDraw
out = sys.argv[1]; png = sys.argv[2]
S = 1024
img = Image.new("RGBA", (S, S), (0,0,0,0))
# radial gradient #2563eb -> #7c3aed, center (32,32) radius 30 in 64-space
c0 = (0x25,0x63,0xeb); c1 = (0x7c,0x3a,0xed)
grad = Image.new("RGBA", (S, S))
px = grad.load()
cx = cy = S/2; R = S*30/64
for y in range(S):
    for x in range(S):
        t = min(1.0, math.hypot(x-cx, y-cy)/R)
        px[x,y] = tuple(int(c0[i]+(c1[i]-c0[i])*t) for i in range(3)) + (255,)
mask = Image.new("L", (S,S), 0)
d = ImageDraw.Draw(mask)
m = S*4/64; 
d.ellipse([m, m, S-m, S-m], fill=255)
img.paste(grad, (0,0), mask)
d2 = ImageDraw.Draw(img)
w = int(S*3/64)
d2.ellipse([m-w/2, m-w/2, S-m+w/2, S-m+w/2], outline=(0x00,0xd4,0xff,255), width=w)
sizes = [256,128,64,48,32,24,16]
big = img.resize((256,256), Image.LANCZOS)
big.save(png)
big.save(out, format="ICO", sizes=[(s,s) for s in sizes])
print("ok")
