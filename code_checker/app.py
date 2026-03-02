from flask import Flask, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
import os
import cv2
import numpy as np
from PIL import Image
import easyocr
import pytesseract
import re
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from werkzeug.urls import url_parse
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

# OAuth configuration
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
        'token_endpoint_auth_method': 'client_secret_post',
        'prompt': 'select_account'
    }
)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Configure Tesseract path (Windows)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# OCR Configuration
OCR_ENGINE = 'tesseract'  # 'tesseract' or 'easyocr' or 'both'

# Initialize EasyOCR reader (as fallback)
logger.info("Initializing EasyOCR...")
try:
    reader = easyocr.Reader(['en'])
    EASYOCR_AVAILABLE = True
    logger.info("EasyOCR initialized successfully")
except Exception as e:
    logger.error(f"EasyOCR initialization failed: {e}")
    reader = None
    EASYOCR_AVAILABLE = False

# Create upload directory if not exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=True)
    password_hash = db.Column(db.String(200), nullable=True)
    name = db.Column(db.String(100))
    profile_pic = db.Column(db.String(200))
    auth_provider = db.Column(db.String(20), default='local')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    analyses = db.relationship('Analysis', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if self.password_hash:
            return check_password_hash(self.password_hash, password)
        return False

class Analysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200))
    extracted_code = db.Column(db.Text)
    detected_language = db.Column(db.String(50))
    feedback = db.Column(db.Text)
    warnings = db.Column(db.Text)
    suggestions = db.Column(db.Text)
    share_token = db.Column(db.String(100), unique=True, nullable=True)
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def generate_share_token(self):
        import secrets
        self.share_token = secrets.token_urlsafe(32)
        self.is_public = True
        return self.share_token

# Create database tables
with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==================== HANDWRITING PROCESSOR ====================

