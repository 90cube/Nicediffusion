from ....core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)
"""
CLIP Vision Service
이미지 분석 및 텍스트-이미지 매칭을 위한 CLIP 서비스
"""

import torch
from PIL import Image
from typing import List, Dict, Any, Optional
import numpy as np


class CLIPService:
    """CLIP Vision 서비스 - 이미지 분석 및 매칭"""
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.clip_model = None
        self.clip_processor = None
        self.is_loaded = False
        
    async def load_model(self):
        """CLIP 모델 로드"""
        try:
            from transformers import CLIPVisionModel, CLIPProcessor
            
            process_emoji(r"CLIP Vision 모델 로드 중...")
            
            # CLIP Vision 모델 로드
            self.clip_model = CLIPVisionModel.from_pretrained("openai/clip-vit-base-patch32")
            self.clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            
            # GPU로 이동
            if torch.cuda.is_available() and self.device == "cuda":
                self.clip_model = self.clip_model.to(self.device)
            
            self.is_loaded = True
            success(r"CLIP Vision 모델 로드 완료")
            
        except Exception as e:
            failure(f"CLIP Vision 모델 로드 실패: {e}")
            self.is_loaded = False
    
    def analyze_image(self, image: Image.Image) -> Dict[str, Any]:
        """이미지 분석"""
        if not self.is_loaded:
            return {"error": "CLIP 모델이 로드되지 않음"}
        
        try:
            # 이미지 전처리
            inputs = self.clip_processor(images=image, return_tensors="pt")
            
            # GPU로 이동
            if torch.cuda.is_available() and self.device == "cuda":
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # 특징 추출
            with torch.no_grad():
                features = self.clip_model(**inputs)
                image_features = features.pooler_output
            
            # 특징 벡터를 numpy로 변환
            feature_vector = image_features.cpu().numpy().flatten()
            
            return {
                "feature_vector": feature_vector,
                "feature_dim": len(feature_vector),
                "image_size": image.size,
                "success": True
            }
            
        except Exception as e:
            failure(f"이미지 분석 실패: {e}")
            return {"error": str(e), "success": False}
    
    def calculate_similarity(self, image1: Image.Image, image2: Image.Image) -> float:
        """두 이미지 간 유사도 계산"""
        if not self.is_loaded:
            return 0.0
        
        try:
            # 두 이미지 분석
            result1 = self.analyze_image(image1)
            result2 = self.analyze_image(image2)
            
            if not result1.get("success") or not result2.get("success"):
                return 0.0
            
            # 코사인 유사도 계산
            vec1 = result1["feature_vector"]
            vec2 = result2["feature_vector"]
            
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            return float(similarity)
            
        except Exception as e:
            failure(f"유사도 계산 실패: {e}")
            return 0.0
    
    def find_similar_regions(self, target_image: Image.Image, reference_images: List[Image.Image], 
                           threshold: float = 0.7) -> List[Dict[str, Any]]:
        """유사한 영역 찾기"""
        if not self.is_loaded:
            return []
        
        try:
            results = []
            target_features = self.analyze_image(target_image)
            
            if not target_features.get("success"):
                return results
            
            for i, ref_image in enumerate(reference_images):
                similarity = self.calculate_similarity(target_image, ref_image)
                
                if similarity >= threshold:
                    results.append({
                        "index": i,
                        "similarity": similarity,
                        "image": ref_image
                    })
            
            # 유사도 순으로 정렬
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results
            
        except Exception as e:
            failure(f"유사 영역 찾기 실패: {e}")
            return []
    
    def extract_image_attributes(self, image: Image.Image) -> Dict[str, Any]:
        """이미지 속성 추출 (색상, 구성, 스타일 등)"""
        if not self.is_loaded:
            return {}
        
        try:
            # 기본 이미지 분석
            analysis = self.analyze_image(image)
            
            if not analysis.get("success"):
                return {}
            
            # 추가 속성 분석
            attributes = {
                "size": image.size,
                "mode": image.mode,
                "feature_vector": analysis["feature_vector"],
                "dominant_colors": self._extract_dominant_colors(image),
                "brightness": self._calculate_brightness(image),
                "contrast": self._calculate_contrast(image)
            }
            
            return attributes
            
        except Exception as e:
            failure(f"이미지 속성 추출 실패: {e}")
            return {}
    
    def _extract_dominant_colors(self, image: Image.Image, num_colors: int = 5) -> List[tuple]:
        """주요 색상 추출"""
        try:
            # 이미지를 RGB로 변환
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 이미지를 numpy 배열로 변환
            img_array = np.array(image)
            
            # 픽셀을 2D 배열로 재구성
            pixels = img_array.reshape(-1, 3)
            
            # K-means 클러스터링으로 주요 색상 추출
            from sklearn.cluster import KMeans
            
            kmeans = KMeans(n_clusters=num_colors, random_state=42)
            kmeans.fit(pixels)
            
            # 클러스터 중심을 주요 색상으로 사용
            dominant_colors = kmeans.cluster_centers_.astype(int)
            
            return [tuple(color) for color in dominant_colors]
            
        except Exception as e:
            failure(f"주요 색상 추출 실패: {e}")
            return []
    
    def _calculate_brightness(self, image: Image.Image) -> float:
        """이미지 밝기 계산"""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            brightness = np.mean(img_array)
            return float(brightness)
            
        except Exception as e:
            failure(f"밝기 계산 실패: {e}")
            return 0.0
    
    def _calculate_contrast(self, image: Image.Image) -> float:
        """이미지 대비 계산"""
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            img_array = np.array(image)
            contrast = np.std(img_array)
            return float(contrast)
            
        except Exception as e:
            failure(f"대비 계산 실패: {e}")
            return 0.0
    
    def unload_model(self):
        """CLIP 모델 언로드"""
        if self.clip_model is not None:
            del self.clip_model
            self.clip_model = None
        
        if self.clip_processor is not None:
            del self.clip_processor
            self.clip_processor = None
        
        self.is_loaded = False
        success(r"CLIP Vision 모델 언로드 완료") 