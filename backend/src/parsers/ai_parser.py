import re
import json
import ast  # <--- NEW: Safely parses Python dictionaries
import pdfplumber
import pytesseract
from pdf2image import convert_from_path
from openai import OpenAI
from src.parsers.base import BasePDFParser
from src.models import RemittanceAdvice, InvoiceLine
from decimal import Decimal
from datetime import datetime, date

class UniversalAIParser(BasePDFParser):
    def __init__(self):
        print("DEBUG: Initializing Local AI (Ollama)...")
        self.client = OpenAI(
            base_url="[http://host.docker.internal:11434/v1](http://host.docker.internal:11434/v1)",
            api_key="ollama"
        )
        self.model = "llama3.2-vision" 

    def can_parse(self, file_path: str) -> bool:
        return True

    def _extract_text(self, file_path: str) -> str:
        text_content = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extract = page.extract_text(layout=True)
                    if extract: text_content += extract + "\n"
        except: pass

        if len(text_content.strip()) < 50:
            print("DEBUG: No digital text found. Switching to OCR...")
            try:
                images = convert_from_path(file_path)
                for img in images:
                    text_content += pytesseract.image_to_string(img, config='--psm 6') + "\n"
            except Exception as e:
                print(f"❌ OCR Failed: {e}")
        
        return text_content

    def parse(self, file_path: str) -> RemittanceAdvice:
        # 1. Get Text
        raw_text = self._extract_text(file_path)
        print(f"DEBUG: Extracted {len(raw_text)} chars of text.")
        
        # 2. Ask Ollama for Regex
        # We explicitly ask for a Python Dictionary format now, since that's what it wants to give.
        prompt = f"""
        You are a Python Regex Expert.
        Here is the text from a German Invoice:
        '''
        {raw_text[:3000]} 
        '''
        
        TASK: Write Python Regex patterns to extract data.
        1. "sender_pattern": Capture the Sender Name.
        2. "total_amount_pattern": Capture the Total (Gesamtsumme).
        3. "line_pattern": Capture table rows with named groups: (?P<invoice_no>...), (?P<date>...), (?P<amount>...).

        OUTPUT:
        Return ONLY a Python Dictionary. Do not use Markdown.
        {{
            'sender_pattern': r'Start_Marker\\s+(?P<sender_name>.*)\\s+End_Marker',
            'total_amount_pattern': r'Gesamtsumme\\s+(?P<amount>[\\d\\.,]+)',
            'line_pattern': r'(?P<invoice_no>\\d+)\\s+(?P<date>\\d{{2}}\\.\\d{{2}}\\.\\d{{4}})\\s+(?P<amount>[\\d\\.,]+)'
        }}
        """

        print("DEBUG: Asking Ollama for Regex...")
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        regex_json_str = response.choices[0].message.content.strip()
        print(f"DEBUG: LLM Response: {regex_json_str[:100]}...")
        
        # 3. Robust Parsing (The Fix)
        regex_config = self._clean_and_parse_json(regex_json_str)
        
        # 4. Execute Regex
        return self._apply_regex(raw_text, regex_config)

    def _clean_and_parse_json(self, raw_str):
        """
        Parses the AI output even if it's messy or uses single quotes.
        """
        try:
            # 1. Strip Markdown (```python, ```json, ```)
            clean_str = re.sub(r'```[a-zA-Z]*', '', raw_str).replace('```', '').strip()
            
            # 2. Find the Dictionary part { ... }
            start = clean_str.find('{')
            end = clean_str.rfind('}')
            
            if start != -1 and end != -1:
                candidate = clean_str[start:end+1]
                
                # A. Try Standard JSON (Double Quotes)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    # B. Try Python Eval (Single Quotes / Raw Strings)
                    # This handles { 'key': r'\d+' } which JSON fails on.
                    try:
                        return ast.literal_eval(candidate)
                    except:
                        print(f"⚠️ AST Eval failed on: {candidate[:50]}...")
            
            return {} # Fallback
            
        except Exception as e:
            print(f"❌ Failed to parse Regex: {e}")
            # Fallback Pattern (Bike Team Specific)
            return {
                "sender_pattern": r"Bike Team GmbH", 
                "total_amount_pattern": r"Gesamtsumme\s+([\d\.,]+)",
                "line_pattern": r"(?P<invoice_no>\d{5,})\s+(?P<date>\d{2}\.\d{2}\.\d{4})\s+(?P<amount>[\d\.,]+)"
            }

    def _apply_regex(self, text, patterns) -> RemittanceAdvice:
        # Defaults
        sender = "Unknown"
        total = Decimal("0.00")
        lines = []

        if not patterns: return RemittanceAdvice(sender_name=sender, total_amount=total, lines=[], currency="EUR")

        # A. Extract Sender
        try:
            p = patterns.get("sender_pattern") or patterns.get("sender_regex")
            if p:
                match = re.search(p, text)
                if match:
                    if "sender_name" in match.groupdict(): sender = match.group("sender_name")
                    else: sender = match.group(0)
        except Exception as e: print(f"Regex Error (Sender): {e}")

        # B. Extract Total
        try:
            p = patterns.get("total_amount_pattern") or patterns.get("total_amount_regex")
            if p:
                match = re.search(p, text)
                if match:
                    val = match.group("amount") if "amount" in match.groupdict() else match.group(1)
                    total = self._parse_german_number(val)
        except Exception as e: print(f"Regex Error (Total): {e}")

        # C. Extract Lines
        try:
            p = patterns.get("line_pattern") or patterns.get("table_line_regex") or patterns.get("line_regex")
            if p:
                for match in re.finditer(p, text):
                    g = match.groupdict()
                    
                    d_obj = date.today()
                    if "date" in g:
                        try: d_obj = datetime.strptime(g["date"], "%d.%m.%Y").date()
                        except: pass
                    
                    amt = Decimal("0.00")
                    if "amount" in g:
                        amt = self._parse_german_number(g["amount"])
                    
                    lines.append(InvoiceLine(
                        internal_ref=g.get("invoice_no", "UNK"), 
                        invoice_number=g.get("invoice_no", "UNK"),
                        date=d_obj,
                        gross_amount=amt,
                        net_amount=amt
                    ))
        except Exception as e: print(f"Regex Error (Lines): {e}")

        return RemittanceAdvice(
            sender_name=sender.strip(),
            total_amount=total,
            lines=lines,
            currency="EUR"
        )

    def _parse_german_number(self, val: str) -> Decimal:
        if not val: return Decimal(0)
        clean = val.replace('.', '').replace(',', '.')
        try: return Decimal(clean)
        except: return Decimal(0)