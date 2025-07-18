# 고급 프롬프트 시스템 통합 구현 지침

## 🎯 목표
**ComfyUI 고급 인코딩 + 프리셋 시스템 통합으로 프롬프트 처리를 완전히 개선**

## 📋 구현 내용

### 1. 고급 텍스트 인코더 구현 (ComfyUI 기반)

**파일: src/nicediff/domains/generation/services/advanced_encoder.py**

```python
import torch
import numpy as np
import itertools
from typing import List, Tuple, Dict, Any, Optional
from math import gcd
import re

class AdvancedTextEncoder:
    """ComfyUI 스타일 고급 텍스트 인코딩"""
    
    def __init__(self, pipeline, weight_mode="A1111", use_custom_tokenizer=True):
        self.pipeline = pipeline
        self.weight_mode = weight_mode  # "A1111" 또는 "comfy++"
        self.use_custom_tokenizer = use_custom_tokenizer
        self.tokenizer = pipeline.tokenizer
        self.text_encoder = pipeline.text_encoder
        
    def parse_prompt_weights(self, text: str) -> List[Tuple[str, float, int]]:
        """A1111 스타일 가중치 파싱: (word:1.2), ((word)), [word]"""
        
        # 가중치 패턴 정의
        patterns = [
            (r'\(\((.*?)\)\)', 1.21),  # ((word)) = 1.21
            (r'\((.*?):([0-9\.]+)\)', None),  # (word:1.2)
            (r'\((.*?)\)', 1.1),  # (word) = 1.1
            (r'\[(.*?)\]', 0.909),  # [word] = 1/1.1
        ]
        
        tokens = []
        word_id = 1
        
        remaining_text = text
        while remaining_text:
            matched = False
            
            # 패턴 매칭 시도
            for pattern, default_weight in patterns:
                match = re.search(pattern, remaining_text)
                if match:
                    # 매칭 이전 텍스트 처리
                    before = remaining_text[:match.start()].strip()
                    if before:
                        for word in before.split():
                            tokens.append((word, 1.0, word_id))
                            word_id += 1
                    
                    # 가중치 적용된 부분 처리
                    if default_weight is None:  # (word:1.2) 형태
                        word, weight = match.groups()
                        weight = float(weight)
                    else:
                        word = match.group(1)
                        weight = default_weight
                    
                    for w in word.strip().split():
                        tokens.append((w, weight, word_id))
                        word_id += 1
                    
                    # 매칭된 부분 제거
                    remaining_text = remaining_text[match.end():].strip()
                    matched = True
                    break
            
            if not matched:
                # 패턴이 없으면 일반 단어로 처리
                words = remaining_text.split()
                if words:
                    for word in words:
                        tokens.append((word, 1.0, word_id))
                        word_id += 1
                break
        
        return tokens
    
    def tokenize_with_weights(self, text: str) -> Dict[str, List]:
        """텍스트를 토큰화하고 가중치 정보 포함"""
        
        if not self.use_custom_tokenizer:
            # 기본 토크나이저 사용
            tokens = self.tokenizer.encode(text, add_special_tokens=True)
            weights = [1.0] * len(tokens)
            word_ids = list(range(len(tokens)))
            return {'tokens': [tokens], 'weights': [weights], 'word_ids': [word_ids]}
        
        # 고급 가중치 파싱
        parsed = self.parse_prompt_weights(text)
        
        tokens = []
        weights = []
        word_ids = []
        
        for word, weight, word_id in parsed:
            # 단어를 토큰으로 변환
            word_tokens = self.tokenizer.encode(word, add_special_tokens=False)
            
            tokens.extend(word_tokens)
            weights.extend([weight] * len(word_tokens))
            word_ids.extend([word_id] * len(word_tokens))
        
        # 특수 토큰 추가
        tokens = [self.tokenizer.bos_token_id] + tokens + [self.tokenizer.eos_token_id]
        weights = [1.0] + weights + [1.0]
        word_ids = [0] + word_ids + [0]
        
        return {'tokens': [tokens], 'weights': [weights], 'word_ids': [word_ids]}
    
    def _grouper(self, n, iterable):
        """청킹 헬퍼"""
        it = iter(iterable)
        while True:
            chunk = list(itertools.islice(it, n))
            if not chunk:
                return
            yield chunk
    
    def _norm_mag(self, w, n):
        """가중치 정규화"""
        d = w - 1
        return 1 + np.sign(d) * np.sqrt(np.abs(d)**2 / n)
    
    def divide_length(self, word_ids, weights):
        """단어 길이별 가중치 분배"""
        sums = dict(zip(*np.unique(word_ids, return_counts=True)))
        sums[0] = 1
        weights = [[self._norm_mag(w, sums[id]) if id != 0 else 1.0
                    for w, id in zip(x, y)] for x, y in zip(weights, word_ids)]
        return weights
    
    def from_zero(self, weights, base_emb):
        """가중치를 임베딩에 적용 (A1111 방식)"""
        weight_tensor = torch.tensor(weights, dtype=base_emb.dtype, device=base_emb.device)
        weight_tensor = weight_tensor.reshape(1, -1, 1).expand(base_emb.shape)
        return base_emb * weight_tensor
    
    def encode_prompt(self, prompt: str, negative_prompt: str = "") -> Tuple[torch.Tensor, torch.Tensor]:
        """프롬프트 인코딩 (메인 함수)"""
        
        # 긍정 프롬프트 처리
        pos_tokenized = self.tokenize_with_weights(prompt)
        pos_embeddings = self._encode_tokens(pos_tokenized)
        
        # 부정 프롬프트 처리
        if negative_prompt:
            neg_tokenized = self.tokenize_with_weights(negative_prompt)
            neg_embeddings = self._encode_tokens(neg_tokenized)
        else:
            # 빈 프롬프트 임베딩
            empty_tokens = self.tokenizer.encode("", add_special_tokens=True)
            empty_input = torch.tensor([empty_tokens], device=self.text_encoder.device)
            with torch.no_grad():
                neg_embeddings = self.text_encoder(empty_input)[0]
        
        return pos_embeddings, neg_embeddings
    
    def _encode_tokens(self, tokenized_data: Dict[str, List]) -> torch.Tensor:
        """토큰을 임베딩으로 변환"""
        
        tokens = tokenized_data['tokens'][0]
        weights = tokenized_data['weights'][0]
        word_ids = tokenized_data['word_ids'][0]
        
        # 토큰 길이 조정 (77토큰 제한 해제)
        max_length = 77  # 기본값, 필요시 확장
        if len(tokens) > max_length:
            # 청킹 처리
            return self._encode_long_prompt(tokens, weights, word_ids, max_length)
        
        # 패딩
        while len(tokens) < max_length:
            tokens.append(self.tokenizer.pad_token_id or 0)
            weights.append(1.0)
            word_ids.append(0)
        
        # 기본 임베딩 생성
        token_tensor = torch.tensor([tokens], device=self.text_encoder.device)
        with torch.no_grad():
            base_embeddings = self.text_encoder(token_tensor)[0]
        
        # 가중치 적용
        if self.weight_mode == "A1111":
            return self._apply_a1111_weights(base_embeddings, weights, word_ids)
        elif self.weight_mode == "comfy++":
            return self._apply_comfy_weights(base_embeddings, weights, word_ids)
        else:
            return base_embeddings
    
    def _encode_long_prompt(self, tokens: List[int], weights: List[float], word_ids: List[int], chunk_size: int) -> torch.Tensor:
        """긴 프롬프트 청킹 처리"""
        
        chunks = []
        for i in range(0, len(tokens), chunk_size-2):  # 특수 토큰 공간 확보
            chunk_tokens = tokens[i:i+chunk_size-2]
            chunk_weights = weights[i:i+chunk_size-2]
            chunk_word_ids = word_ids[i:i+chunk_size-2]
            
            # 특수 토큰 추가
            full_tokens = [self.tokenizer.bos_token_id] + chunk_tokens + [self.tokenizer.eos_token_id]
            full_weights = [1.0] + chunk_weights + [1.0]
            full_word_ids = [0] + chunk_word_ids + [0]
            
            # 패딩
            while len(full_tokens) < chunk_size:
                full_tokens.append(self.tokenizer.pad_token_id or 0)
                full_weights.append(1.0)
                full_word_ids.append(0)
            
            # 인코딩
            token_tensor = torch.tensor([full_tokens], device=self.text_encoder.device)
            with torch.no_grad():
                chunk_emb = self.text_encoder(token_tensor)[0]
            
            # 가중치 적용
            if self.weight_mode == "A1111":
                chunk_emb = self._apply_a1111_weights(chunk_emb, full_weights, full_word_ids)
            elif self.weight_mode == "comfy++":
                chunk_emb = self._apply_comfy_weights(chunk_emb, full_weights, full_word_ids)
            
            chunks.append(chunk_emb)
        
        # 청크 병합 (평균)
        if len(chunks) == 1:
            return chunks[0]
        else:
            return torch.mean(torch.stack(chunks), dim=0)
    
    def _apply_a1111_weights(self, embeddings: torch.Tensor, weights: List[float], word_ids: List[int]) -> torch.Tensor:
        """A1111 스타일 가중치 적용"""
        weighted_emb = self.from_zero([weights], embeddings)
        
        # A1111 정규화
        norm_base = torch.linalg.norm(embeddings)
        norm_weighted = torch.linalg.norm(weighted_emb)
        
        if norm_weighted > 0:
            embeddings_final = (norm_base / norm_weighted) * weighted_emb
        else:
            embeddings_final = weighted_emb
        
        return embeddings_final
    
    def _apply_comfy_weights(self, embeddings: torch.Tensor, weights: List[float], word_ids: List[int]) -> torch.Tensor:
        """ComfyUI++ 스타일 가중치 적용 (고급)"""
        
        # 길이별 가중치 분배
        weights_normalized = self.divide_length([word_ids], [weights])[0]
        
        # 가중치 적용
        weighted_emb = self.from_zero([weights_normalized], embeddings)
        
        # 분포 복원
        fixed_std = (embeddings.std() / weighted_emb.std()) * (weighted_emb - weighted_emb.mean())
        embeddings_final = fixed_std + (embeddings.mean() - fixed_std.mean())
        
        return embeddings_final
```

