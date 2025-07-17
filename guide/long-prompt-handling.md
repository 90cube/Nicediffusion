# 📝 긴 프롬프트 처리 가이드

## 🎯 문제 상황
- **CLIP 토크나이저 제한**: SD15는 77 토큰, SDXL은 225 토큰으로 제한
- **긴 프롬프트 잘림**: 77 토큰을 초과하면 자동으로 잘림
- **중요 정보 손실**: 핵심 키워드가 잘려서 원하는 결과를 얻기 어려움

## 🔧 해결 방법

### 1. **프롬프트 분할 및 병합 (Chunking)**
```
긴 프롬프트 → 여러 개의 짧은 프롬프트로 분할 → 각각 인코딩 → 병합
```

### 2. **중요도 기반 우선순위**
```
1순위: 핵심 키워드 (주제, 스타일)
2순위: 세부 묘사 (색상, 질감)
3순위: 배경, 분위기
```

### 3. **BREAK 키워드 활용**
```
"beautiful girl, BREAK, wearing red dress, BREAK, in garden"
```

### 4. **프롬프트 압축 기법**
- 불필요한 단어 제거
- 동의어 사용으로 토큰 절약
- 핵심 키워드만 추출

## 🛠️ 구현 방법

### 백엔드 구현
```python
class LongPromptHandler:
    def __init__(self, max_tokens=77):
        self.max_tokens = max_tokens
    
    def split_prompt(self, prompt: str) -> List[str]:
        """프롬프트를 토큰 제한에 맞게 분할"""
        # 구현 로직
        pass
    
    def merge_embeddings(self, embeddings: List[torch.Tensor]) -> torch.Tensor:
        """분할된 임베딩을 병합"""
        # 구현 로직
        pass
    
    def prioritize_keywords(self, prompt: str) -> str:
        """핵심 키워드 우선순위 적용"""
        # 구현 로직
        pass
```

### UI 개선
- 토큰 카운터 표시
- 프롬프트 길이 경고
- 자동 분할 옵션
- 핵심 키워드 하이라이트

## 📊 사용 예시

### 긴 프롬프트 예시
```
"a beautiful young woman with long flowing hair, wearing an elegant red dress with intricate embroidery, standing in a magical garden filled with blooming flowers, soft golden sunlight filtering through the trees, cinematic lighting, highly detailed, 8k resolution"
```

### 분할 결과
```
Chunk 1: "a beautiful young woman with long flowing hair"
Chunk 2: "wearing an elegant red dress with intricate embroidery"  
Chunk 3: "standing in a magical garden filled with blooming flowers"
Chunk 4: "soft golden sunlight filtering through the trees"
Chunk 5: "cinematic lighting, highly detailed, 8k resolution"
```

## ⚡ 성능 최적화

### 1. **캐싱 시스템**
- 자주 사용되는 프롬프트 조합 캐싱
- 임베딩 재사용으로 속도 향상

### 2. **배치 처리**
- 여러 프롬프트를 한 번에 처리
- GPU 메모리 효율적 사용

### 3. **점진적 로딩**
- 긴 프롬프트를 단계적으로 처리
- 사용자 경험 개선

## 🎨 실제 적용

### 1. **자동 분할 모드**
- 사용자가 긴 프롬프트 입력 시 자동으로 분할
- 각 청크의 중요도 표시

### 2. **수동 분할 모드**
- 사용자가 직접 청크 단위로 입력
- BREAK 키워드로 구분

### 3. **하이브리드 모드**
- 자동 분할 + 사용자 수정
- 실시간 토큰 카운터

## 📈 효과 측정

### 품질 지표
- 프롬프트 완성도
- 이미지 품질 점수
- 사용자 만족도

### 성능 지표
- 처리 속도
- 메모리 사용량
- 토큰 효율성

## 🔮 향후 개선 방향

### 1. **AI 기반 프롬프트 최적화**
- GPT를 활용한 자동 압축
- 컨텍스트 기반 키워드 추출

### 2. **학습 기반 분할**
- 사용 패턴 학습
- 개인화된 분할 전략

### 3. **멀티모달 통합**
- 이미지 참조를 통한 프롬프트 보완
- 시각적 컨텍스트 활용 