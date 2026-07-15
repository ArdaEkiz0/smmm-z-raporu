import sys; sys.path.insert(0, '.')
from PIL import Image
from ocr import ocr_gorsel_isle_hibrit, parse_z_raporu
for s in ['sample_mikail.jpeg', 'sample_isa.jpeg']:
    img = Image.open(s).convert('RGB')
    text = ocr_gorsel_isle_hibrit(img)
    r = parse_z_raporu(text)
    print(f'{s}: KK={r["kredi_karti"]:.2f} Brut={r["brut"]:.2f}')