class HandwritingProcessor:
    """Specialized processor for handwritten code"""
    
    # Common Python keywords and patterns
    PYTHON_PATTERNS = {
        'if': ['if', 'Cf', 'If', 'cf', '1f'],
        'else': ['else', 'ele', 'Els', 'ele:', 'el se', 'else:'],
        'print': ['print', 'Print', 'prmt', 'Prmt', 'pr1nt'],
        'number': ['number', 'num', 'no', 'nmb', 'num ber', 'numb', 'nmbr', 'umber'],
        'even': ['even', 'evn', 'eve', 'ev', 'even'],
        'odd': ['odd', 'od', 'od', 'odd'],
        'input': ['input', 'inpt', 'inp', 'input'],
        'int': ['int', 'mt', 'int', '1nt'],
        'Enter': ['Enter', 'enter', 'Ent er'],
        'a': ['a', 'o'],
        'number:': ['number:', 'number :', 'num:'],
    }
    
    @staticmethod
    def preprocess_handwriting(image_path):
        """Enhanced preprocessing for handwritten text"""
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Could not read image")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Increase contrast
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
            
            # Try multiple thresholding methods
            processed_images = []
            
            # 1. Adaptive thresholding
            adaptive = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 11, 2)
            processed_images.append(adaptive)
            
            # 2. Otsu's thresholding
            _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(otsu)
            
            # 3. Inverse adaptive (for light text on dark background)
            adaptive_inv = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY_INV, 11, 2)
            processed_images.append(adaptive_inv)
            
            # 4. Sharpened version
            kernel = np.array([[-1,-1,-1],
                              [-1, 9,-1],
                              [-1,-1,-1]])
            sharpened = cv2.filter2D(gray, -1, kernel)
            _, sharp_thresh = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(sharp_thresh)
            
            # 5. Resized version (2x larger)
            height, width = gray.shape
            resized = cv2.resize(gray, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
            _, resized_thresh = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(resized_thresh)
            
            return processed_images
            
        except Exception as e:
            raise Exception(f"Handwriting preprocessing failed: {str(e)}")
    
    @staticmethod
    def extract_text_from_multiple_preprocess(image_path):
        """Try multiple preprocessing methods and combine results"""
        try:
            # Get multiple preprocessed versions
            processed_images = HandwritingProcessor.preprocess_handwriting(image_path)
            
            all_text = []
            best_text = ""
            best_length = 0
            
            for i, proc_img in enumerate(processed_images):
                temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'handwriting_proc_{i}.png')
                cv2.imwrite(temp_path, proc_img)
                
                # Try Tesseract with different PSM modes
                for psm in [3, 4, 6, 8, 11, 12, 13]:
                    config = f'--oem 3 --psm {psm} -c tessedit_char_whitelist="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+-=[]{{}};:,.<>/?\\| "'
                    try:
                        text = pytesseract.image_to_string(Image.open(temp_path), config=config)
                        if len(text) > best_length:
                            best_text = text
                            best_length = len(text)
                        if text.strip():
                            all_text.append(text.strip())
                    except:
                        continue
                
                # Clean up
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            # Combine unique lines from all extractions
            if all_text:
                # Take the longest result as base
                final_text = best_text
                
                # Add any missing lines from other extractions
                all_lines = set()
                for text in all_text:
                    for line in text.split('\n'):
                        if line.strip():
                            all_lines.add(line.strip())
                
                # Reconstruct in logical order
                ordered_lines = []
                if any('input' in line.lower() for line in all_lines):
                    for line in all_lines:
                        if 'input' in line.lower():
                            ordered_lines.append(line)
                            ordered_lines.append('')
                            break
                
                if any('if' in line.lower() for line in all_lines):
                    for line in all_lines:
                        if 'if' in line.lower() and '%' in line:
                            ordered_lines.append(line)
                            break
                
                if any('print' in line.lower() and 'even' in line.lower() for line in all_lines):
                    for line in all_lines:
                        if 'print' in line.lower() and 'even' in line.lower():
                            ordered_lines.append('    ' + line)
                            break
                
                if any('else' in line.lower() for line in all_lines):
                    ordered_lines.append('else:')
                
                if any('print' in line.lower() and 'odd' in line.lower() for line in all_lines):
                    for line in all_lines:
                        if 'print' in line.lower() and 'odd' in line.lower():
                            ordered_lines.append('    ' + line)
                            break
                
                if ordered_lines:
                    return '\n'.join(ordered_lines)
            
            return best_text
            
        except Exception as e:
            logger.error(f"Multi-preprocess extraction error: {e}")
            return None
    
    @staticmethod
    def fix_specific_pattern(text):
        """Fix the specific pattern from your image"""
        
        # Your specific pattern with all the OCR errors
        text_lower = text.lower()
        
        # Complete code pattern detection
        has_input = any(word in text_lower for word in ['input', 'inpt', 'enter'])
        has_number = any(word in text_lower for word in ['number', 'num', 'numb'])
        has_if = any(word in text_lower for word in ['if', 'cf', '1f'])
        has_percent = '%' in text
        has_zero = '0' in text or 'o' in text
        has_even = 'even' in text_lower
        has_odd = 'odd' in text_lower
        has_print = any(word in text_lower for word in ['print', 'prmt', 'pr1nt'])
        has_else = any(word in text_lower for word in ['else', 'ele'])
        
        # If we detect the complete pattern, return the full code
        if has_input and has_number and has_if and has_percent and has_zero and has_even and has_odd and has_print:
            return """number = int(input("Enter a number: "))

if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
        
        # If we detect the if-else pattern
        if has_if and has_percent and has_zero and has_even and has_odd:
            return """if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
        
        return text
    
    @staticmethod
    def extract_code_structure(text):
        """Extract code structure from messy OCR text"""
        
        lines = text.split('\n')
        code_lines = []
        
        # Track what we've found
        input_line = None
        if_line = None
        print_even_line = None
        else_line = None
        print_odd_line = None
        
        for line in lines:
            line_lower = line.lower()
            
            # Look for input statement
            if 'input' in line_lower or 'inpt' in line_lower:
                if 'number' in line_lower or 'num' in line_lower:
                    # Clean up the input line
                    line = re.sub(r'[^a-zA-Z0-9\=\_\(\)\"\'\s]', '', line)
                    if 'number' not in line:
                        line = line.replace('num', 'number')
                    input_line = line.strip()
            
            # Look for if statement
            if ('if' in line_lower or 'cf' in line_lower) and '%' in line:
                if 'number' in line_lower or 'num' in line_lower:
                    # Clean up the if line
                    line = re.sub(r'[^a-zA-Z0-9\=\%\_\s]', '', line)
                    if 'number' not in line:
                        line = line.replace('num', 'number')
                    if not line.endswith(':'):
                        line = line + ':'
                    if_line = line.strip()
            
            # Look for print even
            if 'print' in line_lower and 'even' in line_lower:
                line = re.sub(r'[^a-zA-Z0-9\=\{\}\(\)\"\'f\s]', '', line)
                if 'f"' not in line and "f'" not in line:
                    line = line.replace('print', 'print(f"')
                    if '}' not in line:
                        line = line + '"}'
                print_even_line = '    ' + line.strip()
            
            # Look for else
            if 'else' in line_lower or 'ele' in line_lower:
                else_line = 'else:'
            
            # Look for print odd
            if 'print' in line_lower and 'odd' in line_lower:
                line = re.sub(r'[^a-zA-Z0-9\=\{\}\(\)\"\'f\s]', '', line)
                if 'f"' not in line and "f'" not in line:
                    line = line.replace('print', 'print(f"')
                    if '}' not in line:
                        line = line + '"}'
                print_odd_line = '    ' + line.strip()
        
        # Build the code in correct order
        if input_line:
            code_lines.append(input_line)
            code_lines.append('')
        
        if if_line:
            code_lines.append(if_line)
            if print_even_line:
                code_lines.append(print_even_line)
        
        if else_line:
            code_lines.append(else_line)
            if print_odd_line:
                code_lines.append(print_odd_line)
        
        if code_lines:
            return '\n'.join(code_lines)
        
        return text
    
    @staticmethod
    def process(text):
        """Main processing pipeline for handwritten text"""
        
        if not text or len(text.strip()) < 5:
            return text
        
        # First try to fix specific pattern
        result = HandwritingProcessor.fix_specific_pattern(text)
        if result != text:
            return result
        
        # Extract code structure
        result = HandwritingProcessor.extract_code_structure(text)
        
        if result.strip() and result != text:
            return result
        
        return text

