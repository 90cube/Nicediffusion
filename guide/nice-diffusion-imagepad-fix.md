# Nice Diffusion Image Pad 수정 지시사항

## 🎯 목적
Nice Diffusion의 Image Pad가 생성된 이미지를 썸네일이 아닌 원본 크기로 Canvas에 표시하고, t2i → i2i 워크플로우가 제대로 작동하도록 수정

## 🔍 현재 문제점
1. 생성된 이미지가 원본 크기로 표시되지 않고 썸네일만 표시됨
2. Image Pad의 Canvas 기능이 작동하지 않음
3. t2i에서 i2i로 전환 시 생성된 이미지가 자동으로 전달되지 않음
4. 업로드한 이미지가 제대로 표시되지 않음

## ⚠️ 주의사항
- **기존 UI 구조를 변경하지 마세요**
- **다른 컴포넌트에 영향을 주지 마세요**
- **StateManager의 기존 이벤트를 삭제하지 마세요**
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

class ImagePad:
    """이미지 패드 컴포넌트"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_mode = 'txt2img'
        self.current_image = None
        self.image_container = None
        self.canvas_container = None
        self.upload_area = None
        self.status_label = None
        self.placeholder_overlay = None
        
        # 이벤트 구독 - 기존 이벤트명 유지
        self.state.subscribe('mode_changed', self._on_mode_changed)
        self.state.subscribe('image_generated', self._on_image_generated)
        self.state.subscribe('generation_completed', self._on_generation_completed)  # 추가
        self.state.subscribe('uploaded_image', self._on_uploaded_image_changed)
        
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full bg-gray-800 rounded-lg overflow-hidden relative') as main_container:
            self.main_container = main_container
            
            # 상단 도구바
            with ui.row().classes('absolute top-2 left-2 right-2 justify-between items-center z-10'):
                ui.label('🖼️ 이미지 패드').classes('text-white bg-black bg-opacity-50 px-3 py-1 rounded text-sm font-bold')
                ui.button(icon='refresh', on_click=self._refresh_image_pad).props('round color=white text-color=black size=sm')
            
            # Canvas 컨테이너
            self.canvas_container = ui.element('div').classes('w-full h-full relative')
            with self.canvas_container:
                # HTML5 Canvas
                ui.html('''
                    <canvas id="imagepad-canvas" 
                            style="width: 100%; height: 100%; display: block; cursor: crosshair;">
                    </canvas>
                ''').classes('w-full h-full')
                
                # 플레이스홀더 오버레이
                self.placeholder_overlay = ui.element('div').classes(
                    'absolute inset-0 flex items-center justify-center'
                ).style('pointer-events: auto;')
                
            # Canvas 초기화
            await self._init_canvas()
            
            # 우측 하단 상태 표시
            with ui.row().classes('absolute bottom-2 right-2 z-10'):
                self.status_label = ui.label('준비됨').classes('text-white text-sm bg-gray-800 px-2 py-1 rounded')
    
    async def _init_canvas(self):
        """Canvas 초기화 및 이벤트 설정"""
        ui.run_javascript('''
            // Canvas 매니저 초기화
            window.imagePadCanvas = {
                canvas: document.getElementById('imagepad-canvas'),
                ctx: null,
                currentImage: null,
                
                init: function() {
                    this.canvas = document.getElementById('imagepad-canvas');
                    if (!this.canvas) {
                        console.error('Canvas element not found');
                        return;
                    }
                    
                    this.ctx = this.canvas.getContext('2d');
                    this.resizeCanvas();
                    this.drawCheckerboard();
                    
                    // 리사이즈 이벤트
                    window.addEventListener('resize', () => this.resizeCanvas());
                    
                    // 드래그 앤 드롭 설정
                    this.setupDragAndDrop();
                },
                
                resizeCanvas: function() {
                    if (!this.canvas) return;
                    
                    const rect = this.canvas.getBoundingClientRect();
                    this.canvas.width = rect.width;
                    this.canvas.height = rect.height;
                    
                    // 현재 이미지가 있으면 다시 그리기
                    if (this.currentImage) {
                        this.drawImage(this.currentImage);
                    } else {
                        this.drawCheckerboard();
                    }
                },
                
                drawCheckerboard: function() {
                    if (!this.ctx || !this.canvas) return;
                    
                    const size = 20;
                    const ctx = this.ctx;
                    ctx.fillStyle = '#2a2a2a';
                    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
                    
                    ctx.fillStyle = '#3a3a3a';
                    for (let x = 0; x < this.canvas.width; x += size * 2) {
                        for (let y = 0; y < this.canvas.height; y += size * 2) {
                            ctx.fillRect(x, y, size, size);
                            ctx.fillRect(x + size, y + size, size, size);
                        }
                    }
                },
                
                drawImage: function(img) {
                    if (!this.ctx || !this.canvas || !img) return;
                    
                    // Canvas 클리어
                    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                    this.drawCheckerboard();
                    
                    // 이미지 비율 유지하며 중앙에 표시
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
                    this.ctx.fillText(`원본: ${img.width} x ${img.height}px`, 15, this.canvas.height - 25);
                    this.ctx.fillText(`표시: ${Math.round(width)} x ${Math.round(height)}px`, 15, this.canvas.height - 10);
                    this.ctx.restore();
                },
                
                loadImageFromBase64: function(base64Data) {
                    const img = new Image();
                    img.onload = () => {
                        this.currentImage = img;
                        this.drawImage(img);
                    };
                    img.src = 'data:image/png;base64,' + base64Data;
                },
                
                setupDragAndDrop: function() {
                    const canvas = this.canvas;
                    
                    canvas.addEventListener('dragover', (e) => {
                        e.preventDefault();
                        canvas.style.border = '3px dashed #4a90e2';
                    });
                    
                    canvas.addEventListener('dragleave', (e) => {
                        e.preventDefault();
                        canvas.style.border = 'none';
                    });
                    
                    canvas.addEventListener('drop', (e) => {
                        e.preventDefault();
                        canvas.style.border = 'none';
                        
                        const file = e.dataTransfer.files[0];
                        if (file && file.type.startsWith('image/')) {
                            const reader = new FileReader();
                            reader.onload = (event) => {
                                const img = new Image();
                                img.onload = () => {
                                    this.currentImage = img;
                                    this.drawImage(img);
                                    // Python에 알림
                                    window.handleImageDrop && window.handleImageDrop(event.target.result);
                                };
                                img.src = event.target.result;
                            };
                            reader.readAsDataURL(file);
                        }
                    });
                }
            };
            
            // Canvas 초기화 실행
            window.imagePadCanvas.init();
            
            // 드롭 핸들러 설정
            window.handleImageDrop = function(dataUrl) {
                // Python 콜백 실행
                // 실제 구현은 NiceGUI의 이벤트 시스템 사용
            };
        ''')
        
        # 모드에 따른 초기 표시
        await self._show_placeholder()
    
    async def _show_placeholder(self):
        """플레이스홀더 표시"""
        current_mode = self.state.get('current_mode', 'txt2img')
        
        if self.placeholder_overlay:
            try:
                self.placeholder_overlay.clear()
            except RuntimeError:
                return
                
            with self.placeholder_overlay:
                if current_mode in ['img2img', 'inpaint', 'upscale']:
                    # 업로드 영역 표시
                    with ui.column().classes('bg-gray-700 bg-opacity-90 p-8 rounded-lg').style('pointer-events: auto;'):
                        ui.icon('cloud_upload', size='4em').classes('text-gray-400 mb-4')
                        ui.label('이미지를 드래그하거나 클릭하여 업로드').classes('text-gray-300 text-center')
                        
                        # 파일 업로드 버튼
                        self.upload_component = ui.upload(
                            on_upload=self._handle_upload,
                            auto_upload=True,
                            multiple=False
                        ).props('accept=image/*').classes('mt-4')
                else:
                    # t2i 모드 - 생성 대기 메시지
                    with ui.column().classes('text-center').style('pointer-events: none;'):
                        ui.icon('brush', size='3em').classes('text-gray-500 mb-2')
                        ui.label('생성 버튼을 클릭하여 이미지를 생성하세요').classes('text-gray-400')
    
    async def _display_image_on_canvas(self, image):
        """Canvas에 이미지 표시 (원본 크기 유지)"""
        if not image:
            return
            
        try:
            # PIL Image를 base64로 변환
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # JavaScript로 Canvas에 이미지 그리기
            ui.run_javascript(f'''
                if (window.imagePadCanvas) {{
                    window.imagePadCanvas.loadImageFromBase64('{img_str}');
                }}
            ''')
            
            # 플레이스홀더 숨기기
            if self.placeholder_overlay:
                self.placeholder_overlay.style('display: none;')
            
            # 현재 이미지 저장
            self.current_image = image
            
            # 상태 업데이트
            if self.status_label:
                self.status_label.set_text(f'이미지 표시됨 ({image.width}x{image.height})')
                self.status_label.classes('text-green-400 text-white text-sm bg-gray-800 px-2 py-1 rounded')
                
        except Exception as e:
            print(f"❌ Canvas에 이미지 표시 실패: {e}")
    
    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트 처리 (기존 이벤트 유지)"""
        await self._handle_generated_images(data)
    
    async def _on_generation_completed(self, event_data):
        """생성 완료 이벤트 처리 (새 이벤트)"""
        await self._handle_generated_images(event_data)
    
    async def _handle_generated_images(self, data):
        """생성된 이미지 처리 (통합)"""
        try:
            images = None
            
            # 다양한 데이터 형식 처리
            if isinstance(data, dict):
                images = data.get('images', [])
                if not images and 'image_path' in data:
                    # 경로에서 이미지 로드
                    image_path = data.get('image_path')
                    if image_path and Path(image_path).exists():
                        pil_image = Image.open(image_path)
                        images = [pil_image]
            elif isinstance(data, list):
                images = data
            
            if images and len(images) > 0:
                # 첫 번째 이미지를 Canvas에 표시
                await self._display_image_on_canvas(images[0])
                
                # 워크플로우를 위해 생성된 이미지 저장
                self.state.set('last_generated_images', images)
                
                # t2i → i2i 워크플로우를 위한 자동 설정
                if self.state.get('current_mode') == 'txt2img':
                    self.state.set('pending_init_image', images[0])
                    
        except Exception as e:
            print(f"❌ 생성된 이미지 처리 실패: {e}")
            import traceback
            traceback.print_exc()
    
    async def _on_mode_changed(self, event_data):
        """모드 변경 시 처리"""
        try:
            new_mode = event_data.get('mode', 'txt2img') if isinstance(event_data, dict) else event_data
            old_mode = self.current_mode
            self.current_mode = new_mode
            
            # t2i → i2i 전환 시 생성된 이미지를 init_image로 설정
            if old_mode == 'txt2img' and new_mode in ['img2img', 'inpaint', 'upscale']:
                if self.current_image:
                    self.state.set('init_image', self.current_image)
                    # Canvas는 유지 (이미지 그대로 표시)
                else:
                    # pending_init_image 확인
                    pending_image = self.state.get('pending_init_image')
                    if pending_image:
                        self.state.set('init_image', pending_image)
                        await self._display_image_on_canvas(pending_image)
                        self.state.set('pending_init_image', None)
            else:
                # 다른 모드 전환 시 Canvas 초기화 (t2i로 갈 때만)
                if new_mode == 'txt2img':
                    ui.run_javascript('''
                        if (window.imagePadCanvas) {
                            window.imagePadCanvas.currentImage = null;
                            window.imagePadCanvas.drawCheckerboard();
                        }
                    ''')
                    self.current_image = None
            
            # 플레이스홀더 업데이트
            if self.placeholder_overlay:
                self.placeholder_overlay.style('display: block;')
            await self._show_placeholder()
            
        except Exception as e:
            print(f"❌ 모드 변경 처리 실패: {e}")
    
    async def _on_uploaded_image_changed(self, np_image):
        """업로드된 이미지 변경 시"""
        if np_image is not None:
            try:
                # numpy to PIL
                pil_image = Image.fromarray(np_image.astype('uint8'))
                await self._display_image_on_canvas(pil_image)
            except Exception as e:
                print(f"❌ 업로드 이미지 표시 실패: {e}")
    
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
            
            ui.notify(f'이미지 업로드 완료 ({pil_image.width}x{pil_image.height})', type='positive')
            
        except Exception as ex:
            print(f"❌ 이미지 업로드 실패: {ex}")
            ui.notify('이미지 업로드 실패', type='negative')
    
    def _refresh_image_pad(self):
        """Image Pad 새로고침"""
        try:
            if self.current_image:
                # 현재 이미지가 있으면 다시 그리기
                ui.run_javascript('''
                    if (window.imagePadCanvas && window.imagePadCanvas.currentImage) {
                        window.imagePadCanvas.drawImage(window.imagePadCanvas.currentImage);
                    }
                ''')
                ui.notify('Image Pad 새로고침 완료', type='info')
            else:
                # 없으면 체커보드
                ui.run_javascript('''
                    if (window.imagePadCanvas) {
                        window.imagePadCanvas.drawCheckerboard();
                    }
                ''')
        except Exception as e:
            print(f"❌ 새로고침 실패: {e}")
