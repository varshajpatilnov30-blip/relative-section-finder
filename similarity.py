import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

with open("data/bns_sections.txt", "r", encoding="utf-8") as f:
    sections = [s.strip() for s in f.read().split("\n\n") if s.strip()]

vectorizer = TfidfVectorizer(stop_words="english")
matrix = vectorizer.fit_transform(sections)
similarity = cosine_similarity(matrix)

pairs = []

for i in range(len(sections)):
    for j in range(i + 1, len(sections)):
        score = similarity[i][j]
        pairs.append((score, i, j))

pairs.sort(reverse=True)

print("\nTOP 10 SIMILAR BNS SECTIONS\n")

for score, i, j in pairs[:10]:
    num1 = re.match(r"(\d+)", sections[i])
    num2 = re.match(r"(\d+)", sections[j])

    section1 = num1.group(1) if num1 else "?"
    section2 = num2.group(1) if num2 else "?"

    print(
        f"Section {section1} <-> Section {section2} | "
        f"Similarity: {score:.3f}"
    )