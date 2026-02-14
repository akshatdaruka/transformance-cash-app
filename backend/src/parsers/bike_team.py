import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from decimal import Decimal
from datetime import datetime
import re
from src.parsers.base import BasePDFParser
from src.models import RemittanceAdvice, InvoiceLine

class BikeTeamParser(BasePDFParser):
    def can_parse(self, file_path: str) -> bool:
        try:
            with pdfplumber.open(file_path) as pdf:
                if not pdf.pages: return False
                text = pdf.pages[0].extract_text() or ""
            
            # Fallback to OCR if text layer is missing
            if len(text.strip()) < 10:
                images = convert_from_path(file_path, first_page=1, last_page=1)
                if images:
                    text = pytesseract.image_to_string(images[0])
            
            normalized = text.lower()
            return "bike team" in normalized or "zahlungsavis" in normalized
        except:
            return False

    def parse(self, file_path: str) -> RemittanceAdvice:
        all_lines = []
        raw_text = ""

        # 1. Extract Text (Native or OCR)
        with pdfplumber.open(file_path) as pdf:
            text = pdf.pages[0].extract_text() or ""
            
        if len(text.strip()) < 10:
            images = convert_from_path(file_path)
            custom_config = r'--oem 3 --psm 6'
            for img in images:
                raw_text += pytesseract.image_to_string(img, config=custom_config)
        else:
            for page in pdf.pages:
                raw_text += page.extract_text() or ""

        # 2. Extract Document Date from Header (to exclude it later)
        doc_date = None
        header_match = re.search(r"Datum\s+(\d{2}\.\d{2}\.\d{4})", raw_text)
        if header_match:
            doc_date = header_match.group(1)

        lines = raw_text.split('\n')
        date_pattern = re.compile(r"(\d{2}\.\d{2}\.\d{4})")
        money_pattern = re.compile(r"[\d.,]+\d{2}") 

        parsing_active = True

        for line in lines:
            # Stop parsing if we hit the total line
            if "Gesamtsumme" in line or "Summe" in line:
                parsing_active = False
                continue
            
            if not parsing_active:
                continue

            if "Zahlungsbeleg" in line:
                continue

            date_match = date_pattern.search(line)
            if not date_match:
                continue 

            try:
                date_str = date_match.group(1)
                
                # Exclude if date matches header date (likely footer/summary)
                if doc_date and date_str == doc_date:
                    continue

                date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()

                # Find money after the date
                post_date_text = line.split(date_str)[-1]
                candidates = money_pattern.findall(post_date_text)
                
                valid_amounts = []
                for c in candidates:
                    clean = c.replace(' ', '')
                    if ',' in clean and '.' in clean:
                        if clean.rfind(',') > clean.rfind('.'):
                            clean = clean.replace('.', '').replace(',', '.')
                        else:
                            clean = clean.replace(',', '')
                    elif ',' in clean:
                         clean = clean.replace(',', '.')
                    
                    try:
                        val = Decimal(clean)
                        if val > 0: valid_amounts.append(val)
                    except:
                        continue

                if valid_amounts:
                    net_amount = valid_amounts[-1]

                    # Extract References (Col 1 and Col 2)
                    parts = line.split()
                    col1_ref = "UNKNOWN"
                    col2_ref = "UNKNOWN"
                    
                    # Heuristic: Ref is usually at start of line
                    if len(parts) >= 2:
                        # Clean potential garbage
                        p0 = re.sub(r'[^A-Za-z0-9]', '', parts[0])
                        p1 = re.sub(r'[^A-Za-z0-9]', '', parts[1])
                        
                        # Verify length to ensure they are refs
                        if len(p0) > 4: col1_ref = p0
                        if len(p1) > 4: col2_ref = p1
                    
                    # Fallback if split failed (e.g. "97000... 38000...")
                    if col1_ref == "UNKNOWN":
                        col1_ref = parts[0]

                    line_item = InvoiceLine(
                        internal_ref=col1_ref,
                        invoice_number=col2_ref,
                        date=date_obj,
                        gross_amount=net_amount,
                        net_amount=net_amount
                    )
                    all_lines.append(line_item)

            except Exception:
                continue

        total_amount = sum(l.net_amount for l in all_lines)
        
        return RemittanceAdvice(
            sender_name="Bike Team GmbH",
            total_amount=total_amount,
            lines=all_lines,
            currency="EUR"
        )