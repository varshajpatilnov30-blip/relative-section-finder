from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import re

with open("data/bns_sections.txt", "r", encoding="utf-8") as f:
    sections = [s.strip() for s in f.read().split("\n\n") if s.strip()]

model = SentenceTransformer("all-MiniLM-L6-v2")

texts = [re.sub(r"\s+", " ", section) for section in sections]

embeddings = model.encode(texts)

similarity_matrix = cosine_similarity(embeddings)

results = []

for i in range(len(sections)):
    for j in range(i + 1, len(sections)):
        score = similarity_matrix[i][j]

        if score >= 0.40:
            num1 = re.match(r"(\d+)", sections[i])
            num2 = re.match(r"(\d+)", sections[j])

            if num1 and num2:
                results.append(
                    (score, num1.group(1), num2.group(1))
                )

results.sort(reverse=True)

print("\nTOP 20 SEMANTICALLY SIMILAR BNS SECTIONS\n")

for score, sec1, sec2 in results[:20]:
    print(
        f"Section {sec1} <-> Section {sec2} | "
        f"Similarity: {score:.3f}"
    )