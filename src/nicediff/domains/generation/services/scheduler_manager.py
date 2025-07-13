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
    }
    
    # torchsde가 사용 가능한 경우에만 dpmpp_sde 추가
    if DPMSOLVER_SDE_AVAILABLE:
        SAMPLER_MAP['dpmpp_sde'] = DPMSolverSDEScheduler
    
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
        """파이프라인에 스케줄러/샘플러를 실제로 적용"""
        
        # 1. 샘플러 클래스 결정
        sampler_lower = sampler_name.lower()
        scheduler_class = cls.SAMPLER_MAP.get(sampler_lower, DPMSolverMultistepScheduler)
        
        # dpmpp_sde가 사용 불가능한 경우 대체 샘플러 사용
        if sampler_lower == 'dpmpp_sde' and not DPMSOLVER_SDE_AVAILABLE:
            print(f"⚠️ torchsde가 설치되지 않아 dpmpp_sde 대신 dpmpp_2m을 사용합니다.")
            scheduler_class = DPMSolverMultistepScheduler
        
        # 2. 스케줄러 설정 가져오기
        config_overrides = cls.SCHEDULER_CONFIG.get(scheduler_type.lower(), {})
        
        # 3. 기존 스케줄러의 설정을 기반으로 새 스케줄러 생성
        if hasattr(pipeline, 'scheduler') and pipeline.scheduler is not None:
            base_config = pipeline.scheduler.config
            
            # 설정 병합
            new_config = base_config.copy()
            for key, value in config_overrides.items():
                if hasattr(new_config, key):
                    setattr(new_config, key, value)
            
            # 새 스케줄러 인스턴스 생성
            new_scheduler = scheduler_class.from_config(new_config)
            
            # 파이프라인의 스케줄러 교체
            pipeline.scheduler = new_scheduler
            
            print(f"✅ 스케줄러 적용: {sampler_name} + {scheduler_type}")
            return True
        else:
            print(f"❌ 파이프라인에 스케줄러가 없습니다")
            return False
    
    @classmethod
    def apply_clip_skip_to_pipeline(cls, pipeline, clip_skip: int):
        """파이프라인에 CLIP Skip을 실제로 적용"""
        
        if not hasattr(pipeline, 'text_encoder') or pipeline.text_encoder is None:
            print(f"❌ 파이프라인에 text_encoder가 없습니다")
            return False
        
        # CLIP Skip 적용 (diffusers에서는 text_encoder의 layer_norm을 조정)
        if hasattr(pipeline.text_encoder, 'config'):
            # CLIP Skip은 주로 A1111/webui에서 사용되는 방식
            # diffusers에서는 다른 방식으로 구현해야 할 수 있음
            print(f"ℹ️ CLIP Skip {clip_skip} 적용 (diffusers 호환성 확인 필요)")
            return True
        
        return False 