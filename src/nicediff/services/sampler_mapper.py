from diffusers import (
    EulerDiscreteScheduler,
    DPMSolverMultistepScheduler, 
    DPMSolverSinglestepScheduler,
    DDIMScheduler,
    PNDMScheduler,
    EulerAncestralDiscreteScheduler
)

class SamplerMapper:
    """ComfyUI 샘플러명을 diffusers 스케줄러로 매핑"""
    
    SAMPLER_MAP = {
        # 기본 샘플러들
        'euler': EulerDiscreteScheduler,
        'euler_a': EulerAncestralDiscreteScheduler,
        'euler a': EulerAncestralDiscreteScheduler,  # 공백 포함 버전
        'euler-a': EulerAncestralDiscreteScheduler,  # 하이픈 포함 버전
        
        # DPM++ 시리즈
        'dpmpp_2m': DPMSolverMultistepScheduler,
        'dpmpp_2s_a': DPMSolverMultistepScheduler,  # Ancestral sampling
        'dpmpp_sde': DPMSolverMultistepScheduler,  # SDE 알고리즘
        'dpmpp_2m_sde': DPMSolverMultistepScheduler,  # 2M + SDE 조합
        'dpmpp_3m_sde': DPMSolverMultistepScheduler,  # 3차 방법 + SDE
        
        # 기존 호환성 (GPU 접미사)
        'dpmpp_sde_gpu': DPMSolverMultistepScheduler,
        'dpmpp_2m_sde_gpu': DPMSolverMultistepScheduler,
        'dpmpp_3m_sde_gpu': DPMSolverMultistepScheduler,
        
        # 기타 샘플러들
        'ddim': DDIMScheduler,
        'pndm': PNDMScheduler,
    }
    
    SCHEDULER_CONFIG = {
        'normal': {},
        'karras': {'use_karras_sigmas': True},
        'exponential': {'beta_schedule': 'exponential'},
        'sgm_uniform': {'timestep_spacing': 'trailing'},
        'simple': {'timestep_spacing': 'leading'},
        'ddim_uniform': {'timestep_spacing': 'linspace'}
    }
    
    @staticmethod
    def get_scheduler(sampler_name: str, scheduler_type: str, pipeline=None):
        """적절한 스케줄러 인스턴스 반환"""
        scheduler_class = SamplerMapper.SAMPLER_MAP.get(sampler_name, EulerDiscreteScheduler)
        config_overrides = SamplerMapper.SCHEDULER_CONFIG.get(scheduler_type, {})
        
        # DPM++ 시리즈별 특별 처리
        if sampler_name == 'dpmpp_2m':
            config_overrides['algorithm_type'] = 'dpmsolver++'
            config_overrides['solver_order'] = 2
        elif sampler_name == 'dpmpp_2s_a':
            config_overrides['algorithm_type'] = 'dpmsolver++'
            config_overrides['solver_order'] = 2
            config_overrides['use_karras_sigmas'] = True
        elif 'sde' in sampler_name.lower():
            config_overrides['algorithm_type'] = 'sde-dpmsolver++'
            if '3m' in sampler_name.lower():
                config_overrides['solver_order'] = 3
            else:
                config_overrides['solver_order'] = 2
        
        # pipeline이 제공되면 기존 설정을 기반으로 생성
        if pipeline and hasattr(pipeline, 'scheduler'):
            base_config = pipeline.scheduler.config
            return scheduler_class.from_config(base_config, **config_overrides)
        else:
            # 기본 설정으로 생성
            try:
                return scheduler_class(**config_overrides)
            except TypeError:
                # 일부 설정이 지원되지 않는 경우 기본값으로 생성
                return scheduler_class()