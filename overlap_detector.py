import re

with open("data/bns_sections.txt", "r", encoding="utf-8") as f:
    sections = [s.strip() for s in f.read().split("\n\n") if s.strip()]

legal_concepts = [
    "theft",
    "robbery",
    "snatching",
    "cheating",
    "fraud",
    "property",
    "hurt",
    "death",
    "murder",
    "kidnapping",
    "abduction",
    "extortion",
    "forgery",
    "document",
    "electronic record",
    "public servant",
    "unlawful assembly",
    "rape",
    "miscarriage",
    "criminal breach of trust",
    "criminal intimidation",
    "wrongful confinement",
    "wrongful restraint",
    "trespass"
]

results = []

for i in range(len(sections)):
    for j in range(i + 1, len(sections)):

        text1 = sections[i].lower()
        text2 = sections[j].lower()

        common = []

        for concept in legal_concepts:
            if concept in text1 and concept in text2:
                common.append(concept)

        if len(common) >= 2:

            num1 = re.match(r"(\d+)", sections[i])
            num2 = re.match(r"(\d+)", sections[j])

            if num1 and num2:
                results.append(
                    (len(common), num1.group(1), num2.group(1), common)
                )

results.sort(reverse=True)

print("\nPOTENTIAL OVERLAPPING PROVISIONS\n")

for count, sec1, sec2, concepts in results[:20]:
    print(
        f"Section {sec1} <-> Section {sec2} | "
        f"Shared concepts: {', '.join(concepts)}"
    )