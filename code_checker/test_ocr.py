import pytesseract
from PIL import Image
import cv2
import os

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def test_tesseract():
    print("Testing Tesseract OCR...")
    print(f"Version: {pytesseract.get_tesseract_version()}")
    
    # Test with a sample image if you have one
    test_image = "uploads/test_image.png"
    if os.path.exists(test_image):
        text = pytesseract.image_to_string(Image.open(test_image))
        print(f"\nExtracted text:\n{text}")
    else:
        print("\nNo test image found. Please upload an image through the web interface.")
        print("Tesseract is configured and ready to use!")

if __name__ == "__main__":
    test_tesseract()