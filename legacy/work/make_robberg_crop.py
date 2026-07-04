from PIL import Image, ImageDraw
from pathlib import Path
image = Image.open(r"C:\Users\Burn Holiday\Documents\Butterfly Blu\Invoices\20260617_181206.jpg").convert("RGB")
w,h=image.size
print(image.size)
# Crop invoice table area only.
box=(int(w*0.03), int(h*0.355), int(w*0.965), int(h*0.585))
crop=image.crop(box)
draw=ImageDraw.Draw(crop)
for rel,color in [(0.04,'red'),(0.16,'blue'),(0.42,'green'),(0.53,'orange'),(0.60,'purple'),(0.70,'brown'),(0.84,'pink'),(0.94,'cyan')]:
    x=int(crop.width*rel)
    draw.line((x,0,x,crop.height),fill=color,width=5)
preview=crop.resize((int(crop.width*0.4), int(crop.height*0.4)))
Path('work').mkdir(exist_ok=True)
preview.save('work/robberg-table-crop-preview.jpg')
print(crop.size, preview.size, box)
