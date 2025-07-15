# src/nicediff/ui/canvas_editor.py (새로 생성)

from nicegui import ui
import base64
from pathlib import Path
from ..core.state_manager import StateManager

class CanvasEditor:
    """HTML5 Canvas 기반 이미지 편집 시스템"""
    
    def __init__(self, state_manager: StateManager):
        self.state = state_manager
        self.canvas_id = "main-canvas"
        self.layers = []  # 레이어 관리
        self.current_tool = "brush"
        self.mask_mode = False
        
    async def render(self):
        """캔버스 편집기 렌더링"""
        
        # HTML 구조만 포함 (script 태그 제외)
        canvas_html = f"""
        <div id="canvas-container" style="position: relative; width: 100%; height: 100%;">
            <canvas id="{self.canvas_id}" 
                    style="border: 1px solid #666; cursor: crosshair; background: #1a1a1a;"
                    oncontextmenu="return false;">
            </canvas>
            
            <!-- 마스크 오버레이 -->
            <canvas id="mask-canvas" 
                    style="position: absolute; top: 0; left: 0; pointer-events: none; opacity: 0.7;">
            </canvas>
            
            <!-- 도구 정보 -->
            <div id="tool-info" style="position: absolute; top: 10px; left: 10px; 
                                     color: white; font-size: 12px; pointer-events: none;">
                도구: <span id="current-tool">브러시</span> | 크기: <span id="brush-size">10</span>px
            </div>
        </div>
        """
        
        # HTML 구조 렌더링
        ui.html(canvas_html).classes('w-full h-full')
        
        # JavaScript 코드를 add_body_html로 분리
        canvas_script = f"""
        <script>
        // 캔버스 초기화
        const canvas = document.getElementById('{self.canvas_id}');
        const ctx = canvas.getContext('2d');
        const maskCanvas = document.getElementById('mask-canvas');
        const maskCtx = maskCanvas.getContext('2d');
        
        let isDrawing = false;
        let currentTool = 'brush';
        let brushSize = 10;
        let currentColor = '#ffffff';
        
        // 캔버스 크기 설정
        function resizeCanvas() {{
            const container = document.getElementById('canvas-container');
            const rect = container.getBoundingClientRect();
            canvas.width = maskCanvas.width = rect.width;
            canvas.height = maskCanvas.height = rect.height;
        }}
        
        // 이벤트 리스너
        canvas.addEventListener('mousedown', startDrawing);
        canvas.addEventListener('mousemove', draw);
        canvas.addEventListener('mouseup', stopDrawing);
        canvas.addEventListener('mouseout', stopDrawing);
        
        // 터치 이벤트 (모바일 지원)
        canvas.addEventListener('touchstart', handleTouch);
        canvas.addEventListener('touchmove', handleTouch);
        canvas.addEventListener('touchend', stopDrawing);
        
        function startDrawing(e) {{
            isDrawing = true;
            draw(e);
        }}
        
        function draw(e) {{
            if (!isDrawing) return;
            
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            if (currentTool === 'brush') {{
                ctx.globalCompositeOperation = 'source-over';
                ctx.strokeStyle = currentColor;
                ctx.lineWidth = brushSize;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                
                ctx.lineTo(x, y);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(x, y);
            }} else if (currentTool === 'eraser') {{
                ctx.globalCompositeOperation = 'destination-out';
                ctx.lineWidth = brushSize;
                ctx.lineCap = 'round';
                
                ctx.lineTo(x, y);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(x, y);
            }}
        }}
        
        function stopDrawing() {{
            if (isDrawing) {{
                isDrawing = false;
                ctx.beginPath();
                
                // 변경사항을 Python으로 전송
                sendCanvasData();
            }}
        }}
        
        function handleTouch(e) {{
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent(e.type === 'touchstart' ? 'mousedown' : 
                                           e.type === 'touchmove' ? 'mousemove' : 'mouseup', {{
                clientX: touch.clientX,
                clientY: touch.clientY
            }});
            canvas.dispatchEvent(mouseEvent);
        }}
        
        function sendCanvasData() {{
            const imageData = canvas.toDataURL('image/png');
            // Python 콜백으로 전송
            window.pywebview?.api?.on_canvas_change(imageData);
        }}
        
        // 도구 변경 함수들 (Python에서 호출)
        window.setTool = function(tool) {{
            currentTool = tool;
            document.getElementById('current-tool').textContent = tool === 'brush' ? '브러시' : '지우개';
        }}
        
        window.setBrushSize = function(size) {{
            brushSize = size;
            document.getElementById('brush-size').textContent = size;
        }}
        
        window.setBrushColor = function(color) {{
            currentColor = color;
        }}
        
        window.clearCanvas = function() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }}
        
        window.loadImage = function(imageData) {{
            const img = new Image();
            img.onload = function() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
            }}
            img.src = imageData;
        }}
        
        // 마스크 토글
        window.toggleMask = function(show) {{
            maskCanvas.style.display = show ? 'block' : 'none';
        }}
        
        // 초기화
        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        </script>
        """
        
        # JavaScript 코드를 body에 추가
        ui.add_body_html(canvas_script)
        
        # 캔버스 변경 콜백 등록
        ui.run_javascript('window.on_canvas_change = function(data) { console.log("Canvas changed"); }')
    
    def set_tool(self, tool: str):
        """도구 변경"""
        self.current_tool = tool
        ui.run_javascript(f'window.setTool("{tool}")')
    
    def set_brush_size(self, size: int):
        """브러시 크기 변경"""
        ui.run_javascript(f'window.setBrushSize({size})')
    
    def set_brush_color(self, color: str):
        """브러시 색상 변경"""
        ui.run_javascript(f'window.setBrushColor("{color}")')
    
    def load_image(self, image_path: str):
        """이미지 로드"""
        if Path(image_path).exists():
            with open(image_path, 'rb') as f:
                b64_data = base64.b64encode(f.read()).decode()
            ui.run_javascript(f'window.loadImage("data:image/png;base64,{b64_data}")')
    
    def clear_canvas(self):
        """캔버스 지우기"""
        ui.run_javascript('window.clearCanvas()')
    
    def toggle_mask_view(self, show: bool):
        """마스크 보기 토글"""
        self.mask_mode = show
        ui.run_javascript(f'window.toggleMask({str(show).lower()})')
    
    def export_mask(self) -> str:
        """마스크 데이터 내보내기"""
        # 마스크 데이터 내보내기 구현 예정
        return ""