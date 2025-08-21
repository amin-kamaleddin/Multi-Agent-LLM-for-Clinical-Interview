import re
from typing import List, Dict

class PIIRedactor:
    def __init__(self):
        self.patterns = {
            'phone': r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'ssn': r'\b(?:\d{3}[-.\s]?\d{2}[-.\s]?\d{4})\b',
            'date': r'\b(?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.](?:19|20)?\d{2}\b',
            'address': r'\b\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct)\b',
            'name_patterns': r'\b(?:my name is|i am|i\'m|call me)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*?)(?:\s+and|\s*$|\s*[.!?])',
            'age_over_89': r'\b(?:i am|i\'m|age)\s*(?:is\s*)?(\d{2,3})\s*(?:years?\s*old)?\b',
        }

        self.medical_patterns = {
            'mrn': r'\b(?:MRN|medical record|patient id)[\s:#]*([A-Z0-9]{6,})\b',
            'medication': r'\b(?:taking|prescribed|medication|pills?)\s+([A-Z][a-z]+(?:\s+\d+\s*mg)?)\b',
        }

    def redact_pii(self, text: str) -> str:
        if not text:
            return text
        
        censored = text

        censored = re.sub(self.patterns['phone'], '[PHONE_REDACTED]', censored)
        censored = re.sub(self.patterns['email'], '[EMAIL_REDACTED]', censored)
        censored = re.sub(self.patterns['ssn'], '[SSN_REDACTED]', censored)
        censored = re.sub(self.patterns['date'], '[DATE_REDACTED]', censored)
        censored = re.sub(self.patterns['address'], '[ADDRESS_REDACTED]', censored)

        censored = re.sub(self.patterns['name_patterns'], 
                          lambda m: f"{m.group(0).split()[0]} [NAME_REDACTED]", censored, flags=re.IGNORECASE)
        
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