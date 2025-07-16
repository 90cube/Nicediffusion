#!/usr/bin/env python3

from diffusers.pipelines.stable_diffusion_xl.pipeline_stable_diffusion_xl import StableDiffusionXLPipeline
import inspect

def check_sdxl_structure():
    print("=== SDXL 파이프라인 구조 분석 ===")
    
    # __init__ 메서드의 파라미터 확인
    sig = inspect.signature(StableDiffusionXLPipeline.__init__)
    print("\n1. __init__ 파라미터:")
    for param_name, param in sig.parameters.items():
        if param_name != 'self':
            print(f"  {param_name}: {param.annotation}")
    
    # 클래스 속성 확인
    print("\n2. 클래스 속성:")
    class_attrs = dir(StableDiffusionXLPipeline)
    tokenizer_attrs = [attr for attr in class_attrs if 'tokenizer' in attr.lower()]
    encoder_attrs = [attr for attr in class_attrs if 'encoder' in attr.lower()]
    
    print("  토크나이저 관련:", tokenizer_attrs)
    print("  인코더 관련:", encoder_attrs)
    
    # 실제 인스턴스 생성 시 필요한 파라미터 확인
    print("\n3. 필수 파라미터:")
    required_params = []
    for param_name, param in sig.parameters.items():
        if param_name != 'self' and param.default == inspect.Parameter.empty:
            required_params.append(param_name)
    
    for param in required_params:
        print(f"  {param}")
    
    print("\n4. SDXL 토크나이저 정보:")
    print("  - SDXL은 두 개의 CLIP 토크나이저를 사용합니다")
    print("  - tokenizer: CLIP-L (OpenAI CLIP)")
    print("  - tokenizer_2: CLIP-G (OpenCLIP)")
    print("  - 두 토크나이저는 서로 다른 어휘와 특성을 가집니다")

if __name__ == "__main__":
    check_sdxl_structure() 