### 2. 프리셋 시스템 구현

**파일: src/nicediff/services/preset_manager.py**

```python
import json
import os
from pathlib import Path
from typing import List, Dict, Any

class PresetManager:
    """프롬프트 프리셋 관리"""
    
    def __init__(self):
        self.preset_dir = Path("models/preset")
        self.pos_dir = self.preset_dir / "pos_prompt"
        self.neg_dir = self.preset_dir / "neg_prompt"
        
        # 디렉토리 생성
        self.pos_dir.mkdir(parents=True, exist_ok=True)
        self.neg_dir.mkdir(parents=True, exist_ok=True)
        
        # 기본 프리셋 생성
        self._create_default_presets()
    
    def _create_default_presets(self):
        """기본 프리셋 파일 생성"""
        
        # 긍정 프롬프트 프리셋들
        positive_presets = {
            "Quality": {
                "prompt": "masterpiece, best quality, highly detailed, sharp focus, professional",
                "description": "기본 품질 향상 태그"
            },
            "Photorealistic": {
                "prompt": "photorealistic, realistic, photo, 8k uhd, high resolution, professional photography",
                "description": "사실적인 사진 스타일"
            },
            "Anime": {
                "prompt": "anime style, manga style, illustration, detailed anime art, vibrant colors",
                "description": "애니메이션 스타일"
            },
            "Portrait": {
                "prompt": "beautiful face, detailed eyes, detailed skin, perfect anatomy, beautiful lighting",
                "description": "인물화 전용 태그"
            },
            "Landscape": {
                "prompt": "beautiful landscape, scenic view, natural lighting, atmospheric perspective, depth of field",
                "description": "풍경화 전용 태그"
            },
            "Fantasy": {
                "prompt": "fantasy art, magical, mystical, ethereal, enchanting, otherworldly",
                "description": "판타지 아트 스타일"
            },
            "Cinematic": {
                "prompt": "cinematic lighting, dramatic lighting, film grain, movie poster style",
                "description": "영화적 분위기"
            }
        }
        
        # 부정 프롬프트 프리셋들
        negative_presets = {
            "Basic": {
                "prompt": "worst quality, low quality, normal quality, lowres, bad anatomy, bad hands",
                "description": "기본 품질 제외 태그"
            },
            "People": {
                "prompt": "bad anatomy, bad hands, bad fingers, missing fingers, extra fingers, bad proportions, deformed, ugly face",
                "description": "인물 그릴 때 제외할 것들"
            },
            "Artifacts": {
                "prompt": "blurry, noisy, jpeg artifacts, compression artifacts, oversaturated, duplicate",
                "description": "이미지 아티팩트 제거"
            },
            "NSFW": {
                "prompt": "nsfw, nude, explicit, sexual content, inappropriate",
                "description": "성인 콘텐츠 제외"
            },
            "Text": {
                "prompt": "text, watermark, signature, logo, username, artist name, copyright",
                "description": "텍스트 및 워터마크 제거"
            },
            "Deformed": {
                "prompt": "deformed, disfigured, mutation, mutated, extra limbs, missing limbs, poorly drawn",
                "description": "변형된 형태 제외"
            }
        }
        
        # JSON 파일로 저장
        for name, data in positive_presets.items():
            preset_file = self.pos_dir / f"{name}.json"
            if not preset_file.exists():
                with open(preset_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        
        for name, data in negative_presets.items():
            preset_file = self.neg_dir / f"{name}.json"
            if not preset_file.exists():
                with open(preset_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_positive_presets(self) -> List[Dict[str, str]]:
        """긍정 프롬프트 프리셋 목록 반환"""
        presets = []
        
        for preset_file in self.pos_dir.glob("*.json"):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    presets.append({
                        'name': preset_file.stem,
                        'prompt': data.get('prompt', ''),
                        'description': data.get('description', '')
                    })
            except Exception as e:
                print(f"프리셋 로드 실패 {preset_file}: {e}")
        
        return sorted(presets, key=lambda x: x['name'])
    
    def get_negative_presets(self) -> List[Dict[str, str]]:
        """부정 프롬프트 프리셋 목록 반환"""
        presets = []
        
        for preset_file in self.neg_dir.glob("*.json"):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    presets.append({
                        'name': preset_file.stem,
                        'prompt': data.get('prompt', ''),
                        'description': data.get('description', '')
                    })
            except Exception as e:
                print(f"프리셋 로드 실패 {preset_file}: {e}")
        
        return sorted(presets, key=lambda x: x['name'])
    
    def add_preset(self, name: str, prompt: str, description: str, is_negative: bool = False):
        """새 프리셋 추가"""
        preset_data = {
            'prompt': prompt,
            'description': description
        }
        
        target_dir = self.neg_dir if is_negative else self.pos_dir
        preset_file = target_dir / f"{name}.json"
        
        with open(preset_file, 'w', encoding='utf-8') as f:
            json.dump(preset_data, f, ensure_ascii=False, indent=2)
    
    def delete_preset(self, name: str, is_negative: bool = False):
        """프리셋 삭제"""
        target_dir = self.neg_dir if is_negative else self.pos_dir
        preset_file = target_dir / f"{name}.json"
        
        if preset_file.exists():
            preset_file.unlink()
```

