import sys; sys.path.insert(0, '.')
from PIL import Image
from ocr import ocr_image, parse_z_raporu
from utils import ocr_skorla

for s in ['sample_mikail.jpeg', 'sample_isa.jpeg']:
    img = Image.open(s).convert('RGB')
    tess = ocr_image(img)
    r = parse_z_raporu(tess)
    print(f'{s}: score={ocr_skorla(tess):.0f} KK={r["kredi_karti"]:.2f}')