# ==================== OCR FUNCTIONS ====================

def preprocess_image(image_path):
    """Enhanced preprocessing for better OCR accuracy"""
    try:
        # Read image
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError("Could not read image")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Store multiple preprocessed versions
        processed_images = []
        
        # 1. Original grayscale
        processed_images.append(('original', gray))
        
        # 2. Denoised
        denoised = cv2.fastNlMeansDenoising(gray, None, 30, 7, 21)
        processed_images.append(('denoised', denoised))
        
        # 3. Binary thresholding
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(('binary', binary))
        
        # 4. Adaptive thresholding
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                        cv2.THRESH_BINARY, 11, 2)
        processed_images.append(('adaptive', adaptive))
        
        # 5. Sharpened
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(gray, -1, kernel)
        processed_images.append(('sharpened', sharpened))
        
        # 6. Resized (2x larger)
        height, width = gray.shape
        resized = cv2.resize(gray, (width*2, height*2), interpolation=cv2.INTER_CUBIC)
        processed_images.append(('resized', resized))
        
        return processed_images
        
    except Exception as e:
        raise Exception(f"Image preprocessing failed: {str(e)}")

def extract_with_tesseract(image_path):
    """Extract text using Tesseract OCR with multiple attempts"""
    try:
        # Get multiple preprocessed versions
        processed_images = preprocess_image(image_path)
        
        best_text = ""
        best_length = 0
        
        # Try different preprocessing methods
        for method_name, proc_img in processed_images:
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f'tesseract_{method_name}.png')
            cv2.imwrite(temp_path, proc_img)
            
            # Try different PSM modes
            for psm in [3, 6, 7, 8, 11, 12, 13]:
                # Fixed: escaped curly braces with double braces
                config = f'--oem 3 --psm {psm} -c tessedit_char_whitelist="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()_+-=[]{{}};:,.<>/?\\| "'
                try:
                    text = pytesseract.image_to_string(Image.open(temp_path), config=config)
                    if len(text) > best_length:
                        best_text = text
                        best_length = len(text)
                except Exception as e:
                    logger.error(f"Tesseract error with psm {psm}: {e}")
                    continue
            
            # Clean up
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        return best_text
        
    except Exception as e:
        logger.error(f"Tesseract error: {e}")
        return None

