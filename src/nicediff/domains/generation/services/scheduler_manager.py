"""
스케줄러/샘플러 관리 도메인 서비스
UI나 StateManager에 의존하지 않는 순수한 비즈니스 로직
"""

from typing import Dict, Any, Optional, Union

import torch
from diffusers.schedulers.scheduling_euler_discrete import EulerDiscreteScheduler
from diffusers.schedulers.scheduling_dpmsolver_multistep import DPMSolverMultistepScheduler
from diffusers.schedulers.scheduling_dpmsolver_singlestep import DPMSolverSinglestepScheduler
from diffusers.schedulers.scheduling_ddim import DDIMScheduler
from diffusers.schedulers.scheduling_pndm import PNDMScheduler
from diffusers.schedulers.scheduling_euler_ancestral_discrete import EulerAncestralDiscreteScheduler

# torchsde 의존성이 있는 스케줄러는 안전하게 import
try:
    from diffusers.schedulers.scheduling_dpmsolver_sde import DPMSolverSDEScheduler
    DPMSOLVER_SDE_AVAILABLE = True
except ImportError:
    print("⚠️ torchsde가 설치되지 않아 DPMSolverSDEScheduler를 사용할 수 없습니다.")
    print("   pip install torchsde로 설치 후 재실행하세요.")
    DPMSOLVER_SDE_AVAILABLE = False
    DPMSolverSDEScheduler = None


