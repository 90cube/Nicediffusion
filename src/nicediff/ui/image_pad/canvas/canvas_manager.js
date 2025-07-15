/**
 * 통합 Canvas Manager
 * 모드별 Canvas 기능을 관리하는 JavaScript 모듈
 */

class CanvasManager {
    constructor() {
        this.mode = 'view';
        this.layers = new Map();
        this.tools = new Map();
        this.history = [];
        this.currentTool = 'brush';
        this.brushSize = 20;
        this.brushHardness = 0.8;
        this.isDrawing = false;
        this.lastX = 0;
        this.lastY = 0;
        
        // Canvas 요소들
        this.canvas = null;
        this.ctx = null;
        this.imageCanvas = null;
        this.maskCanvas = null;
        
        this.init();
    }
    
    init() {
        console.log('🎨 Canvas Manager 초기화');
        
        // 전역 함수 등록
        window.handleFileUpload = this.handleFileUpload.bind(this);
        window.canvasManager = this;
        
        // 모드별 Canvas 초기화
        this.initViewCanvas();
        this.initImg2ImgCanvas();
        this.initInpaintCanvas();
    }
    
    // 모드 전환
    switchMode(newMode) {
        console.log(`🔄 모드 전환: ${this.mode} → ${newMode}`);
        this.cleanup();
        this.mode = newMode;
        this.loadModeModule(newMode);
    }
    
    cleanup() {
        // 이벤트 리스너 정리
        if (this.canvas) {
            this.canvas.removeEventListener('mousedown', this.onMouseDown);
            this.canvas.removeEventListener('mousemove', this.onMouseMove);
            this.canvas.removeEventListener('mouseup', this.onMouseUp);
            this.canvas.removeEventListener('touchstart', this.onTouchStart);
            this.canvas.removeEventListener('touchmove', this.onTouchMove);
            this.canvas.removeEventListener('touchend', this.onTouchEnd);
        }
    }
    
    loadModeModule(mode) {
        switch (mode) {
            case 'view':
                this.initViewCanvas();
                break;
            case 'img2img':
                this.initImg2ImgCanvas();
                break;
            case 'inpaint':
                this.initInpaintCanvas();
                break;
            default:
                this.initViewCanvas();
        }
    }
    
    // View 모드 Canvas
    initViewCanvas() {
        this.canvas = document.getElementById('view-canvas');
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.setupCanvasSize();
    }
    
    // Img2Img 모드 Canvas
    initImg2ImgCanvas() {
        this.canvas = document.getElementById('img2img-canvas');
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.setupCanvasSize();
        this.setupDragAndDrop();
    }
    
    // Inpaint 모드 Canvas
    initInpaintCanvas() {
        this.canvas = document.getElementById('inpaint-canvas');
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.setupCanvasSize();
        this.setupDrawingTools();
        
        // Inpaint 전용 전역 함수
        window.inpaintCanvas = {
            init: () => this.initInpaintCanvas(),
            setTool: (tool) => this.setTool(tool),
            setBrushSize: (size) => this.setBrushSize(size),
            setBrushHardness: (hardness) => this.setBrushHardness(hardness),
            undo: () => this.undo(),
            redo: () => this.redo()
        };
    }
    
    setupCanvasSize() {
        if (!this.canvas) return;
        
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        
        // 체커보드 배경 그리기
        this.drawCheckerboard();
    }
    