### 3. 프롬프트 패널 UI 개선

**파일: src/nicediff/ui/prompt_panel.py (수정)**

```python
# 기존 import에 추가
from ..services.preset_manager import PresetManager

class PromptPanel:
    def __init__(self, state_manager):
        self.state = state_manager
        self.preset_manager = PresetManager()
        
        # 고급 인코딩 설정
        self.use_custom_tokenizer = True
        self.weight_interpretation = "A1111"  # "A1111" 또는 "comfy++"
    
    def render(self):
        with ui.card().classes('w-full p-4'):
            # 고급 인코딩 설정 (상단에 추가)
            with ui.expansion('고급 프롬프트 설정', icon='settings').classes('w-full mb-4'):
                with ui.row().classes('w-full gap-4 items-center'):
                    # 커스텀 토크나이저 토글
                    ui.label('커스텀 토크나이저:').classes('min-w-fit')
                    self.custom_tokenizer_switch = ui.switch(
                        value=self.use_custom_tokenizer,
                        on_change=self._on_tokenizer_change
                    ).props('color=blue')
                    
                    # 가중치 해석 방식 선택
                    ui.label('가중치 처리:').classes('min-w-fit ml-4')
                    self.weight_mode_select = ui.select(
                        options=['A1111', 'comfy++'],
                        value=self.weight_interpretation,
                        on_change=self._on_weight_mode_change
                    ).classes('min-w-32')
            
            # 긍정 프롬프트
            with ui.column().classes('w-full gap-2'):
                ui.label('긍정 프롬프트').classes('text-lg font-medium text-green-400')
                
                self.positive_textarea = ui.textarea(
                    placeholder='긍정적인 프롬프트를 입력하세요...',
                    value=self.state.get_param('prompt', ''),
                ).props('outlined autogrow').classes('w-full min-h-24').on(
                    'update:model-value', 
                    lambda e: self.state.update_param('prompt', e.args[0])
                )
                
                # 긍정 프롬프트 프리셋 버튼들
                with ui.row().classes('w-full gap-1 flex-wrap'):
                    ui.label('프리셋:').classes('text-sm text-gray-400 mr-2')
                    for preset in self.preset_manager.get_positive_presets():
                        ui.button(
                            preset['name'],
                            on_click=lambda p=preset: self._add_positive_preset(p)
                        ).props('size=sm color=green outline').tooltip(preset['description'])
            
            # 부정 프롬프트  
            with ui.column().classes('w-full gap-2 mt-4'):
                ui.label('부정 프롬프트').classes('text-lg font-medium text-red-400')
                
                self.negative_textarea = ui.textarea(
                    placeholder='제외할 내용을 입력하세요...',
                    value=self.state.get_param('negative_prompt', ''),
                ).props('outlined autogrow').classes('w-full min-h-24').on(
                    'update:model-value',
                    lambda e: self.state.update_param('negative_prompt', e.args[0])
                )
                
                # 부정 프롬프트 프리셋 버튼들
                with ui.row().classes('w-full gap-1 flex-wrap'):
                    ui.label('프리셋:').classes('text-sm text-gray-400 mr-2')
                    for preset in self.preset_manager.get_negative_presets():
                        ui.button(
                            preset['name'],
                            on_click=lambda p=preset: self._add_negative_preset(p)
                        ).props('size=sm color=red outline').tooltip(preset['description'])
    
    def _on_tokenizer_change(self, event):
        """커스텀 토크나이저 설정 변경"""
        self.use_custom_tokenizer = event.args[0]
        self.state.set('use_custom_tokenizer', self.use_custom_tokenizer)
        print(f"✅ 커스텀 토크나이저: {'활성화' if self.use_custom_tokenizer else '비활성화'}")
    
    def _on_weight_mode_change(self, event):
        """가중치 해석 방식 변경"""
        self.weight_interpretation = event.args[0]
        self.state.set('weight_interpretation', self.weight_interpretation)
        print(f"✅ 가중치 처리 방식: {self.weight_interpretation}")
    
    def _add_positive_preset(self, preset):
        """긍정 프롬프트 프리셋 추가"""
        current_prompt = self.positive_textarea.value or ''
        
        if current_prompt and not current_prompt.endswith(', '):
            new_prompt = current_prompt + ', ' + preset['prompt']
        else:
            new_prompt = current_prompt + preset['prompt']
        
        self.positive_textarea.set_value(new_prompt)
        self.state.update_param('prompt', new_prompt)
        
        ui.notify(f"프리셋 '{preset['name']}' 추가됨", type='positive')
    
    def _add_negative_preset(self, preset):
        """부정 프롬프트 프리셋 추가"""
        current_prompt = self.negative_textarea.value or ''
        
        if current_prompt and not current_prompt.endswith(', '):
            new_prompt = current_prompt + ', ' + preset['prompt']
        else:
            new_prompt = current_prompt + preset['prompt']
        
        self.negative_textarea.set_value(new_prompt)
        self.state.update_param('negative_prompt', new_prompt)
        
        ui.notify(f"부정 프리셋 '{preset['name']}' 추가됨", type='positive')
```

