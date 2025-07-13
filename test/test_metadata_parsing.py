#!/usr/bin/env python3
"""메타데이터 파싱 테스트 스크립트"""

import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nicediff.core.state_manager import StateManager, GenerationParams

def test_metadata_parsing():
    """메타데이터 파싱 테스트"""
    print("🔍 메타데이터 파싱 테스트 시작...")
    
    # 테스트용 메타데이터 (사용자가 제안한 형식)
    test_metadata = {
        "prompt": "1girl, souryuu asuka langley, neon genesis evangelion, sensitive, solo, eyepatch, red plugsuit, sitting on throne, crossed legs, head tilt, holding weapon, lance of longinus \\(evangelion\\), cowboy shot, depth of field, faux traditional media, painterly, impressionism, masterpiece, high score, great score, absurdres",
        "negativeprompt": "lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry",
        "resolution": "832 x 1216",
        "guidancescale": 5,
        "numinferencesteps": 28,
        "stylepreset": "(None)",
        "seed": 0,
        "sampler": "Euler a",
        "Model": "Animagine XL 4.0 Early Test",
        "useupscaler": {
            "upscalemethod": "nearest-exact",
            "upscalerstrength": 0.55,
            "upscaleby": 1.5,
            "newresolution": "1248 x 1824"
        }
    }
    
    # StateManager 인스턴스 생성
    state_manager = StateManager()
    
    # 테스트용 모델 정보
    test_model_info = {
        'name': 'Test Model',
        'path': '/test/path',
        'metadata': test_metadata
    }
    
    print("📋 테스트 메타데이터:")
    for key, value in test_metadata.items():
        print(f"  {key}: {value}")
    
    print("\n🔄 메타데이터 파싱 적용 중...")
    
    # 메타데이터 파싱 적용
    state_manager.apply_params_from_metadata(test_model_info)
    
    # 결과 확인
    current_params = state_manager.get('current_params')
    
    print("\n✅ 파싱 결과:")
    print(f"  긍정 프롬프트: {current_params.prompt}")
    print(f"  부정 프롬프트: {current_params.negative_prompt}")
    print(f"  너비: {current_params.width}")
    print(f"  높이: {current_params.height}")
    print(f"  CFG: {current_params.cfg_scale}")
    print(f"  Steps: {current_params.steps}")
    print(f"  Seed: {current_params.seed}")
    print(f"  Sampler: {current_params.sampler}")
    
    # 예상 결과와 비교
    expected_results = {
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
    for key, expected in expected_results.items():
        actual = getattr(current_params, key)
        if actual == expected:
            print(f"  ✅ {key}: {actual}")
        else:
            print(f"  ❌ {key}: 예상 {expected}, 실제 {actual}")
            success = False
    
    if success:
        print("\n🎉 모든 테스트 통과!")
    else:
        print("\n💥 일부 테스트 실패!")
    
    return success

if __name__ == "__main__":
    test_metadata_parsing() 