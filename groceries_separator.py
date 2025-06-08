from ultralytics import YOLO

# Load a pretrained YOLO11n model
model = YOLO("yolo11n.pt")

# Train the model on the COCO8 dataset for 100 epochs
#train_results = model.train(
    #data="configs/yolo_config.yaml",  # Path to dataset configuration file
    #epochs=10,  # Number of training epochs
    #imgsz=640,  # Image size for training
    #device=0, # Device to run on (e.g., 'cpu', 0, [0,1,2,3])sds
#)

# Evaluate the model's performance on the validation set
# metrics = model.val()

# Perform object detection on an image
results = model.train(data = "configs/yolo_config.yaml", epochs = 2)  # Predict on an image
#results[0].show()  # Display results

# Export the model to ONNX format for deployment
# path = model.export(format="onnx")  # Returns the path to the exported model