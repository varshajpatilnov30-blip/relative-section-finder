import hashlib
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from legal_topics import concept_aliases


PROJECT_FOLDER = Path(__file__).parent
with open(PROJECT_FOLDER / "data" / "bns_sections.txt", "r", encoding="utf-8") as file:
    source_text = file.read()

# Remove repeated Gazette page headers and divider rules embedded by PDF extraction.
source_text = "\n".join(
    line
    for line in source_text.splitlines()
    if "THE GAZETTE OF INDIA EXTRAORDINARY" not in line.upper()
    and not re.fullmatch(r"\s*[_\-—=]{5,}\s*", line)
)
# The PDF ends with a digital-signature certificate. It is not part of Section 2;
# without removing it, its number (2.5.4.20) can be mistaken for a section heading.
source_text = re.split(r"(?im)^\s*Kshitiz\s*$", source_text, maxsplit=1)[0]

sections = [
    section.strip()
    for section in re.split(r"(?m)(?=^\d{1,3}\.(?=\s|[A-Z]))", source_text)
    if section.strip()
]

# The source file contains page-side headings after Section 205's final sentence.
for index, section in enumerate(sections):
    if re.match(r"^205\.", section):
        sections[index] = re.split(
            r"\nPublic servant\s+disobeying\s+direction\s+under\s+law\.",
            section,
            maxsplit=1,
        )[0].rstrip()

# Reuse the expensive semantic-similarity calculation across app restarts.
# If the BNS source text changes, its hash changes and the matrix is rebuilt.
MODEL_NAME = "all-MiniLM-L6-v2"
similarity_cache = PROJECT_FOLDER / "data" / "section_similarity.npz"
source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
similarity_matrix = None

if similarity_cache.exists():
    try:
        with np.load(similarity_cache, allow_pickle=False) as cached:
            if (
                str(cached["source_hash"]) == source_hash
                and str(cached["model_name"]) == MODEL_NAME
                and cached["similarity_matrix"].shape == (len(sections), len(sections))
            ):
                similarity_matrix = cached["similarity_matrix"]
    except (OSError, KeyError, ValueError):
        # A partial or outdated cache is safely rebuilt below.
        similarity_matrix = None

if similarity_matrix is None:
    from sentence_transformers import SentenceTransformer, util

    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(sections, convert_to_tensor=True, show_progress_bar=False)
    similarity_matrix = util.cos_sim(embeddings, embeddings).cpu().numpy()
    np.savez_compressed(
        similarity_cache,
        similarity_matrix=similarity_matrix,
        source_hash=np.array(source_hash),
        model_name=np.array(MODEL_NAME),
    )

COMMON_WORDS = {
    "about", "above", "after", "again", "against", "also", "although",
    "among", "any", "are", "because", "been", "before", "being", "below",
    "between", "both", "could", "does", "each", "every", "from", "further",
    "here", "herself", "himself", "however", "into", "itself", "more", "most",
    "other", "others", "over", "same", "shall", "should", "since", "some",
    "such", "than", "that", "their", "them", "then", "there", "these", "they",
    "this", "those", "through", "under", "until", "upon", "very", "were", "what",
    "when", "where", "which", "while", "who", "whom", "whose", "will", "with",
    "within", "without", "would", "your", "person", "persons", "whoever", "court",
    "section", "sanhita", "offender", "offenders", "case", "cases", "order", "orders",
}

# Repeated legal boilerplate that does not explain why two provisions are related.
GENERIC_SHARED_TERMS = {
    "described", "description", "intending", "liable", "manner", "particular",
    "possession", "purpose", "punishable", "punished", "security", "thereof",
    "therein", "used", "valuable", "offence", "offences", "offense", "offenses",
    "punishment", "punishments", "penalty", "penalties", "imprisonment",
    "sentence", "sentences", "sentenced", "fine", "fines",
}


def find_shared_concepts(text1, text2):
    first = text1.lower()
    second = text2.lower()
    return [
        concept
        for concept, variants in concept_aliases.items()
        if any(re.search(rf"\b{re.escape(variant)}\b", first) for variant in variants)
        and any(re.search(rf"\b{re.escape(variant)}\b", second) for variant in variants)
    ]


def find_shared_terms(text1, text2):
    first_words = re.findall(r"\b[a-z]{4,}\b", text1.lower())
    second_words = re.findall(r"\b[a-z]{4,}\b", text2.lower())
    known_variants = {
        word
        for variants in concept_aliases.values()
        for variant in variants
        for word in re.findall(r"\b[a-z]{4,}\b", variant)
    }
    first_set = set(first_words)
    second_set = set(second_words)
    common_terms = (
        (first_set & second_set)
        - COMMON_WORDS
        - GENERIC_SHARED_TERMS
        - known_variants
    )
    return sorted(
        common_terms,
        key=lambda word: (-min(first_words.count(word), second_words.count(word)), -len(word), word),
    )[:10]


def shared_items(text1, text2):
    concepts = find_shared_concepts(text1, text2)
    terms = find_shared_terms(text1, text2)
    return concepts + terms


def find_shared_phrases(text1, text2, limit=6):
    """Return exact multiword snippets that occur in both provision texts."""
    words1 = re.findall(r"[a-z]+", text1.lower())
    words2 = re.findall(r"[a-z]+", text2.lower())
    stop_words = COMMON_WORDS | {
        "whoever", "shall", "person", "persons", "offence", "offences",
        "punished", "imprisonment", "description", "term", "extend",
        "years", "year", "months", "month", "fine", "liable",
    }
    candidates = []
    for size in range(7, 1, -1):
        seen = set()
        phrases2 = {
            tuple(words2[start:start + size])
            for start in range(len(words2) - size + 1)
        }
        for start in range(len(words1) - size + 1):
            phrase = tuple(words1[start:start + size])
            if phrase in seen or phrase not in phrases2:
                continue
            seen.add(phrase)
            if sum(word not in stop_words for word in phrase) >= 2:
                candidates.append(phrase)

    selected = []
    for phrase in candidates:
        if any(
            any(phrase[i:i + len(existing)] == existing
                for i in range(len(phrase) - len(existing) + 1))
            for existing in selected
        ):
            continue
        selected.append(phrase)
        if len(selected) == limit:
            break

    return [" ".join(phrase) for phrase in selected]


