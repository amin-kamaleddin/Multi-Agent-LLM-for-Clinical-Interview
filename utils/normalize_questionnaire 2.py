#!/usr/bin/env python3
import json
import re

def clean_text(text):
    """Clean and normalize question text"""
    # Remove reversed/corrupted text
    text = re.sub(r'etisbew no ot si tI', '', text)
    
    # Fix spacing issues
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Remove YES/NO markers embedded in text
    text = re.sub(r'\bNO YES\b', '', text)
    text = re.sub(r'\bYES NO\b', '', text)
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def parse_multi_part_question(text, base_id, module):
    """Parse multi-part questions into separate components"""
    questions = []
    
    # Clean up common instruction patterns first
    text = re.sub(r'IF NO, CODE NO TO \w+:', '', text)
    text = re.sub(r'IF YES ASK:', '', text)
    text = re.sub(r'➨.*$', '', text)  # Remove scoring instructions
    
    # Handle explicit a/b pattern questions
    if re.search(r'\ba\s+[A-Z]', text) and re.search(r'\bb\s+[A-Z]', text):
        # Split on letter patterns
        parts = re.split(r'\s+([ab])\s+', text)
        
        if len(parts) >= 5:  # intro + a + content + b + content
            a_text = parts[2].strip()
            b_text = parts[4].strip()
            
            questions.append({
                'id': f"{base_id}a",
                'module': module,
                'question_type': 'screening',
                'text': clean_text(a_text),
                'response_type': 'yes_no'
            })
            
            questions.append({
                'id': f"{base_id}b", 
                'module': module,
                'question_type': 'current_symptoms',
                'text': clean_text(b_text),
                'response_type': 'yes_no',
                'depends_on': f"{base_id}a_yes"
            })
    
    # Handle complex multi-item questions (like A3)
    elif 'Past 2 Weeks' in text and 'Past Episode' in text:
        # This is a complex episode comparison question
        questions.append({
            'id': base_id,
            'module': module,
            'question_type': 'episode_comparison',
            'text': clean_text(text),
            'response_type': 'episode_matrix',
            'note': 'Complex multi-symptom episode comparison requiring custom handling'
        })
    
    # Handle summary/scoring questions
    elif 'SUMMARY' in text.upper() or 'ARE' in text and 'CODED YES' in text:
        questions.append({
            'id': base_id,
            'module': module,
            'question_type': 'scoring_rule',
            'text': clean_text(text),
            'response_type': 'computed',
            'note': 'Scoring rule - computed based on other responses'
        })
    
    # If no clear pattern, return as single question
    if not questions:
        question_type = 'standard'
        if 'SUMMARY' in text.upper():
            question_type = 'scoring'
        elif len(text) > 500:  # Very long questions likely need special handling
            question_type = 'complex'
            
        questions.append({
            'id': base_id,
            'module': module,
            'question_type': question_type,
            'text': clean_text(text),
            'response_type': 'yes_no'
        })
    
    return questions

def extract_response_options(text):
    """Extract response options from question text"""
    # Look for multiple choice patterns
    if '☐' in text:
        options = re.findall(r'([^☐]+)☐', text)
        if options:
            return {
                'type': 'multiple_choice',
                'options': [opt.strip() for opt in options if opt.strip()]
            }
    
    # Look for rating scales
    if 'consecutive days' in text:
        return {
            'type': 'duration_scale',
            'options': [
                '3 consecutive days or less',
                '4, 5 or 6 consecutive days', 
                '7 consecutive days or more'
            ]
        }
    
    # Default to yes/no
    return {'type': 'yes_no'}

def normalize_questionnaire(input_file, output_file):
    """Normalize the questionnaire JSON file"""
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    normalized_questions = []
    
    for item in data:
        original_id = item.get('id', '')
        module = item.get('module', '')
        text = item.get('text', '')
        
        # Skip if missing essential data
        if not original_id or not text:
            continue
            
        # Parse multi-part questions
        questions = parse_multi_part_question(text, original_id, module)
        
        # Process each question
        for question in questions:
            # Extract response options
            response_info = extract_response_options(question['text'])
            question['response_type'] = response_info['type']
            
            if 'options' in response_info:
                question['response_options'] = response_info['options']
            
            # Add scoring info if present
            if 'Points' in text or 'SUMMARY' in text.upper():
                question['question_type'] = 'scoring'
            
            normalized_questions.append(question)
    
    # Write normalized data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(normalized_questions, f, indent=2, ensure_ascii=False)
    
    print(f"Normalized {len(data)} original questions into {len(normalized_questions)} questions")
    print(f"Output saved to: {output_file}")

if __name__ == "__main__":
    normalize_questionnaire(
        '/Users/jack/Desktop/mini-agenti-ai/mini_modules/mini_questionnaire.json',
        '/Users/jack/Desktop/mini-agenti-ai/mini_modules/mini_questionnaire_normalized.json'
    )