# Nice Diffusion Canvas 초기화 문제 해결 가이드

## 🎯 목적
Canvas 매니저가 초기화되지 않는 문제를 해결하고, 생성된 이미지가 원본 크기로 표시되도록 수정

## 🔍 현재 문제점
1. `window.imagePadCanvas`가 `undefined`로 표시됨
2. Canvas 초기화 실패
3. JavaScript 코드 실행 타이밍 문제
4. 생성된 이미지가 Canvas에 표시되지 않음

## ⚠️ 주의사항
- **기존 UI 구조를 변경하지 마세요**
- **다른 컴포넌트에 영향을 주지 마세요**
- **StateManager의 기존 이벤트를 유지하세요**
- **모든 수정은 ImagePad 클래스 내부에서만 진행하세요**

## 📝 수정할 파일
`src/nicediff/ui/image_viewer.py`

## 🔧 전체 수정 코드

```python
"""
중앙 이미지 뷰어/캔버스 컴포넌트
"""

from nicegui import ui
from pathlib import Path
from ..core.state_manager import StateManager
import asyncio
from PIL import Image
import numpy as np
from typing import Optional, Dict, Any
import base64
import io
import uuid

class ImagePad:
    """이미지 패드 컴포넌트"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_mode = 'txt2img'
        self.current_image = None
        self.image_container = None
        self.canvas_id = f'imagepad-canvas-{uuid.uuid4().hex[:8]}'  # 고유 ID 생성
        self.upload_area = None
        self.status_label = None
        self.canvas_initialized = False
        self.pending_image = None  # 초기화 전 대기 이미지
        
        # 이벤트 구독
        self.state.subscribe('mode_changed', self._on_mode_changed)
        self.state.subscribe('image_generated', self._on_image_generated)
        self.state.subscribe('generation_completed', self._on_generation_completed)
        self.state.subscribe('uploaded_image', self._on_uploaded_image_changed)
        
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full bg-gray-800 rounded-lg overflow-hidden relative') as main_container:
            self.main_container = main_container
            
            # 상단 도구바
            with ui.row().classes('absolute top-2 left-2 right-2 justify-between items-center z-10'):
                ui.label('🖼️ 이미지 패드').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                ui.button(icon='refresh', on_click=self._refresh_image_pad).props('round color=white text-color=black size=sm')
            
            # 메인 이미지 영역 - 기존 구조 유지하면서 Canvas 추가
            with ui.element('div').classes('w-full h-full flex items-center justify-center') as image_container:
                self.image_container = image_container
                
                # Canvas 요소 직접 생성
                self.canvas_element = ui.html(f'''
                    <canvas id="{self.canvas_id}" 
                            style="width: 100%; height: 100%; display: block; position: absolute; top: 0; left: 0;">
                    </canvas>
                ''').classes('w-full h-full')
                
                # 플레이스홀더는 Canvas 위에 오버레이
                self.placeholder_container = ui.element('div').classes(
                    'absolute inset-0 flex items-center justify-center'
                ).style('z-index: 10;')
                
                await self._show_placeholder()
            
            # 우측 하단 상태 표시
            with ui.row().classes('absolute bottom-2 right-2 z-10'):
                self.status_label = ui.label('준비됨').classes('text-white text-sm bg-gray-800 px-2 py-1 rounded')
        
        # Canvas 초기화 (렌더링 후 타이머로 실행)
        ui.timer(0.1, lambda: self._init_canvas(), once=True)
    
    def _init_canvas(self):
        """Canvas 초기화 - 타이머로 지연 실행"""
        try:
            # 디버깅용 로그
            print(f"🎨 Canvas 초기화 시작: {self.canvas_id}")
            
            # JavaScript 코드를 문자열로 정의
            init_script = f'''
                console.log("🚀 Canvas 초기화 스크립트 실행 시작");
                
                // 전역 Canvas 매니저 생성
                if (!window.imagePadCanvasManager) {{
                    window.imagePadCanvasManager = {{}};
                }}
                
                // 이 인스턴스의 Canvas 매니저
                const canvasId = '{self.canvas_id}';
                const canvas = document.getElementById(canvasId);
                
                if (!canvas) {{
                    console.error("❌ Canvas 요소를 찾을 수 없음:", canvasId);
                    return;
                }}
                
                console.log("✅ Canvas 요소 찾음:", canvas);
                
                // Canvas 매니저 객체 생성
                const manager = {{
                    canvas: canvas,
                    ctx: canvas.getContext('2d'),
                    currentImage: null,
                    
                    init: function() {{
                        console.log("📐 Canvas 크기 설정");
                        this.resizeCanvas();
                        this.drawCheckerboard();
                        
                        // 리사이즈 이벤트
                        const resizeHandler = () => this.resizeCanvas();
                        window.addEventListener('resize', resizeHandler);
                        
                        console.log("✅ Canvas 초기화 완료");
                    }},
                    
                    resizeCanvas: function() {{
                        const rect = this.canvas.getBoundingClientRect();
                        this.canvas.width = rect.width;
                        this.canvas.height = rect.height;
                        
                        if (this.currentImage) {{
                            this.drawImage(this.currentImage);
                        }} else {{
                            this.drawCheckerboard();
                        }}
                    }},
                    
                    drawCheckerboard: function() {{
                        const ctx = this.ctx;
                        const size = 20;
                        
                        ctx.fillStyle = '#2a2a2a';
                        ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
                        
                        ctx.fillStyle = '#3a3a3a';
                        for (let x = 0; x < this.canvas.width; x += size * 2) {{
                            for (let y = 0; y < this.canvas.height; y += size * 2) {{
                                ctx.fillRect(x, y, size, size);
                                ctx.fillRect(x + size, y + size, size, size);
                            }}
                        }}
                    }},
                    
                    drawImage: function(img) {{
                        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                        this.drawCheckerboard();
                        
                        const scale = Math.min(
                            this.canvas.width / img.width,
                            this.canvas.height / img.height
                        );
                        
                        const width = img.width * scale;
                        const height = img.height * scale;
                        const x = (this.canvas.width - width) / 2;
                        const y = (this.canvas.height - height) / 2;
                        
                        this.ctx.drawImage(img, x, y, width, height);
                        
                        // 이미지 정보 표시
                        this.ctx.save();
                        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                        this.ctx.fillRect(10, this.canvas.height - 40, 250, 30);
                        this.ctx.fillStyle = 'white';
                        this.ctx.font = '12px Arial';
                        this.ctx.fillText(`원본: ${{img.width}} x ${{img.height}}px`, 15, this.canvas.height - 25);
                        this.ctx.fillText(`표시: ${{Math.round(width)}} x ${{Math.round(height)}}px`, 15, this.canvas.height - 10);
                        this.ctx.restore();
                    }},
                    
                    loadImageFromBase64: function(base64Data) {{
                        console.log("🖼️ Base64 이미지 로드 시작");
                        const img = new Image();
                        img.onload = () => {{
                            console.log("✅ 이미지 로드 성공:", img.width, "x", img.height);
                            this.currentImage = img;
                            this.drawImage(img);
                        }};
                        img.onerror = (e) => {{
                            console.error("❌ 이미지 로드 실패:", e);
                        }};
                        img.src = 'data:image/png;base64,' + base64Data;
                    }}
                }};
                
                // 전역 객체에 저장
                window.imagePadCanvasManager[canvasId] = manager;
                window.imagePadCanvas = manager;  // 호환성을 위한 전역 참조
                
                // 초기화 실행
                manager.init();
                
                console.log("✅ Canvas 매니저 생성 완료");
                
                // Python에 초기화 완료 알림
                return true;
            '''
            
            # JavaScript 실행
            ui.run_javascript(init_script)
            
            # 초기화 플래그 설정
            self.canvas_initialized = True
            print(f"✅ Python: Canvas 초기화 완료")
            
            # 대기 중인 이미지가 있으면 표시
            if self.pending_image:
                print(f"📸 대기 중인 이미지 표시")
                ui.timer(0.2, lambda: self._display_pending_image(), once=True)
                
        except Exception as e:
            print(f"❌ Canvas 초기화 실패: {e}")
            import traceback
            traceback.print_exc()
    
    def _display_pending_image(self):
        """대기 중인 이미지 표시"""
        if self.pending_image and self.canvas_initialized:
            asyncio.create_task(self._display_image_on_canvas(self.pending_image))
            self.pending_image = None
    
    async def _show_placeholder(self):
        """플레이스홀더 표시"""
        current_mode = self.state.get('current_mode', 'txt2img')
        
        if self.placeholder_container:
            try:
                self.placeholder_container.clear()
            except RuntimeError as e:
                if "deleted" in str(e).lower():
                    print("⚠️ 클라이언트가 삭제되었습니다. 플레이스홀더 표시를 건너뜁니다.")
                    return
                else:
                    raise e
                    
            with self.placeholder_container:
                if current_mode in ['img2img', 'inpaint', 'upscale']:
                    await self._show_upload_area()
                else:
                    # t2i 모드 - 생성 대기 메시지
                    with ui.column().classes('text-center bg-gray-700 bg-opacity-50 p-4 rounded').style('pointer-events: none;'):
                        ui.icon('brush', size='3em').classes('text-gray-400 mb-2')
                        ui.label('생성 버튼을 클릭하여 이미지를 생성하세요').classes('text-gray-300')
    
    async def _show_upload_area(self):
        """업로드 영역 표시"""
        with ui.card().classes('p-8 bg-gray-700').style('pointer-events: auto;'):
            ui.icon('cloud_upload', size='4em').classes('text-gray-400')
            ui.label('이미지를 업로드하세요').classes('text-gray-300 mt-2')
            
            self.upload_area = ui.upload(
                on_upload=self._handle_upload,
                auto_upload=True,
                multiple=False
            ).props('accept=image/*').classes('mt-4')
    
    async def _display_image_on_canvas(self, image):
        """Canvas에 이미지 표시"""
        if not image:
            return
        
        try:
            # Canvas 초기화 확인
            if not self.canvas_initialized:
                print("⚠️ Canvas가 아직 초기화되지 않음. 대기 중...")
                self.pending_image = image
                return
            
            print(f"🎨 이미지를 Canvas에 표시: {image.size}")
            
            # PIL Image를 base64로 변환
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # JavaScript로 이미지 표시 (디버깅 로그 포함)
            display_script = f'''
                console.log("🔍 Canvas 매니저 상태 확인:");
                console.log("- window.imagePadCanvas:", window.imagePadCanvas);
                console.log("- window.imagePadCanvas?.loadImageFromBase64:", window.imagePadCanvas?.loadImageFromBase64);
                
                if (window.imagePadCanvas && window.imagePadCanvas.loadImageFromBase64) {{
                    console.log("✅ Canvas 매니저 찾음. 이미지 로드 시작...");
                    window.imagePadCanvas.loadImageFromBase64('{img_str}');
                }} else if (window.imagePadCanvasManager && window.imagePadCanvasManager['{self.canvas_id}']) {{
                    console.log("✅ Canvas 매니저 찾음 (ID 방식). 이미지 로드 시작...");
                    window.imagePadCanvasManager['{self.canvas_id}'].loadImageFromBase64('{img_str}');
                }} else {{
                    console.error("❌ Canvas 매니저를 찾을 수 없음");
                    console.log("🔄 Canvas 초기화 대기 중...");
                    
                    // 재시도
                    setTimeout(() => {{
                        if (window.imagePadCanvas && window.imagePadCanvas.loadImageFromBase64) {{
                            console.log("✅ 재시도 성공");
                            window.imagePadCanvas.loadImageFromBase64('{img_str}');
                        }} else {{
                            console.error("❌ Canvas 초기화 실패");
                        }}
                    }}, 500);
                }}
            '''
            
            ui.run_javascript(display_script)
            
            # 플레이스홀더 숨기기
            if self.placeholder_container:
                self.placeholder_container.style('display: none;')
            
            # 현재 이미지 저장
            self.current_image = image
            
            # 상태 업데이트
            if self.status_label:
                self.status_label.set_text(f'표시됨: {image.width}×{image.height}')
                
        except Exception as e:
            print(f"❌ Canvas에 이미지 표시 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def _on_image_generated(self, data):
        """이미지 생성 이벤트 처리"""
        await self._handle_generated_images(data)
    
    async def _on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리"""
        await self._handle_generated_images(event_data)
    
    async def _handle_generated_images(self, data):
        """생성된 이미지 처리"""
        try:
            images = None
            
            if isinstance(data, dict):
                images = data.get('images', [])
                if not images and 'image_path' in data:
                    image_path = data.get('image_path')
                    if image_path and Path(image_path).exists():
                        pil_image = Image.open(image_path)
                        images = [pil_image]
            elif isinstance(data, list):
                images = data
                
            if images and len(images) > 0:
                print(f"✅ 생성된 이미지 수신: {len(images)}개")
                
                # 첫 번째 이미지를 Canvas에 표시
                await self._display_image_on_canvas(images[0])
                
                # 워크플로우를 위한 상태 저장
                self.state.set('last_generated_images', images)
                
                if self.state.get('current_mode') == 'txt2img':
                    self.state.set('pending_init_image', images[0])
                    
                # 상태 업데이트
                if self.status_label:
                    self.status_label.set_text('생성 완료')
                    self.status_label.classes('text-green-400 text-white text-sm bg-gray-800 px-2 py-1 rounded')
                    
        except Exception as e:
            print(f"❌ 생성된 이미지 처리 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def _on_mode_changed(self, data):
        """모드 변경 이벤트 처리"""
        mode = data.get('mode', 'txt2img') if isinstance(data, dict) else data
        old_mode = self.current_mode
        self.current_mode = mode
        
        print(f"🔄 모드 변경: {old_mode} → {mode}")
        
        # t2i → i2i 전환 시
        if old_mode == 'txt2img' and mode in ['img2img', 'inpaint', 'upscale']:
            if self.current_image:
                self.state.set('init_image', self.current_image)
            else:
                pending_image = self.state.get('pending_init_image')
                if pending_image:
                    self.state.set('init_image', pending_image)
                    await self._display_image_on_canvas(pending_image)
        
        # UI 새로고침
        await self._show_placeholder()
    
    async def _on_uploaded_image_changed(self, np_image):
        """업로드된 이미지 변경 시"""
        if np_image is not None:
            # numpy to PIL
            pil_image = Image.fromarray(np_image.astype('uint8'))
            await self._display_image_on_canvas(pil_image)
    
    async def _handle_upload(self, e):
        """파일 업로드 처리"""
        try:
            content = e.content.read()
            pil_image = Image.open(io.BytesIO(content))
            
            # Canvas에 표시
            await self._display_image_on_canvas(pil_image)
            
            # 상태 저장
            self.state.set('init_image', pil_image)
            self.state.set('uploaded_image', np.array(pil_image))
            
            ui.notify(f'업로드 완료: {pil_image.width}×{pil_image.height}', type='positive')
            
        except Exception as ex:
            print(f"❌ 이미지 업로드 실패: {ex}")
            ui.notify('이미지 업로드 실패', type='negative')
    
    def _refresh_image_pad(self):
        """Image Pad 새로고침"""
        if self.current_image:
            # 현재 이미지 다시 표시
            asyncio.create_task(self._display_image_on_canvas(self.current_image))
        else:
            # Canvas 초기화
            ui.run_javascript('''
                if (window.imagePadCanvas) {
                    window.imagePadCanvas.drawCheckerboard();
                }
            ''')
```

