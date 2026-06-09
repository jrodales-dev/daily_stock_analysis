import logging
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch.nn.functional as F
from typing import List, Dict

logger = logging.getLogger(__name__)

class SentimentPipeline:
    """
    Local NLP Pipeline using HuggingFace Transformers for financial sentiment analysis.
    Uses ProsusAI/finbert model.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SentimentPipeline, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self.model_name = "ProsusAI/finbert"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        try:
            logger.info(f"Loading NLP Model {self.model_name} on {self.device}...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name).to(self.device)
            self._initialized = True
            logger.info("NLP Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load NLP model: {e}")
            self._initialized = False

    def analyze(self, texts: List[str]) -> List[Dict[str, float]]:
        """
        Analyze sentiment of a list of texts.
        Returns a list of dictionaries with probabilities for positive, negative, neutral.
        """
        if not self._initialized or not texts:
            # Fallback if model failed to load
            return [{"positive": 0.0, "negative": 0.0, "neutral": 1.0, "label": "neutral"} for _ in texts]
            
        try:
            inputs = self.tokenizer(texts, padding=True, truncation=True, max_length=512, return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                
            probs = F.softmax(outputs.logits, dim=-1)
            
            # ProsusAI/finbert labels: 0 -> positive, 1 -> negative, 2 -> neutral
            results = []
            for prob in probs:
                prob_list = prob.cpu().tolist()
                pos, neg, neu = prob_list[0], prob_list[1], prob_list[2]
                
                # Determine label
                max_idx = prob.argmax().item()
                if max_idx == 0:
                    label = "positive"
                elif max_idx == 1:
                    label = "negative"
                else:
                    label = "neutral"
                    
                results.append({
                    "positive": pos,
                    "negative": neg,
                    "neutral": neu,
                    "label": label
                })
                
            return results
        except Exception as e:
            logger.error(f"Error during sentiment analysis: {e}")
            return [{"positive": 0.0, "negative": 0.0, "neutral": 1.0, "label": "error"} for _ in texts]
