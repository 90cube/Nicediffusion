# 다양한 긴 프롬프트 처리 방식 구현

class PromptProcessor:
    """긴 프롬프트 처리를 위한 프로세서"""
    
    @staticmethod
    def method_1_truncate(prompt: str, tokenizer, max_tokens: int = 77):
        """방법 1: 단순 자르기 (기본)"""
        tokens = tokenizer.encode(prompt)
        if len(tokens) > max_tokens:
            print(f"⚠️ 프롬프트가 {max_tokens} 토큰을 초과. 자동으로 잘립니다.")
            tokens = tokens[:max_tokens]
        return tokenizer.decode(tokens)
    
    @staticmethod
    def method_2_emphasis_parsing(prompt: str, tokenizer, max_tokens: int = 77):
        """방법 2: 강조 구문 파싱 (A1111 스타일)"""
        # (word:1.5) 형태의 강조 구문 처리
        import re
        
        # 강조 구문 추출
        emphasis_pattern = r'\(([^:]+):([0-9.]+)\)'
        emphasized_words = re.findall(emphasis_pattern, prompt)
        
        # 중요도 순으로 정렬
        emphasized_words.sort(key=lambda x: float(x[1]), reverse=True)
        
        # 중요한 단어를 우선 배치
        important_parts = [word for word, weight in emphasized_words[:20]]
        base_prompt = re.sub(emphasis_pattern, r'\1', prompt)
        
        # 재구성
        reconstructed = ' '.join(important_parts) + ' ' + base_prompt
        return PromptProcessor.method_1_truncate(reconstructed, tokenizer, max_tokens)
    
    @staticmethod
    def method_3_semantic_chunking(prompt: str, tokenizer, max_tokens: int = 77):
        """방법 3: 의미 단위로 청킹"""
        # 문장 단위로 분리
        sentences = prompt.split('. ')
        
        current_tokens = 0
        selected_sentences = []
        
        for sentence in sentences:
            sentence_tokens = len(tokenizer.encode(sentence))
            if current_tokens + sentence_tokens <= max_tokens:
                selected_sentences.append(sentence)
                current_tokens += sentence_tokens
            else:
                break
        
        return '. '.join(selected_sentences)
    
    @staticmethod
    def method_4_keyword_extraction(prompt: str, tokenizer, max_tokens: int = 77):
        """방법 4: 키워드 추출 방식"""
        # 중요 키워드 패턴
        important_patterns = [
            r'\b(?:masterpiece|best quality|high quality|detailed|realistic|8k|4k)\b',
            r'\b(?:beautiful|gorgeous|stunning|amazing|perfect)\b',
            r'\b\w+(?:_\w+)*\b',  # 언더스코어로 연결된 단어 (보통 중요)
        ]
        
        keywords = []
        for pattern in important_patterns:
            keywords.extend(re.findall(pattern, prompt, re.IGNORECASE))
        
        # 중복 제거하면서 순서 유지
        seen = set()
        unique_keywords = []
        for k in keywords:
            if k.lower() not in seen:
                seen.add(k.lower())
                unique_keywords.append(k)
        
        # 나머지 텍스트 추가
        remaining_text = prompt
        for keyword in unique_keywords:
            remaining_text = remaining_text.replace(keyword, '', 1)
        
        # 재구성
        result = ' '.join(unique_keywords[:30]) + ' ' + remaining_text.strip()
        return PromptProcessor.method_1_truncate(result, tokenizer, max_tokens)
    
    @staticmethod
    def method_5_prompt_weighting(prompt: str, model_type: str = 'SD15'):
        """방법 5: 프롬프트 가중치 시스템 (ComfyUI 스타일)"""
        if model_type == 'SDXL':
            # SDXL: 두 개의 인코더 활용
            return {
                'clip_l': prompt[:500],  # 주요 내용
                'clip_g': prompt[500:1000]  # 추가 디테일
            }
        else:
            # SD1.5: 단일 인코더
            return {'clip': prompt[:350]}  # 약 77 토큰

# 실제 사용 예제
class EnhancedPromptEncoder:
    """향상된 프롬프트 인코더"""
    
    def __init__(self, pipeline, method='semantic'):
        self.pipeline = pipeline
        self.method = method
        self.tokenizer = pipeline.tokenizer
        
    def encode_long_prompt(self, prompt: str, negative_prompt: str = ""):
        """긴 프롬프트 인코딩"""
        
        # 선택한 방법으로 프롬프트 처리
        if self.method == 'truncate':
            processed_prompt = PromptProcessor.method_1_truncate(
                prompt, self.tokenizer
            )
        elif self.method == 'emphasis':
            processed_prompt = PromptProcessor.method_2_emphasis_parsing(
                prompt, self.tokenizer
            )
        elif self.method == 'semantic':
            processed_prompt = PromptProcessor.method_3_semantic_chunking(
                prompt, self.tokenizer
            )
        elif self.method == 'keyword':
            processed_prompt = PromptProcessor.method_4_keyword_extraction(
                prompt, self.tokenizer
            )
        else:
            processed_prompt = prompt
        
        print(f"📝 원본 길이: {len(prompt)} → 처리 후: {len(processed_prompt)}")
        
        # 토큰화 및 인코딩
        text_inputs = self.tokenizer(
            processed_prompt,
            padding="max_length",
            max_length=self.tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        
        # 네거티브도 동일하게 처리
        if negative_prompt:
            negative_processed = PromptProcessor.method_1_truncate(
                negative_prompt, self.tokenizer
            )
            uncond_inputs = self.tokenizer(
                negative_processed,
                padding="max_length",
                max_length=self.tokenizer.model_max_length,
                truncation=True,
                return_tensors="pt",
            )
        
        return text_inputs, uncond_inputs

# UI에 옵션 추가
def create_prompt_options_ui():
    """프롬프트 처리 옵션 UI"""
    with ui.card().classes('w-full bg-gray-800 p-3'):
        ui.label('📝 긴 프롬프트 처리').classes('text-lg font-bold mb-2')
        
        prompt_method = ui.select(
            label='처리 방식',
            options=[
                {'label': '단순 자르기 (기본)', 'value': 'truncate'},
                {'label': '강조 구문 우선', 'value': 'emphasis'},
                {'label': '의미 단위 유지', 'value': 'semantic'},
                {'label': '키워드 추출', 'value': 'keyword'},
            ],
            value='semantic'
        ).classes('w-full')
        
        # 토큰 카운터
        with ui.row().classes('w-full items-center gap-2 mt-2'):
            ui.label('현재 토큰 수:').classes('text-sm')
            token_count_label = ui.label('0 / 77').classes(
                'text-sm font-bold px-2 py-1 bg-blue-600 rounded'
            )
        
        # 프롬프트 미리보기
        with ui.expansion('처리된 프롬프트 미리보기', icon='visibility').classes('w-full mt-2'):
            preview_area = ui.textarea(
                label='처리 결과',
                value='',
                readonly=True
            ).classes('w-full text-xs font-mono')
        
        return prompt_method, token_count_label, preview_area