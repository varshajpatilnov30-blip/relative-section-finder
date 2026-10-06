import re

input_file = "data/bns_text.txt"
output_file = "data/bns_sections.txt"

with open(input_file, "r", encoding="utf-8") as f:
    text = f.read()

sections = re.split(r"\n(?=\d+\.\s)", text)

with open(output_file, "w", encoding="utf-8") as f:
    for section in sections:
        section = section.strip()
        if section:
            f.write(section + "\n\n")

print("Sections extracted successfully.")
