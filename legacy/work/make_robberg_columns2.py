from PIL import Image, ImageOps
from pathlib import Path
image = Image.open(r"C:\Users\Burn Holiday\Documents\Butterfly Blu\Invoices\20260617_181206.jpg").convert("RGB")
w,h=image.size
left, top, right, bottom = int(w*0.03), int(h*0.325), int(w*0.965), int(h*0.56)
table = image.crop((left, top, right, bottom))
resample = getattr(Image, 'Resampling', Image).LANCZOS
table = table.resize((table.width*2, table.height*2), resample)
table = ImageOps.autocontrast(table.convert('L')).convert('RGB')
Path('work/robberg-crops').mkdir(exist_ok=True)
for name, box in {
  'qty_wide': (0.45, 0.00, 0.62, 1.00),
  'desc_no_qty': (0.17, 0.00, 0.49, 1.00),
  'code_desc_qty': (0.00, 0.00, 0.62, 1.00),
}.items():
    lx,ty,rx,by=box
    crop = table.crop((int(table.width*lx), int(table.height*ty), int(table.width*rx), int(table.height*by)))
    crop.save(f'work/robberg-crops/{name}.png')
print('saved')
