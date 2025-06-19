from ultralytics import YOLO
from bbox_grouper import ProductGrouper
import cv2
import os

def run_inference_with_grouping(model_path, image_path, output_dir="test_results"):
    """Run inference and group related bounding boxes"""
    model = YOLO(model_path)
    grouper = ProductGrouper(proximity_threshold=0.075)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Run inference
    results = model(image_path, conf=0.1)
    
    # Extract detections
    detections = []
    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for i in range(len(boxes)):
                class_id = int(boxes.cls[i])
                x_center = float(boxes.xywhn[i][0])
                y_center = float(boxes.xywhn[i][1])
                width = float(boxes.xywhn[i][2])
                height = float(boxes.xywhn[i][3])
                confidence = float(boxes.conf[i])
                
                # Convert to absolute coordinates for visualization
                img_h, img_w = result.orig_shape
                x1 = int((x_center - width/2) * img_w)
                y1 = int((y_center - height/2) * img_h)
                x2 = int((x_center + width/2) * img_w)
                y2 = int((y_center + height/2) * img_h)
                
                detections.append((class_id, x_center, y_center, width, height, confidence, x1, y1, x2, y2))
    
    # Group detections
    groups = grouper.group_by_vertical_alignment(detections)

    # Limit each group to one detection per class (keep highest confidence)
    filtered_groups = []
    for group in groups:
        class_best = {}
        for det in group:
            class_id = det[0]
            conf = det[5]
            if (class_id not in class_best) or (conf > class_best[class_id][5]):
                class_best[class_id] = det
        filtered_groups.append(list(class_best.values()))

    # Visualize grouped results
    image = cv2.imread(image_path)
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255), (128, 128, 0), (128, 0, 128), (0, 128, 128), (192, 192, 192), (128, 128, 128), (64, 64, 64)]
    class_names = ['Name', 'Price', 'Weight', 'Discount', 'Date']

    for group_idx, group in enumerate(filtered_groups):
        group_color = colors[group_idx % len(colors)]
        for det in group:
            class_id, _, _, _, _, confidence, x1, y1, x2, y2 = det
            cv2.rectangle(image, (x1, y1), (x2, y2), group_color, 2)
            label = f"{class_names[class_id]}: {confidence:.2f}"
            cv2.putText(image, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, group_color, 2)

    # Save result
    output_path = os.path.join(output_dir, f"grouped_{os.path.basename(image_path)}")
    cv2.imwrite(output_path, image)

    return filtered_groups

if __name__ == "__main__":
    model_path = "./runs/detect/lidl_products_v1/weights/best.pt"
    image_path = "lidl_prospekt_screenshots_20250608_140554/page_05.png"
    
    groups = run_inference_with_grouping(model_path, image_path)
    print(f"Found {len(groups)} product groups")