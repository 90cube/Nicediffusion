from .mode_handlers.view_handler import ViewModeHandler
from .mode_handlers.img2img_handler import Img2ImgHandler
from .mode_handlers.inpaint_handler import InpaintHandler
import numpy as np
from typing import Optional
import base64
import io
from PIL import Image
from nicegui import ui
from pathlib import Path
import asyncio

class ImagePad:
    def __init__(self, state_manager):
        self.state = state_manager
        self.current_mode = 'view'
        self.layers = {}
        self.canvas_manager = None
        self.mode_handlers = {
            'view': ViewModeHandler(),
            'txt2img': None,  # 추후 구현
            'img2img': Img2ImgHandler(),
            'inpaint': InpaintHandler(),
            'upscale': None
        }
        self.uploaded_image = None  # numpy array
        
        # 기존 ImagePad 호환성을 위한 속성들
        self.current_image_path = None
        self.is_processing = False
        self.display_mode = 'contain'
        self.main_container = None
        self.canvas_container = None
        self.canvas = None
        self.loading_spinner = None
        self.loading_label = None
        self.progress_bar = None
        self.info_label = None
        self.display_buttons = []
        self.mode_label = None
        self.refresh_button = None
        self.temp_image_path = None

    async def render(self):
        """이미지 패드 렌더링"""
        from nicegui import ui
        
        # StateManager에서 uploaded_image 변경사항 구독
        self.state.subscribe('uploaded_image_changed', self._on_uploaded_image_changed)
        
        # 메인 컨테이너
        with ui.column().classes('w-full h-full relative'):
            # 우측 상단 버튼들
            with ui.row().classes('absolute top-2 right-2 z-10'):
                ui.button('🖼️ 커스텀 패드', on_click=self._open_custom_pad).classes('bg-blue-500 text-white px-3 py-1 text-sm rounded mr-2')
                ui.button('🗑️ 캔버스 비우기', on_click=self._clear_canvas).classes('bg-red-500 text-white px-3 py-1 text-sm rounded')
            
            # 표시 모드 선택 (Full, Fit, Stretch)
            with ui.row().classes('absolute top-2 left-2 z-10'):
                ui.html('''
                    <select id="canvas-display-mode" style="padding:4px 8px;border-radius:6px;">
                        <option value="fit">Fit</option>
                        <option value="full">Full</option>
                        <option value="stretch">Stretch</option>
                    </select>
                ''')
            
            # 중앙 컨테이너
            with ui.column().classes('w-full h-full flex items-center justify-center relative'):
                # 메인 이미지 표시 영역
                ui.html('''
                    <div id="image-container" style="width:100%;height:100%;max-width:800px;max-height:600px;position:relative;border:1px solid #333;">
                        <!-- Canvas 요소 -->
                        <canvas id="imagepad-canvas" style="width:100%;height:100%;z-index:1;position:absolute;top:0;left:0;"></canvas>
                        
                        <!-- 대체 이미지 표시 영역 (Canvas가 안 될 때 사용) -->
                        <div id="image-display-area" style="width:100%;height:100%;display:none;z-index:1;position:absolute;top:0;left:0;">
                            <img id="displayed-image" style="width:100%;height:100%;object-fit:contain;" />
                        </div>
                        
                        <!-- 드래그앤드롭 오버레이 (가장 위에) -->
                        <div id="drag-drop-area" style="position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(26,26,26,0.9);display:flex;align-items:center;justify-content:center;transition:opacity 0.3s;z-index:10;cursor:pointer;">
                            <div style="text-align:center;pointer-events:none;">
                                <div style="font-size:48px;">📁</div>
                                <div>이미지를 여기에 드래그앤드롭하세요</div>
                                <div style="font-size:14px;color:#718096;">또는 클릭하여 파일 선택</div>
                            </div>
                        </div>
                    </div>
                ''')
                
                # 숨겨진 파일 입력
                ui.html('<input id="api-upload-input" type="file" accept="image/*" style="display:none" />')
                
                # 업로드된 이미지 프리뷰 (작은 크기로)
                ui.html('<div id="uploaded-image-preview" style="margin-top:16px;text-align:center;max-width:300px;"></div>')
        
        # CanvasManager를 인라인으로 정의
        canvas_manager_script = '''
        <script>
        // CanvasManager 구현
        window.canvasManager = {
            loadImageFit: function(imageData, containerWidth, containerHeight) {
                console.log('🎨 loadImageFit 호출됨:', {
                    imageData: imageData ? imageData.substring(0, 50) + '...' : 'null',
                    containerWidth,
                    containerHeight
                });
                
                const canvas = document.getElementById('imagepad-canvas');
                if (!canvas) {
                    console.error('❌ Canvas 요소를 찾을 수 없음');
                    return;
                }
                
                console.log('✅ Canvas 요소 찾음:', canvas);
                
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = function() {
                    console.log('🖼️ 이미지 로드 완료:', img.width, 'x', img.height);
                    
                    // Canvas 크기 설정
                    canvas.width = containerWidth || canvas.clientWidth;
                    canvas.height = containerHeight || canvas.clientHeight;
                    
                    console.log('📐 Canvas 크기 설정:', canvas.width, 'x', canvas.height);
                    
                    // 이미지를 Canvas에 맞춤
                    const scale = Math.min(
                        canvas.width / img.width,
                        canvas.height / img.height
                    );
                    const x = (canvas.width - img.width * scale) / 2;
                    const y = (canvas.height - img.height * scale) / 2;
                    
                    console.log('📏 스케일링 정보:', { scale, x, y });
                    
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, x, y, img.width * scale, img.height * scale);
                    
                    console.log('✅ Canvas에 이미지 그리기 완료');
                };
                
                img.onerror = function() {
                    console.error('❌ 이미지 로드 실패:', imageData);
                };
                
                img.src = imageData;
            },
            
            loadImageFull: function(imageData, containerWidth, containerHeight) {
                const canvas = document.getElementById('imagepad-canvas');
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = function() {
                    // Canvas 크기를 이미지 크기로 설정
                    canvas.width = img.width;
                    canvas.height = img.height;
                    
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, 0, 0);
                };
                
                img.src = imageData;
            },
            
            loadImageStretch: function(imageData, containerWidth, containerHeight) {
                const canvas = document.getElementById('imagepad-canvas');
                if (!canvas) return;
                
                const ctx = canvas.getContext('2d');
                const img = new Image();
                
                img.onload = function() {
                    // Canvas 크기를 컨테이너 크기로 설정
                    canvas.width = containerWidth || canvas.clientWidth;
                    canvas.height = containerHeight || canvas.clientHeight;
                    
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                };
                
                img.src = imageData;
            },
            
            clearCanvas: function() {
                const canvas = document.getElementById('imagepad-canvas');
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                }
            }
        };
        </script>
        '''
        
        ui.add_body_html(canvas_manager_script)
        
        # 개선된 업로드 스크립트
        upload_script = '''
        <script>
        // 전역 변수로 선언하여 디버깅 용이하게
        window.imagePadDebug = {
            uploadInput: null,
            dragDropArea: null,
            canvas: null,
            canvasManager: null,
            initialized: false
        };
        
        function initializeImagePad() {
            console.log('🔄 ImagePad JavaScript 초기화 시작');
            
            // 요소들 찾기
            window.imagePadDebug.uploadInput = document.getElementById('api-upload-input');
            window.imagePadDebug.dragDropArea = document.getElementById('drag-drop-area');
            window.imagePadDebug.canvas = document.getElementById('imagepad-canvas');
            window.imagePadDebug.canvasManager = window.canvasManager;
            
            console.log('📁 uploadInput:', window.imagePadDebug.uploadInput);
            console.log('📁 dragDropArea:', window.imagePadDebug.dragDropArea);
            console.log('📁 canvas:', window.imagePadDebug.canvas);
            console.log('📁 canvasManager:', window.imagePadDebug.canvasManager);
            
            // 요소들이 모두 있는지 확인
            if (!window.imagePadDebug.uploadInput || !window.imagePadDebug.dragDropArea || !window.imagePadDebug.canvas) {
                console.error('❌ 필수 요소를 찾을 수 없음, 1초 후 재시도');
                setTimeout(initializeImagePad, 1000);
                return;
            }
            
            window.imagePadDebug.initialized = true;
            console.log('✅ ImagePad 초기화 완료');
            
            // 이벤트 리스너 등록
            setupEventListeners();
        }
        
        function setupEventListeners() {
            const uploadInput = window.imagePadDebug.uploadInput;
            const dragDropArea = window.imagePadDebug.dragDropArea;
            const imageContainer = document.getElementById('image-container');
            
            console.log('🔗 이벤트 리스너 설정 시작');
            
            // 파일 입력 이벤트
            if (uploadInput) {
                uploadInput.onchange = function(e) {
                    console.log('📁 파일 선택됨');
                    const file = e.target.files[0];
                    if (file) handleFileUpload(file);
                };
            }
            
            // 드래그앤드롭 이벤트 - 더 명확하게 설정
            if (dragDropArea) {
                console.log('📁 드래그앤드롭 영역 이벤트 설정');
                
                // 클릭으로 파일 선택
                dragDropArea.addEventListener('click', function(e) {
                    console.log('🖱️ 드래그앤드롭 영역 클릭됨');
                    e.preventDefault();
                    e.stopPropagation();
                    if (uploadInput) {
                        uploadInput.click();
                    }
                });
                
                // 드래그오버
                dragDropArea.addEventListener('dragover', function(e) {
                    console.log('🔄 드래그오버');
                    e.preventDefault();
                    e.stopPropagation();
                    dragDropArea.style.background = 'rgba(59, 130, 246, 0.3)';
                });
                
                // 드래그리브
                dragDropArea.addEventListener('dragleave', function(e) {
                    console.log('🔄 드래그리브');
                    e.preventDefault();
                    e.stopPropagation();
                    dragDropArea.style.background = 'rgba(26,26,26,0.9)';
                });
                
                // 드롭
                dragDropArea.addEventListener('drop', function(e) {
                    console.log('📥 파일 드롭됨');
                    e.preventDefault();
                    e.stopPropagation();
                    dragDropArea.style.background = 'rgba(26,26,26,0.9)';
                    
                    const files = e.dataTransfer.files;
                    if (files.length > 0) {
                        handleFileUpload(files[0]);
                    }
                });
            }
            
            // 이미지 컨테이너에도 드래그앤드롭 이벤트 추가 (백업)
            if (imageContainer) {
                console.log('📁 이미지 컨테이너 이벤트 설정');
                
                imageContainer.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                });
                
                imageContainer.addEventListener('drop', function(e) {
                    console.log('📥 컨테이너에 파일 드롭됨');
                    e.preventDefault();
                    e.stopPropagation();
                    
                    const files = e.dataTransfer.files;
                    if (files.length > 0) {
                        handleFileUpload(files[0]);
                    }
                });
            }
            
            // 표시 모드 변경 이벤트
            const displayModeSelect = document.getElementById('canvas-display-mode');
            if (displayModeSelect) {
                displayModeSelect.addEventListener('change', function() {
                    const mode = this.value;
                    console.log('표시 모드 변경:', mode);
                });
            }
        }
            
            async function handleFileUpload(file) {
                if (!file) return;
                
                console.log('📤 파일 업로드 시작:', file.name, file.size);
                
                // 로딩 표시
                if (dragDropArea) {
                    dragDropArea.innerHTML = '<div style="text-align:center;"><div style="font-size:24px;">⏳</div><div>업로드 중...</div></div>';
                }
                
                const formData = new FormData();
                formData.append('file', file);
                
                try {
                    console.log('🌐 API 요청 전송 중...');
                    const res = await fetch('/api/upload_image', { 
                        method: 'POST', 
                        body: formData 
                    });
                    
                    console.log('📥 API 응답 받음:', res.status, res.statusText);
                    
                    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                    
                    const data = await res.json();
                    console.log('📋 API 응답 데이터:', data);
                    
                    if (data.success) {
                        console.log('✅ 업로드 성공, UI 업데이트 시작');
                        
                        // 업로드 성공 시 오버레이 숨기기
                        if (dragDropArea) {
                            console.log('👁️ 오버레이 숨기기');
                            dragDropArea.style.display = 'none';
                        }
                        
                        // 이미지 표시 시도 (Canvas 우선, 실패 시 img 태그 사용)
                        if (data.base64) {
                            console.log('🎨 이미지 표시 시도...');
                            
                            // Canvas 시도
                            if (window.canvasManager) {
                                try {
                                    console.log('🎨 Canvas에 이미지 로드 중...');
                                    window.canvasManager.loadImageFit(data.base64, 800, 600);
                                    console.log('✅ Canvas 표시 성공');
                                } catch (canvasError) {
                                    console.error('❌ Canvas 표시 실패:', canvasError);
                                    // Canvas 실패 시 img 태그 사용
                                    showImageWithImgTag(data.base64);
                                }
                            } else {
                                console.log('📁 CanvasManager 없음, img 태그 사용');
                                showImageWithImgTag(data.base64);
                            }
                        } else {
                            console.error('❌ base64 데이터 없음');
                        }
                        
                        // 프리뷰에 작은 이미지 표시
                        const preview = document.getElementById('uploaded-image-preview');
                        if (preview && data.base64) {
                            console.log('🖼️ 프리뷰 업데이트');
                            preview.innerHTML = '<img src="' + data.base64 + '" style="max-width:100%;max-height:200px;border-radius:8px;box-shadow:0 2px 8px #0003;" />';
                        } else {
                            console.error('❌ preview 또는 base64 없음:', {
                                preview: !!preview,
                                base64: !!data.base64
                            });
                        }
                        
                        function showImageWithImgTag(base64Data) {
                            console.log('🖼️ img 태그로 이미지 표시');
                            const canvas = document.getElementById('imagepad-canvas');
                            const displayArea = document.getElementById('image-display-area');
                            const displayedImage = document.getElementById('displayed-image');
                            
                            if (canvas && displayArea && displayedImage) {
                                canvas.style.display = 'none';
                                displayArea.style.display = 'block';
                                displayedImage.src = base64Data;
                                console.log('✅ img 태그 표시 성공');
                            } else {
                                console.error('❌ img 태그 요소를 찾을 수 없음');
                            }
                        }
                        
                        console.log('✅ UI 업데이트 완료');
                        
                    } else {
                        throw new Error(data.error || '업로드 실패');
                    }
                    
                } catch (error) {
                    console.error('❌ 업로드 실패:', error);
                    
                    // 오버레이 복원
                    if (dragDropArea) {
                        dragDropArea.innerHTML = '<div style="text-align:center;pointer-events:none;"><div style="font-size:48px;">📁</div><div>이미지를 여기에 드래그앤드롭하세요</div><div style="font-size:14px;color:#718096;">또는 클릭하여 파일 선택</div></div>';
                    }
                    
                    // 에러 알림 (NiceGUI notify 사용)
                    if (window.nicegui && window.nicegui.notify) {
                        window.nicegui.notify('이미지 업로드 실패: ' + error.message, 'negative');
                    }
                }
            }
            
            // 파일 입력 이벤트
            if (uploadInput) {
                uploadInput.onchange = function(e) {
                    const file = e.target.files[0];
                    if (file) handleFileUpload(file);
                };
            }
            
            // 드래그앤드롭 이벤트
            if (dragDropArea) {
                // 클릭으로 파일 선택
                dragDropArea.addEventListener('click', function() {
                    if (uploadInput) uploadInput.click();
                });
                
                // 드래그오버
                dragDropArea.addEventListener('dragover', function(e) {
                    e.preventDefault();
                    dragDropArea.style.background = 'rgba(59, 130, 246, 0.3)';
                });
                
                // 드래그리브
                dragDropArea.addEventListener('dragleave', function(e) {
                    e.preventDefault();
                    dragDropArea.style.background = 'rgba(26,26,26,0.9)';
                });
                
                // 드롭
                dragDropArea.addEventListener('drop', function(e) {
                    e.preventDefault();
                    dragDropArea.style.background = 'rgba(26,26,26,0.9)';
                    
                    const files = e.dataTransfer.files;
                    if (files.length > 0) {
                        handleFileUpload(files[0]);
                    }
                });
            }
            
            // 표시 모드 변경 이벤트
            const displayModeSelect = document.getElementById('canvas-display-mode');
            if (displayModeSelect) {
                displayModeSelect.addEventListener('change', function() {
                    const mode = this.value;
                    console.log('표시 모드 변경:', mode);
                    // 여기에 모드 변경 로직 추가 가능
                });
            }
        }
        
        // DOM 로드 완료 시 초기화
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeImagePad);
        } else {
            // 이미 로드된 경우 즉시 초기화
            initializeImagePad();
        }
        
        // 추가 안전장치: 3초 후에도 초기화되지 않았다면 재시도
        setTimeout(function() {
            if (!window.imagePadDebug.initialized) {
                console.log('🔄 지연 초기화 시도');
                initializeImagePad();
            }
        }, 3000);
        </script>
        '''
        
        ui.add_body_html(upload_script)

    async def _open_custom_pad(self):
        """커스텀 이미지 패드 열기"""
        try:
            from .image_pad_integration import ImagePadIntegration
            
            # 이미 열려있는지 확인
            if not hasattr(self, 'custom_pad_integration'):
                self.custom_pad_integration = ImagePadIntegration(self.state)
                
            # 이미지 패드 열기
            self.custom_pad_integration.open_image_pad()
            
            from nicegui import ui
            ui.notify('커스텀 이미지 패드가 열렸습니다!', type='positive')
            
        except Exception as e:
            from nicegui import ui
            ui.notify(f'커스텀 이미지 패드 열기 실패: {str(e)}', type='negative')
            print(f"❌ 커스텀 이미지 패드 오류: {e}")
            
    async def _clear_canvas(self):
        """캔버스 비우기 (모든 이미지/프리뷰/썸네일/메시지/상태 완전 초기화)"""
        from nicegui import ui
        self.state.set('init_image', None)
        self.state.set('uploaded_image', None)
        self.current_image_path = None
        self.uploaded_image = None
        
        # 프론트엔드 UI 완전 초기화
        ui.run_javascript('''
            // Canvas 비우기
            if (window.canvasManager) {
                window.canvasManager.clearCanvas();
            }
            
            // 프리뷰 비우기
            const preview = document.getElementById('uploaded-image-preview');
            if (preview) {
                preview.innerHTML = '';
            }
            
            // 업로드 안내 오버레이 다시 표시
            const dragDropArea = document.getElementById('drag-drop-area');
            if (dragDropArea) {
                dragDropArea.style.display = 'flex';
                dragDropArea.innerHTML = '<div style="text-align:center;pointer-events:none;"><div style="font-size:48px;">📁</div><div>이미지를 여기에 드래그앤드롭하세요</div><div style="font-size:14px;color:#718096;">또는 클릭하여 파일 선택</div></div>';
            }
        ''')
        ui.notify('캔버스가 비워졌습니다', type='info')

    # 기존 ImagePad 호환 메서드들 (뼈대 구현)
    async def _on_generation_started(self, data):
        """생성 시작 이벤트"""
        print("🎨 생성 시작됨")
        self.is_processing = True

    async def _on_image_generated(self, data):
        """이미지 생성 완료 이벤트"""
        print("🖼️ 이미지 생성 완료")
        self.is_processing = False

    async def _show_empty(self):
        """빈 상태 표시 (프리뷰/캔버스 초기화)"""
        from nicegui import ui
        ui.run_javascript('document.getElementById("uploaded-image-preview").innerHTML = "";')
        ui.run_javascript('if(window.canvasManager){window.canvasManager.loadImageFit("", 512, 512);}')

    async def _show_loading(self):
        """로딩 상태 표시 (스피너 등)"""
        from nicegui import ui
        ui.run_javascript('document.getElementById("uploaded-image-preview").innerHTML = "<span style=\"color:gray\">로딩 중...</span>";')

    async def _show_image(self, image_path: str):
        """이미지 표시"""
        self.current_image_path = image_path
        print(f"🎉 이미지 표시: {image_path}")

    async def _show_error(self, message: str):
        """오류 상태 표시"""
        ui.notify(message, type='negative')

    async def _change_display_mode(self, mode: str):
        """이미지 표시 방식 변경"""
        self.display_mode = mode
        print(f"🔄 이미지 표시 방식 변경: {mode}")

    async def _show_fullscreen(self):
        """전체화면 보기 (새 창에 이미지 표시)"""
        if self.uploaded_image is not None:
            from PIL import Image
            import io, base64
            img = Image.fromarray(self.uploaded_image)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            from nicegui import ui
            ui.run_javascript(f'window.open("data:image/png;base64,{b64}", "_blank")')

    def _download_image(self):
        """이미지 다운로드"""
        if self.current_image_path:
            ui.download(self.current_image_path)

    def _delete_image(self):
        """이미지 삭제"""
        if self.current_image_path:
            try:
                Path(self.current_image_path).unlink()
                self.current_image_path = None
                ui.notify('이미지가 삭제되었습니다', type='positive')
            except Exception as e:
                ui.notify(f'이미지 삭제 실패: {e}', type='negative')

    async def _retry_generation(self):
        """생성 재시도"""
        await self._show_empty()

    async def handle_image_upload(self, image_data: str, file_name: str):
        """JavaScript에서 호출되는 이미지 업로드 처리 메서드"""
        print(f"📸 이미지 업로드: {file_name}")

    async def _resize_image_for_generation(self, pil_image):
        """생성용 이미지 리사이즈"""
        return pil_image

    async def _show_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 표시"""
        print(f"✅ 업로드된 이미지 표시: {file_name}")

    async def _on_file_uploaded(self, e):
        """파일 업로드 이벤트 처리 - 1544 크기 제한 적용"""
        print(f"🎉 파일 업로드: {e.name}")
        
        try:
            if not e.content:
                print(f"❌ 파일 내용이 없음: {e.name}")
                ui.notify('파일 내용을 읽을 수 없습니다', type='negative')
                return
            
            # PIL Image로 변환
            import io
            import tempfile
            print(f"🔄 PIL Image 변환 시작...")
            pil_image = Image.open(io.BytesIO(e.content))
            print(f"✅ PIL Image 변환 완료: 크기={pil_image.size}, 모드={pil_image.mode}")
            
            # 1544 크기 제한 적용
            pil_image = self._resize_image_to_1544_limit(pil_image)
            print(f"🔄 크기 조정 완료: {pil_image.size}")
            
            # numpy array로 변환하여 저장
            np_image = np.array(pil_image)
            self.set_uploaded_image(np_image)
            
            # 임시 파일로 저장
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            pil_image.save(temp_file.name)
            self.state.set('init_image_path', temp_file.name)
            print(f'✅ 업로드된 이미지 임시 파일 경로: {temp_file.name}')
            
            ui.notify(f'이미지 업로드 완료: {e.name} ({pil_image.size[0]}×{pil_image.size[1]})', type='positive')
            
        except Exception as e:
            print(f"❌ 파일 업로드 처리 실패: {e}")
            import traceback
            traceback.print_exc()
            ui.notify(f'파일 업로드 처리 실패: {str(e)}', type='negative')

    def _resize_image_to_1544_limit(self, pil_image):
        """이미지의 가장 긴 변이 1544를 넘으면 비율을 유지하여 1544에 맞춰 축소, SDXL 최소 크기 보장"""
        width, height = pil_image.size
        max_size = 1544
        min_size = 768  # SDXL 최소 크기
        
        # 가장 긴 변이 1544를 넘는지 확인
        if width <= max_size and height <= max_size:
            # SDXL 최소 크기 보장
            if width < min_size or height < min_size:
                # 비율을 유지하면서 최소 크기로 확대
                if width < height:
                    new_height = min_size
                    new_width = int(width * (min_size / height))
                else:
                    new_width = min_size
                    new_height = int(height * (min_size / width))
                
                # 8의 배수로 조정
                new_width = new_width - (new_width % 8)
                new_height = new_height - (new_height % 8)
                
                resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"🔄 SDXL 최소 크기로 조정: {width}×{height} → {new_width}×{new_height}")
                return resized_image
            
            return pil_image  # 크기 조정 불필요
        
        # 비율 계산
        if width > height:
            # 가로가 더 긴 경우
            new_width = max_size
            new_height = int(height * (max_size / width))
        else:
            # 세로가 더 긴 경우
            new_height = max_size
            new_width = int(width * (max_size / height))
        
        # 8의 배수로 조정
        new_width = new_width - (new_width % 8)
        new_height = new_height - (new_height % 8)
        
        # SDXL 최소 크기 보장
        if new_width < min_size:
            new_width = min_size
            new_height = int(height * (min_size / width))
            new_height = new_height - (new_height % 8)
        elif new_height < min_size:
            new_height = min_size
            new_width = int(width * (min_size / height))
            new_width = new_width - (new_width % 8)
        
        # 고품질 리사이즈
        resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        print(f"🔄 이미지 크기 조정: {width}×{height} → {new_width}×{new_height}")
        
        return resized_image

    async def _upload_image(self):
        """이미지 파일 업로드"""
        print("🔄 이미지 업로드 다이얼로그")

    async def _process_uploaded_image(self, pil_image, file_name: str):
        """업로드된 이미지 처리"""
        print(f"🔄 이미지 처리: {file_name}")

    async def _remove_uploaded_image(self):
        """업로드된 이미지 제거"""
        self.uploaded_image = None
        ui.notify('업로드된 이미지가 제거되었습니다', type='info')

    def _apply_image_size_to_params(self):
        """이미지 크기를 파라미터에 적용"""
        if self.uploaded_image is not None:
            height, width = self.uploaded_image.shape[:2]
            self.state.update_param('width', width)
            self.state.update_param('height', height)
            ui.notify(f'이미지 크기를 파라미터에 적용: {width}×{height}', type='positive')

    async def _refresh_image_pad(self):
        """이미지 패드 새로고침"""
        print("🔄 이미지 패드 새로고침")

    async def _show_upload_area(self):
        """업로드 영역 표시"""
        pass

    def set_uploaded_image(self, np_image: np.ndarray):
        """API로 받은 numpy 이미지를 ImagePad에 세팅"""
        self.uploaded_image = np_image
        print(f"✅ 이미지 업로드 완료: {np_image.shape}")

    def get_uploaded_image(self) -> Optional[np.ndarray]:
        """현재 업로드된 이미지를 numpy array 또는 None으로 반환"""
        return self.uploaded_image

    def get_uploaded_image_base64(self) -> str:
        """업로드된 numpy 이미지를 base64 PNG로 변환해 반환"""
        if self.uploaded_image is None:
            return ''
        img = Image.fromarray(self.uploaded_image)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f'data:image/png;base64,{b64}'

    def show_uploaded_image_fit(self, container_width: int, container_height: int):
        """프론트엔드 JS에 fit 표시 명령 전송 (NiceGUI run_javascript 사용)"""
        b64img = self.get_uploaded_image_base64()
        ui.run_javascript(f'window.canvasManager.loadImageFit("{b64img}", {container_width}, {container_height})')

    def add_image_layer(self):
        """레이어 시스템에 업로드 이미지를 배경/이미지 레이어로 추가 (뼈대)"""
        if self.uploaded_image is not None:
            self.layers['image'] = self.uploaded_image 

    async def on_mode_changed(self, new_mode):
        """모드가 변경될 때 init_image를 자동으로 ImagePad에 표시"""
        self.current_mode = new_mode
        init_image = self.state.get('init_image')
        if init_image is not None:
            # numpy array → base64 변환 후 바로 Canvas에 적용
            from PIL import Image
            import io, base64
            img = Image.fromarray(init_image)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            from nicegui import ui
            ui.run_javascript(f'''
                // 프리뷰에 표시
                const preview = document.getElementById('uploaded-image-preview');
                if (preview) {{
                    preview.innerHTML = '<img src="data:image/png;base64,{b64}" style="max-width:100%;max-height:200px;border-radius:8px;box-shadow:0 2px 8px #0003;" />';
                }}
                
                // 바로 Canvas에 적용
                if (window.canvasManager && window.canvasManager.loadImageFit) {{
                    window.canvasManager.loadImageFit("data:image/png;base64,{b64}", 1024, 1024);
                }}
            ''')

    async def on_history_image_selected(self, np_image):
        """히스토리에서 이미지 선택 시 ImagePad에 자동 반영"""
        self.set_uploaded_image(np_image)
        # numpy array → base64 변환 후 바로 Canvas에 적용
        from PIL import Image
        import io, base64
        img = Image.fromarray(np_image)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        from nicegui import ui
        ui.run_javascript(f'''
            // 프리뷰에 표시
            const preview = document.getElementById('uploaded-image-preview');
            if (preview) {{
                preview.innerHTML = '<img src="data:image/png;base64,{b64}" style="max-width:100%;max-height:200px;border-radius:8px;box-shadow:0 2px 8px #0003;" />';
            }}
            
            // 바로 Canvas에 적용
            if (window.canvasManager && window.canvasManager.loadImageFit) {{
                window.canvasManager.loadImageFit("data:image/png;base64,{b64}", 1024, 1024);
            }}
        ''')

    async def _on_uploaded_image_changed(self, np_image):
        """StateManager에서 uploaded_image가 변경되었을 때 호출"""
        if np_image is not None:
            print(f"🖼️ StateManager에서 이미지 변경 감지: {np_image.shape}")
            self.uploaded_image = np_image
            
            # 생성된 이미지와 완전히 동일한 방식으로 처리
            # JavaScript 호출 완전 제거 - UI 컨텍스트 오류 방지
            print(f"✅ 업로드된 이미지 상태 업데이트 완료")
            
            # JavaScript 호출 없이 상태만 업데이트
            # UI 업데이트는 사용자가 직접 새로고침하거나 다른 이벤트에서 처리 