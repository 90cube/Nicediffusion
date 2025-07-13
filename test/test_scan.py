#!/usr/bin/env python3
"""모델 스캔 테스트 스크립트"""

import asyncio
import sys
import os

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nicediff.services.model_scanner import ModelScanner

async def test_scan():
    """모델 스캔 테스트"""
    print("🔍 모델 스캔 테스트 시작...")
    
    try:
        # ModelScanner 인스턴스 생성 (설정 파일에서 경로 읽기)
        import tomllib
        with open("config.toml", "rb") as f:
            config = tomllib.load(f)
        paths_config = config.get('paths', {})
        
        scanner = ModelScanner(paths_config=paths_config)
        
        # 전체 모델 스캔 실행
        result = await scanner.scan_all_models()
        
        print("✅ 스캔 완료!")
        print(f"📁 체크포인트: {len(result.get('checkpoints', {}))}개")
        print(f"📁 VAE: {len(result.get('vae', {}))}개")
        print(f"📁 LoRA: {len(result.get('loras', {}))}개")
        
        # 상세 정보 출력
        if result.get('checkpoints'):
            print("\n📋 체크포인트 목록:")
            for model_type, models in result['checkpoints'].items():
                print(f"  {model_type}: {len(models)}개")
                for model in models[:3]:  # 처음 3개만 출력
                    print(f"    - {model['name']}")
                if len(models) > 3:
                    print(f"    ... 외 {len(models)-3}개")
        
        if result.get('vae'):
            print("\n📋 VAE 목록:")
            for model_type, vaes in result['vae'].items():
                print(f"  {model_type}: {len(vaes)}개")
                for vae in vaes[:3]:  # 처음 3개만 출력
                    print(f"    - {vae['name']}")
                if len(vaes) > 3:
                    print(f"    ... 외 {len(vaes)-3}개")
        
        if result.get('loras'):
            print("\n📋 LoRA 목록:")
            for model_type, loras in result['loras'].items():
                print(f"  {model_type}: {len(loras)}개")
                for lora in loras[:3]:  # 처음 3개만 출력
                    print(f"    - {lora['name']}")
                if len(loras) > 3:
                    print(f"    ... 외 {len(loras)-3}개")
        
        return result
        
    except Exception as e:
        print(f"❌ 스캔 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_scan())
    if result:
        print("\n🎉 모델 스캔 테스트 성공!")
    else:
        print("\n💥 모델 스캔 테스트 실패!")
