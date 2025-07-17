// canvas_manager.js에 추가할 함수

// 이미지를 Canvas에 비율 유지하며 꽉 차게 그리기
function drawImageFitToCanvas(img, canvas, ctx) {
    if (!img || !canvas || !ctx) return;
    
    // Canvas 크기
    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;
    
    // 이미지 크기
    const imgWidth = img.width;
    const imgHeight = img.height;
    
    // 비율 계산 (Canvas를 꽉 채우도록)
    const scaleX = canvasWidth / imgWidth;
    const scaleY = canvasHeight / imgHeight;
    const scale = Math.max(scaleX, scaleY); // 꽉 차게 하려면 max 사용
    
    // 크기 계산
    const scaledWidth = imgWidth * scale;
    const scaledHeight = imgHeight * scale;
    
    // 중앙 정렬을 위한 오프셋
    const offsetX = (canvasWidth - scaledWidth) / 2;
    const offsetY = (canvasHeight - scaledHeight) / 2;
    
    // Canvas 초기화
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    
    // 체커보드 배경 (선택사항)
    drawCheckerboard(ctx, canvasWidth, canvasHeight);
    
    // 이미지 그리기
    ctx.drawImage(img, offsetX, offsetY, scaledWidth, scaledHeight);
}

// 우측 하단에 리사이즈 버튼 추가
function addResizeButton(container) {
    const button = document.createElement('button');
    button.innerHTML = '⛶'; // 전체화면 아이콘
    button.style.cssText = `
        position: absolute;
        bottom: 10px;
        right: 10px;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        background: rgba(255,255,255,0.8);
        border: 1px solid #ccc;
        cursor: pointer;
        z-index: 1000;
        font-size: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
    `;
    
    button.onclick = () => {
        const canvas = container.querySelector('canvas');
        const img = canvas.__currentImage; // 현재 이미지 저장
        if (img) {
            drawImageFitToCanvas(img, canvas, canvas.getContext('2d'));
        }
    };
    
    container.appendChild(button);
}

// 체커보드 배경 그리기
function drawCheckerboard(ctx, width, height) {
    const size = 20;
    ctx.fillStyle = '#333';
    ctx.fillRect(0, 0, width, height);
    
    ctx.fillStyle = '#444';
    for (let x = 0; x < width; x += size * 2) {
        for (let y = 0; y < height; y += size * 2) {
            ctx.fillRect(x, y, size, size);
            ctx.fillRect(x + size, y + size, size, size);
        }
    }
}