def find_distinct_phrases(text1, text2, limit=4):
    """Return source-formatted unmatched wording snippets from each section."""
    tokens1 = list(re.finditer(r"[a-z]+", text1, re.IGNORECASE))
    tokens2 = list(re.finditer(r"[a-z]+", text2, re.IGNORECASE))
    words1 = [token.group(0).lower() for token in tokens1]
    words2 = [token.group(0).lower() for token in tokens2]
    matcher = SequenceMatcher(None, words1, words2, autojunk=False)
    stop_words = COMMON_WORDS | {
        "whoever", "shall", "person", "persons", "offence", "offences",
        "punished", "imprisonment", "description", "term", "extend",
        "years", "year", "months", "month", "fine", "liable",
    }
    unique1, unique2 = [], []
    for tag, start1, end1, start2, end2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        phrase1 = words1[start1:end1]
        phrase2 = words2[start2:end2]
        if len(phrase1) >= 3 and sum(word not in stop_words for word in phrase1) >= 2:
            unique1.append(text1[tokens1[start1].start():tokens1[end1 - 1].end()])
        if len(phrase2) >= 3 and sum(word not in stop_words for word in phrase2) >= 2:
            unique2.append(text2[tokens2[start2].start():tokens2[end2 - 1].end()])
    return unique1[:limit], unique2[:limit]


def compare_sections(section1, section2):
    section_numbers = [re.match(r"(\d{1,3})\.", section) for section in sections]
    first_index = next(
        (i for i, match in enumerate(section_numbers) if match and match.group(1) == section1),
        None,
    )
    second_index = next(
        (i for i, match in enumerate(section_numbers) if match and match.group(1) == section2),
        None,
    )

    if first_index is None:
        return f"ERROR: Section {section1} was not found in the data."
    if second_index is None:
        return f"ERROR: Section {section2} was not found in the data."
    if first_index == second_index:
        return "ERROR: Enter two different section numbers."

    first_number = section_numbers[first_index].group(1)
    second_number = section_numbers[second_index].group(1)
    score = float(similarity_matrix[first_index, second_index])
    concepts = shared_items(sections[first_index], sections[second_index])
    shared = ", ".join(concepts) if concepts else "none detected"

    return "\n".join(
        [
            f"Section {first_number} <-> Section {second_number}",
            f"Similarity: {score:.3f}",
            f"Shared concepts: {shared}",
            f"Section {first_number} text: {sections[first_index]}",
            f"Section {second_number} text: {sections[second_index]}",
        ]
    )


def run_detector(requested_section="", minimum_similarity=0.70):
    section_numbers = [re.match(r"(\d{1,3})\.", section) for section in sections]
    results = []

    if requested_section:
        target_index = next(
            (
                index
                for index, match in enumerate(section_numbers)
                if match and match.group(1) == requested_section
            ),
            None,
        )

        if target_index is None:
            return f"Section {requested_section} was not found in the data.\n"

        target_text = sections[target_index]
        target_number = section_numbers[target_index].group(1)

        for other_index, other_text in enumerate(sections):
            other_match = section_numbers[other_index]
            if other_index == target_index or other_match is None:
                continue

            score = float(similarity_matrix[target_index, other_index])
            common = shared_items(target_text, other_text)

            if score >= minimum_similarity:
                results.append(
                    (
                        score,
                        target_number,
                        other_match.group(1),
                        common,
                        target_text,
                        other_text,
                    )
                )

        results.sort(key=lambda row: row[0], reverse=True)
        results = results[:10]
        results.sort(key=lambda row: int(row[2]))
        heading = f"\nTOP RELATED PROVISIONS FOR SECTION {target_number}\n"
    else:
        candidate_pairs = np.argwhere(
            np.triu(similarity_matrix >= minimum_similarity, k=1)
        )
        for index, other_index in candidate_pairs:
            number1 = section_numbers[index]
            number2 = section_numbers[other_index]
            if number1 is None or number2 is None:
                continue

            common_concepts = find_shared_concepts(sections[index], sections[other_index])
            if len(common_concepts) < 2:
                continue

            score = float(similarity_matrix[index, other_index])
            common = shared_items(sections[index], sections[other_index])
            results.append(
                (
                    score,
                    number1.group(1),
                    number2.group(1),
                    common,
                    sections[index],
                    sections[other_index],
                )
            )

        results.sort(key=lambda row: row[0], reverse=True)
        results = results[:50]
        results.sort(key=lambda row: (int(row[1]), int(row[2])))
        heading = "\nPOTENTIALLY RELATED PROVISIONS\n"

    output = [heading]
    for score, section1, section2, concepts, text1, text2 in results:
        shared = ", ".join(concepts) if concepts else "none detected"
        output.extend(
            [
                f"\nSection {section1} <-> Section {section2}",
                f"Similarity: {score:.3f}",
                f"Shared concepts / terms: {shared}",
                f"Section {section1} text: {text1}",
                f"Section {section2} text: {text2}",
            ]
        )
    return "\n".join(output)


if __name__ == "__main__":
    requested_section = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    print(run_detector(requested_section))

