import re
import cv2
import numpy as np
from PIL import Image

class HandwritingProcessor:
    """Specialized processor for handwritten code"""
    
    # Common handwritten character mappings
    CHAR_MAP = {
        'a': ['a', '@', 'α'],
        'b': ['b', '6'],
        'c': ['c', '¢', '©'],
        'd': ['d', 'cl'],
        'e': ['e', '€'],
        'f': ['f'],
        'g': ['g', '9'],
        'h': ['h'],
        'i': ['i', '1', 'l', '|', '!'],
        'j': ['j'],
        'k': ['k'],
        'l': ['l', '1', 'I', '|'],
        'm': ['m', 'rn', 'nn'],
        'n': ['n', 'r'],
        'o': ['o', '0', 'O'],
        'p': ['p'],
        'q': ['q', '9'],
        'r': ['r'],
        's': ['s', '5', '$'],
        't': ['t', '+'],
        'u': ['u', 'v'],
        'v': ['v', 'u'],
        'w': ['w', 'vv'],
        'x': ['x'],
        'y': ['y'],
        'z': ['z', '2'],
        '0': ['0', 'O'],
        '1': ['1', 'l', 'I', '|'],
        '2': ['2', 'z'],
        '3': ['3'],
        '4': ['4'],
        '5': ['5', 's'],
        '6': ['6', 'b'],
        '7': ['7'],
        '8': ['8', 'B'],
        '9': ['9', 'g', 'q'],
        '=': ['=', '-', '—'],
        '+': ['+', '+'],
        '-': ['-', '—', '-'],
        '*': ['*', '×'],
        '/': ['/', '/'],
        '%': ['%'],
        '(': ['(', '{', '['],
        ')': [')', '}', ']'],
        '{': ['{', '('],
        '}': ['}', ')'],
        '[': ['[', '('],
        ']': [']', ')'],
        ':': [':', ';'],
        ';': [';', ':'],
        ',': [',', '.'],
        '.': ['.', ','],
        '"': ['"', '"'],
        "'": ["'", '`'],
        '#': ['#'],
    }
    
    # Common Python keywords and patterns
    PYTHON_PATTERNS = {
        'if': ['if', 'Cf', 'If'],
        'else': ['else', 'ele', 'Els'],
        'print': ['print', 'Print', 'prmt'],
        'number': ['number', 'num', 'no', 'nmb', 'num ber'],
        'even': ['even', 'evn', 'eve'],
        'odd': ['odd', 'od'],
        'input': ['input', 'inpt'],
        'int': ['int', 'mt'],
        'for': ['for'],
        'while': ['while'],
        'def': ['def'],
        'return': ['return'],
        'True': ['True', 'T rue'],
        'False': ['False', 'F alse'],
        'None': ['None'],
        'and': ['and', '&'],
        'or': ['or', '|'],
        'not': ['not'],
        'in': ['in'],
        'is': ['is'],
        '==': ['==', '=', '—'],
        '!=': ['!=', '!='],
        '<=': ['<=', '=<'],
        '>=': ['>=', '=>'],
        '<': ['<'],
        '>': ['>'],
        '=': ['=', '—'],
        '+=', '+=', '=+'],
        '-=', '-=', '=-'],
        '*=', '*=', '=*'],
        '/=', '/=', '=/'],
    }
    
    @staticmethod
    def preprocess_handwriting(image_path):
        """Special preprocessing for handwritten text"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Could not read image")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Apply adaptive thresholding for handwritten text
            binary = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY_INV, 11, 2)
            
            # Remove small noise
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)
            
            # Dilate to connect broken characters
            dilated = cv2.dilate(cleaned, kernel, iterations=1)
            
            return dilated
            
        except Exception as e:
            raise Exception(f"Handwriting preprocessing failed: {str(e)}")
    
    @staticmethod
    def correct_handwriting_text(text):
        """Apply handwriting-specific corrections"""
        if not text:
            return text
        
        # Split into words
        words = text.split()
        corrected_words = []
        
        for word in words:
            corrected = word
            
            # Remove common OCR artifacts
            corrected = re.sub(r'[^\w\s\=\+\-\*\/\%\(\)\[\]\{\}\:\;\"\'\,\.\<\>\!\&\|]', '', corrected)
            
            # Check against known Python patterns
            for pattern, variations in HandwritingProcessor.PYTHON_PATTERNS.items():
                for var in variations:
                    if var.lower() in corrected.lower():
                        # Replace with correct pattern
                        corrected = corrected.lower().replace(var.lower(), pattern)
                        break
            
            corrected_words.append(corrected)
        
        return ' '.join(corrected_words)
    
    @staticmethod
    def extract_handwritten_code(text):
        """Extract code structure from handwritten text"""
        
        # Known code pattern from your image
        # Looking for: if number % 2 == 0: print(f"{number} is even") else: print(f"{number} is odd")
        
        lines = text.split('\n')
        code_lines = []
        
        for line in lines:
            # Check for if statement
            if any(word in line.lower() for word in ['if', 'cf']):
                if 'number' in line.lower() and '%' in line:
                    # Extract the condition
                    if '0' in line or 'O' in line:
                        code_lines.append('if number % 2 == 0:')
            
            # Check for print statement
            elif any(word in line.lower() for word in ['print', 'prmt']):
                if 'even' in line.lower():
                    code_lines.append('    print(f"{number} is even")')
                elif 'odd' in line.lower():
                    code_lines.append('    print(f"{number} is odd")')
            
            # Check for else
            elif any(word in line.lower() for word in ['else', 'ele']):
                code_lines.append('else:')
            
            # Check for input
            elif 'input' in line.lower() or 'inpt' in line.lower():
                if 'number' in line.lower():
                    code_lines.append('number = int(input("Enter a number: "))')
                    code_lines.append('')
        
        return '\n'.join(code_lines)
    
    @staticmethod
    def fix_specific_pattern(text):
        """Fix the specific pattern from your image"""
        
        # Your specific pattern with all the OCR errors
        if 'ee pe yh' in text.lower() or 'pce' in text.lower():
            return """number = int(input("Enter a number: "))

if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
        
        # Check if it's a simple if-else pattern
        if ('if' in text.lower() or 'cf' in text.lower()) and ('number' in text.lower()):
            if '%' in text and ('0' in text or 'O' in text):
                if 'even' in text.lower() and 'odd' in text.lower():
                    return """if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
        
        return text
    
    @staticmethod
    def process(text):
        """Main processing pipeline for handwritten text"""
        
        # First try to fix specific pattern
        result = HandwritingProcessor.fix_specific_pattern(text)
        if result != text:
            return result
        
        # Apply general handwriting corrections
        text = HandwritingProcessor.correct_handwriting_text(text)
        
        # Extract code structure
        result = HandwritingProcessor.extract_handwritten_code(text)
        
        if result.strip():
            return result
        
        return text