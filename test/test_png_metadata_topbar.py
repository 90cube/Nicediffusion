#!/usr/bin/env python3
"""animagineXL40_v4Opt.png의 메타데이터를 TopBar 규칙에 따라 추출 및 확인"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.nicediff.services.metadata_parser import MetadataParser
from src.nicediff.core.state_manager import StateManager

def test_png_metadata_for_topbar():
    png_path = Path("models/checkpoints/SDXL/animagineXL40_v4Opt.png")
    if not png_path.exists():
        print(f"❌ 파일 없음: {png_path}")
        return
    print(f"📁 파일: {png_path}")
    metadata = MetadataParser.extract_from_png(png_path)
    if not metadata:
        print("❌ 메타데이터 추출 실패")
        return
    print("\n📋 추출된 메타데이터:")
    for k, v in metadata.items():
        print(f"  {k}: {v}")
    # StateManager 파싱 적용
    state_manager = StateManager()
    test_model_info = {
        'name': 'animagineXL40_v4Opt',
        'path': str(png_path),
        'metadata': metadata
    }
    state_manager.apply_params_from_metadata(test_model_info)
    params = state_manager.get('current_params')
    print("\n✅ TopBar에 표시될 파싱 결과:")
    print(f"  긍정 프롬프트: {params.prompt}")
    print(f"  부정 프롬프트: {params.negative_prompt}")
    print(f"  너비: {params.width}")
    print(f"  높이: {params.height}")
    print(f"  CFG: {params.cfg_scale}")
    print(f"  Steps: {params.steps}")
    print(f"  Seed: {params.seed}")
    print(f"  Sampler: {params.sampler}")

def main():
    test_png_metadata_for_topbar()

if __name__ == "__main__":
    main() 