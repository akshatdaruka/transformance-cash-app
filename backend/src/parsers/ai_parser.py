import re
import ast
import json
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from openai import OpenAI
import base64
from io import BytesIO
from src.parsers.base import BasePDFParser
from src.models import RemittanceAdvice, InvoiceLine
from decimal import Decimal
from datetime import datetime, date

class UniversalAIParser(BasePDFParser):
    def __init__(self):
        print("DEBUG: Initializing Local AI (Ollama)...")
        self.client = OpenAI(
            base_url="http://host.docker.internal:11434/v1",
            api_key="ollama"
        )
        self.model = "llama3.2-vision" 

    def can_parse(self, file_path: str) -> bool:
        return True

    def _encode_image(self, image):
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def _extract_text(self, file_path: str) -> str:
        text_content = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extract = page.extract_text(layout=True)
                    if extract: text_content += extract + "\n"
        except: pass

        if len(text_content.strip()) < 50:
            print("DEBUG: Low text detected. Running OCR...")
            try:
                images = convert_from_path(file_path)
                for img in images:
                    text_content += pytesseract.image_to_string(img, config='--psm 6') + "\n"
            except Exception as e:
                print(f"❌ OCR Failed: {e}")
        
        return text_content

    def parse(self, file_path: str) -> RemittanceAdvice:
        # 1. Inputs
        raw_text = self._extract_text(file_path)
        print(f"DEBUG: Extracted {len(raw_text)} chars of text.")
        
        images = convert_from_path(file_path, first_page=1, last_page=1)
        base64_image = self._encode_image(images[0])

        # 2. PROMPT (Unchanged)
        prompt = f"""
        You are a Data Extraction API. Your job is to extract data from German Invoices into a Python Dictionary.

        ### EXAMPLE INPUT:
        "Bike Team GmbH. Invoice #123. Date: 12.12.2023. Bruttobetrag: 1.500,00. Zahlbetrag: 1.470,00"

        ### EXAMPLE OUTPUT:
        {{
            'sender_name': 'Bike Team GmbH',
            'total_amount': '1.470,00',
            'lines': [
                 {{ 'internal_ref': '123', 'invoice_number': '123', 'amount_na': '1.500,00', 'amount': '1.470,00' }}
            ]
        }}

        ### YOUR TASK:
        Extract data from the text below.
        
        INPUT TEXT:
        '''
        {raw_text}
        '''

        GUIDELINES:
        1. **sender_name**: Look for the company name at the top left.
        2. **total_amount**: Look for "Gesamtsumme" or "Zahlbetrag" (The final total).
        3. **lines**: Extract the table rows.
           - "Ihre Belegnr" -> 'internal_ref'
           - "Referenz" -> 'invoice_number'
           - "Bruttobetrag" (2nd Last Column) -> 'amount_na' (Capture this but we might ignore it)
           - "Zahlbetrag" (LAST Column) -> 'amount' (This is the Payment Amount we strictly need)

        OUTPUT:
        Return ONLY the Python dictionary. Start with {{ and end with }}.
        """

        print("DEBUG: Asking Ollama for Dictionary...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]}
                ],
                temperature=0.0, 
            )
            llm_response = response.choices[0].message.content.strip()
            print(f"DEBUG: LLM Response: {llm_response[:]}...")
        except Exception as e:
            raise ValueError(f"AI Connection Error: {str(e)}")
        
        # 3. Robust Extraction
        data = self._extract_dict_from_response(llm_response)
        
        # 4. Convert
        return self._convert_to_model(data)

    def _extract_dict_from_response(self, text):
        """
        Extracts a Python dictionary from the LLM response.
        Prioritizes Markdown code blocks to avoid capturing "reasoning text".
        """
        try:
            # STRATEGY 1: Extract content inside ```python ... ``` or ``` ... ``` blocks
            # re.DOTALL ensures '.' matches newlines
            code_blocks = re.findall(r"```(?:python)?\s*([\s\S]*?)\s*```", text, re.DOTALL)
            
            if code_blocks:
                # If multiple blocks exist, the Last one is usually the final answer.
                for block in reversed(code_blocks):
                    clean_block = block.strip()
                    # Ensure it looks like a dict
                    if clean_block.startswith("{") and clean_block.endswith("}"):
                        try:
                            return ast.literal_eval(clean_block)
                        except:
                            continue # Try the next block (which is the previous one in the list)

            # STRATEGY 2: Fallback - Find the largest outer { ... } 
            # (Only used if no code blocks were found)
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                candidate = match.group(0)
                try:
                    return ast.literal_eval(candidate)
                except:
                    pass
            
            print("❌ Parsing Failed. No valid dictionary found.")
            return {}

        except Exception as e:
            print(f"❌ Error extracting dict: {e}")
            return {}

    def _convert_to_model(self, data: dict) -> RemittanceAdvice:
        # 1. Sender
        sender = str(data.get("sender_name", "Bike Team GmbH"))
        
        # 2. Total
        total = self._clean_german_number(data.get("total_amount", 0))

        # 3. Lines
        lines = []
        raw_lines = data.get("lines", [])
        
        for item in raw_lines:
            try:
                amt = self._clean_german_number(item.get("amount", 0))
                d_str = str(item.get("date", ""))
                d_obj = date.today()
                
                for fmt in ["%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"]:
                    try:
                        d_obj = datetime.strptime(d_str, fmt).date()
                        break
                    except: pass

                if amt > 0:
                    lines.append(InvoiceLine(
                        internal_ref=str(item.get("internal_ref", "UNK")),
                        invoice_number=str(item.get("invoice_number", "UNK")),
                        date=d_obj,
                        gross_amount=amt,
                        net_amount=amt
                    ))
            except: pass

        # --- NEW: Math Check (Hallucination Guardrail) ---
        calculated_sum = sum(line.net_amount for line in lines)
        is_valid = True
        
        # Check if difference is greater than 0.05 (floating point tolerance)
        if abs(calculated_sum - total) > Decimal("0.05"):
            is_valid = False
            print(f"⚠️ Math Mismatch! AI Total: {total}, Calculated Sum: {calculated_sum}")

        return RemittanceAdvice(
            sender_name=sender,
            total_amount=total,
            lines=lines,
            currency="EUR",
            calculated_total=calculated_sum, # Send back so UI can show it
            is_math_valid=False
        )

    def _clean_german_number(self, val) -> Decimal:
        if isinstance(val, (int, float)): return Decimal(val)
        val_str = str(val).strip()
        if not val_str: return Decimal(0)
        
        val_str = re.sub(r"[^\d,.-]", "", val_str)

        if ',' in val_str and '.' in val_str:
            if val_str.rfind(',') > val_str.rfind('.'):
                val_str = val_str.replace('.', '').replace(',', '.')
            else:
                val_str = val_str.replace(',', '')
        elif ',' in val_str:
            val_str = val_str.replace(',', '.')
            
        try: return Decimal(val_str)
        except: return Decimal(0)