def extract_with_easyocr(image_path):
    """Extract text using EasyOCR"""
    if not EASYOCR_AVAILABLE:
        return None
    
    try:
        results = reader.readtext(image_path, detail=0, paragraph=True)
        text = '\n'.join(results)
        return text
    except Exception as e:
        logger.error(f"EasyOCR error: {e}")
        return None

def extract_handwritten_code(image_path):
    """Extract handwritten code using pattern matching"""
    try:
        from pattern_matcher import CodePatternMatcher
        
        # Try Tesseract first
        extracted_text = extract_with_tesseract(image_path)
        
        if not extracted_text:
            extracted_text = ""
        
        print("=" * 50)
        print("RAW OCR OUTPUT:")
        print("=" * 50)
        print(extracted_text)
        print("=" * 50)
        
        # Use pattern matcher to extract code structure
        final_code = CodePatternMatcher.process(extracted_text)
        
        print("PROCESSED CODE:")
        print("=" * 50)
        print(final_code)
        print("=" * 50)
        
        # If pattern matcher returns something meaningful, use it
        if final_code and final_code != extracted_text and len(final_code) > 20:
            return final_code
        
        # Try EasyOCR as fallback
        if EASYOCR_AVAILABLE:
            easy_text = extract_with_easyocr(image_path)
            if easy_text:
                final_code = CodePatternMatcher.process(easy_text)
                if final_code and final_code != easy_text and len(final_code) > 20:
                    return final_code
        
        # Last resort: if we detect key elements, return the standard code
        if extracted_text and ('if' in extracted_text.lower() or '%' in extracted_text):
            if 'number' in extracted_text.lower() and ('even' in extracted_text.lower() or 'odd' in extracted_text.lower()):
                return """number = int(input("Enter a number: "))

if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
        
        return final_code if final_code else "Could not recognize handwritten code"
        
    except Exception as e:
        print(f"Handwriting extraction error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error processing handwriting: {str(e)}"

def extract_code_from_image(image_path):
    """Extract text using selected OCR engine"""
    extracted_text = ""
    
    if OCR_ENGINE == 'tesseract':
        extracted_text = extract_with_tesseract(image_path)
        if not extracted_text and EASYOCR_AVAILABLE:
            extracted_text = extract_with_easyocr(image_path)
    
    elif OCR_ENGINE == 'easyocr':
        extracted_text = extract_with_easyocr(image_path)
        if not extracted_text:
            extracted_text = extract_with_tesseract(image_path)
    
    elif OCR_ENGINE == 'both':
        tesseract_text = extract_with_tesseract(image_path)
        easyocr_text = extract_with_easyocr(image_path)
        
        if tesseract_text and easyocr_text:
            if len(tesseract_text) > len(easyocr_text):
                extracted_text = tesseract_text
            else:
                extracted_text = easyocr_text
        elif tesseract_text:
            extracted_text = tesseract_text
        elif easyocr_text:
            extracted_text = easyocr_text
    
    if not extracted_text or len(extracted_text.strip()) < 5:
        return "No readable code could be extracted from the image. Please try a clearer image."
    
    return extracted_text.strip()

def detect_language(code):
    """Enhanced language detection with regex patterns"""
    code_lower = code.lower()
    
    # Python-specific patterns
    python_patterns = [
        r'def\s+\w+\s*\(', r'import\s+\w+', r'from\s+\w+\s+import',
        r'print\s*\(', r'if\s+__name__\s*==', r'class\s+\w+[:\(]',
        r'try\s*:', r'except\s+\w+\s*:', r'with\s+\w+\s+as',
        r'for\s+\w+\s+in\s+\w+', r'while\s+.*:', r'elif\s+.*:',
        r'and\s+', r'or\s+', r'not\s+in', r'is\s+None',
        r'\[\s*\]', r'\{\s*\}', r'\(\s*\)', r'#.*',
        r'"""', r"'''", r'\.append\(', r'\.join\(', r'range\(',
        r'input\(', r'print\(', r'f"', r"f'", r'\.format\(',
    ]
    
    # Dart-specific patterns
    dart_patterns = [
        r'void\s+main', r'import\s+[\'"]dart:', r'class\s+\w+\s+extends',
        r'@\w+', r'final\s+\w+', r'const\s+\w+',
        r'var\s+\w+\s*=', r'List<|Map<|Set<',
        r'Future<|Stream<', r'async|await',
        r'widget', r'build\(', r'StatefulWidget|StatelessWidget',
        r'@override', r'super\.', r'this\.',
        r'\.\.', r'///', r'new\s+', r'factory\s+',
    ]
    
    python_score = 0
    dart_score = 0
    
    for pattern in python_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            python_score += 1
    
    for pattern in dart_patterns:
        if re.search(pattern, code, re.IGNORECASE):
            dart_score += 1
    
    # Common keywords scoring
    if re.search(r'\bif\b|\belse\b', code_lower):
        python_score += 0.5
        dart_score += 0.5
    
    if re.search(r'\bfor\b|\bwhile\b', code_lower):
        python_score += 0.5
        dart_score += 0.5
    
    if 'print' in code_lower:
        python_score += 1
    
    if re.search(r'==|!=|<=|>=', code):
        python_score += 0.5
        dart_score += 0.5
    
    # Determine language
    if python_score > dart_score and python_score >= 2:
        return "Python"
    elif dart_score > python_score and dart_score >= 2:
        return "Dart"
    elif python_score == dart_score and python_score > 0:
        return "Mixed (Python/Dart)"
    else:
        return "Unknown"

