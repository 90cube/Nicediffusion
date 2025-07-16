#!/usr/bin/env python3

import torch
from diffusers.pipelines.stable_diffusion_xl.pipeline_stable_diffusion_xl import StableDiffusionXLPipeline

def test_sdxl_loading():
    print("=== SDXL 모델 로딩 테스트 ===")
    
    try:
        print("🔄 SDXL 모델 로딩 중 (diffusers 내장 모델 사용)...")
        print("⚠️ 이 작업은 시간이 오래 걸릴 수 있습니다...")
        
        # diffusers 내장 SDXL 모델 사용
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            "stabilityai/stable-diffusion-xl-base-1.0",
            torch_dtype=torch.float16,
            variant="fp16",
            use_safetensors=True
        )
        
        print("✅ SDXL 파이프라인 로드 완료")
        
        # 토크나이저 확인
        print("\n📋 토크나이저 확인:")
        print(f"  tokenizer 존재: {hasattr(pipeline, 'tokenizer')}")
        print(f"  tokenizer_2 존재: {hasattr(pipeline, 'tokenizer_2')}")
        
        if hasattr(pipeline, 'tokenizer') and pipeline.tokenizer is not None:
            print(f"  tokenizer 타입: {type(pipeline.tokenizer)}")
            print(f"  tokenizer 모델 최대 길이: {pipeline.tokenizer.model_max_length}")
            print(f"  tokenizer 어휘 크기: {pipeline.tokenizer.vocab_size}")
        
        if hasattr(pipeline, 'tokenizer_2') and pipeline.tokenizer_2 is not None:
            print(f"  tokenizer_2 타입: {type(pipeline.tokenizer_2)}")
            print(f"  tokenizer_2 모델 최대 길이: {pipeline.tokenizer_2.model_max_length}")
            print(f"  tokenizer_2 어휘 크기: {pipeline.tokenizer_2.vocab_size}")
        
        # 텍스트 인코더 확인
        print("\n📋 텍스트 인코더 확인:")
        print(f"  text_encoder 존재: {hasattr(pipeline, 'text_encoder')}")
        print(f"  text_encoder_2 존재: {hasattr(pipeline, 'text_encoder_2')}")
        
        if hasattr(pipeline, 'text_encoder') and pipeline.text_encoder is not None:
            print(f"  text_encoder 타입: {type(pipeline.text_encoder)}")
        
        if hasattr(pipeline, 'text_encoder_2') and pipeline.text_encoder_2 is not None:
            print(f"  text_encoder_2 타입: {type(pipeline.text_encoder_2)}")
        
        # 토크나이저 차이점 테스트
        if hasattr(pipeline, 'tokenizer') and hasattr(pipeline, 'tokenizer_2'):
            test_prompt = "a beautiful landscape"
            print(f"\n🧪 토크나이저 차이점 테스트:")
            print(f"  테스트 프롬프트: '{test_prompt}'")
            
            # 첫 번째 토크나이저로 토큰화
            tokens1 = pipeline.tokenizer(test_prompt, return_tensors="pt")
            print(f"  tokenizer 토큰 수: {tokens1.input_ids.shape[1]}")
            
            # 두 번째 토크나이저로 토큰화
            tokens2 = pipeline.tokenizer_2(test_prompt, return_tensors="pt")
            print(f"  tokenizer_2 토큰 수: {tokens2.input_ids.shape[1]}")
            
            # 토큰 ID 비교
            print(f"  토큰 ID가 다른가?: {not torch.equal(tokens1.input_ids, tokens2.input_ids)}")
            
            # 토큰 ID 상세 비교
            print(f"  tokenizer 토큰 ID: {tokens1.input_ids[0].tolist()}")
            print(f"  tokenizer_2 토큰 ID: {tokens2.input_ids[0].tolist()}")
        
        print("\n✅ SDXL 두 토크나이저 설정 확인 완료")
        
    except Exception as e:
        print(f"❌ SDXL 모델 로딩 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sdxl_loading() 