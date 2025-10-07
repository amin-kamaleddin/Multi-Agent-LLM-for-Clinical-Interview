import re
from typing import List, Dict
import spacy

nlp = spacy.load("en_core_web_sm")

class PIIRedactor:
    def __init__(self):
        self.patterns = {
            'phone': r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'ssn': r'\b(?:\d{3}[-.\s]?\d{2}[-.\s]?\d{4})\b',
            'date': r'\b(?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.](?:19|20)?\d{2}\b',
            'address': r'\b\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct)\b',
            'age_over_89': r'\b(?:i am|i\'m|age)\s*(?:is\s*)?(\d{2,3})\s*(?:years?\s*old)?\b',
        }

        self.medical_patterns = {
            'mrn': r'\b(?:MRN|medical record|patient id)[\s:#]*([A-Z0-9]{6,})\b',
            'medication': r'\b(?:taking|prescribed|medication|pills?)\s+([A-Z][a-z]+(?:\s+\d+\s*mg)?)\b',
        }

    def redact_names_with_ner(self, text: str, token="[NAME_REDACTED]") -> str:
        doc = nlp(text)
        spans = [(ent.start_char, ent.end_char) for ent in doc.ents if ent.label_ == "PERSON"]
        if not spans:
            return text
        spans.sort()
        merged = []
        for s, e in spans:
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        out = list(text)
        for s, e in reversed(merged):
            out[s:e] = token
        return "".join(out)
        

    def redact_pii(self, text: str) -> str:
        if not text:
            return text
        
        censored = text

        censored = re.sub(self.patterns['phone'], '[PHONE_REDACTED]', censored)
        censored = re.sub(self.patterns['email'], '[EMAIL_REDACTED]', censored)
        censored = re.sub(self.patterns['ssn'], '[SSN_REDACTED]', censored)
        censored = re.sub(self.patterns['date'], '[DATE_REDACTED]', censored)
        censored = re.sub(self.patterns['address'], '[ADDRESS_REDACTED]', censored)

        censored = self.redact_names_with_ner(censored, token="[NAME_REDACTED]")
        
        def age_replacer(match):
            try:
                age = int(match.group(1))
                if age > 89:
                    return match.group(0).replace(str(age), '[AGE>89_REDACTED]')
                return match.group(0)
            except ValueError:
                return match.group(0)  # Return unchanged if not a valid number
        
        censored = re.sub(self.patterns['age_over_89'], age_replacer, censored, flags=re.IGNORECASE)

        for pattern_name, pattern in self.medical_patterns.items():
            censored = re.sub(pattern, f'[{pattern_name.upper()}_REDACTED]', censored, flags=re.IGNORECASE)

        return censored
    
# Global instance
pii_filter = PIIRedactor()

# Function to sanitize text before sending to LLM
def sanitize_for_llm(text: str) -> str:
    """Sanitize text before sending to LLM"""
    return pii_filter.redact_pii(text)

if __name__ == "__main__":
    # text = "I am going to the doctor tomorrow. I'm John Doe. My phone number is 123-456-7890. My email is john.doe@example.com. My SSN is 123-45-6789. My date of birth is 01/01/1990. My address is 123 Main St, Anytown, USA. I am 90 years old. I am taking 10mg of Xanax. My MRN is 1234567890."
    text = "i'm nghia"
    print(sanitize_for_llm(text))