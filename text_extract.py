import os
import torch
from PIL import Image, ImageDraw
from pathlib import Path
import json

def simple_text_recognition(image_crop):
    """
    Simple placeholder for text recognition without external libraries
    You can replace this with your own ML model for text recognition
    """
    # For now, return placeholder text based on image properties
    width, height = image_crop.size
    # You could analyze pixel patterns, use a trained CNN, etc.
    return f"[TEXT_{width}x{height}]"

def process_image_with_bboxes(image_path, bboxes_path, output_dir):
    """
    Process a single image with its bounding boxes
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load image
    image = Image.open(image_path).convert("RGB")
    image_name = image_path.stem
    
    # Load bounding boxes
    bboxes = []
    if bboxes_path.exists():
        with open(bboxes_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 7:
                    img_name, class_name, conf, x1, y1, x2, y2 = parts
                    bboxes.append((img_name, class_name, float(conf), int(x1), int(y1), int(x2), int(y2)))
    
    if not bboxes:
        print(f"No bounding boxes found for {image_path}")
        return
    
    # Create annotated version of original image
    annotated_image = image.copy()
    draw = ImageDraw.Draw(annotated_image)
    
    # Process each bounding box
    results = []
    for i, (img_name, class_name, conf, x1, y1, x2, y2) in enumerate(bboxes):
        # Crop the bounding box region
        cropped_image = image.crop((x1, y1, x2, y2))
        
        # Generate text recognition (replace with your ML model)
        recognized_text = simple_text_recognition(cropped_image)
        
        # Save cropped image
        crop_filename = f"{image_name}_crop_{i:02d}_{class_name}.png"
        crop_path = output_dir / crop_filename
        cropped_image.save(crop_path)
        
        # Draw bounding box on annotated image
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
        draw.text((x1, y1-15), f"{class_name} {conf:.2f}", fill="red")
        
        # Store results
        results.append({
            "crop_id": i,
            "class_name": class_name,
            "confidence": conf,
            "bbox": [x1, y1, x2, y2],
            "crop_filename": crop_filename,
            "recognized_text": recognized_text
        })
        
        print(f"Crop {i}: {class_name} ({conf:.2f}) -> {recognized_text}")
    
    # Save annotated original image
    annotated_path = output_dir / f"{image_name}_annotated.png"
    annotated_image.save(annotated_path)
    
    # Save original image copy
    original_path = output_dir / f"{image_name}_original.png"
    image.save(original_path)
    
    # Save results as JSON
    results_path = output_dir / f"{image_name}_results.json"
    with open(results_path, "w") as f:
        json.dump({
            "original_image": str(original_path),
            "annotated_image": str(annotated_path),
            "total_crops": len(results),
            "crops": results
        }, f, indent=2)
    
    print(f"Processed {len(results)} crops from {image_path}")
    print(f"Results saved to {output_dir}")
    
    return results

def process_all_images_in_directory(test_results_dir, image_dir="data/test"):
    """
    Process all images in test_results directory using a single all_bboxes.txt file,
    loading original images from image_dir.
    """
    test_results_dir = Path(test_results_dir)
    image_dir = Path(image_dir)
    bboxes_file = test_results_dir / "all_bboxes.txt"
    image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}

    # Build a mapping from image name to list of bboxes
    bboxes_dict = {}
    if bboxes_file.exists():
        with open(bboxes_file, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 7:
                    img_name, class_name, conf, x1, y1, x2, y2 = parts
                    bbox = (img_name, class_name, float(conf), int(x1), int(y1), int(x2), int(y2))
                    bboxes_dict.setdefault(img_name, []).append(bbox)
    else:
        print(f"No all_bboxes.txt file found in {test_results_dir}")
        return

    # Process each image that has bboxes
    for img_name, bboxes in bboxes_dict.items():
        img_path = image_dir / img_name
        if img_path.suffix.lower() in image_extensions and img_path.exists():
            output_dir = test_results_dir / f"crops_{img_path.stem}"
            # Write a temporary bbox file for compatibility with process_image_with_bboxes
            temp_bbox_path = test_results_dir / f"temp_bboxes_{img_path.stem}.txt"
            with open(temp_bbox_path, "w") as f:
                for bbox in bboxes:
                    f.write(" ".join([str(x) for x in bbox]) + "\n")
            process_image_with_bboxes(img_path, temp_bbox_path, output_dir)
            temp_bbox_path.unlink()  # Remove temp file after processing
        else:
            print(f"Image file not found or unsupported: {img_path}")

if __name__ == "__main__":
    process_all_images_in_directory("test_results", image_dir="data/test")