    setupDragAndDrop() {
        const uploadArea = document.getElementById('img2img-upload-area');
        if (!uploadArea) return;
        
        uploadArea.addEventListener('click', () => {
            this.openFileDialog();
        });
        
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.style.background = 'rgba(59,130,246,0.3)';
        });
        
        uploadArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            uploadArea.style.background = 'rgba(26,26,26,0.9)';
        });
        
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.style.background = 'rgba(26,26,26,0.9)';
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                this.handleFileUpload(file);
            }
        });
    }
    
    setupDrawingTools() {
        if (!this.canvas) return;
        
        this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
        
        // 터치 이벤트
        this.canvas.addEventListener('touchstart', this.onTouchStart.bind(this));
        this.canvas.addEventListener('touchmove', this.onTouchMove.bind(this));
        this.canvas.addEventListener('touchend', this.onTouchEnd.bind(this));
    }
    
    // 파일 업로드 처리
    async handleFileUpload(file) {
        try {
            console.log('📁 파일 업로드:', file.name);
            
            const reader = new FileReader();
            reader.onload = (e) => {
                const base64 = e.target.result;
                this.loadImage(base64);
                
                // Python으로 파일 전송
                this.sendToPython(file, base64);
            };
            reader.readAsDataURL(file);
            
        } catch (error) {
            console.error('❌ 파일 업로드 실패:', error);
        }
    }
    
    openFileDialog() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                this.handleFileUpload(file);
            }
        };
        input.click();
    }
    
    // 이미지 로드
    loadImage(imageData) {
        if (!this.canvas) return;
        
        const img = new Image();
        img.onload = () => {
            this.drawImageFit(img);
            
            // 드래그앤드롭 영역 숨기기
            const uploadArea = document.getElementById(`${this.mode}-upload-area`);
            if (uploadArea) {
                uploadArea.style.display = 'none';
            }
        };
        img.src = imageData;
    }
    
    // 이미지를 Canvas에 맞춰 그리기
    drawImageFit(img) {
        if (!this.ctx) return;
        
        const canvas = this.canvas;
        const scale = Math.min(
            canvas.width / img.width,
            canvas.height / img.height
        );
        const x = (canvas.width - img.width * scale) / 2;
        const y = (canvas.height - img.height * scale) / 2;
        
        this.ctx.clearRect(0, 0, canvas.width, canvas.height);
        this.ctx.drawImage(img, x, y, img.width * scale, img.height * scale);
    }
    
    // 체커보드 배경 그리기
    drawCheckerboard() {
        if (!this.ctx) return;
        
        const size = 20;
        const canvas = this.canvas;
        
        for (let x = 0; x < canvas.width; x += size) {
            for (let y = 0; y < canvas.height; y += size) {
                const isEven = ((x / size) + (y / size)) % 2 === 0;
                this.ctx.fillStyle = isEven ? '#808080' : '#ffffff';
                this.ctx.fillRect(x, y, size, size);
            }
        }
    }
    
    // 그리기 도구
    onMouseDown(e) {
        if (this.mode !== 'inpaint') return;
        
        this.isDrawing = true;
        const rect = this.canvas.getBoundingClientRect();
        this.lastX = e.clientX - rect.left;
        this.lastY = e.clientY - rect.top;
    }
    
    onMouseMove(e) {
        if (!this.isDrawing || this.mode !== 'inpaint') return;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        this.draw(this.lastX, this.lastY, x, y);
        this.lastX = x;
        this.lastY = y;
    }
    
    onMouseUp() {
        this.isDrawing = false;
        this.saveToHistory();
    }
    
    // 터치 이벤트
    onTouchStart(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousedown', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.onMouseDown(mouseEvent);
    }
    
    onTouchMove(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousemove', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.onMouseMove(mouseEvent);
    }
    
    onTouchEnd(e) {
        e.preventDefault();
        this.onMouseUp();
    }
    
    // 그리기 함수
    draw(startX, startY, endX, endY) {
        if (!this.ctx) return;
        
        this.ctx.beginPath();
        this.ctx.moveTo(startX, startY);
        this.ctx.lineTo(endX, endY);
        this.ctx.strokeStyle = '#ff0000';
        this.ctx.lineWidth = this.brushSize;
        this.ctx.lineCap = 'round';
        this.ctx.stroke();
    }
    
    // 도구 설정
    setTool(tool) {
        this.currentTool = tool;
        console.log('🛠️ 도구 변경:', tool);
    }
    
    setBrushSize(size) {
        this.brushSize = size;
        console.log('🖌️ 브러시 크기:', size);
    }
    
    setBrushHardness(hardness) {
        this.brushHardness = hardness;
        console.log('🖌️ 브러시 경도:', hardness);
    }
    
    // 히스토리 관리
    saveToHistory() {
        if (!this.canvas) return;
        
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        this.history.push(imageData);
        
        // 히스토리 크기 제한
        if (this.history.length > 50) {
            this.history.shift();
        }
    }
    
    undo() {
        if (this.history.length > 0) {
            const imageData = this.history.pop();
            this.ctx.putImageData(imageData, 0, 0);
            console.log('↩️ 실행 취소');
        }
    }
    
    redo() {
        // 재실행 기능은 별도 스택으로 구현 가능
        console.log('↪️ 다시 실행');
    }
    
    // Python으로 데이터 전송
    sendToPython(file, base64) {
        // NiceGUI의 Python 함수 호출
        if (window.pywebview) {
            window.pywebview.api.handle_file_upload(file.name, base64);
        } else {
            // 일반적인 방법으로 Python에 전송
            fetch('/api/upload_image', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    filename: file.name,
                    data: base64
                })
            });
        }
    }
    
    // 이미지 데이터 추출
    getImageData() {
        if (!this.canvas) return null;
        return this.canvas.toDataURL('image/png');
    }
    
    getMaskData() {
        if (!this.canvas || this.mode !== 'inpaint') return null;
        return this.canvas.toDataURL('image/png');
    }
    
    getMetadata() {
        return {
            mode: this.mode,
            tool: this.currentTool,
            brushSize: this.brushSize,
            brushHardness: this.brushHardness
        };
    }
    
    // Canvas 비우기
    clearCanvas() {
        if (!this.ctx) return;
        
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.drawCheckerboard();
        
        // 드래그앤드롭 영역 다시 표시
        const uploadArea = document.getElementById(`${this.mode}-upload-area`);
        if (uploadArea) {
            uploadArea.style.display = 'flex';
        }
    }
}

// 전역 인스턴스 생성
window.canvasManager = new CanvasManager(); 