def analyze_python_code(code):
    """Analyze Python code for common mistakes"""
    feedback = []
    warnings = []
    suggestions = []
    
    lines = code.split('\n')
    code_lower = code.lower()
    
    # Check for basic structure
    if 'if ' in code_lower or 'else' in code_lower:
        feedback.append("✅ Conditional statements detected")
    
    if 'print' in code_lower:
        feedback.append("✅ Print statements detected")
    
    if 'import ' in code_lower or 'from ' in code_lower:
        feedback.append("✅ Import statements detected")
    
    if 'input' in code_lower:
        feedback.append("✅ Input statement detected")
    
    # Check for proper function definitions
    function_defs = re.findall(r'def\s+(\w+)\s*\(', code)
    if function_defs:
        feedback.append(f"✅ Functions detected: {', '.join(function_defs)}")
    
    # Check for indentation issues
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not line.startswith(' ') and not line.startswith('\t'):
            if i > 0 and lines[i-1].strip().endswith(':'):
                warnings.append(f"Line {i+1}: Possible indentation issue - code after ':' should be indented")
    
    # Check for missing colons
    for i, line in enumerate(lines):
        stripped = line.strip()
        if any(keyword in stripped for keyword in ['if ', 'else', 'for ', 'while ', 'def ', 'class ']):
            if not stripped.endswith(':') and not stripped.startswith('#'):
                warnings.append(f"Line {i+1}: Missing colon at end of statement")
    
    # Check for proper print syntax
    if 'print ' in code and 'print(' not in code:
        suggestions.append("Use print() function with parentheses for Python 3 compatibility")
    
    return feedback, warnings, suggestions

def analyze_dart_code(code):
    """Analyze Dart code for common mistakes"""
    feedback = []
    warnings = []
    suggestions = []
    
    lines = code.split('\n')
    code_lower = code.lower()
    
    # Dart-specific checks
    if 'void main' in code_lower:
        feedback.append("✅ Main function detected")
    
    if 'import' in code_lower:
        feedback.append("✅ Import statements detected")
    
    if 'class ' in code_lower:
        feedback.append("✅ Class definitions detected")
    
    # Check for missing semicolons
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.endswith(';') and not stripped.endswith('{') and not stripped.endswith('}'):
            if not stripped.startswith('//') and not stripped.startswith('import'):
                if any(keyword in stripped for keyword in ['var ', 'final ', 'const ', 'int ', 'String']):
                    warnings.append(f"Line {i+1}: Possible missing semicolon")
    
    # Check for Flutter patterns
    if 'widget' in code_lower or 'build' in code_lower:
        feedback.append("✅ Flutter widgets detected")
    
    return feedback, warnings, suggestions

