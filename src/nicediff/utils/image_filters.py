"""
이미지 필터 유틸리티 (I2I 제안서 스타일)
"""

import numpy as np
from PIL import Image
from typing import Callable, Dict, Any


class ImageFilters:
    """이미지 필터 모음 (I2I 제안서 스타일)"""
    
    @staticmethod
    def sepia(input_img: np.ndarray) -> np.ndarray:
        """Sepia 필터 적용"""
        sepia_filter = np.array([
            [0.393, 0.769, 0.189],
            [0.349, 0.686, 0.168],
            [0.272, 0.534, 0.131]
        ])
        
        if len(input_img.shape) == 3:  # RGB 이미지
            sepia_img = input_img.dot(sepia_filter.T)
            sepia_img = np.clip(sepia_img, 0, 255)
            return sepia_img.astype(np.uint8)
        return input_img
    
    @staticmethod
    def grayscale(input_img: np.ndarray) -> np.ndarray:
        """그레이스케일 변환"""
        if len(input_img.shape) == 3:
            # RGB to grayscale
            gray = np.dot(input_img[..., :3], [0.299, 0.587, 0.114])
            return gray.astype(np.uint8)
        return input_img
    
    @staticmethod
    def invert(input_img: np.ndarray) -> np.ndarray:
        """색상 반전"""
        return 255 - input_img
    
    @staticmethod
    def brightness(input_img: np.ndarray, factor: float = 1.2) -> np.ndarray:
        """밝기 조정"""
        brightened = input_img * factor
        return np.clip(brightened, 0, 255).astype(np.uint8)
    
    @staticmethod
    def contrast(input_img: np.ndarray, factor: float = 1.5) -> np.ndarray:
        """대비 조정"""
        # 평균값 계산
        mean = np.mean(input_img)
        # 대비 조정
        contrasted = (input_img - mean) * factor + mean
        return np.clip(contrasted, 0, 255).astype(np.uint8)
    
    @staticmethod
    def blur(input_img: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """가우시안 블러 (간단한 구현)"""
        if len(input_img.shape) == 3:
            # RGB 각 채널에 대해 블러 적용
            blurred = np.zeros_like(input_img)
            for i in range(3):
                blurred[:, :, i] = ImageFilters._apply_kernel_blur(input_img[:, :, i], kernel_size)
            return blurred.astype(np.uint8)
        else:
            return ImageFilters._apply_kernel_blur(input_img, kernel_size).astype(np.uint8)
    
    @staticmethod
    def _apply_kernel_blur(img: np.ndarray, kernel_size: int) -> np.ndarray:
        """커널 기반 블러 적용"""
        # 간단한 평균 필터
        kernel = np.ones((kernel_size, kernel_size)) / (kernel_size * kernel_size)
        
        # 패딩 추가
        pad_size = kernel_size // 2
        padded = np.pad(img, pad_size, mode='edge')
        
        # 컨볼루션 적용
        h, w = img.shape
        blurred = np.zeros_like(img)
        
        for i in range(h):
            for j in range(w):
                blurred[i, j] = np.sum(padded[i:i+kernel_size, j:j+kernel_size] * kernel)
        
        return blurred
    
    @staticmethod
    def sharpen(input_img: np.ndarray) -> np.ndarray:
        """샤프닝 필터"""
        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ])
        
        if len(input_img.shape) == 3:
            sharpened = np.zeros_like(input_img)
            for i in range(3):
                sharpened[:, :, i] = ImageFilters._apply_kernel(input_img[:, :, i], kernel)
            return np.clip(sharpened, 0, 255).astype(np.uint8)
        else:
            sharpened = ImageFilters._apply_kernel(input_img, kernel)
            return np.clip(sharpened, 0, 255).astype(np.uint8)
    
    @staticmethod
    def _apply_kernel(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
        """커널 적용"""
        h, w = img.shape
        kh, kw = kernel.shape
        pad_h, pad_w = kh // 2, kw // 2
        
        # 패딩 추가
        padded = np.pad(img, ((pad_h, pad_h), (pad_w, pad_w)), mode='edge')
        
        # 컨볼루션 적용
        result = np.zeros_like(img)
        for i in range(h):
            for j in range(w):
                result[i, j] = np.sum(padded[i:i+kh, j:j+kw] * kernel)
        
        return result
    
    @staticmethod
    def edge_detection(input_img: np.ndarray) -> np.ndarray:
        """엣지 검출 (Sobel 필터)"""
        if len(input_img.shape) == 3:
            gray = ImageFilters.grayscale(input_img)
        else:
            gray = input_img
        
        # Sobel 필터
        sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]])
        sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]])
        
        grad_x = ImageFilters._apply_kernel(gray, sobel_x)
        grad_y = ImageFilters._apply_kernel(gray, sobel_y)
        
        # 그래디언트 크기 계산
        magnitude = np.sqrt(grad_x**2 + grad_y**2)
        return np.clip(magnitude, 0, 255).astype(np.uint8)
    
    @staticmethod
    def noise_reduction(input_img: np.ndarray, strength: float = 0.1) -> np.ndarray:
        """노이즈 감소 (중간값 필터)"""
        if len(input_img.shape) == 3:
            denoised = np.zeros_like(input_img)
            for i in range(3):
                denoised[:, :, i] = ImageFilters._apply_median_filter(input_img[:, :, i], strength)
            return denoised.astype(np.uint8)
        else:
            return ImageFilters._apply_median_filter(input_img, strength).astype(np.uint8)
    
    @staticmethod
    def _apply_median_filter(img: np.ndarray, strength: float) -> np.ndarray:
        """중간값 필터 적용"""
        # 간단한 구현: 3x3 윈도우의 중간값
        h, w = img.shape
        result = np.zeros_like(img)
        
        for i in range(1, h-1):
            for j in range(1, w-1):
                window = img[i-1:i+2, j-1:j+2]
                result[i, j] = np.median(window)
        
        # 가장자리는 원본 유지
        result[0, :] = img[0, :]
        result[-1, :] = img[-1, :]
        result[:, 0] = img[:, 0]
        result[:, -1] = img[:, -1]
        
        return result


# 필터 함수들을 딕셔너리로 관리
FILTER_FUNCTIONS: Dict[str, Callable] = {
    'sepia': ImageFilters.sepia,
    'grayscale': ImageFilters.grayscale,
    'invert': ImageFilters.invert,
    'brightness': ImageFilters.brightness,
    'contrast': ImageFilters.contrast,
    'blur': ImageFilters.blur,
    'sharpen': ImageFilters.sharpen,
    'edge_detection': ImageFilters.edge_detection,
    'noise_reduction': ImageFilters.noise_reduction,
}


def apply_filter(filter_name: str, input_img: np.ndarray, **kwargs) -> np.ndarray:
    """필터 적용 함수"""
    if filter_name not in FILTER_FUNCTIONS:
        raise ValueError(f"알 수 없는 필터: {filter_name}")
    
    filter_func = FILTER_FUNCTIONS[filter_name]
    return filter_func(input_img, **kwargs)


def get_available_filters() -> list:
    """사용 가능한 필터 목록 반환"""
    return list(FILTER_FUNCTIONS.keys()) 