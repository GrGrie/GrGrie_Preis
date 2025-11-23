from pathlib import Path
from typing import Union, List, Dict, Any
import numpy as np
from paddleocr import PaddleOCR, TextRecognition


class PaddleOcrService:
    """
    OCR service for German text recognition using PaddleOCR.
    
    This class provides an interface for performing optical character recognition
    on images containing German text.
    """

    def __init__(self):
        """
        Initialize the PaddleOCR service.
        """
        
        try:
            self._ocr = TextRecognition(model_name="latin_PP-OCRv5_mobile_rec")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize PaddleOCR: {e}")
    
    
    def extract_text(
        self, 
        image: Union[str, Path, np.ndarray],
        min_confidence: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Extract text from image with structured output.
        
        Args:
            image: Path to image file or numpy array
            min_confidence: Minimum confidence threshold to include results
            
        Returns:
            List of dictionaries containing:
            - 'text': Recognized text
            - 'confidence': Confidence score (0-1)
            - 'bbox': Bounding box coordinates
        """
        results = self.infer(image)
        
        extracted = []
        for line in results:
            if line is None:
                continue
                
            bbox, (text, confidence) = line
            
            if confidence >= min_confidence:
                extracted.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': bbox
                })
        
        return extracted



def main():
    rec_dir = "models/ocr/latin_PP-OCRv5_mobile_rec"  # Path to the downloaded model directory
    img = "eval-results/crops/crop001_page_01.png"

    ocr = PaddleOCR(
        text_recognition_model_name="latin_PP-OCRv5_mobile_rec",
        text_recognition_model_dir=rec_dir,
        use_doc_orientation_classify=False,
        use_textline_orientation=False,
        use_doc_unwarping=False
    )
    
    print("\n=== Structured Results ===")
    output = ocr.predict(img)
    result = output[0]
    
    texts = result['rec_texts']
    scores = result['rec_scores']
    
    # Print text with confidence scores
    print("\n=== Text with Confidence ===")
    for text, score in zip(texts, scores):
        print(f"{text:30s} (confidence: {score:.4f})")
    
    # Get all text as a single string
    all_text = "\n".join(texts)
    print("\n=== All Extracted Text ===")
    print(all_text)
    
    # Or as a single line
    single_line = " ".join(texts)
    print("\n=== Single Line ===")
    print(single_line)
    
    high_confidence_texts = [text for text, score in zip(texts, scores) if score > 0.95]
    print("\n=== High Confidence Text (> 0.95) ===")
    print(" ".join(high_confidence_texts))
        
        
if __name__ == "__main__":
    main()