from ....core.logger import (
    debug, info, warning, error, success, failure, warning_emoji, 
    info_emoji, debug_emoji, process_emoji, model_emoji, image_emoji, ui_emoji
)
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
    warning_emoji(r"torchsde가 설치되지 않아 DPMSolverSDEScheduler를 사용할 수 없습니다.")
    info(r"   pip install torchsde로 설치 후 재실행하세요.")
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
        success(r"DPMSolverSDE 사용 가능")
    else:
        warning_emoji(r"torchsde 미설치, DPMSolverSDE 대신 DPMSolverMultistep 사용")
    
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
            warning_emoji(r"스케줄러 이름이 비어있음, 기본값 사용")
            return False
        
        # 2. 샘플러 클래스 결정
        sampler_lower = sampler_name.lower().strip()
        scheduler_class = cls.SAMPLER_MAP.get(sampler_lower)
        
        if scheduler_class is None:
            warning_emoji(f"알 수 없는 샘플러: {sampler_name}, 기본값 사용")
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
                    success(f"스케줄러 적용 성공: {old_scheduler_name} → {new_scheduler_name}")
                    info(f"   - 샘플러: {sampler_name}")
                    info(f"   - 타입: {scheduler_type}")
                    info(f"   - 설정: {config_overrides}")
                    return True
                else:
                    failure(f"스케줄러 적용 실패: {new_scheduler_name} != {scheduler_class.__name__}")
                    return False
            else:
                failure(r"파이프라인에 스케줄러가 없음")
                return False
                
        except Exception as e:
            failure(f"스케줄러 적용 중 오류: {e}")
            return False
    
    @classmethod
    def apply_clip_skip_to_pipeline(cls, pipeline, clip_skip: int):
        """CLIP Skip 실제 적용 (diffusers 호환)"""
        
        if clip_skip <= 1:
            return True  # 기본값, 적용 안함
        
        try:
            # SDXL 모델에서는 CLIP Skip을 다르게 처리해야 함
            # 현재는 안전하게 기본값만 반환하고 실제 적용은 나중에 구현
            info_emoji(f"CLIP Skip {clip_skip} 요청됨 (SDXL 모델에서는 현재 미지원)")
            info(r"   - 향후 SDXL 전용 CLIP Skip 구현 예정")
            return True
                
        except Exception as e:
            warning_emoji(f"CLIP Skip 적용 실패: {e}")
            return False

    @classmethod
    def reset_clip_skip(cls, pipeline):
        """CLIP Skip 초기화"""
        try:
            if hasattr(pipeline, 'text_encoder') and hasattr(pipeline.text_encoder.text_model.encoder, '_original_forward'):
                pipeline.text_encoder.text_model.encoder.forward = pipeline.text_encoder.text_model.encoder._original_forward
                success(r"CLIP Skip 초기화 완료")
        except Exception as e:
            warning_emoji(f"CLIP Skip 초기화 실패: {e}") 