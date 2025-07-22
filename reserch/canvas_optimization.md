# Canvas 준비 시간 단축 최적화 가이드

## 현재 문제점
- Canvas 준비 시간이 5초로 설정되어 있어 사용자 경험이 저하됨
- Fabric.js 초기화가 느림
- 이미지 로딩 시 Canvas 대기 시간이 오래 걸림

## 최적화 방안

### 1. 타임아웃 단축
- 기존: 5.0초 → 변경: 2.0초
- Canvas가 준비되지 않으면 즉시 폴백 모드로 전환

### 2. Canvas 초기화 최적화
```javascript
// 최적화된 Canvas 초기화
class OptimizedCanvasManager {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.canvas = null;
        this.isInitialized = false;
        this.initPromise = null;
        this.init();
    }

    async init() {
        try {
            console.log('🎨 최적화된 Canvas 초기화 시작');
            
            // 비동기 초기화
            this.initPromise = new Promise((resolve, reject) => {
                // Fabric.js 지연 로딩
                if (typeof fabric === 'undefined') {
                    // Fabric.js가 로드되지 않은 경우
                    this.loadFabricJS().then(() => {
                        this.initializeCanvas();
                        resolve();
                    }).catch(reject);
                } else {
                    this.initializeCanvas();
                    resolve();
                }
            });

            await this.initPromise;
            this.isInitialized = true;
            console.log('✅ 최적화된 Canvas 초기화 완료');
            
        } catch (error) {
            console.error('❌ Canvas 초기화 실패:', error);
        }
    }

    initializeCanvas() {
        // 최소한의 설정으로 빠른 초기화
        this.canvas = new fabric.Canvas(this.canvasId, {
            width: 800,  // 기본 크기
            height: 600,
            backgroundColor: '#2d3748',
            selection: false,  // 초기에는 선택 비활성화
            renderOnAddRemove: false  // 렌더링 최적화
        });

        // 필수 이벤트만 설정
        this.setupEssentialListeners();
    }

    setupEssentialListeners() {
        // 필수 이벤트만 설정하여 초기화 속도 향상
        this.canvas.on('after:render', () => {
            this.canvas.renderOnAddRemove = true;  // 초기화 후 렌더링 활성화
        });
    }
}
```

### 3. 이미지 로딩 최적화
```javascript
// 최적화된 이미지 로딩
async loadImageOptimized(base64Data) {
    if (!this.isInitialized) {
        // Canvas가 준비되지 않으면 즉시 폴백
        return false;
    }

    try {
        // 이미지 크기 미리 계산
        const img = new Image();
        img.src = `data:image/png;base64,${base64Data}`;
        
        await new Promise((resolve) => {
            img.onload = resolve;
        });

        // 최적화된 크기 계산
        const optimizedSize = this.calculateOptimalSize(img.width, img.height);
        
        // Fabric.js 이미지 생성
        fabric.Image.fromURL(img.src, (fabricImg) => {
            fabricImg.scaleToWidth(optimizedSize.width);
            this.canvas.add(fabricImg);
            this.canvas.renderAll();
        });

        return true;
    } catch (error) {
        console.error('이미지 로딩 실패:', error);
        return false;
    }
}
```

### 4. 폴백 시스템 강화
```python
def display_with_fallback(self, image):
    """Canvas 실패 시 즉시 폴백으로 전환"""
    try:
        # Canvas 시도 (2초 타임아웃)
        if self.canvas_bridge and self.canvas_bridge.wait_for_ready(timeout=2.0):
            return self.load_image_to_canvas(image)
        else:
            # 즉시 폴백으로 전환
            self._fallback_display(image)
            return True
    except Exception as e:
        # 오류 발생 시 즉시 폴백
        self._fallback_display(image)
        return True
```

## 적용된 변경사항

### 1. 타임아웃 단축
- `wait_for_ready(timeout=5.0)` → `wait_for_ready(timeout=2.0)`

### 2. 즉시 폴백 시스템
- Canvas 준비 실패 시 즉시 기존 표시 방식으로 전환
- 사용자 대기 시간 최소화

### 3. 로그 최적화
- 불필요한 로그 제거
- 성능에 영향을 주는 로그 최소화

## 예상 효과
- Canvas 준비 시간: 5초 → 2초 (60% 단축)
- 사용자 경험 개선
- 시스템 안정성 향상 