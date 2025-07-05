from diffusers import (
    EulerDiscreteScheduler,
    DPMSolverMultistepScheduler, 
    DPMSolverSinglestepScheduler,
    DDIMScheduler,
    PNDMScheduler
)

class SamplerMapper:
    """ComfyUI 샘플러명을 diffusers 스케줄러로 매핑"""
    
    SAMPLER_MAP = {
        'euler': EulerDiscreteScheduler,
        'dpmpp_2m': DPMSolverMultistepScheduler,
        'dpmpp_sde_gpu': DPMSolverSinglestepScheduler,
        'dpmpp_2m_sde_gpu': DPMSolverMultistepScheduler,
        'dpmpp_3m_sde_gpu': DPMSolverMultistepScheduler,
        'ddim': DDIMScheduler,
        'pndm': PNDMScheduler,
    }
    
    SCHEDULER_CONFIG = {
        'normal': {},
        'karras': {'use_karras_sigmas': True},
        'exponential': {'exponential': True},
        'sgm_uniform': {'sgm_uniform': True},
        'simple': {'simple': True},
        'ddim_uniform': {'ddim_uniform': True}
    }
    
    @staticmethod
    def get_scheduler(sampler_name: str, scheduler_type: str):
        """적절한 스케줄러 인스턴스 반환"""
        scheduler_class = SamplerMapper.SAMPLER_MAP.get(sampler_name, EulerDiscreteScheduler)
        config = SamplerMapper.SCHEDULER_CONFIG.get(scheduler_type, {})
        return scheduler_class.from_config(scheduler_class.default_config(), **config)