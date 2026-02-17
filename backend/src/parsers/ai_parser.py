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
from src.models_db import VendorConfig # <--- Import DB Model
from decimal import Decimal
from datetime import datetime, date

class UniversalAIParser(BasePDFParser):
    def __init__(self, vendor_config: VendorConfig = None):
        """
        Initialize with an optional Vendor Configuration.
        If provided, the prompt becomes dynamic.
        """
        print("DEBUG: Initializing Local AI (Ollama)...")
        self.client = OpenAI(
            base_url="http://host.docker.internal:11434/v1",
            api_key="ollama"
        )
        self.model = "llama3.2-vision" 
        self.config = vendor_config # <--- Store the config

    def can_parse(self, file_path: str) -> bool:
        return True

    def _encode_image(self, image):
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def _extract_text(self, file_path: str) -> str:
        # ... (Same OCR logic as before - omitted for brevity, keep your existing logic here if you want, 
        # or just copy the simple version below which is sufficient for the demo)
        text_content = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extract = page.extract_text(layout=True)
                    if extract: text_content += extract + "\n"
        except: pass
        return text_content

    def parse(self, file_path: str) -> RemittanceAdvice:
        # 1. Inputs
        raw_text = self._extract_text(file_path)
        images = convert_from_path(file_path, first_page=1, last_page=1)
        base64_image = self._encode_image(images[0])

        # 2. DYNAMIC PROMPT GENERATION
        # Defaults (if no config provided)
        total_lbl = "Gesamtsumme"
        table_start = "lines"
        
        if self.config:
            print(f"DEBUG: Using Dynamic Prompt for Vendor: {self.config.name}")
            total_lbl = self.config.total_label
            table_start = self.config.table_start_keyword

        prompt = f"""
        You are a Data Extraction API. Extract data from this invoice into a Python Dictionary.

        ### CRITICAL INSTRUCTIONS (FROM DB CONFIG):
        1. **sender_name**: Find the company name.
        2. **total_amount**: Look specifically for the label "{total_lbl}". This is the Payment Total.
        3. **lines**: Extract the table rows. The table likely starts near "{table_start}".
           - "Ihre Belegnr" -> 'internal_ref'
           - "Referenz" -> 'invoice_number'
           - "Zahlbetrag" -> 'amount' (Payment Amount)

        ### OUTPUT FORMAT:
        {{
            'sender_name': 'Name',
            'total_amount': '1.000,00',
            'lines': [ {{ 'internal_ref': '...', 'amount': '...' }} ]
        }}
        
        Return ONLY the Python dictionary.
        """

        # 3. Call LLM
        print("DEBUG: Sending Prompt to Ollama...")
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
        except Exception as e:
            raise ValueError(f"AI Connection Error: {str(e)}")
        
        # 4. Extract & Convert
        data = self._extract_dict_from_response(llm_response)
        return self._convert_to_model(data)

    def _extract_dict_from_response(self, text):
        # ... (Keep your existing regex logic here) ...
        try:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                clean_json_str = match.group(0)
                try: return ast.literal_eval(clean_json_str)
                except: return json.loads(clean_json_str)
            return {}
        except: return {}

    def _convert_to_model(self, data: dict) -> RemittanceAdvice:
        # ... (Keep your existing conversion logic here) ...
        # Simplified for brevity in this copy-paste:
        sender = str(data.get("sender_name", "Unknown"))
        total = self._clean_german_number(data.get("total_amount", 0))
        lines = []
        for item in data.get("lines", []):
            try:
                amt = self._clean_german_number(item.get("amount", 0))
                if amt > 0:
                    lines.append(InvoiceLine(
                        internal_ref=str(item.get("internal_ref", "UNK")),
                        invoice_number=str(item.get("invoice_number", "UNK")),
                        date=date.today(),
                        gross_amount=amt,
                        net_amount=amt
                    ))
            except: pass
        
        return RemittanceAdvice(sender_name=sender, total_amount=total, lines=lines, currency="EUR")

    def _clean_german_number(self, val) -> Decimal:
        if isinstance(val, (int, float)): return Decimal(val)
        val_str = str(val).strip()
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