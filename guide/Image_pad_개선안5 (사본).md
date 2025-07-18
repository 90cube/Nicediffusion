## 🔧 이미지 생성 시스템 문제 정리

### 발생한 문제들

**Preview 관련 문제**
- 생성된 이미지가 image pad에 표시되지 않음
- i2i 모드에서 업로드한 이미지가 즉시 preview에 나타나지 않음
- 생성하기 버튼 클릭 시 preview가 사라짐

**i2i 모드 기능 문제**
- 디노이징이 정상 작동하지 않음 (preview 이미지를 제대로 디코딩하지 못하는 것으로 추정)
- 원본과 결과물 비교 기능 부재

**LoRA 관련 문제**
- LoRA 적용 여부를 확인할 수 없음

### 📝 Code Agent AI 질문 전략

**효과적인 질문 구성:**

```
"이미지 생성 WebUI에서 다음 문제들이 발생하고 있습니다:

1. 환경 정보:
   - 사용 중인 UI: [Gradio/Streamlit/기타]
   - 프레임워크: [Stable Diffusion WebUI/ComfyUI/기타]
   - 관련 코드 파일 위치: [경로]

2. 구체적 문제 상황:
   - Image Preview 컴포넌트가 생성 후 업데이트되지 않음
   - i2i 모드에서 FileUpload 이벤트와 Preview 연동 실패
   - 디노이징 강도가 적용되지 않는 것으로 보임

3. 현재 코드 구조:
   [관련 코드 스니펫 첨부]

디버깅을 위한 체크포인트와 수정 방향을 제안해주세요."
```

### 🛠️ 예상 해결 방법

**Preview 문제 해결:**
- 이미지 생성 콜백 함수에서 UI 업데이트 로직 확인
- State 관리 및 이벤트 리스너 점검
- 비동기 처리 관련 Promise/await 구조 검토

**i2i 모드 수정사항:**
```python
# 업로드 즉시 preview 표시
def on_image_upload(file):
    preview_component.update(value=file)
    return file

# 디노이징 강도 적용 확인
def generate_i2i(image, denoising_strength):
    # 이미지 전처리 로직 확인
    processed_img = preprocess_image(image)
    # 디노이징 파라미터 전달 확인
    result = pipeline(image=processed_img, strength=denoising_strength)
```

**비교 기능 구현:**
- 이미지 슬라이더 컴포넌트 추가
- 원본 이미지 저장 및 표시 로직 구현
- CSS/JavaScript로 비교 UI 구성

**LoRA 검증 방법:**
- 콘솔 로그에 LoRA 로딩 메시지 확인
- 생성 파라미터에 LoRA 가중치 포함 여부 체크
- 테스트용 극단적 LoRA 설정으로 효과 확인

### 🎯 추가 디버깅 팁

**로그 추가 위치:**
- 이미지 업로드 시점
- Preview 컴포넌트 업데이트 함수
- 생성 파이프라인 시작/종료
- LoRA 모델 로딩 부분

**테스트 순서:**
1. 개발자 도구 콘솔에서 에러 메시지 확인
2. 네트워크 탭에서 이미지 전송 상태 체크
3. 각 컴포넌트의 state 값 실시간 모니터링
4. 단계별 breakpoint 설정하여 데이터 흐름 추적

이렇게 체계적으로 접근하면 문제의 원인을 더 빠르게 찾을 수 있을 것입니다.
