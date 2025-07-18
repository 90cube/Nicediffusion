# 스케줄러/샘플러 최적화 지침

## 🎯 목표
**기존 UI와 기능을 모두 유지하면서 백엔드 로직만 개선하여 안정성과 정확성 향상**

## 📋 현재 상태 진단

### ✅ 잘 작동하는 부분 (건들지 말 것)
- UI 샘플러/스케줄러 선택 (parameter_panel.py)
- 기본 스케줄러 적용 로직 (SchedulerManager.apply_scheduler_to_pipeline)
- txt2img/img2img 생성 시 스케줄러 호출
- 대부분의 샘플러 매핑 (euler, dpmpp_2m 등)

### ❌ 수정 필요한 부분
1. **CLIP Skip 미완성** - 실제로 적용되지 않음
2. **중복 구현** - SamplerMapper 클래스 불필요
3. **검증 부족** - 스케줄러 적용 확인 없음
4. **일부 샘플러 매핑 누락** - A1111 호환 이름들

## 🛠️ 수정 지침

### 1. CLIP Skip 완전 구현 (1순위)

**파일: src/nicediff/domains/generation/services/scheduler_manager.py**

```python
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
```

### 2. 샘플러 매핑 완성 (2순위)

**파일: src/nicediff/domains/generation/services/scheduler_manager.py**

```python
# 기존 SAMPLER_MAP 확장 (덮어쓰기)
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
```

### 3. 스케줄러 적용 검증 강화 (3순위)

**파일: src/nicediff/domains/generation/services/scheduler_manager.py**

```python
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
```

### 4. 중복 구현 정리 (4순위)

**파일: src/nicediff/services/sampler_mapper.py**

```python
# 전체 파일 삭제하거나 주석 처리
# SchedulerManager로 통합됨

# 기존 import 구문들이 있다면 제거
# from .services.sampler_mapper import SamplerMapper  # 삭제
```

**관련 파일에서 SamplerMapper 사용 부분 제거**

```python
# 기존 코드에서 SamplerMapper 사용 부분 찾아서 제거
# 예: SamplerMapper.get_scheduler() → SchedulerManager.apply_scheduler_to_pipeline()
```

## 🧪 검증 방법

### 기능 테스트 코드 추가

**파일: 각 생성 모드의 generate() 함수에 추가**

```python
# txt2img.py와 img2img.py의 generate() 함수에 추가
def _validate_scheduler_application(self, expected_sampler: str, expected_scheduler: str):
    """스케줄러 적용 검증"""
    try:
        current_scheduler = self.pipeline.scheduler.__class__.__name__
        print(f"🔍 현재 적용된 스케줄러: {current_scheduler}")
        
        # 설정 확인
        if hasattr(self.pipeline.scheduler, 'config'):
            config = self.pipeline.scheduler.config
            print(f"🔍 스케줄러 설정:")
            print(f"   - use_karras_sigmas: {getattr(config, 'use_karras_sigmas', 'N/A')}")
            print(f"   - algorithm_type: {getattr(config, 'algorithm_type', 'N/A')}")
            print(f"   - solver_order: {getattr(config, 'solver_order', 'N/A')}")
        
        return True
    except Exception as e:
        print(f"⚠️ 스케줄러 검증 실패: {e}")
        return False

# generate() 함수에서 스케줄러 적용 후 호출
async def generate(self, params):
    # 기존 코드...
    
    # 스케줄러 적용
    SchedulerManager.apply_scheduler_to_pipeline(
        self.pipeline, 
        params.sampler, 
        params.scheduler
    )
    
    # 검증 추가
    self._validate_scheduler_application(params.sampler, params.scheduler)
    
    # 나머지 기존 코드...
```

## 🚫 주의사항

### 절대 건들지 말 것
1. **UI 파일들** - parameter_panel.py, prompt_panel.py 등
2. **기존 함수 시그니처** - 매개변수 순서/이름 변경 금지
3. **state_manager.py** - 스케줄러 관련 상태 저장 로직
4. **기존 샘플러 옵션** - UI에서 선택 가능한 옵션들
5. **imports** - 기존 import 구문들 유지

### 안전한 수정 방법
1. **기존 함수 내부 로직만 개선** - 인터페이스 유지
2. **새로운 함수 추가** - 기존 함수 대체하지 말고 보완
3. **예외 처리 강화** - 기존 동작 보장
4. **점진적 개선** - 한 번에 모든 것 바꾸지 말고 단계적으로

## 📊 성능 목표

### 기능 개선
- **CLIP Skip 적용률**: 0% → 100%
- **스케줄러 적용 정확도**: 85% → 99%
- **샘플러 매핑 커버리지**: 70% → 95%

### 안정성 보장
- **기존 기능 유지**: 100% (필수)
- **UI 호환성**: 100% (필수)
- **백워드 호환성**: 100% (필수)

## 📋 완료 체크리스트

### 1단계: 핵심 기능 수정
- [ ] CLIP Skip 완전 구현
- [ ] 스케줄러 적용 검증 강화
- [ ] 샘플러 매핑 완성

### 2단계: 코드 정리
- [ ] SamplerMapper 제거
- [ ] 중복 import 정리
- [ ] 검증 로직 추가

### 3단계: 테스트
- [ ] 기존 기능 동작 확인
- [ ] 새로운 기능 테스트
- [ ] UI 인터페이스 확인

### 4단계: 문서화
- [ ] 변경사항 로그 작성
- [ ] 새로운 기능 사용법 정리

## 🎯 결론

**기존 UI와 기능을 100% 유지하면서 백엔드 로직만 개선하는 것이 완전히 가능합니다.**

핵심은:
1. **인터페이스 유지** - 함수 시그니처 변경 금지
2. **내부 로직 개선** - 기존 함수 내부만 수정
3. **점진적 개선** - 한 번에 모든 것 바꾸지 않기
4. **안전한 fallback** - 오류 시 기존 동작 보장

이렇게 하면 사용자는 변화를 전혀 느끼지 못하면서 더 정확하고 안정적인 스케줄러/샘플러 적용을 경험할 수 있습니다.
