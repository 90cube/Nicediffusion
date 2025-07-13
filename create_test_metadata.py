#!/usr/bin/env python3
"""테스트용 메타데이터 파일 생성 스크립트"""

import json
import struct
from pathlib import Path

def create_test_safetensors_with_metadata():
    """사용자가 제안한 형식의 메타데이터를 가진 테스트 safetensors 파일 생성"""
    
    # 사용자가 제안한 메타데이터
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
    
    # Safetensors 헤더 구조
    header = {
        "__metadata__": test_metadata,
        "model.diffusion_model.input_blocks.0.0.weight": {
            "dtype": "F32",
            "shape": [320, 4, 3, 3],
            "data_offsets": [0, 11520]
        }
    }
    
    # 헤더를 JSON으로 직렬화
    header_json = json.dumps(header, separators=(',', ':'))
    header_bytes = header_json.encode('utf-8')
    
    # 헤더 크기 (8바이트 리틀 엔디안)
    header_size = len(header_bytes)
    header_size_bytes = struct.pack('<Q', header_size)
    
    # 테스트 파일 생성
    test_file_path = Path("models/checkpoints/SDXL/test_metadata_model.safetensors")
    test_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(test_file_path, 'wb') as f:
        # 헤더 크기 (8바이트)
        f.write(header_size_bytes)
        # 헤더 JSON
        f.write(header_bytes)
        # 더미 데이터 (최소 크기)
        f.write(b'\x00' * 1000)  # 1KB 더미 데이터
    
    print(f"✅ 테스트 메타데이터 파일 생성 완료: {test_file_path}")
    print(f"📁 파일 크기: {test_file_path.stat().st_size} bytes")
    
    return test_file_path

def create_test_png_with_metadata():
    """사용자가 제안한 형식의 메타데이터를 가진 테스트 PNG 파일 생성"""
    from PIL import Image, PngImagePlugin
    
    # 사용자가 제안한 메타데이터를 A1111 형식으로 변환
    a1111_metadata = """1girl, souryuu asuka langley, neon genesis evangelion, sensitive, solo, eyepatch, red plugsuit, sitting on throne, crossed legs, head tilt, holding weapon, lance of longinus \(evangelion\), cowboy shot, depth of field, faux traditional media, painterly, impressionism, masterpiece, high score, great score, absurdres

Negative prompt: lowres, bad anatomy, bad hands, text, error, missing finger, extra digits, fewer digits, cropped, worst quality, low quality, low score, bad score, average score, signature, watermark, username, blurry

Steps: 28, Sampler: Euler a, CFG scale: 5, Seed: 0, Size: 832x1216, Model: Animagine XL 4.0 Early Test"""
    
    # 1x1 픽셀 이미지 생성
    img = Image.new('RGB', (1, 1), color='white')
    
    # 메타데이터 추가
    meta = PngImagePlugin.PngInfo()
    meta.add_text('parameters', a1111_metadata)
    
    # 테스트 파일 생성
    test_file_path = Path("models/checkpoints/SDXL/test_metadata_model.png")
    test_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    img.save(test_file_path, 'PNG', pnginfo=meta)
    
    print(f"✅ 테스트 PNG 메타데이터 파일 생성 완료: {test_file_path}")
    print(f"📁 파일 크기: {test_file_path.stat().st_size} bytes")
    
    return test_file_path

if __name__ == "__main__":
    print("🔧 테스트용 메타데이터 파일 생성 시작...")
    
    # Safetensors 파일 생성
    safetensors_path = create_test_safetensors_with_metadata()
    
    # PNG 파일 생성
    png_path = create_test_png_with_metadata()
    
    print("\n🎉 모든 테스트 파일 생성 완료!")
    print(f"📋 생성된 파일들:")
    print(f"  - {safetensors_path}")
    print(f"  - {png_path}")
    print("\n💡 이제 애플리케이션에서 이 파일들을 선택하여 메타데이터 파싱을 테스트할 수 있습니다.") 