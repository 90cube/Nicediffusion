class CanvasManager {
    constructor() {
        this.mode = 'view';
        this.layers = new Map();
        this.tools = new Map();
        this.history = [];
    }
    switchMode(newMode) {
        this.cleanup();
        this.mode = newMode;
        this.loadModeModule(newMode);
    }
    loadImage(source) {
        // File, URL, Base64, Blob 등 다양한 소스 지원
    }
    // 이미지 표시 관련 함수 완전 제거
    getCanvasContext() {
        const canvas = document.getElementById('imagepad-canvas');
        if (!canvas) return { clearRect:()=>{}, drawImage:()=>{} };
        return canvas.getContext('2d');
    }
    async uploadImageFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        await fetch('/api/upload_image', {
            method: 'POST',
            body: formData
        });
        // 업로드 성공 후 별도 이미지 표시/프리뷰 없음 (Python에서만 처리)
    }
    exportData() {
        return {
            image: this.getImageData(),
            mask: this.getMaskData(),
            metadata: this.getMetadata()
        };
    }
}

window.canvasManager = new CanvasManager(); 