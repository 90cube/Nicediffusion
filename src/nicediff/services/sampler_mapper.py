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
        'euler': EulerDiscreteScheduler,
        'euler_a': EulerAncestralDiscreteScheduler,
        'euler a': EulerAncestralDiscreteScheduler,  # 공백 포함 버전
        'euler-a': EulerAncestralDiscreteScheduler,  # 하이픈 포함 버전
        'dpmpp_2m': DPMSolverMultistepScheduler,
        'dpmpp_sde_gpu': DPMSolverMultistepScheduler,  # SDE 알고리즘 사용
        'dpmpp_2m_sde_gpu': DPMSolverMultistepScheduler,  # SDE 알고리즘 사용
        'dpmpp_3m_sde_gpu': DPMSolverMultistepScheduler,  # 3차 방법
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
        
        # SDE 기반 샘플러들에 대한 특별 처리
        if 'sde' in sampler_name.lower():
            config_overrides['algorithm_type'] = 'sde-dpmsolver++'
            if sampler_name == 'dpmpp_3m_sde_gpu':
                config_overrides['solver_order'] = 3
            else:
                config_overrides['solver_order'] = 2
        elif sampler_name == 'dpmpp_2m':
            config_overrides['algorithm_type'] = 'dpmsolver++'
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