```

## 🧪 테스트 방법

1. **T2I 모드 테스트**
   - 이미지 생성 후 Canvas에 원본 크기로 표시되는지 확인
   - 이미지 정보(크기)가 표시되는지 확인

2. **I2I 모드 전환 테스트**
   - T2I에서 이미지 생성 후 I2I로 전환
   - 생성된 이미지가 자동으로 전달되는지 확인

3. **업로드 테스트**
   - I2I 모드에서 이미지 드래그 앤 드롭
   - 업로드 버튼으로 이미지 선택
   - Canvas에 제대로 표시되는지 확인

4. **새로고침 테스트**
   - 우측 상단 새로고침 버튼 클릭
   - 현재 이미지가 유지되는지 확인

## ✅ 예상 결과
- 생성된 이미지가 썸네일이 아닌 원본 크기로 Canvas에 표시됨
- 이미지 정보(원본 크기, 표시 크기)가 Canvas 하단에 표시됨
- T2I → I2I 워크플로우가 자동으로 연결됨
- 드래그 앤 드롭으로 이미지 업로드 가능
- 체커보드 배경이 표시됨

## ⚠️ 기존 기능 보호
- StateManager의 기존 이벤트 구독은 모두 유지
- 다른 UI 컴포넌트에 영향 없음
- 기존 생성 로직 변경 없음
- 파라미터 패널, 사이드바 등 다른 UI 요소 영향 없음