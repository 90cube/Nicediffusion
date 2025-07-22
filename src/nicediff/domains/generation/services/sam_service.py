from ....core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)
"""
Segment Anything Model (SAM) Service
이미지 세그멘테이션 및 마스크 생성을 위한 SAM 서비스
"""

import torch
from PIL import Image
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import cv2


class SAMService:
    """Segment Anything Model 서비스 - 이미지 세그멘테이션"""
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.sam_model = None
        self.sam_predictor = None
        self.is_loaded = False
        
    async def load_model(self, model_type: str = "vit_h"):
        """SAM 모델 로드"""
        try:
            from segment_anything import sam_model_registry, SamPredictor
            
            process_emoji(r"SAM 모델 로드 중...")
            
            # SAM 모델 타입에 따른 체크포인트 경로
            model_paths = {
                "vit_h": "models/sam/sam_vit_h_4b8939.pth",
                "vit_l": "models/sam/sam_vit_l_0b3195.pth", 
                "vit_b": "models/sam/sam_vit_b_01ec64.pth"
            }
            
            model_path = model_paths.get(model_type, model_paths["vit_h"])
            
            # 모델 로드
            self.sam_model = sam_model_registry[model_type](checkpoint=model_path)
            
            # GPU로 이동
            if torch.cuda.is_available() and self.device == "cuda":
                self.sam_model = self.sam_model.to(self.device)
            
            # 예측기 생성
            self.sam_predictor = SamPredictor(self.sam_model)
            
            self.is_loaded = True
            success(f"SAM 모델 로드 완료 ({model_type})")
            
        except Exception as e:
            failure(f"SAM 모델 로드 실패: {e}")
            self.is_loaded = False
    
    def set_image(self, image: Image.Image):
        """이미지 설정"""
        if not self.is_loaded:
            return False
        
        try:
            # PIL Image를 numpy 배열로 변환
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            image_array = np.array(image)
            
            # SAM 예측기에 이미지 설정
            self.sam_predictor.set_image(image_array)
            
            return True
            
        except Exception as e:
            failure(f"이미지 설정 실패: {e}")
            return False
    
    def generate_mask_from_point(self, point: Tuple[int, int], label: int = 1) -> Optional[np.ndarray]:
        """점 클릭으로 마스크 생성"""
        if not self.is_loaded or self.sam_predictor is None:
            return None
        
        try:
            # 입력 포인트 설정
            input_point = np.array([point])
            input_label = np.array([label])
            
            # 마스크 예측
            masks, scores, logits = self.sam_predictor.predict(
                point_coords=input_point,
                point_labels=input_label,
                multimask_output=True
            )
            
            # 가장 높은 점수의 마스크 선택
            best_mask_idx = np.argmax(scores)
            best_mask = masks[best_mask_idx]
            
            return best_mask
            
        except Exception as e:
            failure(f"포인트 마스크 생성 실패: {e}")
            return None
    
    def generate_mask_from_box(self, box: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """박스로 마스크 생성"""
        if not self.is_loaded or self.sam_predictor is None:
            return None
        
        try:
            # 박스 좌표 설정 (x1, y1, x2, y2)
            input_box = np.array(box)
            
            # 마스크 예측
            masks, scores, logits = self.sam_predictor.predict(
                box=input_box,
                multimask_output=True
            )
            
            # 가장 높은 점수의 마스크 선택
            best_mask_idx = np.argmax(scores)
            best_mask = masks[best_mask_idx]
            
            return best_mask
            
        except Exception as e:
            failure(f"박스 마스크 생성 실패: {e}")
            return None
    
    def generate_mask_from_points_and_box(self, points: List[Tuple[int, int]], 
                                        labels: List[int], 
                                        box: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """점과 박스를 조합하여 마스크 생성"""
        if not self.is_loaded or self.sam_predictor is None:
            return None
        
        try:
            # 입력 포인트 설정
            input_point = np.array(points)
            input_label = np.array(labels)
            
            # 마스크 예측
            if box is not None:
                input_box = np.array(box)
                masks, scores, logits = self.sam_predictor.predict(
                    point_coords=input_point,
                    point_labels=input_label,
                    box=input_box,
                    multimask_output=True
                )
            else:
                masks, scores, logits = self.sam_predictor.predict(
                    point_coords=input_point,
                    point_labels=input_label,
                    multimask_output=True
                )
            
            # 가장 높은 점수의 마스크 선택
            best_mask_idx = np.argmax(scores)
            best_mask = masks[best_mask_idx]
            
            return best_mask
            
        except Exception as e:
            failure(f"복합 마스크 생성 실패: {e}")
            return None
    
    def refine_mask(self, mask: np.ndarray, points: List[Tuple[int, int]], 
                   labels: List[int]) -> Optional[np.ndarray]:
        """기존 마스크를 점으로 정제"""
        if not self.is_loaded or self.sam_predictor is None:
            return None
        
        try:
            # 입력 포인트 설정
            input_point = np.array(points)
            input_label = np.array(labels)
            
            # 마스크 정제
            masks, scores, logits = self.sam_predictor.predict(
                point_coords=input_point,
                point_labels=input_label,
                mask_input=mask[None, :, :],
                multimask_output=True
            )
            
            # 가장 높은 점수의 마스크 선택
            best_mask_idx = np.argmax(scores)
            best_mask = masks[best_mask_idx]
            
            return best_mask
            
        except Exception as e:
            failure(f"마스크 정제 실패: {e}")
            return None
    
    def generate_multiple_masks(self, points: List[Tuple[int, int]], 
                              labels: List[int]) -> List[Dict[str, Any]]:
        """여러 마스크 생성"""
        if not self.is_loaded or self.sam_predictor is None:
            return []
        
        try:
            # 입력 포인트 설정
            input_point = np.array(points)
            input_label = np.array(labels)
            
            # 마스크 예측
            masks, scores, logits = self.sam_predictor.predict(
                point_coords=input_point,
                point_labels=input_label,
                multimask_output=True
            )
            
            # 결과 정리
            results = []
            for i, (mask, score) in enumerate(zip(masks, scores)):
                results.append({
                    "mask": mask,
                    "score": float(score),
                    "index": i
                })
            
            # 점수 순으로 정렬
            results.sort(key=lambda x: x["score"], reverse=True)
            
            return results
            
        except Exception as e:
            failure(f"다중 마스크 생성 실패: {e}")
            return []
    
    def mask_to_image(self, mask: np.ndarray, original_image: Image.Image) -> Image.Image:
        """마스크를 이미지로 변환"""
        try:
            # 마스크를 0-255 범위로 변환
            mask_image = (mask * 255).astype(np.uint8)
            
            # PIL Image로 변환
            mask_pil = Image.fromarray(mask_image, mode='L')
            
            # 원본 이미지 크기에 맞춤
            mask_pil = mask_pil.resize(original_image.size, Image.Resampling.LANCZOS)
            
            return mask_pil
            
        except Exception as e:
            failure(f"마스크 이미지 변환 실패: {e}")
            return None
    
    def apply_mask_to_image(self, image: Image.Image, mask: np.ndarray, 
                          background_color: Tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
        """마스크를 이미지에 적용"""
        try:
            # 이미지를 numpy 배열로 변환
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            image_array = np.array(image)
            
            # 마스크를 3채널로 확장
            mask_3d = np.stack([mask] * 3, axis=-1)
            
            # 마스크 적용
            masked_image = image_array * mask_3d + np.array(background_color) * (1 - mask_3d)
            
            # PIL Image로 변환
            result_image = Image.fromarray(masked_image.astype(np.uint8))
            
            return result_image
            
        except Exception as e:
            failure(f"마스크 적용 실패: {e}")
            return image
    
    def get_mask_contours(self, mask: np.ndarray) -> List[np.ndarray]:
        """마스크의 윤곽선 추출"""
        try:
            # 마스크를 8비트로 변환
            mask_uint8 = (mask * 255).astype(np.uint8)
            
            # 윤곽선 찾기
            contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            return contours
            
        except Exception as e:
            failure(f"윤곽선 추출 실패: {e}")
            return []
    
    def calculate_mask_area(self, mask: np.ndarray) -> float:
        """마스크 영역 계산"""
        try:
            return float(np.sum(mask))
            
        except Exception as e:
            failure(f"마스크 영역 계산 실패: {e}")
            return 0.0
    
    def unload_model(self):
        """SAM 모델 언로드"""
        if self.sam_predictor is not None:
            del self.sam_predictor
            self.sam_predictor = None
        
        if self.sam_model is not None:
            del self.sam_model
            self.sam_model = None
        
        self.is_loaded = False
        success(r"SAM 모델 언로드 완료") 