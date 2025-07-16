"""
긴 프롬프트 처리 서비스
CLIP 토크나이저 제한을 우회하기 위한 프롬프트 분할 및 병합 기능
"""

import re
import torch
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass


@dataclass
class PromptChunk:
    """프롬프트 청크 정보"""
    text: str
    tokens: List[int]
    importance: float  # 0.0 ~ 1.0
    start_pos: int
    end_pos: int


class LongPromptHandler:
    """긴 프롬프트 처리 핸들러"""
    
    def __init__(self, tokenizer, max_tokens: int = 77):
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens
        self.break_keyword = "BREAK"
        
        # 중요도 가중치 정의
        self.importance_weights = {
            'subject': 1.0,      # 주제 (사람, 물체)
            'style': 0.9,        # 스타일 (artistic, realistic)
            'quality': 0.8,      # 품질 (high quality, detailed)
            'color': 0.7,        # 색상
            'lighting': 0.6,     # 조명
            'background': 0.5,   # 배경
            'mood': 0.4,         # 분위기
        }
    
    def count_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 계산"""
        tokens = self.tokenizer.encode(text, add_special_tokens=False)
        return len(tokens)
    
    def split_by_break(self, prompt: str) -> List[str]:
        """BREAK 키워드로 프롬프트 분할"""
        if self.break_keyword not in prompt:
            return [prompt]
        
        chunks = prompt.split(self.break_keyword)
        return [chunk.strip() for chunk in chunks if chunk.strip()]
    
    def split_by_commas(self, prompt: str) -> List[str]:
        """쉼표로 프롬프트 분할"""
        # 쉼표로 분할하되, 괄호 안의 쉼표는 무시
        chunks = re.split(r',\s*(?![^()]*\))', prompt)
        return [chunk.strip() for chunk in chunks if chunk.strip()]
    
    def analyze_importance(self, chunk: str) -> float:
        """청크의 중요도 분석"""
        chunk_lower = chunk.lower()
        importance = 0.5  # 기본 중요도
        
        # 키워드 기반 중요도 계산
        for category, weight in self.importance_weights.items():
            if self._has_category_keywords(chunk_lower, category):
                importance = max(importance, weight)
        
        return importance
    
    def _has_category_keywords(self, text: str, category: str) -> bool:
        """카테고리별 키워드 확인"""
        category_keywords = {
            'subject': ['girl', 'woman', 'man', 'boy', 'person', 'character', 'portrait'],
            'style': ['artistic', 'realistic', 'anime', 'cartoon', 'oil painting', 'watercolor'],
            'quality': ['high quality', 'detailed', '8k', '4k', 'masterpiece', 'best quality'],
            'color': ['red', 'blue', 'green', 'yellow', 'black', 'white', 'colorful'],
            'lighting': ['light', 'dark', 'sunlight', 'shadow', 'bright', 'dim'],
            'background': ['background', 'garden', 'forest', 'city', 'room', 'outdoor'],
            'mood': ['happy', 'sad', 'mysterious', 'romantic', 'dramatic', 'peaceful']
        }
        
        keywords = category_keywords.get(category, [])
        return any(keyword in text for keyword in keywords)
    
    def smart_split(self, prompt: str) -> List[PromptChunk]:
        """스마트 프롬프트 분할"""
        # 1. BREAK 키워드로 먼저 분할
        break_chunks = self.split_by_break(prompt)
        
        chunks = []
        current_pos = 0
        
        for break_chunk in break_chunks:
            # 2. 각 BREAK 청크를 토큰 제한에 맞게 분할
            if self.count_tokens(break_chunk) <= self.max_tokens:
                # 토큰 제한 내에 있으면 그대로 사용
                importance = self.analyze_importance(break_chunk)
                tokens = self.tokenizer.encode(break_chunk, add_special_tokens=False)
                
                chunks.append(PromptChunk(
                    text=break_chunk,
                    tokens=tokens,
                    importance=importance,
                    start_pos=current_pos,
                    end_pos=current_pos + len(break_chunk)
                ))
                current_pos += len(break_chunk) + len(self.break_keyword)
            else:
                # 토큰 제한을 초과하면 쉼표로 분할
                comma_chunks = self.split_by_commas(break_chunk)
                
                for comma_chunk in comma_chunks:
                    if self.count_tokens(comma_chunk) <= self.max_tokens:
                        importance = self.analyze_importance(comma_chunk)
                        tokens = self.tokenizer.encode(comma_chunk, add_special_tokens=False)
                        
                        chunks.append(PromptChunk(
                            text=comma_chunk,
                            tokens=tokens,
                            importance=importance,
                            start_pos=current_pos,
                            end_pos=current_pos + len(comma_chunk)
                        ))
                        current_pos += len(comma_chunk) + 1  # 쉼표 포함
                    else:
                        # 여전히 긴 경우 강제 분할
                        forced_chunks = self._force_split(comma_chunk)
                        for forced_chunk in forced_chunks:
                            importance = self.analyze_importance(forced_chunk)
                            tokens = self.tokenizer.encode(forced_chunk, add_special_tokens=False)
                            
                            chunks.append(PromptChunk(
                                text=forced_chunk,
                                tokens=tokens,
                                importance=importance,
                                start_pos=current_pos,
                                end_pos=current_pos + len(forced_chunk)
                            ))
                            current_pos += len(forced_chunk) + 1
        
        return chunks
    
    def _force_split(self, text: str) -> List[str]:
        """강제 분할 (단어 단위)"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for word in words:
            word_tokens = self.count_tokens(word)
            
            if current_tokens + word_tokens <= self.max_tokens:
                current_chunk.append(word)
                current_tokens += word_tokens
            else:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_tokens = word_tokens
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def merge_embeddings(self, embeddings: List[torch.Tensor], 
                        chunks: List[PromptChunk]) -> torch.Tensor:
        """분할된 임베딩을 중요도 기반으로 병합"""
        if not embeddings or not chunks:
            return embeddings[0] if embeddings else torch.empty(0)
        
        # 중요도 기반 가중 평균
        total_importance = sum(chunk.importance for chunk in chunks)
        
        if total_importance == 0:
            # 중요도가 모두 0인 경우 단순 평균
            return torch.mean(torch.stack(embeddings), dim=0)
        
        # 가중 평균 계산
        weighted_sum = torch.zeros_like(embeddings[0])
        for embedding, chunk in zip(embeddings, chunks):
            weight = chunk.importance / total_importance
            weighted_sum += embedding * weight
        
        return weighted_sum
    
    def optimize_prompt(self, prompt: str) -> str:
        """프롬프트 최적화 (불필요한 단어 제거)"""
        # 중복 단어 제거
        words = prompt.split()
        seen = set()
        optimized_words = []
        
        for word in words:
            if word.lower() not in seen:
                optimized_words.append(word)
                seen.add(word.lower())
        
        return ' '.join(optimized_words)
    
    def add_break_keywords(self, prompt: str, max_chunk_tokens: int = 50) -> str:
        """자동으로 BREAK 키워드 추가"""
        chunks = self.smart_split(prompt)
        
        if len(chunks) <= 1:
            return prompt
        
        # 토큰 수가 많은 청크에 BREAK 추가
        result_parts = []
        for i, chunk in enumerate(chunks):
            result_parts.append(chunk.text)
            
            # 마지막 청크가 아니고, 토큰 수가 많으면 BREAK 추가
            if i < len(chunks) - 1 and len(chunk.tokens) > max_chunk_tokens:
                result_parts.append(self.break_keyword)
        
        return f" {self.break_keyword} ".join(result_parts)
    
    def get_prompt_stats(self, prompt: str) -> Dict:
        """프롬프트 통계 정보"""
        total_tokens = self.count_tokens(prompt)
        chunks = self.smart_split(prompt)
        
        return {
            'total_tokens': total_tokens,
            'max_tokens': self.max_tokens,
            'chunks_count': len(chunks),
            'is_truncated': total_tokens > self.max_tokens,
            'truncation_ratio': total_tokens / self.max_tokens if self.max_tokens > 0 else 0,
            'chunks': [
                {
                    'text': chunk.text,
                    'tokens': len(chunk.tokens),
                    'importance': chunk.importance
                }
                for chunk in chunks
            ]
        } 