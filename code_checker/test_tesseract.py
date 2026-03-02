import pytesseract
from PIL import Image
import os

# Set Tesseract path explicitly
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

print("Testing Tesseract installation...")
print("-" * 40)

# Check version
try:
    version = pytesseract.get_tesseract_version()
    print(f"✅ Tesseract version: {version}")
except Exception as e:
    print(f"❌ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Is Tesseract installed? Check: C:\\Program Files\\Tesseract-OCR\\")
    print("2. Is the path correct in app.py?")
    print("3. Did you restart your terminal/command prompt?")
    exit()

# Check available languages
try:
    languages = pytesseract.get_languages()
    print(f"✅ Available languages: {languages}")
except:
    print("⚠️ Could not get languages list")

# Test with a simple image
print("\nCreating test image...")
from PIL import ImageDraw, ImageFont
import numpy as np

# Create a simple test image
img = Image.new('RGB', (400, 100), color='white')
draw = ImageDraw.Draw(img)
draw.text((10, 40), "if number % 2 == 0:", fill='black')
test_path = 'test_image.png'
img.save(test_path)

# Test OCR
print("Testing OCR on test image...")
try:
    text = pytesseract.image_to_string(Image.open(test_path))
    print(f"✅ OCR Result: {text.strip()}")
except Exception as e:
    print(f"❌ OCR failed: {e}")

# Cleanup
if os.path.exists(test_path):
    os.remove(test_path)

print("\n" + "=" * 40)
print("If you see version info above, Tesseract is working!")
print("Now restart your Flask app: python app.py")