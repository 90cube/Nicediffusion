#!/usr/bin/env python3
"""생성된 테스트 파일의 메타데이터 파싱 확인"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nicediff.services.metadata_parser import MetadataParser
from src.nicediff.core.state_manager import StateManager

def test_created_files():
    """생성된 테스트 파일들의 메타데이터 파싱 확인"""
    print("🔍 생성된 테스트 파일 메타데이터 파싱 확인...")
    
    # 테스트 파일들
    test_files = [
        "models/checkpoints/SDXL/test_metadata_model.safetensors",
        "models/checkpoints/SDXL/test_metadata_model.png"
    ]
    
    for file_path in test_files:
        path = Path(file_path)
        if not path.exists():
            print(f"❌ 파일을 찾을 수 없습니다: {path}")
            continue
        
        print(f"\n📁 파일: {path.name}")
        
        # 메타데이터 추출
        if path.suffix.lower() == '.safetensors':
            metadata = MetadataParser.extract_from_safetensors(path)
        else:
            metadata = MetadataParser.extract_from_png(path)
        
        if not metadata:
            print("❌ 메타데이터를 추출할 수 없습니다.")
            continue
        
        print("📋 추출된 메타데이터:")
        for key, value in metadata.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}...")
            else:
                print(f"  {key}: {value}")
        
        # StateManager 파싱 테스트
        print("\n🔄 StateManager 파싱 테스트...")
        state_manager = StateManager()
        
        test_model_info = {
            'name': path.stem,
            'path': str(path),
            'metadata': metadata
        }
        
        # 메타데이터 파싱 적용
        state_manager.apply_params_from_metadata(test_model_info)
        
        # 결과 확인
        current_params = state_manager.get('current_params')
        
        print("✅ 파싱 결과:")
        print(f"  긍정 프롬프트: {current_params.prompt[:100]}..." if current_params.prompt else "  긍정 프롬프트: 없음")
        print(f"  부정 프롬프트: {current_params.negative_prompt[:100]}..." if current_params.negative_prompt else "  부정 프롬프트: 없음")
        print(f"  너비: {current_params.width}")
        print(f"  높이: {current_params.height}")
        print(f"  CFG: {current_params.cfg_scale}")
        print(f"  Steps: {current_params.steps}")
        print(f"  Seed: {current_params.seed}")
        print(f"  Sampler: {current_params.sampler}")
        
        # 예상 결과와 비교
        expected = {
            'prompt': "1girl, souryuu asuka langley, neon genesis evangelion, sensitive, solo, eyepatch, red plugsuit, sitting on throne, crossed legs, head tilt, holding weapon, lance of longinus \\(evangelion\\), cowboy shot, depth of field, faux traditional media, painterly, impressionism, masterpiece, high score, great score, absurdres",
            'negative_prompt': "lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry",
            'width': 832,
            'height': 1216,
            'cfg_scale': 5.0,
            'steps': 28,
            'seed': 0,
            'sampler': 'euler_a'
        }
        
        print("\n🔍 결과 검증:")
        success = True
        for key, expected_val in expected.items():
            actual_val = getattr(current_params, key)
            if actual_val == expected_val:
                print(f"  ✅ {key}: {actual_val}")
            else:
                print(f"  ❌ {key}: 예상 {expected_val}, 실제 {actual_val}")
                success = False
        
        if success:
            print("🎉 모든 테스트 통과!")
        else:
            print("💥 일부 테스트 실패!")

if __name__ == "__main__":
    test_created_files() 