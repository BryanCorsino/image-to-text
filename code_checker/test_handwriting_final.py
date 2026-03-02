from handwriting_ocr import HandwritingOCR, fix_specific_pattern
import cv2
import os
import sys

# Force console to use ascii
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='ascii', errors='ignore')

def test_with_image(image_path):
    """Test handwriting OCR with an image"""
    print("=" * 50)
    print("TESTING HANDWRITING OCR")
    print("=" * 50)
    print(f"Image: {image_path}")
    print("-" * 50)
    
    if not os.path.exists(image_path):
        print("[ERROR] Image not found!")
        print(f"Path: {image_path}")
        return
    
    print("[OK] Image found")
    print("-" * 50)
    
    # Process with handwriting OCR
    print("Processing handwriting...")
    result = HandwritingOCR.process(image_path)
    
    print("\n[RAW EXTRACTED TEXT]")
    print("-" * 30)
    print(result)
    print("-" * 30)
    
    # Apply specific pattern fix
    fixed = fix_specific_pattern(result)
    
    print("\n[FINAL CORRECTED CODE]")
    print("-" * 30)
    print(fixed)
    print("-" * 30)
    
    # Expected output
    expected = """number = int(input("Enter a number: "))

if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
    
    print("\n[EXPECTED OUTPUT]")
    print("-" * 30)
    print(expected)
    print("-" * 30)
    
    if fixed.strip() == expected.strip():
        print("[SUCCESS] Code matches expected output!")
    else:
        print("[WARNING] Code differs from expected output")
    
    print("=" * 50)

if __name__ == "__main__":
    # Test with your image
    test_image = "uploads/b734cec7-9c7d-46e6-8ea9-fae1f69a0bde_20260301_201706.jpg"
    test_with_image(test_image)