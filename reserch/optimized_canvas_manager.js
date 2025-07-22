/**
 * 최적화된 Canvas Manager
 * 빠른 초기화와 효율적인 이미지 로딩을 위한 개선된 버전
 */

class OptimizedCanvasManager {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.canvas = null;
        this.isInitialized = false;
        this.initPromise = null;
        this.objects = new Map();
        this.selectedObject = null;
        this.init();
    }

    async init() {
        try {
            console.log('🎨 최적화된 Canvas 초기화 시작:', this.canvasId);
            
            // 비동기 초기화
            this.initPromise = new Promise((resolve, reject) => {
                // Fabric.js 지연 로딩
                if (typeof fabric === 'undefined') {
                    console.log('📦 Fabric.js 로딩 중...');
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
            
            // 초기화 완료 이벤트 발생
            this.emitCanvasReady();
            
        } catch (error) {
            console.error('❌ Canvas 초기화 실패:', error);
            this.isInitialized = false;
        }
    }

    async loadFabricJS() {
        return new Promise((resolve, reject) => {
            if (typeof fabric !== 'undefined') {
                resolve();
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/fabric.js/5.3.0/fabric.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    initializeCanvas() {
        // 최소한의 설정으로 빠른 초기화
        this.canvas = new fabric.Canvas(this.canvasId, {
            width: 800,  // 기본 크기
            height: 600,
            backgroundColor: '#2d3748',
            selection: false,  // 초기에는 선택 비활성화
            renderOnAddRemove: false,  // 렌더링 최적화
            skipTargetFind: true,  // 성능 향상
            skipOffscreen: true    // 성능 향상
        });

        // 필수 이벤트만 설정
        this.setupEssentialListeners();
        
        // 초기화 후 설정 활성화
        setTimeout(() => {
            this.canvas.selection = true;
            this.canvas.renderOnAddRemove = true;
            this.canvas.skipTargetFind = false;
            this.canvas.skipOffscreen = false;
        }, 100);
    }

    setupEssentialListeners() {
        // 필수 이벤트만 설정하여 초기화 속도 향상
        this.canvas.on('after:render', () => {
            // 초기 렌더링 완료 후 추가 설정
        });

        // 객체 선택 이벤트 (지연 설정)
        setTimeout(() => {
            this.canvas.on('selection:created', (e) => {
                this.selectedObject = e.selected[0];
                this.onObjectSelected(this.selectedObject);
            });

            this.canvas.on('selection:cleared', () => {
                this.selectedObject = null;
                this.onObjectDeselected();
            });

            this.canvas.on('object:modified', (e) => {
                this.onObjectModified(e.target);
            });
        }, 200);
    }

    // 최적화된 이미지 로딩
    async loadImageOptimized(base64Data, options = {}) {
        if (!this.isInitialized) {
            console.error('❌ Canvas가 초기화되지 않음');
            return false;
        }

        try {
            console.log('🖼️ 최적화된 이미지 로드 시작');
            
            // 이미지 크기 미리 계산
            const img = new Image();
            img.src = `data:image/png;base64,${base64Data}`;
            
            await new Promise((resolve, reject) => {
                img.onload = resolve;
                img.onerror = reject;
            });

            // 최적화된 크기 계산
            const optimizedSize = this.calculateOptimalSize(img.width, img.height);
            
            // Fabric.js 이미지 생성
            return new Promise((resolve) => {
                fabric.Image.fromURL(img.src, (fabricImg) => {
                    fabricImg.scaleToWidth(optimizedSize.width);
                    fabricImg.set({
                        left: (this.canvas.getWidth() - fabricImg.getScaledWidth()) / 2,
                        top: (this.canvas.getHeight() - fabricImg.getScaledHeight()) / 2
                    });
                    
                    this.canvas.add(fabricImg);
                    this.canvas.renderAll();
                    
                    // 객체 ID 생성 및 저장
                    const objectId = `img_${Date.now()}`;
                    this.objects.set(objectId, fabricImg);
                    
                    console.log('✅ 최적화된 이미지 로드 완료');
                    this.emitImageLoaded(objectId, fabricImg);
                    resolve(true);
                });
            });

        } catch (error) {
            console.error('❌ 이미지 로딩 실패:', error);
            return false;
        }
    }

    calculateOptimalSize(imgWidth, imgHeight) {
        const canvasWidth = this.canvas.getWidth();
        const canvasHeight = this.canvas.getHeight();
        
        const scaleX = canvasWidth / imgWidth;
        const scaleY = canvasHeight / imgHeight;
        const scale = Math.min(scaleX, scaleY, 1); // 최대 100% 크기
        
        return {
            width: imgWidth * scale,
            height: imgHeight * scale
        };
    }

    // 빠른 이미지 로드 (동기 버전)
    loadImageFast(base64Data) {
        if (!this.isInitialized) {
            return false;
        }

        try {
            fabric.Image.fromURL(`data:image/png;base64,${base64Data}`, (img) => {
                const canvasWidth = this.canvas.getWidth();
                const canvasHeight = this.canvas.getHeight();
                
                const scaleX = canvasWidth / img.width;
                const scaleY = canvasHeight / img.height;
                const scale = Math.min(scaleX, scaleY, 1);
                
                img.scale(scale);
                img.set({
                    left: (canvasWidth - img.getScaledWidth()) / 2,
                    top: (canvasHeight - img.getScaledHeight()) / 2
                });
                
                this.canvas.add(img);
                this.canvas.renderAll();
                
                const objectId = `img_${Date.now()}`;
                this.objects.set(objectId, img);
                this.emitImageLoaded(objectId, img);
            });
            
            return true;
        } catch (error) {
            console.error('이미지 로딩 실패:', error);
            return false;
        }
    }

    onObjectSelected(object) {
        console.log('🎯 객체 선택됨:', object);
        // Python으로 선택 이벤트 전송
        if (window.pywebview) {
            window.pywebview.api.on_object_selected({
                objectId: object.id,
                type: object.type,
                position: {
                    left: object.left,
                    top: object.top
                }
            });
        }
    }

    onObjectDeselected() {
        console.log('🎯 객체 선택 해제됨');
        if (window.pywebview) {
            window.pywebview.api.on_object_deselected();
        }
    }

    onObjectModified(object) {
        console.log('✏️ 객체 수정됨:', object);
        if (window.pywebview) {
            window.pywebview.api.on_object_modified({
                objectId: object.id,
                type: object.type,
                position: {
                    left: object.left,
                    top: object.top
                },
                scale: {
                    scaleX: object.scaleX,
                    scaleY: object.scaleY
                }
            });
        }
    }

    emitCanvasReady() {
        console.log('🚀 Canvas 준비 완료 이벤트 발생');
        if (window.pywebview) {
            window.pywebview.api.on_canvas_ready({
                canvasId: this.canvasId,
                isInitialized: this.isInitialized
            });
        }
    }

    emitImageLoaded(objectId, imageObject) {
        console.log('📸 이미지 로드 완료 이벤트 발생:', objectId);
        if (window.pywebview) {
            window.pywebview.api.on_image_loaded({
                objectId: objectId,
                canvasId: this.canvasId,
                imageSize: {
                    width: imageObject.width,
                    height: imageObject.height
                }
            });
        }
    }

    removeObject(objectId) {
        const object = this.objects.get(objectId);
        if (object) {
            this.canvas.remove(object);
            this.objects.delete(objectId);
            this.canvas.renderAll();
            console.log('🗑️ 객체 제거됨:', objectId);
        }
    }

    clearCanvas() {
        this.canvas.clear();
        this.objects.clear();
        this.canvas.renderAll();
        console.log('🧹 Canvas 초기화됨');
    }

    getCanvasState() {
        return {
            isInitialized: this.isInitialized,
            objectCount: this.objects.size,
            canvasSize: {
                width: this.canvas.getWidth(),
                height: this.canvas.getHeight()
            }
        };
    }

    resizeCanvas(width, height) {
        if (!this.canvas) return;
        
        this.canvas.setDimensions({
            width: width,
            height: height
        });
        
        this.canvas.renderAll();
        console.log('📐 Canvas 크기 조정:', width, 'x', height);
    }
}

// 전역 함수로 등록
window.OptimizedCanvasManager = OptimizedCanvasManager;

// 기존 함수와의 호환성을 위한 래퍼
window.getOptimizedCanvasManager = function(canvasId) {
    if (!window.optimizedCanvasManagers) {
        window.optimizedCanvasManagers = new Map();
    }
    
    if (!window.optimizedCanvasManagers.has(canvasId)) {
        window.optimizedCanvasManagers.set(canvasId, new OptimizedCanvasManager(canvasId));
    }
    
    return window.optimizedCanvasManagers.get(canvasId);
}; 