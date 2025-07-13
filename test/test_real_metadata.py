#!/usr/bin/env python3
"""실제 모델 메타데이터 확인 스크립트"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nicediff.services.metadata_parser import MetadataParser

def test_real_model_metadata():
    """실제 모델의 메타데이터 확인"""
    print("🔍 실제 모델 메타데이터 확인 시작...")
    
    # 실제 모델 파일 경로
    model_path = Path("models/checkpoints/SDXL/animagineXL40_v4Opt.safetensors")
    
    if not model_path.exists():
        print(f"❌ 모델 파일을 찾을 수 없습니다: {model_path}")
        return
    
    print(f"📁 모델 파일: {model_path}")
    
    # 메타데이터 추출
    metadata = MetadataParser.extract_from_safetensors(model_path)
    
    if not metadata:
        print("❌ 메타데이터를 추출할 수 없습니다.")
        return
    
    print("\n📋 추출된 메타데이터:")
    for key, value in metadata.items():
        if isinstance(value, str) and len(value) > 100:
            print(f"  {key}: {value[:100]}...")
        else:
            print(f"  {key}: {value}")
    
    # StateManager의 파싱 로직 테스트
    print("\n🔄 StateManager 파싱 로직 테스트...")
    
    from src.nicediff.core.state_manager import StateManager
    
    state_manager = StateManager()
    
    # 테스트용 모델 정보
    test_model_info = {
        'name': 'animagineXL40_v4Opt',
        'path': str(model_path),
        'metadata': metadata
    }
    
    # 메타데이터 파싱 적용
    state_manager.apply_params_from_metadata(test_model_info)
    
    # 결과 확인
    current_params = state_manager.get('current_params')
    
    print("\n✅ 파싱 결과:")
    print(f"  긍정 프롬프트: {current_params.prompt[:100]}..." if current_params.prompt else "  긍정 프롬프트: 없음")
    print(f"  부정 프롬프트: {current_params.negative_prompt[:100]}..." if current_params.negative_prompt else "  부정 프롬프트: 없음")
    print(f"  너비: {current_params.width}")
    print(f"  높이: {current_params.height}")
    print(f"  CFG: {current_params.cfg_scale}")
    print(f"  Steps: {current_params.steps}")
    print(f"  Seed: {current_params.seed}")
    print(f"  Sampler: {current_params.sampler}")

if __name__ == "__main__":
    test_real_model_metadata() 