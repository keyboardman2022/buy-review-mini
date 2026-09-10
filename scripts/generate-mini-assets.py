"""Generate the small, original geometric assets used by the native client."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'miniprogram' / 'assets'
OUT.mkdir(parents=True, exist_ok=True)

for name in ('feed', 'wish', 'approval', 'profile'):
    for active, color in ((False, '#777d73'), (True, '#e9683b')):
        im = Image.new('RGBA', (192, 192))
        d = ImageDraw.Draw(im)
        if name == 'feed':
            d.rounded_rectangle((28, 32, 164, 138), radius=28, outline=color, width=11)
            d.line((52, 135, 48, 163, 82, 138), fill=color, width=11)
            for x in (62, 96, 130): d.ellipse((x-7, 78, x+7, 92), fill=color)
        elif name == 'wish':
            d.rounded_rectangle((30, 61, 162, 162), radius=19, outline=color, width=11)
            d.arc((61, 21, 131, 105), 180, 360, fill=color, width=11)
            d.line((70, 104, 86, 120, 119, 89), fill=color, width=10, joint='curve')
        elif name == 'approval':
            d.rounded_rectangle((39, 29, 153, 165), radius=18, outline=color, width=11)
            d.rounded_rectangle((67, 18, 125, 47), radius=9, fill=color)
            d.line((64, 101, 87, 124, 130, 78), fill=color, width=11, joint='curve')
        else:
            d.ellipse((64, 25, 128, 89), outline=color, width=11)
            d.arc((36, 102, 156, 198), 180, 360, fill=color, width=11)
            d.line((38, 152, 154, 152), fill=color, width=11)
        im.resize((64,64), Image.Resampling.LANCZOS).save(OUT / f'tab-{name}{"-active" if active else ""}.png')

im = Image.new('RGBA', (560, 360))
d = ImageDraw.Draw(im)
d.ellipse((75, 50, 465, 340), fill='#f3eee1')
d.rounded_rectangle((175, 69, 381, 275), radius=14, fill='#fefdf8', outline='#d5c5a8', width=4)
for y in (107, 137, 167): d.line((207, y, 327, y), fill='#d5c5a8', width=7)
d.rounded_rectangle((105, 157, 433, 307), radius=35, fill='#edaa6d', outline='#9c593c', width=5)
d.rounded_rectangle((342, 194, 452, 259), radius=20, fill='#ffdab0', outline='#9c593c', width=5)
d.ellipse((375, 216, 393, 234), fill='#9c593c')
for x in (202, 280): d.ellipse((x, 218, x+12, 234), fill='#533d30')
d.arc((227, 226, 269, 259), 0, 180, fill='#533d30', width=5)
d.ellipse((409, 56, 466, 113), fill='#f6ca69')
im.save(OUT / 'empty-wallet.png')

font = Path('C:/Windows/Fonts/msyh.ttc')
if not font.exists(): raise SystemExit('Microsoft YaHei font required for the Chinese fallback card')
im = Image.new('RGB', (1000, 800), '#f5f2ea')
d = ImageDraw.Draw(im)
d.rounded_rectangle((40, 40, 960, 760), radius=26, fill='white')
def label(pos, text, size, color): d.text(pos, text, font=ImageFont.truetype(str(font), size), fill=color)
label((85, 80), '买前问问 / 一起拿个主意', 32, '#66695f')
wallet = Image.open(OUT / 'empty-wallet.png').resize((420,270))
im.paste(wallet, (65,200), wallet)
label((510, 235), '这件，值得买吗？', 40, '#282d26')
label((510, 310), '想听听你的理由', 32, '#72766b')
d.line((85, 556, 915, 556), fill='#e1dfd6', width=2)
d.rounded_rectangle((85, 602, 915, 708), radius=16, fill='#e9683b')
label((276, 627), '打开查看这次审批', 40, 'white')
im.save(OUT / 'share-fallback.png')
print('Generated 8 tab icons, wallet illustration and share fallback')
