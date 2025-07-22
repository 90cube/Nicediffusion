/**
 * 통합 Canvas Manager
 * 모드별 Canvas 기능을 관리하는 JavaScript 모듈
 */

// Fabric.js 기반 통합 Canvas 매니저
class CanvasManager {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.canvas = null;
        this.isInitialized = false;
        this.objects = new Map();
        this.selectedObject = null;
        this.init();
    }

    init() {
        try {
            console.log('🎨 Canvas 매니저 초기화 시작:', this.canvasId);
            
            // Fabric.js Canvas 초기화
            this.canvas = new fabric.Canvas(this.canvasId, {
                width: window.innerWidth - 400,  // 사이드바 공간 제외
                height: window.innerHeight - 100, // 상단바 공간 제외
                backgroundColor: '#2d3748',  // 다크 테마
                selection: true,
                preserveObjectStacking: true
            });

            // 이벤트 리스너 설정
            this.setupEventListeners();
            
            this.isInitialized = true;
            console.log('✅ Canvas 매니저 초기화 완료');
            
            // 초기화 완료 이벤트 발생
            this.emitCanvasReady();
            
        } catch (error) {
            console.error('❌ Canvas 매니저 초기화 실패:', error);
        }
    }

    setupEventListeners() {
        // Canvas 크기 조정
        window.addEventListener('resize', () => {
            this.resizeCanvas();
        });

        // 객체 선택 이벤트
        this.canvas.on('selection:created', (e) => {
            this.selectedObject = e.selected[0];
            this.onObjectSelected(this.selectedObject);
        });

        this.canvas.on('selection:cleared', () => {
            this.selectedObject = null;
            this.onObjectDeselected();
        });

        // 객체 수정 이벤트
        this.canvas.on('object:modified', (e) => {
            this.onObjectModified(e.target);
        });
    }

    resizeCanvas() {
        if (!this.canvas) return;
        
        const width = window.innerWidth - 400;
        const height = window.innerHeight - 100;
        
        this.canvas.setDimensions({
            width: width,
            height: height
        });
        
        this.canvas.renderAll();
        console.log('📐 Canvas 크기 조정:', width, 'x', height);
    }

    // 이미지를 Canvas에 로드
    loadImageFromBase64(base64Data, options = {}) {
        if (!this.isInitialized) {
            console.error('❌ Canvas가 초기화되지 않음');
            return false;
        }

        try {
            console.log('🖼️ 이미지 로드 시작');
            
            fabric.Image.fromURL(`data:image/png;base64,${base64Data}`, (img) => {
                // 이미지 크기 조정
                const canvasWidth = this.canvas.getWidth();
                const canvasHeight = this.canvas.getHeight();
                
                const scaleX = canvasWidth / img.width;
                const scaleY = canvasHeight / img.height;
                const scale = Math.min(scaleX, scaleY, 1); // 최대 100% 크기
                
                img.scale(scale);
                
                // 중앙 배치
                img.set({
                    left: (canvasWidth - img.width * scale) / 2,
                    top: (canvasHeight - img.height * scale) / 2,
                    selectable: true,
                    evented: true,
                    hasControls: true,
                    hasBorders: true,
                    lockUniScaling: false,
                    lockRotation: false
                });

                // 객체 ID 생성
                const objectId = `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                img.objectId = objectId;
                
                // Canvas에 추가
                this.canvas.add(img);
                this.canvas.setActiveObject(img);
                this.canvas.renderAll();
                
                // 객체 맵에 저장
                this.objects.set(objectId, img);
                
                console.log('✅ 이미지 로드 완료:', objectId);
                
                // 로드 완료 이벤트 발생
                this.emitImageLoaded(objectId, img);
                
            }, { crossOrigin: 'anonymous' });
            
            return true;
            
        } catch (error) {
            console.error('❌ 이미지 로드 실패:', error);
            return false;
        }
    }

    // 객체 선택 처리
    onObjectSelected(object) {
        console.log('🎯 객체 선택됨:', object.objectId);
        
        // Python으로 선택 이벤트 전송
        if (window.nicegui) {
            window.nicegui.emit('object_selected', {
                objectId: object.objectId,
                type: object.type,
                left: object.left,
                top: object.top,
                scaleX: object.scaleX,
                scaleY: object.scaleY,
                angle: object.angle
            });
        }
    }

    // 객체 선택 해제 처리
    onObjectDeselected() {
        console.log('🎯 객체 선택 해제됨');
        
        if (window.nicegui) {
            window.nicegui.emit('object_deselected', {});
        }
    }

    // 객체 수정 처리
    onObjectModified(object) {
        console.log('✏️ 객체 수정됨:', object.objectId);
        
        if (window.nicegui) {
            window.nicegui.emit('object_modified', {
                objectId: object.objectId,
                left: object.left,
                top: object.top,
                scaleX: object.scaleX,
                scaleY: object.scaleY,
                angle: object.angle
            });
        }
    }

    // Canvas 초기화 완료 이벤트
    emitCanvasReady() {
        if (window.nicegui) {
            window.nicegui.emit('canvas_ready', {
                canvasId: this.canvasId,
                width: this.canvas.getWidth(),
                height: this.canvas.getHeight()
            });
        }
    }

    // 이미지 로드 완료 이벤트
    emitImageLoaded(objectId, imageObject) {
        if (window.nicegui) {
            window.nicegui.emit('image_loaded', {
                objectId: objectId,
                width: imageObject.width,
                height: imageObject.height,
                left: imageObject.left,
                top: imageObject.top
            });
        }
    }

    // 객체 삭제
    removeObject(objectId) {
        const object = this.objects.get(objectId);
        if (object) {
            this.canvas.remove(object);
            this.objects.delete(objectId);
            this.canvas.renderAll();
            console.log('🗑️ 객체 삭제됨:', objectId);
            return true;
        }
        return false;
    }

    // 모든 객체 삭제
    clearCanvas() {
        this.canvas.clear();
        this.objects.clear();
        this.selectedObject = null;
        this.canvas.renderAll();
        console.log('🧹 Canvas 초기화됨');
    }

    // Canvas 상태 가져오기
    getCanvasState() {
        return {
            objects: Array.from(this.objects.keys()),
            selectedObject: this.selectedObject ? this.selectedObject.objectId : null,
            canvasSize: {
                width: this.canvas.getWidth(),
                height: this.canvas.getHeight()
            }
        };
    }
}

// 전역 Canvas 매니저 인스턴스 관리
window.canvasManagers = new Map();

// DOM 로드 완료 시 초기화
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎨 Fabric.js Canvas 시스템 초기화 시작');
    
    // Fabric.js 라이브러리 로드 확인
    if (typeof fabric === 'undefined') {
        console.error('❌ Fabric.js 라이브러리가 로드되지 않음');
        return;
    }
    
    console.log('✅ Fabric.js 라이브러리 확인됨');
});

// 전역 함수들 (Python에서 호출 가능)
window.createCanvasManager = function(canvasId) {
    if (window.canvasManagers.has(canvasId)) {
        console.log('⚠️ Canvas 매니저가 이미 존재함:', canvasId);
        return window.canvasManagers.get(canvasId);
    }
    
    const manager = new CanvasManager(canvasId);
    window.canvasManagers.set(canvasId, manager);
    return manager;
};

window.getCanvasManager = function(canvasId) {
    return window.canvasManagers.get(canvasId);
};

window.loadImageToCanvas = function(canvasId, base64Data, options = {}) {
    const manager = window.getCanvasManager(canvasId);
    if (manager) {
        return manager.loadImageFromBase64(base64Data, options);
    }
    console.error('❌ Canvas 매니저를 찾을 수 없음:', canvasId);
    return false;
}; 