## 🧪 테스트 절차

1. **Canvas 초기화 확인**
   - F12 콘솔에서 "Canvas 초기화 완료" 메시지 확인
   - `window.imagePadCanvas` 객체 존재 확인

2. **이미지 생성 테스트**
   - T2I 모드에서 이미지 생성
   - Canvas에 원본 크기로 표시되는지 확인
   - 콘솔에서 오류 메시지 확인

3. **모드 전환 테스트**
   - T2I → I2I 전환 시 이미지 유지 확인
   - 업로드 기능 테스트

## 🔍 디버깅 체크리스트

콘솔(F12)에서 다음 명령어로 상태 확인:

```javascript
// Canvas 매니저 확인
console.log("Canvas Manager:", window.imagePadCanvas);

// Canvas 요소 확인
console.log("Canvas Element:", document.querySelector('canvas[id^="imagepad-canvas"]'));

// 수동 이미지 로드 테스트
if (window.imagePadCanvas) {
    const testImg = new Image();
    testImg.onload = () => window.imagePadCanvas.drawImage(testImg);
    testImg.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==';
}
```

## ⚠️ 주요 변경사항
1. **고유 Canvas ID 사용**: 충돌 방지
2. **타이머 기반 초기화**: DOM 준비 보장
3. **디버깅 로그 추가**: 문제 추적 용이
4. **대기 이미지 처리**: 초기화 전 이미지 처리
5. **에러 핸들링 강화**: 안정성 향상

## ✅ 예상 결과
- Canvas가 정상적으로 초기화됨
- 생성된 이미지가 원본 크기로 표시됨
- 콘솔에 디버깅 로그 표시
- 모드 전환 시 이미지 유지