import fitz  # PyMuPDF
from typing import List, Dict, Tuple

class BatchParser:
    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    def get_total_batches(self, total_pages: int) -> int:
        return (total_pages + self.batch_size - 1) // self.batch_size

    def get_page_range(self, batch_number: int, total_pages: int) -> Tuple[int, int]:
        start = batch_number * self.batch_size
        end = min(start + self.batch_size, total_pages)
        return start, end

    def extract_batch(self, pdf_bytes: bytes, batch_number: int, total_pages: int) -> Dict:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        start_page, end_page = self.get_page_range(batch_number, total_pages)
        
        batch_data = {
            "batch_number": batch_number,
            "start_page": start_page + 1,
            "end_page": end_page,
            "pages": []
        }
        
        for page_num in range(start_page, end_page):
            page = doc[page_num]
            text = page.get_text()
            
            # Extracción simple de posibles afirmaciones (líneas con palabras clave)
            keywords = ["teorema", "lema", "demostración", "entonces", "por lo tanto", "se cumple", "≥", "<=", ">="]
            claims = [line.strip() for line in text.split('\n') if any(k in line.lower() for k in keywords) and len(line) > 10]
            
            batch_data["pages"].append({
                "page_number": page_num + 1,
                "text": text[:500] + "..." if len(text) > 500 else text, # Truncado para UI
                "claims": claims if claims else ["No se detectaron afirmaciones matemáticas claras."]
            })
            
        doc.close()
        return batch_data