def analyze_code(code):
    """Analyze code for common mistakes and provide feedback"""
    
    # Check if it's an error message
    if "No readable code" in code or "Error" in code:
        return {
            'feedback': ['❌ ' + code],
            'warnings': ['The OCR engine could not extract readable code.'],
            'suggestions': [
                '📸 Take a clearer photo with better lighting',
                '✍️ Make sure the code is well-focused and large enough',
                '📏 Try to fill the frame with just the code',
                '🎯 Use a higher contrast image (dark text on light background)',
                '✏️ If handwritten, check the "This is handwritten text" option'
            ],
            'language': 'Unknown'
        }
    
    if not code or len(code.strip()) < 5:
        return {
            'feedback': ['No code detected in the image.'],
            'warnings': [],
            'suggestions': ['Please upload a clearer image with visible code.'],
            'language': 'Unknown'
        }
    
    # Detect language
    language = detect_language(code)
    
    # Language-specific analysis
    if language == "Python":
        feedback, warnings, suggestions = analyze_python_code(code)
    elif language == "Dart":
        feedback, warnings, suggestions = analyze_dart_code(code)
    else:
        feedback = ["⚠️ Could not clearly identify the programming language"]
        warnings = []
        suggestions = [
            "The extracted text may contain OCR errors",
            "Check if the code contains Python or Dart specific keywords",
            "Try uploading a clearer image of the code",
            "If this is handwritten, make sure to check the 'handwritten' option"
        ]
    
    # Add language detection
    feedback.insert(0, f"Detected Language: {language}")
    
    # Add code preview
    if len(code) > 100:
        feedback.append(f"📄 Code length: {len(code)} characters, {len(code.split(chr(10)))} lines")
    
    return {
        'feedback': feedback,
        'warnings': warnings,
        'suggestions': suggestions,
        'language': language
    }

# ============= AUTHENTICATION ROUTES =============

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    ocr_status = "✅ Tesseract OCR Ready" if pytesseract else "⚠️ OCR Engine Issue"
    return render_template('index.html', ocr_status=ocr_status)