### 4. 생성 모드 통합

**파일: src/nicediff/domains/generation/modes/txt2img.py (수정)**

```python
# 기존 import에 추가
from ..services.advanced_encoder import AdvancedTextEncoder

class Txt2ImgMode:
    def __init__(self, pipeline: Any, device: str):
        self.pipeline = pipeline
        self.device = device
    
    async def generate(self, params: Txt2ImgParams) -> List[Any]:
        """텍스트-이미지 생성 (고급 인코딩 적용)"""
        print(f"🎨 Txt2Img 생성 시작 - Seed: {params.seed}")
        
        # 스케줄러 적용
        SchedulerManager.apply_scheduler_to_pipeline(
            self.pipeline, 
            params.sampler, 
            params.scheduler
        )
        
        # CLIP Skip 적용
        if params.clip_skip > 1:
            SchedulerManager.apply_clip_skip_to_pipeline(
                self.pipeline, 
                params.clip_skip
            )
        
        # 고급 텍스트 인코더 사용
        use_custom = getattr(params, 'use_custom_tokenizer', True)
        weight_mode = getattr(params, 'weight_interpretation', 'A1111')
        
        encoder = AdvancedTextEncoder(
            self.pipeline, 
            weight_mode=weight_mode,
            use_custom_tokenizer=use_custom
        )
        
        # 프롬프트 인코딩 (77토큰 제한 없음)
        print(f"📝 프롬프트 인코딩 - 모드: {weight_mode}, 커스텀: {use_custom}")
        prompt_embeds, negative_prompt_embeds = encoder.encode_prompt(
            params.prompt, 
            params.negative_prompt
        )
        
        print(f"✅ 임베딩 생성 완료:")
        print(f"   - 긍정: {prompt_embeds.shape}")
        print(f"   - 부정: {negative_prompt_embeds.shape}")
        
        def _generate():
            """실제 생성 로직"""
            generator = torch.Generator(device=self.device)
            if params.seed > 0:
                generator.manual_seed(params.seed)
            
            try:
                # 임베딩을 직접 사용하여 생성
                result = self.pipeline(
                    prompt_embeds=prompt_embeds,
                    negative_prompt_embeds=negative_prompt_embeds,
                    height=params.height,
                    width=params.width,
                    num_inference_steps=params.steps,
                    guidance_scale=params.cfg_scale,
                    generator=generator,
                    num_images_per_prompt=params.batch_size,
                    output_type='pil'
                )
                
                return result.images if hasattr(result, 'images') else result
                
            except Exception as e:
                print(f"❌ 파이프라인 호출 실패: {e}")
                return []
        
        # 생성 실행
        generated_images = await asyncio.to_thread(_generate)
        
        print(f"✅ 생성 완료: {len(generated_images)}개 이미지")
        return generated_images
```

