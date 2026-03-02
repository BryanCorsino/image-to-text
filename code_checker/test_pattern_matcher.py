from pattern_matcher import CodePatternMatcher

# Test with your actual OCR output
test_cases = [
    """SSS

ii



o> If numberr

x Ais a. == 0):

is

print C{' 4 numberr is evenn )

 loe!

ca,

print if Ooh numberr if odd")

 ||""",
    
    """number % 2 = = 0 Cft t Lnubcr k ic evn Ø Print ele Print Cf number Y 1 odd""",
    
    """if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd')"""
]

for i, test in enumerate(test_cases):
    print(f"\n{'='*60}")
    print(f"TEST CASE {i+1}")
    print(f"{'='*60}")
    print("INPUT:")
    print("-" * 40)
    print(test)
    print("-" * 40)
    print("\nPROCESSING...")
    result = CodePatternMatcher.process(test)
    print("\nOUTPUT:")
    print("-" * 40)
    print(result)
    print("-" * 40)
    
    # Expected output
    expected = """number = int(input("Enter a number: "))

if number % 2 == 0:
    print(f"{number} is even")
else:
    print(f"{number} is odd")"""
    
    if result.strip() == expected.strip():
        print("✅ MATCH: Output matches expected code!")
    else:
        print("⚠️  DIFFERENT: Output differs from expected")
    print(f"{'='*60}")

# Test a simple case
print("\n" + "="*60)
print("SIMPLE TEST")
print("="*60)
simple_text = "if number % 2 == 0: print even else print odd"
result = CodePatternMatcher.process(simple_text)
print(f"Input: {simple_text}")
print(f"Output: {result}")
print("="*60)