"""
ROA OCR — Motor de Segmentación RAG (RAGChunker)
=================================================
Prepara fragmentos de texto (chunks) estructurados con metadatos enriquecidos
compatibles con bases vectoriales como Qdrant, Meilisearch, ChromaDB, LangChain y LlamaIndex.
"""
import uuid
import re
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class RAGChunk:
    """Representa un chunk individual listo para indexación vectorial."""
    chunk_id: str
    text: str
    page_number: int
    char_count: int
    word_count: int
    metadata: Dict[str, Any]

class RAGChunker:
    """
    Segmentador semántico de documentos para RAG.
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = max(100, chunk_size)
        self.chunk_overlap = max(0, min(chunk_overlap, self.chunk_size // 2))

    def chunk_text(
        self,
        text: str,
        source_name: str = "document.pdf",
        page_number: int = 1,
        engine_used: str = "er296",
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Segmenta un texto en fragmentos con metadatos estructurados.
        """
        if not text or not text.strip():
            return []

        # Limpiar texto
        cleaned_text = re.sub(r'\r\n', '\n', text).strip()

        # Separar por párrafos o frases para mantener contexto semántico
        paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [cleaned_text]

        chunks = []
        current_chunk_text = ""
        chunk_index = 0

        for para in paragraphs:
            if len(current_chunk_text) + len(para) + 2 <= self.chunk_size:
                current_chunk_text += ("\n\n" if current_chunk_text else "") + para
            else:
                if current_chunk_text:
                    chunk_index += 1
                    chunks.append(self._build_chunk_dict(
                        chunk_text=current_chunk_text,
                        chunk_index=chunk_index,
                        source_name=source_name,
                        page_number=page_number,
                        engine_used=engine_used,
                        extra_metadata=extra_metadata
                    ))
                
                # Manejar caso donde un solo párrafo supera el chunk_size
                if len(para) > self.chunk_size:
                    sub_paras = self._split_by_sentence(para)
                    current_chunk_text = ""
                    for sub in sub_paras:
                        if len(current_chunk_text) + len(sub) + 1 <= self.chunk_size:
                            current_chunk_text += (" " if current_chunk_text else "") + sub
                        else:
                            if current_chunk_text:
                                chunk_index += 1
                                chunks.append(self._build_chunk_dict(
                                    chunk_text=current_chunk_text,
                                    chunk_index=chunk_index,
                                    source_name=source_name,
                                    page_number=page_number,
                                    engine_used=engine_used,
                                    extra_metadata=extra_metadata
                                ))
                            current_chunk_text = sub
                else:
                    current_chunk_text = para

        if current_chunk_text:
            chunk_index += 1
            chunks.append(self._build_chunk_dict(
                chunk_text=current_chunk_text,
                chunk_index=chunk_index,
                source_name=source_name,
                page_number=page_number,
                engine_used=engine_used,
                extra_metadata=extra_metadata
            ))

        return chunks

    def _split_by_sentence(self, text: str) -> List[str]:
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

    def _build_chunk_dict(
        self,
        chunk_text: str,
        chunk_index: int,
        source_name: str,
        page_number: int,
        engine_used: str,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        chunk_id = f"chk_{uuid.uuid4().hex[:12]}"
        meta = {
            "source": source_name,
            "page": page_number,
            "chunk_index": chunk_index,
            "engine": engine_used,
        }
        if extra_metadata:
            meta.update(extra_metadata)

        return {
            "chunk_id": chunk_id,
            "text": chunk_text,
            "page_number": page_number,
            "char_count": len(chunk_text),
            "word_count": len(chunk_text.split()),
            "metadata": meta,
            "qdrant_payload": {
                "id": chunk_id,
                "payload": {
                    "content": chunk_text,
                    "source": source_name,
                    "page": page_number,
                    "engine": engine_used,
                    **meta
                }
            },
            "meilisearch_doc": {
                "id": chunk_id,
                "text": chunk_text,
                "source": source_name,
                "page": page_number,
                "engine": engine_used,
                **meta
            }
        }
