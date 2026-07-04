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
table.save('work/robberg-crops/table.png')
cols = {
  'code': (0.00, 0.00, 0.17, 1.00),
  'desc': (0.15, 0.00, 0.51, 1.00),
  'qty': (0.49, 0.00, 0.61, 1.00),
  'unit_price': (0.61, 0.00, 0.75, 1.00),
  'vat': (0.76, 0.00, 0.90, 1.00),
  'total': (0.86, 0.00, 1.00, 1.00),
}
for name, (lx,ty,rx,by) in cols.items():
    crop = table.crop((int(table.width*lx), int(table.height*ty), int(table.width*rx), int(table.height*by)))
    crop.save(f'work/robberg-crops/{name}.png')
print('saved', table.size)
