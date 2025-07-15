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
    loadImageFit(imageData, containerWidth, containerHeight) {
        // base64 이미지를 fit로 캔버스에 표시
        const img = new window.Image();
        img.onload = () => {
            const scale = Math.min(containerWidth / img.width, containerHeight / img.height);
            const newW = img.width * scale;
            const newH = img.height * scale;
            const ctx = this.getCanvasContext();
            ctx.clearRect(0, 0, containerWidth, containerHeight);
            ctx.drawImage(img, (containerWidth-newW)/2, (containerHeight-newH)/2, newW, newH);
        };
        img.src = imageData;
    }
    getCanvasContext() {
        const canvas = document.getElementById('imagepad-canvas');
        if (!canvas) return { clearRect:()=>{}, drawImage:()=>{} };
        return canvas.getContext('2d');
    }
    async uploadImageFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch('/api/upload_image', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.success) {
            // 업로드 성공 후 서버에서 fit된 이미지를 다시 받아서 표시할 수도 있음
            // 또는 별도 fetch로 이미지 데이터를 받아서 loadImageFit 호출
        }
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