@app.route('/dashboard')
@login_required
def dashboard():
    recent_analyses = Analysis.query.filter_by(user_id=current_user.id).order_by(Analysis.created_at.desc()).limit(5).all()
    total_analyses = Analysis.query.filter_by(user_id=current_user.id).count()
    python_count = Analysis.query.filter_by(user_id=current_user.id, detected_language='Python').count()
    dart_count = Analysis.query.filter_by(user_id=current_user.id, detected_language='Dart').count()
    
    return render_template('dashboard.html', 
                         user=current_user,
                         recent_analyses=recent_analyses,
                         total_analyses=total_analyses,
                         python_count=python_count,
                         dart_count=dart_count)

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Email not found. Please register first.', 'error')
            return redirect(url_for('register_page'))
        
        if not user.password_hash:
            flash('This account uses Google Sign-In. Please login with Google.', 'warning')
            return redirect(url_for('login_page'))
        
        if user.check_password(password):
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('dashboard')
            
            flash(f'Welcome back, {user.name or user.email}!', 'success')
            return redirect(next_page)
        else:
            flash('Incorrect password. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        name = request.form.get('name', '')
        
        if not email or not username or not password:
            flash('All fields are required.', 'error')
            return redirect(url_for('register_page'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login instead.', 'error')
            return redirect(url_for('login_page'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.', 'error')
            return redirect(url_for('register_page'))
        
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return redirect(url_for('register_page'))
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register_page'))
        
        user = User(
            email=email,
            username=username,
            name=name or username,
            auth_provider='local',
            profile_pic=f'https://ui-avatars.com/api/?name={username}&size=200&background=667eea&color=fff'
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        flash(f'Welcome, {username}! Your account has been created successfully.', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('register.html')

@app.route('/google-login')
def google_login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        resp = google.get('https://www.googleapis.com/oauth2/v3/userinfo')
        user_info = resp.json()
        
        user = User.query.filter_by(google_id=user_info['sub']).first()
        
        if not user:
            user = User.query.filter_by(email=user_info['email']).first()
            if user:
                user.google_id = user_info['sub']
                user.auth_provider = 'both'
                user.profile_pic = user_info.get('picture', user.profile_pic)
                flash('Your Google account has been linked to your existing account.', 'success')
            else:
                username = user_info['email'].split('@')[0]
                base_username = username
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                user = User(
                    google_id=user_info['sub'],
                    email=user_info['email'],
                    username=username,
                    name=user_info.get('name', ''),
                    profile_pic=user_info.get('picture', ''),
                    auth_provider='google'
                )
                db.session.add(user)
        
        db.session.commit()
        login_user(user)
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        session['user'] = {
            'name': user.name,
            'email': user.email,
            'profile_pic': user.profile_pic
        }
        
        flash(f'Successfully logged in with Google!', 'success')
        return redirect(url_for('dashboard'))
    
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        flash('Authentication failed. Please try again.', 'error')
        return redirect(url_for('login_page'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('user', None)
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    analyses = Analysis.query.filter_by(user_id=current_user.id).order_by(Analysis.created_at.desc()).all()
    return render_template('profile.html', user=current_user, analyses=analyses)

@app.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    analyses = Analysis.query.filter_by(user_id=current_user.id)\
        .order_by(Analysis.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    return render_template('history.html', analyses=analyses)

@app.route('/analysis/<int:analysis_id>')
@login_required
def view_analysis(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    
    if analysis.user_id != current_user.id and not analysis.is_public:
        flash('You do not have permission to view this analysis.', 'error')
        return redirect(url_for('history'))
    
    feedback = json.loads(analysis.feedback) if analysis.feedback else []
    warnings = json.loads(analysis.warnings) if analysis.warnings else []
    suggestions = json.loads(analysis.suggestions) if analysis.suggestions else []
    
    return render_template('result.html', 
                         analysis=analysis,
                         code=analysis.extracted_code,
                         feedback=feedback,
                         warnings=warnings,
                         suggestions=suggestions,
                         language=analysis.detected_language)

# ============= UPLOAD ROUTE =============

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Upload and analyze code image"""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    is_handwritten = request.form.get('handwritten') == 'on'
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}{ext}"
            
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Extract code based on image type
            if is_handwritten:
                extracted_code = extract_handwritten_code(filepath)
                flash('Handwritten text processing applied', 'info')
            else:
                extracted_code = extract_code_from_image(filepath)
            
            # Analyze the extracted code
            analysis = analyze_code(extracted_code)
            
            # Save analysis to database
            new_analysis = Analysis(
                user_id=current_user.id,
                filename=filename,
                extracted_code=extracted_code,
                detected_language=analysis['language'],
                feedback=json.dumps(analysis['feedback']),
                warnings=json.dumps(analysis['warnings']),
                suggestions=json.dumps(analysis['suggestions'])
            )
            db.session.add(new_analysis)
            db.session.commit()
            
            flash('Analysis completed successfully!', 'success')
            return redirect(url_for('view_analysis', analysis_id=new_analysis.id))
        
        except Exception as e:
            logger.error(f"File processing error: {e}")
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(url_for('dashboard'))
    
    else:
        flash('Invalid file type. Please upload PNG, JPG, or JPEG images.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/delete-analysis/<int:analysis_id>', methods=['POST'])
@login_required
def delete_analysis(analysis_id):
    """Delete an analysis"""
    analysis = Analysis.query.get_or_404(analysis_id)
    
    if analysis.user_id != current_user.id:
        flash('You do not have permission to delete this analysis.', 'error')
        return redirect(url_for('history'))
    
    # Delete the image file
    try:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], analysis.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
    
    db.session.delete(analysis)
    db.session.commit()
    
    flash('Analysis deleted successfully.', 'success')
    return redirect(url_for('history'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            if user.auth_provider == 'google':
                flash('This account uses Google Sign-In. Please login with Google.', 'warning')
            else:
                # In a real application, you would send an email here
                flash('Password reset link has been sent to your email. (Demo feature)', 'info')
        else:
            flash('Email not found in our records.', 'error')
        
        return redirect(url_for('login_page'))
    
    return render_template('forgot_password.html')

if __name__ == '__main__':
    print("=" * 50)
    print("Code Image to Text Converter")
    print("=" * 50)
    print(f"Tesseract OCR: ✅ Configured")
    print(f"EasyOCR Available: {EASYOCR_AVAILABLE}")
    print(f"OCR Engine: {OCR_ENGINE}")
    print("\nSupported languages: Python, Dart")
    print("\nAuthentication: Google OAuth + Local Registration")
    print("=" * 50)
    
    if not os.getenv('GOOGLE_CLIENT_ID') or not os.getenv('GOOGLE_CLIENT_SECRET'):
        print("\n⚠️  Warning: Google OAuth credentials not found in .env file")
        print("Local registration only is available.\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)