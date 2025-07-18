# VAE 처리 최적화 지침

## 🎯 목표
**복잡한 VAE 처리 로직을 단순화하여 성능과 안정성을 개선**

## 📋 작업 지침

### 1. **즉시 수정 (1순위)**
```python
# src/nicediff/domains/generation/modes/img2img.py
# _encode_image() 함수 80줄 → 15줄로 단순화

def _encode_image(self, image: Image.Image) -> torch.Tensor:
    """VAE 인코딩 (단순화 버전)"""
    # RGB 변환
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # 단일 전처리 방법만 사용 (성공률 95%)
    import torchvision.transforms as T
    transform = T.Compose([
        T.ToTensor(),
        T.Normalize([0.5], [0.5])
    ])
    
    with torch.no_grad():
        tensor = transform(image).unsqueeze(0)
        tensor = tensor.to(self.device, dtype=self.pipeline.vae.dtype)
        
        # VAE 인코딩
        latent = self.pipeline.vae.encode(tensor).latent_dist.sample()
        latent *= self.pipeline.vae.config.scaling_factor
        
    return latent

# 제거할 것들:
# - 모든 print 디버깅 코드 (80% 분량)
# - 3가지 전처리 시도 로직 
# - 복잡한 fallback 처리
# - 상세한 검증 로직
```

### 2. **프리뷰 처리 개선 (2순위)**
```python
# 이미지 업로드 처리 단순화
def handle_image_upload(self, upload_event):
    """업로드 이미지 처리 (리사이즈 금지)"""
    
    # PIL 이미지 변환만
    image = Image.open(io.BytesIO(upload_event.content))
    
    # 상태 저장 (원본 그대로)
    self.state.set('init_image', image)
    
    # 프리뷰 표시 (CSS 반응형)
    self.update_preview_display(image)

# 제거할 것들:
# - 모든 thumbnail(), resize() 호출
# - 불필요한 이미지 복사
# - 프리뷰용 메모리 할당
```

### 3. **VAE 로딩 단순화 (3순위)**
```python
# state_manager.py의 VAE 로딩 로직 단순화
async def load_vae(self, vae_path: str):
    """VAE 로드 (단순화)"""
    try:
        vae_model = AutoencoderKL.from_pretrained(vae_path, torch_dtype=torch.float16)
        self.pipeline.vae = vae_model.to(self.device)
        self.set('current_vae_path', vae_path)
        return True
    except Exception as e:
        print(f"VAE 로드 실패: {e}")
        return False

# 제거할 것들:
# - 복잡한 에러 처리
# - 과도한 로그 출력
# - 불필요한 검증 로직
```

## 🚫 하지 말 것

1. **새로운 모듈 생성 금지** - 기존 코드 수정만
2. **아키텍처 변경 금지** - 성능 우선
3. **추가 라이브러리 금지** - 의존성 증가 방지
4. **프리뷰 이미지 리사이즈 금지** - CSS가 처리
5. **디버깅 코드 추가 금지** - 기존 것도 모두 제거

## ✅ 성능 목표

- **처리시간**: VAE 인코딩 1-2초 → 0.3초
- **메모리**: 불필요한 복사 제거로 -500MB
- **코드량**: 80줄 → 15줄로 단순화
- **안정성**: 에러 케이스 90% 감소

## 🔧 검증 방법

```python
# 성능 테스트 코드
import time
start_time = time.time()
latent = self._encode_image(test_image)
end_time = time.time()
print(f"VAE 인코딩 시간: {end_time - start_time:.3f}초")

# 메모리 사용량 체크
import psutil
process = psutil.Process()
memory_usage = process.memory_info().rss / 1024 / 1024  # MB
print(f"메모리 사용량: {memory_usage:.1f}MB")
```

## 📝 완료 체크리스트

- [ ] `_encode_image()` 함수 80줄 → 15줄 단순화
- [ ] 모든 디버깅 print문 제거
- [ ] 3가지 전처리 시도 로직 제거 
- [ ] 프리뷰 이미지 리사이즈 로직 제거
- [ ] VAE 로딩 로직 단순화
- [ ] 성능 테스트 통과 확인

**핵심: 복잡한 것을 단순하게, 안정적으로, 빠르게!**
