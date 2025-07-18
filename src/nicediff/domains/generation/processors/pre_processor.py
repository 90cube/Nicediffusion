"""
전처리기 도메인 로직
프롬프트 처리, 토큰화, 파라미터 검증 등을 담당
"""

from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass


@dataclass
class PreProcessResult:
    """전처리 결과"""
    prompt: str
    negative_prompt: str
    width: int
    height: int
    steps: int
    cfg_scale: float
    seed: int
    is_valid: bool
    errors: list[str]
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class PreProcessor:
    """전처리기"""
    
    def __init__(self):
        self.max_tokens = 77  # CLIP 토크나이저 최대 토큰 수
    
    def validate_dimensions(self, width: int, height: int, model_type: str) -> Tuple[bool, list[str]]:
        """이미지 크기 검증 - 종횡비 미리 설정값 허용"""
        errors = []
        
        if model_type == 'SD15':
            # SD15: 최소 512, 8의 배수 (종횡비 미리 설정값은 예외 허용)
            if width < 512:
                errors.append(f"SD15 모델의 최소 너비는 512입니다. 현재: {width}")
            if height < 512:
                errors.append(f"SD15 모델의 최소 높이는 512입니다. 현재: {height}")
            if width % 8 != 0:
                errors.append(f"SD15 모델의 너비는 8의 배수여야 합니다. 현재: {width}")
            if height % 8 != 0:
                errors.append(f"SD15 모델의 높이는 8의 배수여야 합니다. 현재: {height}")
        else:  # SDXL
            # SDXL: 최소 768 (실전에서 사용되는 768, 832 등 허용), 8의 배수
            if width < 768:
                errors.append(f"SDXL 모델의 최소 너비는 768입니다. 현재: {width}")
            if height < 768:
                errors.append(f"SDXL 모델의 최소 높이는 768입니다. 현재: {height}")
            if width % 8 != 0:
                errors.append(f"SDXL 모델의 너비는 8의 배수여야 합니다. 현재: {width}")
            if height % 8 != 0:
                errors.append(f"SDXL 모델의 높이는 8의 배수여야 합니다. 현재: {height}")
        
        return len(errors) == 0, errors
    
    def validate_steps(self, steps: int) -> Tuple[bool, list[str]]:
        """스텝 수 검증"""
        errors = []
        
        if steps < 1:
            errors.append("스텝 수는 1 이상이어야 합니다.")
        elif steps > 100:
            errors.append("스텝 수는 100 이하여야 합니다.")
        
        return len(errors) == 0, errors
    
    def validate_cfg_scale(self, cfg_scale: float) -> Tuple[bool, list[str]]:
        """CFG 스케일 검증"""
        errors = []
        
        if cfg_scale < 1.0:
            errors.append("CFG 스케일은 1.0 이상이어야 합니다.")
        elif cfg_scale > 30.0:
            errors.append("CFG 스케일은 30.0 이하여야 합니다.")
        
        return len(errors) == 0, errors
    
    def validate_prompt(self, prompt: str) -> Tuple[bool, list[str]]:
        """프롬프트 검증 (고급 프롬프트 시스템으로 1000자 제한 해제)"""
        errors = []
        
        if not prompt or not prompt.strip():
            errors.append("프롬프트는 비어있을 수 없습니다.")
        # 1000자 제한 제거 - 고급 프롬프트 시스템에서 자동 처리
        
        return len(errors) == 0, errors
    
    def estimate_token_count(self, text: str) -> int:
        """간단한 토큰 수 추정 (정확한 토크나이저 없을 때)"""
        if not text.strip():
            return 0
        
        # 공백으로 분할하여 단어 수 추정
        words = text.split()
        return len(words)
    
    def truncate_prompt_simple(self, text: str, max_tokens: int) -> str:
        """간단한 프롬프트 자르기 (토크나이저 없을 때)"""
        if not text.strip():
            return text
        
        words = text.split()
        if len(words) <= max_tokens:
            return text
        
        # 중요한 키워드들을 우선적으로 유지
        truncated_words = words[:max_tokens]
        return ' '.join(truncated_words)
    
    def process_prompts(self, prompt: str, negative_prompt: str, tokenizer=None) -> Tuple[str, str]:
        """프롬프트 처리 (토큰화 및 길이 제한)"""
        processed_prompt = prompt
        processed_negative = negative_prompt
        
        if tokenizer:
            # 실제 토크나이저 사용
            try:
                # 긍정 프롬프트 처리
                text_inputs = tokenizer(prompt, padding="longest", return_tensors="pt")
                input_ids = text_inputs.input_ids[0]
                if len(input_ids) > self.max_tokens:
                    truncated_ids = input_ids[:self.max_tokens]
                    processed_prompt = tokenizer.decode(truncated_ids, skip_special_tokens=True)
                    print(f"⚠️ 긍정 프롬프트가 잘렸습니다 ({len(input_ids)} > {self.max_tokens} 토큰)")
                
                # 부정 프롬프트 처리
                text_inputs = tokenizer(negative_prompt, padding="longest", return_tensors="pt")
                input_ids = text_inputs.input_ids[0]
                if len(input_ids) > self.max_tokens:
                    truncated_ids = input_ids[:self.max_tokens]
                    processed_negative = tokenizer.decode(truncated_ids, skip_special_tokens=True)
                    print(f"⚠️ 부정 프롬프트가 잘렸습니다 ({len(input_ids)} > {self.max_tokens} 토큰)")
                    
            except Exception as e:
                print(f"⚠️ 토크나이저 처리 중 오류: {e}")
                # 오류 시 간단한 방식 사용
                processed_prompt = self.truncate_prompt_simple(prompt, self.max_tokens)
                processed_negative = self.truncate_prompt_simple(negative_prompt, self.max_tokens)
        else:
            # 간단한 방식 사용
            processed_prompt = self.truncate_prompt_simple(prompt, self.max_tokens)
            processed_negative = self.truncate_prompt_simple(negative_prompt, self.max_tokens)
        
        return processed_prompt, processed_negative
    
    def preprocess(self, params: Dict[str, Any], model_type: str, tokenizer=None) -> PreProcessResult:
        """전체 전처리 과정"""
        errors = []
        
        # 파라미터 추출
        prompt = params.get('prompt', '')
        negative_prompt = params.get('negative_prompt', '')
        width = params.get('width', 512)
        height = params.get('height', 512)
        steps = params.get('steps', 20)
        cfg_scale = params.get('cfg_scale', 7.0)
        seed = params.get('seed', -1)
        
        # 각종 검증
        is_valid_dim, dim_errors = self.validate_dimensions(width, height, model_type)
        errors.extend(dim_errors)
        
        is_valid_steps, step_errors = self.validate_steps(steps)
        errors.extend(step_errors)
        
        is_valid_cfg, cfg_errors = self.validate_cfg_scale(cfg_scale)
        errors.extend(cfg_errors)
        
        is_valid_prompt, prompt_errors = self.validate_prompt(prompt)
        errors.extend(prompt_errors)
        
        # 프롬프트 처리
        processed_prompt, processed_negative = self.process_prompts(prompt, negative_prompt, tokenizer)
        
        # 결과 반환
        is_valid = len(errors) == 0
        
        return PreProcessResult(
            prompt=processed_prompt,
            negative_prompt=processed_negative,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            is_valid=is_valid,
            errors=errors
        )
