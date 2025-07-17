# image_viewer.py 개선

class ImagePad:
    """개선된 이미지 패드"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.current_mode = 'txt2img'
        self.image_container = None
        self.canvas_id = 'main-canvas'
        
        # 이벤트 구독
        self.state.subscribe('current_mode', self._on_mode_changed)
        self.state.subscribe('image_generated', self._on_image_generated)
        self.state.subscribe('uploaded_image', self._on_uploaded_image_changed)
        
    async def render(self):
        """컴포넌트 렌더링"""
        with ui.column().classes('w-full h-full bg-gray-800 rounded-lg overflow-hidden relative') as main_container:
            self.main_container = main_container
            
            # Canvas 영역
            ui.html(f'''
                <canvas id="{self.canvas_id}" 
                    style="width:100%; height:100%; display:block;">
                </canvas>
            ''').classes('w-full h-full')
            
            # 모드별 오버레이 UI
            await self._render_mode_overlay()
            
            # Canvas 초기화 스크립트
            ui.run_javascript(f'''
                // Canvas 초기화
                const canvas = document.getElementById('{self.canvas_id}');
                const ctx = canvas.getContext('2d');
                
                // 크기 설정
                function resizeCanvas() {{
                    const rect = canvas.getBoundingClientRect();
                    canvas.width = rect.width;
                    canvas.height = rect.height;
                    
                    // 체커보드 배경
                    drawCheckerboard(ctx, canvas.width, canvas.height);
                }}
                
                window.addEventListener('resize', resizeCanvas);
                resizeCanvas();
                
                // 전역 객체에 저장
                window.imagePadCanvas = {{
                    canvas: canvas,
                    ctx: ctx,
                    currentImage: null
                }};
            ''')
    
    async def _render_mode_overlay(self):
        """모드별 오버레이 UI 렌더링"""
        current_mode = self.state.get('current_mode', 'txt2img')
        
        if current_mode in ['img2img', 'inpaint', 'upscale']:
            # 드래그앤드롭 영역
            with ui.element('div').classes(
                'absolute inset-0 flex items-center justify-center pointer-events-none'
            ) as overlay:
                self.overlay_container = overlay
                
                # 업로드 영역 (이미지가 없을 때만 표시)
                init_image = self.state.get('init_image')
                if init_image is None:
                    with ui.card().classes(
                        'bg-gray-700 bg-opacity-90 p-8 rounded-lg pointer-events-auto'
                    ).props('draggable').on('dragover', lambda e: e.preventDefault()):
                        ui.icon('cloud_upload', size='64px').classes('text-blue-400 mb-4')
                        ui.label('이미지를 드래그하거나 클릭하여 업로드').classes('text-lg mb-2')
                        
                        # 파일 업로드 버튼
                        ui.upload(
                            on_upload=self._handle_file_upload,
                            auto_upload=True,
                            multiple=False
                        ).classes('w-full').props('accept="image/*"')
    
    async def _handle_file_upload(self, e):
        """파일 업로드 처리"""
        try:
            file = e.sender.value
            if file:
                # 파일 읽기
                content = file.read()
                
                # PIL 이미지로 변환
                from PIL import Image
                import io
                image = Image.open(io.BytesIO(content))
                
                # 상태 업데이트
                self.state.set('init_image', image)
                self.state.set('uploaded_image', np.array(image))
                
                # Canvas에 표시
                await self._display_image_on_canvas(image)
                
                # 오버레이 숨기기
                if hasattr(self, 'overlay_container'):
                    self.overlay_container.clear()
                
                ui.notify('이미지가 업로드되었습니다', type='positive')
                
        except Exception as e:
            print(f"❌ 업로드 실패: {e}")
            ui.notify(f'업로드 실패: {str(e)}', type='negative')
    
    async def _display_image_on_canvas(self, image):
        """Canvas에 이미지 표시"""
        # PIL to base64
        import base64
        from io import BytesIO
        
        buf = BytesIO()
        image.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        # JavaScript로 Canvas에 그리기
        ui.run_javascript(f'''
            const img = new Image();
            img.onload = function() {{
                const canvas = window.imagePadCanvas.canvas;
                const ctx = window.imagePadCanvas.ctx;
                
                // 이미지 저장
                window.imagePadCanvas.currentImage = img;
                canvas.__currentImage = img;
                
                // 비율 유지하며 그리기
                drawImageFitToCanvas(img, canvas, ctx);
            }};
            img.src = 'data:image/png;base64,{b64}';
        ''')
    
    async def _on_mode_changed(self, mode):
        """모드 변경 시 처리"""
        self.current_mode = mode
        
        # t2i에서 i2i로 전환 시 생성된 이미지를 init_image로 설정
        if mode in ['img2img', 'inpaint'] and self.current_image:
            self.state.set('init_image', self.current_image)
        
        # UI 새로고침
        if hasattr(self, 'main_container'):
            self.main_container.clear()
            with self.main_container:
                await self.render()
    
    async def _on_image_generated(self, images):
        """이미지 생성 완료 시"""
        if images and len(images) > 0:
            self.current_image = images[0]
            await self._display_image_on_canvas(images[0])
    
    async def _on_uploaded_image_changed(self, np_image):
        """업로드된 이미지 변경 시"""
        if np_image is not None:
            # numpy to PIL
            from PIL import Image
            pil_image = Image.fromarray(np_image.astype('uint8'))
            await self._display_image_on_canvas(pil_image)