import numpy as np
from sklearn.cluster import DBSCAN
from collections import defaultdict

class ProductGrouper:
    def __init__(self, proximity_threshold=0.1):
        self.proximity_threshold = proximity_threshold
        
    def group_detections(self, detections):
        """
        Group detections based on spatial proximity
        detections: list of (class_id, x_center, y_center, width, height, confidence)
        """
        if len(detections) == 0:
            return []
            
        # Extract coordinates for clustering
        coords = np.array([[det[1], det[2]] for det in detections])  # x_center, y_center
        
        # Use DBSCAN clustering to group nearby boxes
        clustering = DBSCAN(eps=self.proximity_threshold, min_samples=1).fit(coords)
        
        # Group detections by cluster
        groups = defaultdict(list)
        for i, label in enumerate(clustering.labels_):
            groups[label].append(detections[i])
            
        return list(groups.values())
    
    def group_by_vertical_alignment(self, detections):
        """
        Group detections that are vertically aligned (common for product listings)
        """
        groups = []
        sorted_dets = sorted(detections, key=lambda x: x[2])  # Sort by y_center
        
        current_group = []
        current_y = None
        
        for det in sorted_dets:
            y_center = det[2]
            
            # If first detection or within vertical threshold
            if current_y is None or abs(y_center - current_y) < self.proximity_threshold:
                current_group.append(det)
                if current_y is None:
                    current_y = y_center
            else:
                # Start new group
                if current_group:
                    groups.append(current_group)
                current_group = [det]
                current_y = y_center
                
        # Add last group
        if current_group:
            groups.append(current_group)
            
        return groups
    
    def extract_product_info(self, group):
        """
        Extract structured product information from a group of detections
        """
        product = {
            'name': None,
            'price': None,
            'weight': None,
            'discount': None,
            'date': None
        }
        
        class_map = {0: 'name', 1: 'price', 2: 'weight', 3: 'discount', 4: 'date'}
        
        for det in group:
            class_id = det[0]
            if class_id in class_map:
                product[class_map[class_id]] = det
                
        return product