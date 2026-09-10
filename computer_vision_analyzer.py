from loguru import logger

class ComputerVisionAnalyzer:
    """Computer Vision Analyzer for chart pattern recognition"""
    
    def __init__(self):
        self.enabled = False
        logger.debug("ComputerVisionAnalyzer initialized (stub)")
    
    def analyze(self, image_data):
        """Analyze chart image for patterns"""
        return {"patterns": [], "confidence": 0.0}
