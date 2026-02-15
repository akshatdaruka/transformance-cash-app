import base64
import json
import re
from io import BytesIO
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

    def _extract_first_json(self, text: str):
        """
        Surgically extracts the first valid JSON object from a messy string
        by counting bracket balance.
        """
        try:
            # Find the first opening brace
            start = text.find('{')
            if start == -1: 
                return None
            
            # Start counting balance to find the matching closing brace
            balance = 0
            for i in range(start, len(text)):
                char = text[i]
                if char == '{':
                    balance += 1
                elif char == '}':
                    balance -= 1
                    # If balance is back to 0, we found the closing brace
                    if balance == 0:
                        json_str = text[start:i+1]
                        return json.loads(json_str)
            return None
        except Exception:
            return None

    def parse(self, file_path: str) -> RemittanceAdvice:
        print(f"DEBUG: Sending document to Local LLM ({self.model})...")
        
        # 1. Convert PDF to Image
        images = convert_from_path(file_path, first_page=1, last_page=1)
        if not images:
            raise ValueError("Could not convert PDF to image")
        
        base64_image = self._encode_image(images[0])

        # 2. Strict Prompt (Removed "Steps" to stop it from chatting)
        prompt = """
        You are a JSON converter. 
        Convert the image data into a JSON object.

        FOCUS:
        - German Payment Advice (Zahlungsavis)
        - "Rechnungsnummer" = Invoice Number (Column 2 usually)
        - "Referenz" = Internal Ref (Column 1 usually)
        - "Gesamtsumme" = Total Amount

        OUTPUT:
        - ONLY valid JSON. 
        - NO introductory text. 
        - NO "Steps".
        
        REQUIRED JSON FORMAT:
        {
            "sender_name": "string",
            "total_amount": 0.00,
            "currency": "EUR",
            "lines": [
                {
                    "internal_ref": "string",
                    "invoice_number": "string",
                    "date": "YYYY-MM-DD",
                    "net_amount": 0.00
                }
            ]
        }
        """

        try:
            # 3. Call Ollama
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ],
                    }
                ],
                temperature=0.0,
            )

            # 4. Cleaning Logic
            raw_content = response.choices[0].message.content.strip()
            print(f"DEBUG: Raw AI Response: {raw_content[:200]}...")

            # Use the surgical extraction function
            data = self._extract_first_json(raw_content)
            
            if not data:
                # Fallback: Try standard load if surgical failed (rare)
                start_index = raw_content.find('{')
                end_index = raw_content.rfind('}')
                if start_index != -1 and end_index != -1:
                    data = json.loads(raw_content[start_index : end_index + 1])
                else:
                    raise ValueError("Could not find JSON object in AI response")

            return self._convert_to_model(data)

        except Exception as e:
            print(f"❌ Local AI Error: {str(e)}")
            raise ValueError(f"AI Processing Failed: {str(e)}")

    def _convert_to_model(self, data: dict) -> RemittanceAdvice:
        lines = []
        for l in data.get("lines", []):
            try:
                # Robust Date Parsing
                d_str = l.get("date")
                try:
                    d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
                except:
                    try:
                        d_obj = datetime.strptime(d_str, "%d.%m.%Y").date()
                    except:
                        d_obj = date.today()

                lines.append(InvoiceLine(
                    internal_ref=l.get("internal_ref", "UNKNOWN"),
                    invoice_number=l.get("invoice_number", "UNKNOWN"),
                    date=d_obj,
                    gross_amount=Decimal(str(l.get("net_amount", 0))),
                    net_amount=Decimal(str(l.get("net_amount", 0)))
                ))
            except Exception as e:
                print(f"Skipping bad line: {e}")
                continue

        return RemittanceAdvice(
            sender_name=data.get("sender_name", "Unknown"),
            total_amount=Decimal(str(data.get("total_amount", 0))),
            lines=lines,
            currency=data.get("currency", "EUR")
        )