from ultralytics import YOLO

model = YOLO("./runs/detect/train4/weights/best.pt")

result = model("C:/Users/Grigory G/Documents/Python/GrGriePreis/data/images/test/page_05.png", conf = 0.1)

names_dict = result[0].names
probs = result[0].probs

print(names_dict)
print(result)