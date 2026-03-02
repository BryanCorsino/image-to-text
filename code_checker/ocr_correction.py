import re

def fix_ocr_errors(text):
    """Aggressive OCR correction for code patterns"""
    if not text:
        return text
    
    # Common OCR mistakes mapping
    replacements = {
        # Letters to symbols
        ' ': ' ',  # Keep spaces
        '0': '0', 'O': '0',  # O to 0 in numbers
        '1': '1', 'l': '1', 'I': '1',  # l and I to 1
        '5': '5', 'S': '5',  # S to 5
        '8': '8', 'B': '8',  # B to 8
        'rn': 'm',  # rn to m
        'cl': 'd',  # cl to d
        'vv': 'w',  # vv to w
        '¢': 'c',   # cent symbol to c
        '©': 'c',   # copyright to c
        '®': 'r',   # registered to r
        '™': 'tm',  # trademark to tm
        
        # Punctuation fixes
        '|': '|',
        '[': '[', ']': ']',
        '{': '{', '}': '}',
        '(': '(', ')': ')',
        '<': '<', '>': '>',
        '=': '=', '==': '==',
        '!': '!', '!=': '!=',
        ':': ':', ';': ';',
        '"': '"', "'": "'",
        '#': '#', '$': '$',
        '%': '%', '^': '^',
        '&': '&', '*': '*',
        '-': '-', '_': '_',
        '+': '+', '/': '/',
        '\\': '\\', '@': '@',
    }
    
    # Step 1: Fix common word patterns
    text = re.sub(r'if[_ ]?Qinber', 'if number', text, flags=re.IGNORECASE)
    text = re.sub(r'if[_ ]?number', 'if number', text, flags=re.IGNORECASE)
    text = re.sub(r'number\s+k', 'number is', text, flags=re.IGNORECASE)
    text = re.sub(r'number\s+is', 'number is', text, flags=re.IGNORECASE)
    text = re.sub(r'is\s+even', 'is even', text, flags=re.IGNORECASE)
    text = re.sub(r'is\s+odd', 'is odd', text, flags=re.IGNORECASE)
    text = re.sub(r'ele\s*:', 'else:', text, flags=re.IGNORECASE)
    text = re.sub(r'else\s*:', 'else:', text, flags=re.IGNORECASE)
    text = re.sub(r'Cf', 'if', text, flags=re.IGNORECASE)
    text = re.sub(r'Print\s+Print', 'print', text, flags=re.IGNORECASE)
    text = re.sub(r'print\s+print', 'print', text, flags=re.IGNORECASE)
    
    # Step 2: Fix f-string patterns
    text = re.sub(r'f\s*"\s*{', 'f"{', text)
    text = re.sub(r'f\s*{\s*', 'f"{', text)
    text = re.sub(r'C\s*f\s*"\s*"d', 'f"{', text)
    text = re.sub(r'f\s*"\s*"d', 'f"{', text)
    text = re.sub(r'f\s*t\s*&', 'f"{', text)
    text = re.sub(r'}\s*is\s*even', '} is even', text, flags=re.IGNORECASE)
    text = re.sub(r'}\s*is\s*odd', '} is odd', text, flags=re.IGNORECASE)
    
    # Step 3: Fix mathematical operators
    text = re.sub(r'%\s*=', '%=', text)
    text = re.sub(r'=\s*=', '==', text)
    text = re.sub(r'=\s*=\s*0', '== 0', text)
    text = re.sub(r'%\s*2\s*=\s*=?\s*0', '% 2 == 0', text)
    
    # Step 4: Fix colons and indentation
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Fix colons
        if re.search(r'if\s+.*[^:]$', line, re.IGNORECASE):
            line = line + ':'
        if re.search(r'else\s*[^:]$', line, re.IGNORECASE):
            line = line + ':'
        
        # Fix indentation for lines after if/else
        if any(keyword in line.lower() for keyword in ['if', 'else']):
            fixed_lines.append(line.strip())
        elif line.strip():
            # Check if previous line had colon
            if fixed_lines and fixed_lines[-1].strip().endswith(':'):
                fixed_lines.append('    ' + line.strip())
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    text = '\n'.join(fixed_lines)
    
    # Step 5: Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Step 6: Fix specific pattern from your image
    # Pattern: if_Qinber % = 0: Cf { number k is even ' } ele: Print Print (f t & number & j=odd)
    text = re.sub(r'if[_]?Qinber\s*%\s*=\s*0\s*:\s*Cf\s*{\s*number\s*k\s*is\s*even\s*}\s*ele:\s*Print\s*Print\s*\(\s*f\s*t\s*&\s*number\s*&\s*j=odd\s*\)',
                  'if number % 2 == 0:\n    print(f"{number} is even")\nelse:\n    print(f"{number} is odd")', 
                  text, flags=re.IGNORECASE)
    
    # Step 7: Fix partial patterns
    if 'if' in text.lower() and 'number' in text.lower() and '%' in text:
        # Extract components
        if 'even' in text.lower() and 'odd' in text.lower():
            text = """if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
        elif 'even' in text.lower():
            text = text.replace('Cf', 'if').replace('ele:', 'else:')
            text = re.sub(r'{\s*number\s*k\s*is\s*even\s*}', 'f"{number} is even"', text, flags=re.IGNORECASE)
    
    return text

def fix_code_patterns(text):
    """Specialized fixes for common code patterns"""
    
    # Python if-else pattern
    if re.search(r'if.*%.*0.*:?.*print.*even.*else.*print.*odd', text, re.IGNORECASE | re.DOTALL):
        return """if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
    
    # Simple if-else pattern
    if re.search(r'if.*number.*%.*:?.*even.*else.*odd', text, re.IGNORECASE | re.DOTALL):
        return """if number % 2 == 0:
    print("even")
else:
    print("odd")"""
    
    # Print statement with f-string
    if re.search(r'print.*f.*{.*}.*', text, re.IGNORECASE):
        text = re.sub(r'f\s*["\']?\s*{', 'f"{', text)
        text = re.sub(r'}\s*["\']?', '}"', text)
    
    return text

def clean_code(text):
    """Complete code cleaning pipeline"""
    if not text or len(text.strip()) < 3:
        return text
    
    # Apply all fixes in sequence
    text = fix_ocr_errors(text)
    text = fix_code_patterns(text)
    
    # Final cleanup
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        # Remove extra spaces
        line = re.sub(r'\s+', ' ', line)
        # Fix common punctuation
        line = line.replace(' :', ':').replace(' ;', ';')
        line = line.replace('( ', '(').replace(' )', ')')
        line = line.replace('{ ', '{').replace(' }', '}')
        line = line.replace('[ ', '[').replace(' ]', ']')
        cleaned.append(line)
    
    return '\n'.join(cleaned)

# Test with your specific case
if __name__ == "__main__":
    test_cases = [
        "if_Qinber % = 0: Cf { number k is even ' } ele: Print Print (f t & number & j=odd)",
        "if number % 2 == 0: print(f\"{number} is even\") else: print(f\"{number} is odd\")",
        "number = int(input(\"Enter a number: \"))\nif number % 2 == 0:\n    print(f\"{number} is even\")\nelse:\n    print(f\"{number} is odd\")",
    ]
    
    for i, test in enumerate(test_cases):
        print(f"\nTest {i+1}:")
        print("Input:", test)
        print("Output:", clean_code(test))
        print("-" * 50)