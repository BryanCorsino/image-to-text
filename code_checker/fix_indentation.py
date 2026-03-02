# Read the file
with open('app.py', 'r', encoding='utf-8') as file:
    lines = file.readlines()

# Fix indentation around line 587 (adjust the range as needed)
start_line = 580
end_line = 590

print(f"Lines {start_line}-{end_line} before fix:")
for i in range(start_line-1, min(end_line, len(lines))):
    print(f"{i+1}: {repr(lines[i])}")

# Your fix here - manually edit the file
print("\nPlease manually check and fix indentation around line 587")
print("Make sure all lines have consistent indentation (4 spaces per level)")