**파일: src/nicediff/domains/generation/modes/img2img.py (수정)**

```python
# txt2img.py와 동일한 방식으로 고급 인코더 적용

class Img2ImgMode:
    async def generate(self, params: Img2ImgParams) -> List[Any]:
        # 기존 코드 유지하되 프롬프트 처리 부분만 교체
        
        # 고급 텍스트 인코더 사용
        use_custom = getattr(params, 'use_custom_tokenizer', True)
        weight_mode = getattr(params, 'weight_interpretation', 'A1111')
        
        encoder = AdvancedTextEncoder(
            self.pipeline, 
            weight_mode=weight_mode,
            use_custom_tokenizer=use_custom
        )
        
        prompt_embeds, negative_prompt_embeds = encoder.encode_prompt(
            params.prompt, 
            params.negative_prompt
        )
        
        # 나머지 img2img 로직은 기존과 동일하되
        # 파이프라인 호출 시 prompt_embeds 사용
```

### 5. 설정 파일 업데이트

**파일: config.toml (추가)**

```toml
[advanced_encoding]
# 고급 프롬프트 인코딩 설정
use_custom_tokenizer = true
weight_interpretation = "A1111"  # "A1111" 또는 "comfy++"
enable_long_prompts = true
max_chunk_size = 77

[presets]
# 프리셋 시스템 설정
auto_create_defaults = true
preset_directory = "models/preset"
```

