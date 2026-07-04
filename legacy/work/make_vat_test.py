from PIL import Image, ImageOps
from pathlib import Path
image = Image.open(r"C:\Users\Burn Holiday\Documents\Butterfly Blu\Invoices\20260617_162300.jpg").convert("RGB")
w,h=image.size
left, top, right, bottom = int(w*0.02), int(h*0.385), int(w*0.985), int(h*0.595)
table = image.crop((left, top, right, bottom))
resample = getattr(Image, 'Resampling', Image).LANCZOS
table = table.resize((table.width*2, table.height*2), resample)
table = ImageOps.autocontrast(table.convert('L')).convert('RGB')
Path('work/vat-test').mkdir(exist_ok=True)
cols = {
  'code_desc': (0.00, 0.00, 0.50, 1.00),
  'qty': (0.49, 0.00, 0.64, 1.00),
  'unit_price': (0.62, 0.00, 0.76, 1.00),
  'vat': (0.80, 0.00, 0.92, 1.00),
}
for name, (lx,ty,rx,by) in cols.items():
    crop = table.crop((int(table.width*lx), int(table.height*ty), int(table.width*rx), int(table.height*by)))
    crop.save(f'work/vat-test/{name}.png')
print('saved')
