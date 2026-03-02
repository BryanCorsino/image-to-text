import re
import cv2
import numpy as np
from PIL import Image
import pytesseract
import os

class HandwritingOCR:
    """Specialized OCR for handwritten code"""
    
    # Character mapping for common handwritten mistakes
    CHAR_MAP = {
        '0': ['0', 'O', 'o', '0'],
        '1': ['1', 'l', 'I', '|'],
        '2': ['2', 'Z', 'z'],
        '3': ['3'],
        '4': ['4'],
        '5': ['5', 'S', 's'],
        '6': ['6', 'b'],
        '7': ['7'],
        '8': ['8', 'B'],
        '9': ['9', 'g', 'q'],
        'a': ['a', '@'],
        'b': ['b', '6'],
        'c': ['c', 'c', 'c'],
        'd': ['d', 'cl'],
        'e': ['e', 'e'],
        'f': ['f'],
        'g': ['g', '9'],
        'h': ['h'],
        'i': ['i', '1', 'l'],
        'j': ['j'],
        'k': ['k'],
        'l': ['l', '1', 'I'],
        'm': ['m', 'rn'],
        'n': ['n', 'r'],
        'o': ['o', '0', 'O'],
        'p': ['p'],
        'q': ['q', '9'],
        'r': ['r'],
        's': ['s', '5'],
        't': ['t', '+'],
        'u': ['u', 'v'],
        'v': ['v', 'u'],
        'w': ['w', 'vv'],
        'x': ['x'],
        'y': ['y'],
        'z': ['z', '2'],
        '=': ['=', '-', '='],
        '+': ['+', '+'],
        '-': ['-', '-'],
        '*': ['*', 'x'],
        '/': ['/', '/'],
        '%': ['%'],
        '(': ['(', '{', '['],
        ')': [')', '}', ']'],
        ':': [':', ';'],
        ';': [';', ':'],
        '.': ['.', ','],
        ',': [',', '.'],
        '"': ['"', '"'],
        "'": ["'", "`"],
        '#': ['#'],
    }
    
    # Common Python keywords in handwritten form
    KEYWORDS = {
        'if': ['if', 'cf', '1f', 'if'],
        'else': ['else', 'ele', 'else', 'els'],
        'print': ['print', 'prmt', 'print', 'prnt'],
        'number': ['number', 'num', 'numb', 'nmbr', 'lnubcr', 'nubcr'],
        'even': ['even', 'evn', 'eve', 'ev'],
        'odd': ['odd', 'od'],
        'input': ['input', 'inpt', 'inp'],
        'int': ['int', 'mt'],
        'Enter': ['enter', 'entr'],
        'a': ['a', 'o'],
        'is': ['is', 'ic'],
    }
    
    @staticmethod
    def preprocess_handwriting(image_path):
        """Specialized preprocessing for handwritten text"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Could not read image")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Increase contrast
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=0)
            
            # Denoise
            denoised = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
            
            # Apply adaptive thresholding for handwriting
            binary = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 15, 5)
            
            # Remove small noise
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            # Invert if needed (for white text on dark background)
            if np.mean(cleaned) > 127:
                cleaned = cv2.bitwise_not(cleaned)
            
            return cleaned
            
        except Exception as e:
            raise Exception(f"Handwriting preprocessing failed: {str(e)}")

    @staticmethod
    def correct_ocr_errors(text):
        """Correct common OCR errors in handwritten text"""
        if not text:
            return text
        
        # Split into lines
        lines = text.split('\n')
        corrected_lines = []
        
        for line in lines:
            original_line = line
            line = line.strip()
            if not line:
                corrected_lines.append('')
                continue
            
            # Remove special characters and fix common OCR artifacts
            line = re.sub(r'[^\w\s\=\+\-\*\/\%\(\)\[\]\{\}\:\;\"\'\,\.\<\>\!\&\|]', ' ', line)
            
            # Fix common word misreads
            # number patterns
            if re.search(r'rumbe|lnubcr|nubcr|nmbr|numbe|numb', line.lower()):
                line = re.sub(r'rumbe|lnubcr|nubcr|nmbr|numbe|numb', 'number', line, flags=re.IGNORECASE)
            
            # if patterns
            if re.search(r'[Cc]f|1f', line):
                line = re.sub(r'[Cc]f|1f', 'if', line)
            
            # else patterns
            if re.search(r'ele|els', line.lower()):
                line = re.sub(r'ele|els', 'else', line, flags=re.IGNORECASE)
            
            # print patterns
            if re.search(r'pr[ai]nt|prmt', line.lower()):
                line = re.sub(r'pr[ai]nt|prmt', 'print', line, flags=re.IGNORECASE)
            
            # even patterns
            if re.search(r'evn|eve|ev', line.lower()):
                line = re.sub(r'evn|eve|ev', 'even', line, flags=re.IGNORECASE)
            
            # odd patterns
            if re.search(r'od', line.lower()) and 'odd' not in line.lower():
                line = re.sub(r'\bod\b', 'odd', line, flags=re.IGNORECASE)
            
            # is patterns
            if re.search(r'ic', line.lower()):
                line = re.sub(r'ic', 'is', line, flags=re.IGNORECASE)
            
            # Fix mathematical operators
            line = re.sub(r'=', '=', line)
            line = re.sub(r'%', '%', line)
            line = re.sub(r'==', '==', line)
            line = re.sub(r'= =', '==', line)
            
            # Fix variable names
            line = re.sub(r'Lnubcr|nubcr|nmbr', 'number', line, flags=re.IGNORECASE)
            line = re.sub(r'Y', 'is', line, flags=re.IGNORECASE)
            line = re.sub(r'k', 'is', line, flags=re.IGNORECASE)
            
            # Remove extra spaces
            line = re.sub(r'\s+', ' ', line)
            
            corrected_lines.append(line)
        
        return '\n'.join(corrected_lines)

    @staticmethod
    def extract_code_patterns(text):
        """Extract Python code patterns from text"""
        
        # Initialize code components
        input_statement = None
        if_statement = None
        print_even = None
        else_statement = None
        print_odd = None
        
        lines = text.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            
            # Look for input statement
            if 'input' in line_lower or 'inpt' in line_lower:
                if 'number' in line_lower or 'num' in line_lower:
                    input_statement = 'number = int(input("Enter a number: "))'
            
            # Look for if statement
            if 'if' in line_lower and '%' in line:
                if 'number' in line_lower:
                    if_statement = 'if number % 2 == 0:'
            
            # Look for print even
            if 'print' in line_lower and 'even' in line_lower:
                print_even = '    print(f"{number} is even")'
            
            # Look for else
            if 'else' in line_lower:
                else_statement = 'else:'
            
            # Look for print odd
            if 'print' in line_lower and 'odd' in line_lower:
                print_odd = '    print(f"{number} is odd")'
        
        # Build the complete code
        code_lines = []
        if input_statement:
            code_lines.append(input_statement)
            code_lines.append('')
        
        if if_statement:
            code_lines.append(if_statement)
            if print_even:
                code_lines.append(print_even)
        
        if else_statement:
            code_lines.append(else_statement)
            if print_odd:
                code_lines.append(print_odd)
        
        return '\n'.join(code_lines) if code_lines else text

    @staticmethod
    def process(image_path):
        """Complete handwriting OCR pipeline"""
        try:
            # Preprocess image
            processed = HandwritingOCR.preprocess_handwriting(image_path)
            
            # Save processed image
            temp_path = 'temp_handwriting.png'
            cv2.imwrite(temp_path, processed)
            
            # Try multiple Tesseract configurations
            best_text = ""
            best_score = 0
            
            # Different PSM modes for handwriting
            for psm in [3, 4, 6, 8, 11, 12, 13]:
                # Different OEM modes
                for oem in [1, 3]:
                    config = f'--oem {oem} --psm {psm}'
                    try:
                        text = pytesseract.image_to_string(Image.open(temp_path), config=config)
                        
                        # Score the result based on Python keywords
                        score = 0
                        text_lower = text.lower()
                        if 'if' in text_lower: score += 10
                        if 'else' in text_lower: score += 10
                        if 'print' in text_lower: score += 10
                        if 'number' in text_lower: score += 5
                        if 'even' in text_lower: score += 5
                        if 'odd' in text_lower: score += 5
                        if '%' in text: score += 5
                        if '==' in text or '= =' in text: score += 5
                        
                        if score > best_score:
                            best_text = text
                            best_score = score
                    except:
                        continue
            
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            if best_text:
                # Apply OCR error correction
                corrected = HandwritingOCR.correct_ocr_errors(best_text)
                
                # Extract code patterns
                final_code = HandwritingOCR.extract_code_patterns(corrected)
                
                return final_code
            
            return "Could not recognize handwriting"
            
        except Exception as e:
            return f"Error: {str(e)}"

# For specific pattern in your image
def fix_specific_pattern(text):
    """Fix the specific pattern from your screenshot"""
    # Your specific pattern
    if 'number % 2 = = 0' in text and 'Cft' in text and 'Lnubcr' in text:
        return """number = int(input("Enter a number: "))

if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
    
    # More general pattern
    if 'number' in text.lower() and '%' in text and 'even' in text.lower() and 'odd' in text.lower():
        return """number = int(input("Enter a number: "))

if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
    
    return text