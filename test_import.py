#!/usr/bin/env python3

try:
    from src.nicediff.domains.generation.model_definitions.generation_params import GenerationParams
    from src.nicediff.domains.generation.model_definitions.history_item import HistoryItem
    print("✅ 모든 import 성공!")
    
    # 객체 생성 테스트
    params = GenerationParams()
    history = HistoryItem(
        image_path="test.jpg", 
        thumbnail_path="test_thumb.jpg",
        params=params, 
        model="test_model"
    )
    print("✅ 객체 생성 성공!")
    
except Exception as e:
    print(f"❌ Import 실패: {e}") 