class SchedulerManager:
    """스케줄러/샘플러 관리 서비스"""
    
    # 샘플러 매핑
    SAMPLER_MAP = {
        # 기존 매핑 유지
        'euler': EulerDiscreteScheduler,
        'euler_a': EulerAncestralDiscreteScheduler,
        'euler a': EulerAncestralDiscreteScheduler,
        'euler-a': EulerAncestralDiscreteScheduler,
        'dpmpp_2m': DPMSolverMultistepScheduler,
        'dpmpp_sde_gpu': DPMSolverMultistepScheduler,
        'dpmpp_2m_sde_gpu': DPMSolverMultistepScheduler,
        'dpmpp_3m_sde_gpu': DPMSolverMultistepScheduler,
        'ddim': DDIMScheduler,
        'pndm': PNDMScheduler,
        
        # A1111 호환 이름들 추가
        'euler_ancestral': EulerAncestralDiscreteScheduler,
        'dpm++ 2m': DPMSolverMultistepScheduler,
        'dpm++ 2m karras': DPMSolverMultistepScheduler,
        'dpm++ sde': DPMSolverSDEScheduler if DPMSOLVER_SDE_AVAILABLE else DPMSolverMultistepScheduler,
        'dpm++ sde karras': DPMSolverSDEScheduler if DPMSOLVER_SDE_AVAILABLE else DPMSolverMultistepScheduler,
        'dpm++ 2m sde': DPMSolverMultistepScheduler,
        'dpm++ 2m sde karras': DPMSolverMultistepScheduler,
        'dpm++ 3m sde': DPMSolverMultistepScheduler,
        'dpm++ 3m sde karras': DPMSolverMultistepScheduler,
        'heun': EulerDiscreteScheduler,
        'dpm2': DPMSolverSinglestepScheduler,
        'dpm2 karras': DPMSolverSinglestepScheduler,
        'dpm2 a': EulerAncestralDiscreteScheduler,
        'dpm2 a karras': EulerAncestralDiscreteScheduler,
        'lms': DDIMScheduler,
        'lms karras': DDIMScheduler,
    }
    
    # torchsde 체크 강화
    if DPMSOLVER_SDE_AVAILABLE:
        SAMPLER_MAP['dpmpp_sde'] = DPMSolverSDEScheduler
        print("✅ DPMSolverSDE 사용 가능")
    else:
        print("⚠️ torchsde 미설치, DPMSolverSDE 대신 DPMSolverMultistep 사용")
    
    # 스케줄러 설정
    SCHEDULER_CONFIG = {
        'normal': {},
        'karras': {
            'use_karras_sigmas': True,
            'karras_rho': 7.0
        },
        'exponential': {
            'use_karras_sigmas': False
        },
        'sgm_uniform': {
            'use_karras_sigmas': False
        },
        'simple': {
            'use_karras_sigmas': False
        },
        'ddim_uniform': {
            'use_karras_sigmas': False
        }
    }
    
    @classmethod
    def apply_scheduler_to_pipeline(cls, pipeline, sampler_name: str, scheduler_type: str):
        """스케줄러 적용 + 검증 강화"""
        
        # 1. 입력 검증
        if not sampler_name or not scheduler_type:
            print("⚠️ 스케줄러 이름이 비어있음, 기본값 사용")
            return False
        
        # 2. 샘플러 클래스 결정
        sampler_lower = sampler_name.lower().strip()
        scheduler_class = cls.SAMPLER_MAP.get(sampler_lower)
        
        if scheduler_class is None:
            print(f"⚠️ 알 수 없는 샘플러: {sampler_name}, 기본값 사용")
            scheduler_class = DPMSolverMultistepScheduler
        
        # 3. 스케줄러 설정
        config_overrides = cls.SCHEDULER_CONFIG.get(scheduler_type.lower(), {})
        
        # 4. 스케줄러 생성 및 적용
        try:
            if hasattr(pipeline, 'scheduler') and pipeline.scheduler is not None:
                # 기존 설정 기반으로 새 스케줄러 생성
                base_config = pipeline.scheduler.config.copy()
                
                # 설정 병합
                for key, value in config_overrides.items():
                    if hasattr(base_config, key):
                        setattr(base_config, key, value)
                
                # 새 스케줄러 생성
                new_scheduler = scheduler_class.from_config(base_config)
                
                # 파이프라인에 적용
                old_scheduler_name = pipeline.scheduler.__class__.__name__
                pipeline.scheduler = new_scheduler
                
                # 적용 검증
                new_scheduler_name = pipeline.scheduler.__class__.__name__
                
                if new_scheduler_name == scheduler_class.__name__:
                    print(f"✅ 스케줄러 적용 성공: {old_scheduler_name} → {new_scheduler_name}")
                    print(f"   - 샘플러: {sampler_name}")
                    print(f"   - 타입: {scheduler_type}")
                    print(f"   - 설정: {config_overrides}")
                    return True
                else:
                    print(f"❌ 스케줄러 적용 실패: {new_scheduler_name} != {scheduler_class.__name__}")
                    return False
            else:
                print("❌ 파이프라인에 스케줄러가 없음")
                return False
                
        except Exception as e:
            print(f"❌ 스케줄러 적용 중 오류: {e}")
            return False
    
    @classmethod
    def apply_clip_skip_to_pipeline(cls, pipeline, clip_skip: int):
        """CLIP Skip 실제 적용 (diffusers 호환)"""
        
        if clip_skip <= 1:
            return True  # 기본값, 적용 안함
        
        try:
            # diffusers에서 CLIP Skip 적용
            if hasattr(pipeline, 'text_encoder') and hasattr(pipeline.text_encoder, 'text_model'):
                # 텍스트 인코더의 레이어 수 확인
                total_layers = len(pipeline.text_encoder.text_model.encoder.layers)
                target_layer = max(0, total_layers - clip_skip)
                
                # 원본 forward 함수 저장
                if not hasattr(pipeline.text_encoder.text_model.encoder, '_original_forward'):
                    pipeline.text_encoder.text_model.encoder._original_forward = pipeline.text_encoder.text_model.encoder.forward
                
                def clipped_forward(hidden_states, attention_mask=None, **kwargs):
                    # 지정된 레이어까지만 실행
                    for i, layer in enumerate(pipeline.text_encoder.text_model.encoder.layers):
                        if i >= target_layer:
                            break
                        hidden_states = layer(hidden_states, attention_mask=attention_mask, **kwargs)[0]
                    return hidden_states
                
                # 새로운 forward 함수 적용
                pipeline.text_encoder.text_model.encoder.forward = clipped_forward
                
                print(f"✅ CLIP Skip {clip_skip} 적용 완료 (레이어 {target_layer}/{total_layers})")
                return True
                
        except Exception as e:
            print(f"⚠️ CLIP Skip 적용 실패: {e}")
            return False
        
        print(f"⚠️ CLIP Skip {clip_skip} 적용 불가 (지원하지 않는 파이프라인)")
        return False

    @classmethod
    def reset_clip_skip(cls, pipeline):
        """CLIP Skip 초기화"""
        try:
            if hasattr(pipeline, 'text_encoder') and hasattr(pipeline.text_encoder.text_model.encoder, '_original_forward'):
                pipeline.text_encoder.text_model.encoder.forward = pipeline.text_encoder.text_model.encoder._original_forward
                print("✅ CLIP Skip 초기화 완료")
        except Exception as e:
            print(f"⚠️ CLIP Skip 초기화 실패: {e}") 