## 🚫 제거할 기능

### 1. 기존 프롬프트 최적화 버튼 제거

**파일: prompt_panel.py에서 제거할 부분**

```python
# 제거할 코드들:
# - "프롬프트 최적화" 버튼
# - "긴 프롬프트 처리" 버튼  
# - 관련된 모든 최적화 함수들
```

### 2. 기존 토큰 제한 로직 제거

**파일: txt2img.py, img2img.py에서 제거**

```python
# 제거할 코드들:
# - _truncate_prompt_with_tokenizer() 함수
# - 77토큰 제한 체크
# - 프롬프트 잘림 경고 메시지
```

## 📋 완료 체크리스트

### 구현 순서
1. [ ] AdvancedTextEncoder 클래스 구현
2. [ ] PresetManager 클래스 구현  
3. [ ] 기본 프리셋 JSON 파일 생성
4. [ ] prompt_panel.py UI 업데이트
5. [ ] txt2img.py, img2img.py 인코더 통합
6. [ ] 기존 최적화 버튼 제거
7. [ ] config.toml 설정 추가

### 테스트 항목
- [ ] 기존 짧은 프롬프트 동일한 결과
- [ ] 긴 프롬프트 정상 처리 (77토큰 초과)
- [ ] 가중치 문법 적용 확인: (word:1.2), ((word)), [word]
- [ ] A1111과 comfy++ 모드 차이 확인
- [ ] 프리셋 버튼 동작 확인
- [ ] 프리셋 추가/이어쓰기 기능
- [ ] UI 설정 저장/복원

### 최종 결과
✅ **77토큰 제한 완전 해제**  
✅ **고급 가중치 처리 (A1111/ComfyUI 방식)**  
✅ **편리한 프리셋 시스템**  
✅ **기존 UI/기능 100% 호환**  
✅ **긴 프롬프트 자동 청킹**  
✅ **설정 간편화 (2개 토글만)**

## 🎯 최종 사용자 경험

1. **설정**: 프롬프트 패널에서 간단한 토글 2개만 설정
2. **입력**: 기존과 동일하게 프롬프트 입력 (길이 제한 없음)
3. **프리셋**: 원클릭으로 품질/스타일 태그 추가
4. **결과**: 더 정확한 가중치 적용과 긴 프롬프트 지원

**사용자는 설정 한 번만 하면 모든 혜택을 자동으로 누릴 수 있습니다!**
