import re
from dataclasses import dataclass
from app.processors.document_processor import DocumentProcessor


@dataclass
class ChunkData:
    chunk_index: int
    text: str
    page: int
    start_char: int
    end_char: int
    word_count: int


class Chunker:

    @staticmethod
    def chunk_document(
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> list[ChunkData]:
        clean = DocumentProcessor.clean_text(text)
        if not clean:
            return []

        if len(clean) <= chunk_size:
            return [
                ChunkData(
                    chunk_index=0,
                    text=clean,
                    page=1,
                    start_char=0,
                    end_char=len(clean),
                    word_count=len(clean.split()),
                )
            ]

        segments = re.split(r"(?<=[.!?\n])\s+", clean)
        chunks: list[ChunkData] = []
        current_segment_list: list[str] = []
        current_length = 0
        start_char = 0
        chunk_idx = 0

        chars_per_page = 1800

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue

            seg_len = len(seg)

            if seg_len > chunk_size:
                if current_segment_list:
                    chunk_text = " ".join(current_segment_list).strip()
                    end_char = start_char + len(chunk_text)
                    page_num = max(1, (start_char // chars_per_page) + 1)
                    chunks.append(
                        ChunkData(
                            chunk_index=chunk_idx,
                            text=chunk_text,
                            page=page_num,
                            start_char=start_char,
                            end_char=end_char,
                            word_count=len(chunk_text.split()),
                        )
                    )
                    chunk_idx += 1
                    overlap_chars = chunk_text[-chunk_overlap:] if chunk_overlap > 0 else ""
                    current_segment_list = [overlap_chars] if overlap_chars else []
                    current_length = len(overlap_chars)
                    start_char = max(0, end_char - len(overlap_chars))

                for i in range(0, seg_len, chunk_size - chunk_overlap):
                    sub = seg[i : i + chunk_size].strip()
                    if sub:
                        page_num = max(1, ((start_char + i) // chars_per_page) + 1)
                        chunks.append(
                            ChunkData(
                                chunk_index=chunk_idx,
                                text=sub,
                                page=page_num,
                                start_char=start_char + i,
                                end_char=start_char + i + len(sub),
                                word_count=len(sub.split()),
                            )
                        )
                        chunk_idx += 1
                start_char += seg_len
                current_segment_list = []
                current_length = 0
                continue

            if current_length + seg_len + 1 > chunk_size and current_segment_list:
                chunk_text = " ".join(current_segment_list).strip()
                end_char = start_char + len(chunk_text)
                page_num = max(1, (start_char // chars_per_page) + 1)
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        page=page_num,
                        start_char=start_char,
                        end_char=end_char,
                        word_count=len(chunk_text.split()),
                    )
                )
                chunk_idx += 1

                overlap_text = ""
                acc = 0
                for item in reversed(current_segment_list):
                    if acc + len(item) + 1 <= chunk_overlap:
                        overlap_text = item + " " + overlap_text
                        acc += len(item) + 1
                    else:
                        break

                overlap_text = overlap_text.strip()
                if overlap_text:
                    current_segment_list = [overlap_text, seg]
                    current_length = len(overlap_text) + len(seg) + 1
                    start_char = max(0, end_char - len(overlap_text))
                else:
                    current_segment_list = [seg]
                    current_length = seg_len
                    start_char = end_char
            else:
                current_segment_list.append(seg)
                current_length += seg_len + 1

        if current_segment_list:
            chunk_text = " ".join(current_segment_list).strip()
            if chunk_text:
                end_char = start_char + len(chunk_text)
                page_num = max(1, (start_char // chars_per_page) + 1)
                chunks.append(
                    ChunkData(
                        chunk_index=chunk_idx,
                        text=chunk_text,
                        page=page_num,
                        start_char=start_char,
                        end_char=end_char,
                        word_count=len(chunk_text.split()),
                    )
                )

        return chunks
