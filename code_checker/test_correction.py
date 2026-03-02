from ocr_correction import clean_code

# Your problematic OCR output
bad_ocr = "if_Qinber % = 0: Cf { number k is even ' } ele: Print Print (f t & number & j=odd)"

# Expected correct code
correct_code = """if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""

print("Bad OCR:", bad_ocr)
print("\nCorrected:", clean_code(bad_ocr))
print("\nExpected:\n", correct_code)

# Test with your other image
another_bad = """if number % 2 == 0:
    print("C f" "d number is even")
else:
    print("f " "d number is odd")"""

print("\n" + "="*50)
print("Another test:")
print("Bad OCR:", another_bad)
print("\nCorrected:", clean_code(another_bad))