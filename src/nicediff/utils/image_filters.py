# 이미지 필터 유틸리티 (삭제된 파일 재생성)

def get_available_filters():
    """사용 가능한 필터 목록 반환"""
    return ['none', 'blur', 'sharpen', 'grayscale']

def apply_filter(image, filter_name):
    """이미지에 필터 적용"""
    if filter_name == 'none':
        return image
    # TODO: 실제 필터 구현
    return image 