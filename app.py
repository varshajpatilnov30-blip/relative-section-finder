import csv
import html
import re
from datetime import datetime
from difflib import get_close_matches
from io import BytesIO
from pathlib import Path
import textwrap
from xml.sax.saxutils import escape

import streamlit as st
from legal_topics import concept_aliases, primary_sections

st.set_page_config(page_title="Relative Section Finder", page_icon="⚖️", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: radial-gradient(circle at top left, #edf6f7 0, #f4f7fb 38rem); }
    .block-container { max-width: 1120px; padding-top: 2rem; padding-bottom: 4rem; }
    .hero {
        background: linear-gradient(120deg, #102a43, #1f5a75 72%, #287271);
        color: white; padding: 2.4rem 2.6rem; border-radius: 24px;
        margin-bottom: 1.5rem; box-shadow: 0 18px 40px rgba(16, 42, 67, .18);
    }
    .hero-label { display: inline-block; color: #d8f3f0; background: rgba(255,255,255,.12);
        border: 1px solid rgba(255,255,255,.2); padding: .35rem .7rem; border-radius: 99px;
        font-size: .75rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .hero h1 { color: white; margin: .8rem 0 .45rem; font-size: 2.55rem; letter-spacing: -.03em; }
    .hero p { color: #e5edf5; margin: 0; font-size: 1.05rem; max-width: 42rem; line-height: 1.6; }
    div[data-testid="stTextInput"] input {
        background: #fff; border: 1px solid #cbd5e1; border-radius: 12px;
        padding: .7rem .85rem;
    }
    div[data-testid="stTextInput"] input:focus { border-color: #287271; box-shadow: 0 0 0 2px rgba(40,114,113,.15); }
    div[data-testid="stButton"] button {
        background: linear-gradient(100deg, #e76f51, #db6548); color: white;
        border: 0; border-radius: 12px; padding: .7rem 1.1rem; font-weight: 700;
        box-shadow: 0 7px 16px rgba(231,111,81,.22); transition: transform .15s ease, box-shadow .15s ease;
    }
    div[data-testid="stButton"] button:hover { background: #d45d40; color: white; transform: translateY(-1px); box-shadow: 0 10px 20px rgba(231,111,81,.28); }
    div[data-testid="stDownloadButton"] button {
        border: 1px solid #287271; color: #1f5a75; border-radius: 10px; font-weight: 650;
        background: #fff; padding: .55rem .9rem;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #fff; border: 1px solid #e2e8f0; border-radius: 18px;
        box-shadow: 0 8px 22px rgba(16,42,67,.06); padding: .45rem .65rem;
    }
    [data-testid="stMetric"] { background: #fff; border: 1px solid #e2e8f0;
        border-radius: 14px; padding: .8rem 1rem; box-shadow: 0 5px 15px rgba(16,42,67,.04); }
    .results-label { color: #287271; font-size: .78rem; font-weight: 800;
        letter-spacing: .12em; text-transform: uppercase; margin: 1.2rem 0 .5rem; }
    .comparison-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 1rem; align-items: start; margin: .5rem 0 1rem; }
    .comparison-section { min-width: 0; background: #fff; border: 1px solid #dbe4ec;
        border-radius: 14px; padding: 1rem; }
    .comparison-section h4 { margin: 0 0 .8rem; padding-bottom: .6rem;
        min-height: 2.3rem; border-bottom: 1px solid #e2e8f0; color: #173b57; }
    .comparison-section-text { color: #263746; font-size: .94rem; line-height: 1.75;
        overflow-wrap: anywhere; }
    @media (max-width: 720px) { .comparison-grid { grid-template-columns: 1fr; } }
    mark.shared-concept { background: #ffe59a; color: #553900; border-radius: 3px;
        padding: 0 .12rem; }
    mark.different-wording { background: #ffd1c6; color: #742f20; border-radius: 3px;
        padding: 0 .12rem; }
    [data-testid="stMarkdownContainer"] h3 { color: #173b57; letter-spacing: -.02em; }
    </style>
    <div class="hero">
      <div class="hero-label">BNS legal research helper</div>
      <h1>Relative Section Finder</h1>
      <p>Explore provisions that may be related by meaning and shared legal concepts.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

@st.cache_data
def get_search_sections():
    source = Path(__file__).parent / "data" / "bns_sections.txt"
    text = source.read_text(encoding="utf-8")
    text = "\n".join(
        line
        for line in text.splitlines()
        if "THE GAZETTE OF INDIA EXTRAORDINARY" not in line.upper()
        and not re.fullmatch(r"\s*[_\-—=]{5,}\s*", line)
    )
    # OCR sometimes attaches the printed page number to headings (for example,
    # ``266:3.(1)``); remove that prefix so the section number can be recognized.
    text = re.sub(r"(?m)^\d{1,4}:(?=\d{1,3}\.)", "", text)
    text = re.split(r"(?im)^\s*Kshitiz\s*$", text, maxsplit=1)[0]
    sections = re.split(r"(?m)(?=^\d{1,3}\.(?=\s|[A-Z(]))", text)
    return [
        (match.group(1), section.strip())
        for section in sections
        if (match := re.match(r"^(\d{1,3})\.(?=\s|[A-Z(])", section.strip()))
    ]


search_sections = get_search_sections()
section_numbers = sorted({number for number, _ in search_sections}, key=int)
expected_section_numbers = set(range(1, 359))
loaded_section_numbers = {int(number) for number in section_numbers}
missing_section_numbers = sorted(expected_section_numbers - loaded_section_numbers)

with st.expander(
    f"Section text coverage: {len(loaded_section_numbers)} of 358 sections found"
):
    coverage_col1, coverage_col2 = st.columns(2)
    coverage_col1.metric("Sections found", len(loaded_section_numbers))
    coverage_col2.metric("Not detected in text", len(missing_section_numbers))
    if missing_section_numbers:
        st.caption(
            "These section numbers were not recognized in the loaded text. "
            "Some may be affected by PDF/OCR formatting."
        )
        st.write(", ".join(map(str, missing_section_numbers)))
    else:
        st.success("All section numbers from 1 to 358 were recognized.")


def format_section_text(text):
    # Join PDF/OCR line wraps while keeping legal clause markers easy to scan.
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+(?=\([a-z]\)|\(\d+\))", "\n", text, flags=re.IGNORECASE)


st.markdown("### Search by topic")
topic_query = st.text_input(
    "Enter a word or phrase", placeholder="For example: theft or public servant"
)
if st.button("Search topic", key="search_topic_button"):
    if not topic_query.strip():
        st.warning("Enter a word or phrase to search for.")
    else:
        query = topic_query.strip().casefold()
        canonical_topic = next(
            (
                topic
                for topic, forms in concept_aliases.items()
                if query == topic.casefold()
                or query in {form.casefold() for form in forms}
            ),
            None,
        )
        search_terms = (
            concept_aliases[canonical_topic]
            if canonical_topic
            else [topic_query.strip()]
        )
        topic_patterns = [
            re.compile(
                r"(?<!\w)"
                + r"\s+".join(re.escape(word) for word in term.split())
                + r"(?!\w)",
                re.IGNORECASE,
            )
            for term in search_terms
        ]
        matches = [
            (number, text)
            for number, text in search_sections
            if any(
                pattern.search(" ".join(text.split()))
                for pattern in topic_patterns
            )
        ]
        corrected_term = None
        if not matches and len(query) >= 4:
            known_terms = {
                term.casefold(): topic
                for topic, forms in concept_aliases.items()
                for term in [topic, *forms]
            }
            suggestion = get_close_matches(
                query, list(known_terms), n=1, cutoff=0.72
            )
            if suggestion:
                corrected_term = suggestion[0]
                corrected_topic = known_terms[corrected_term]
                corrected_terms = concept_aliases[corrected_topic]
                corrected_patterns = [
                    re.compile(
                        r"(?<!\w)"
                        + r"\s+".join(re.escape(word) for word in term.split())
                        + r"(?!\w)",
                        re.IGNORECASE,
                    )
                    for term in corrected_terms
                ]
                corrected_matches = [
                    (number, text)
                    for number, text in search_sections
                    if any(
                        pattern.search(" ".join(text.split()))
                        for pattern in corrected_patterns
                    )
                ]
                if corrected_matches:
                    canonical_topic = corrected_topic
                    search_terms = corrected_terms
                    topic_patterns = corrected_patterns
                    matches = corrected_matches
                    st.info(
                        f"No exact matches for **{topic_query.strip()}**. "
                        f"Showing results for **{corrected_term}** instead."
                    )
        related_forms = [
            term for term in search_terms
            if term.casefold() not in {query, corrected_term}
        ]
        if related_forms:
            st.caption("Also checking common forms: " + ", ".join(related_forms))
        topic_main_sections = (
            primary_sections.get(canonical_topic)
            if canonical_topic
            else None
        )
        section_text_by_number = dict(search_sections)
        main_section = topic_main_sections[0] if topic_main_sections else None

        if main_section:
            main_number, main_title = main_section
            main_text = section_text_by_number.get(main_number)
            st.markdown(f"#### Main section for **{topic_query.strip()}**")
            if main_text:
                st.markdown(f"**Section {main_number} — {main_title}**")
                formatted = html.escape(format_section_text(main_text)).replace(
                    "\n", "<br>"
                )
                st.markdown(formatted, unsafe_allow_html=True)
            else:
                st.warning(f"Section {main_number} is not present in the loaded section text.")

        other_matches = [
            (number, text)
            for number, text in matches
            if not main_section or number != main_section[0]
        ]
        if other_matches:
            st.markdown("#### Other matching sections")
            st.caption(
                "These sections also contain the searched word or its common forms."
            )
        elif canonical_topic and topic_main_sections is None:
            st.info(
                "This is a broad topic with no single main section. The results below "
                "show sections where the word appears."
            )

        st.write(f"Found **{len(matches)}** sections containing the searched term.")
        if other_matches:
            for number, text in other_matches:
                with st.expander(f"Section {number}"):
                    formatted = html.escape(format_section_text(text)).replace(
                        "\n", "<br>"
                    )
                    st.markdown(formatted, unsafe_allow_html=True)
        elif not main_section:
            if matches:
                st.caption("No other sections matched this search.")
            else:
                st.info("No sections contain that word or phrase.")

st.markdown("### Find related provisions")
selected_section = st.selectbox(
    "Search from section number", ["All sections", *section_numbers]
)
section_number = "" if selected_section == "All sections" else selected_section
similarity_presets = {
    "More matches (0.50)": 0.50,
    "Balanced (0.70)": 0.70,
    "Strong matches (0.85)": 0.85,
}
selected_preset = st.radio(
    "Quick setting",
    list(similarity_presets),
    index=1,
    horizontal=True,
)
if st.session_state.get("_last_similarity_preset") != selected_preset:
    st.session_state["minimum_similarity"] = similarity_presets[selected_preset]
    st.session_state["_last_similarity_preset"] = selected_preset

minimum_similarity = st.slider(
    "Minimum similarity",
    min_value=0.40,
    max_value=0.95,
    step=0.05,
    help="Raise this for fewer, stronger matches; lower it to include more possible matches.",
    key="minimum_similarity",
)

st.markdown("### Compare two sections")
first_column, second_column = st.columns(2)
section_choices = ["Choose a section", *section_numbers]
with first_column:
    first_section = st.selectbox(
        "First section number", section_choices, key="first_section_choice"
    )
with second_column:
    second_section = st.selectbox(
        "Second section number", section_choices, key="second_section_choice"
    )


@st.cache_resource
def load_detector():
    # Importing loads the model and section embeddings once per Streamlit session.
    import combined_overlap

    return combined_overlap


def save_feedback(section1, section2, score, rating):
    feedback_file = Path(__file__).parent / "data" / "feedback.csv"
    new_file = not feedback_file.exists()
    with feedback_file.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["timestamp", "section_1", "section_2", "similarity", "rating"])
        writer.writerow(
            [datetime.now().astimezone().isoformat(timespec="seconds"), section1, section2, score, rating]
        )


def make_pdf_report(blocks, detector, title, include_full_text):
    """Build a simple, readable PDF using Python's standard library only."""
    source_text_by_number = {
        match.group(1): section
        for section in detector.sections
        if (match := re.match(r"^(\d{1,3})\.", section))
    }
    lines = [title, "Bharatiya Nyaya Sanhita, 2023 (Act No. 45 of 2023)",
             "Automated text comparison; review results independently.", ""]

    def add_paragraph(label, text, width=100):
        lines.extend(textwrap.wrap(f"{label}{text}", width=width, replace_whitespace=True,
                                   break_long_words=True, break_on_hyphens=False) or [label])

    for block in blocks:
        pair = re.search(r"^Section (\d+) <-> Section (\d+)$", block, re.MULTILINE)
        if not pair:
            continue
        first, second = pair.groups()
        score = re.search(r"^Similarity: ([0-9.]+)$", block, re.MULTILINE)
        concepts = re.search(r"^Shared concepts(?: / terms)?: (.*)$", block, re.MULTILINE)
        section1 = source_text_by_number.get(first, "")
        section2 = source_text_by_number.get(second, "")
        shared_phrases = detector.find_shared_phrases(section1, section2) if section1 and section2 else []
        distinct = detector.find_distinct_phrases(section1, section2) if section1 and section2 else ([], [])
        lines.extend([f"Sections {first} and {second}",
                      f"Similarity: {score.group(1) if score else 'N/A'}"])
        if concepts:
            add_paragraph("Shared concepts: ", concepts.group(1))
        if shared_phrases:
            add_paragraph("Shared phrases: ", "; ".join(shared_phrases))
        for number, phrases in ((first, distinct[0]), (second, distinct[1])):
            if phrases:
                add_paragraph(f"Wording specific to Section {number}: ", "; ".join(phrases))
        if include_full_text:
            for number, text in ((first, section1), (second, section2)):
                lines.extend([f"Section {number} text:"])
                for paragraph in format_section_text(text).splitlines():
                    lines.extend(textwrap.wrap(paragraph, width=100) or [""])
        lines.extend(["", "-" * 70, ""])

    page_lines = [lines[index:index + 54] for index in range(0, len(lines), 54)] or [[]]

    def pdf_string(value):
        value = value.encode("cp1252", errors="replace").decode("cp1252")
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects = {}
    page_ids = []
    next_id = 4
    for page_number, page in enumerate(page_lines, start=1):
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        page_ids.append(page_id)
        commands = ["BT", "/F1 9 Tf", "45 800 Td", "13 TL"]
        for index, line in enumerate(page):
            if page_number == 1 and index == 0:
                commands.extend(["/F1 18 Tf", "0 -4 Td", f"({pdf_string(line)}) Tj", "/F1 9 Tf", "0 -22 Td"])
            else:
                commands.extend([f"({pdf_string(line)}) Tj", "T*"])
        commands.extend(["ET", "BT", "/F1 8 Tf", "45 25 Td",
                         f"(Relative Section Finder | BNS 2023 | Page {page_number}) Tj", "ET"])
        stream = "\n".join(commands).encode("cp1252", errors="replace")
        objects[page_id] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>").encode()
        objects[content_id] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max(objects) + 1)
    for object_id in sorted(objects):
        offsets[object_id] = pdf.tell()
        pdf.write(f"{object_id} 0 obj\n".encode())
        pdf.write(objects[object_id] + b"\nendobj\n")
    xref_position = pdf.tell()
    pdf.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode())
    pdf.write(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF".encode())
    return pdf.getvalue()


def highlight_section_text(text, concepts, phrases, detector, different_phrases=()):
    formatted = format_section_text(text)
    highlights = {}
    for phrase in different_phrases:
        normalized = re.sub(r"\s+", " ", phrase).strip()
        if normalized:
            highlights[normalized.casefold()] = "different-wording"
    shared_terms = {
        variant
        for concept in concepts
        for variant in detector.concept_aliases.get(concept, [concept])
    }
    shared_terms.update(phrase for phrase in phrases if phrase)
    for term in shared_terms:
        highlights.setdefault(term.casefold(), "shared-concept")

    safe_text = html.escape(formatted, quote=False)
    safe_highlights = {
        html.escape(term, quote=False).casefold(): style
        for term, style in highlights.items()
    }
    terms = sorted(safe_highlights, key=len, reverse=True)
    if terms:
        pattern = re.compile(
            rf"(?<!\w)({'|'.join(re.escape(term) for term in terms)})(?!\w)",
            re.IGNORECASE,
        )
        safe_text = pattern.sub(
            lambda match: (
                f'<mark class="{safe_highlights[match.group(0).casefold()]}">'
                f'{match.group(0)}</mark>'
            ),
            safe_text,
        )

    return safe_text.replace("\n", "<br>")


def show_result_cards(blocks, detector, feedback_context):
    source_text_by_number = {
        match.group(1): section
        for section in detector.sections
        if (match := re.match(r"^(\d{1,3})\.", section))
    }

    for block in blocks:
        pair = re.search(r"^Section (\d+) <-> Section (\d+)$", block, re.MULTILINE)
        if not pair:
            continue

        score = re.search(r"^Similarity: ([0-9.]+)$", block, re.MULTILINE)
        concepts = re.search(
            r"^Shared concepts(?: / terms)?: (.*)$", block, re.MULTILINE
        )
        shared_concepts = (
            [
                concept.strip()
                for concept in concepts.group(1).split(",")
                if concept.strip() and concept.strip().lower() != "none detected"
            ]
            if concepts
            else []
        )
        texts = [
            (number, source_text_by_number[number])
            for number in pair.groups()
            if number in source_text_by_number
        ]
        shared_phrases = (
            detector.find_shared_phrases(texts[0][1], texts[1][1])
            if len(texts) > 1
            else []
        )
        distinct_phrases = (
            detector.find_distinct_phrases(texts[0][1], texts[1][1])
            if len(texts) > 1
            else ([], [])
        )

        with st.container(border=True):
            st.markdown(f"### Section {pair.group(1)} ↔ Section {pair.group(2)}")
            if score:
                st.caption(f"Similarity: {score.group(1)}")
            st.markdown(
                f"**Source:** Bharatiya Nyaya Sanhita, 2023 (Act No. 45 of 2023), "
                f"Sections {pair.group(1)} and {pair.group(2)}"
            )
            if concepts:
                st.write(f"**Shared concepts:** {concepts.group(1)}")
            if shared_phrases:
                st.write("**Shared phrases:** " + " · ".join(shared_phrases))
            else:
                st.caption("No exact shared phrases found.")

            st.markdown("**Wording that differs (highlighted below)**")
            st.caption("Coral = wording specific to that section · Yellow = shared terms")
            unique_left, unique_right = st.columns(2)
            for column, index, section_number in (
                (unique_left, 0, pair.group(1)),
                (unique_right, 1, pair.group(2)),
            ):
                with column:
                    st.caption(f"Wording specific to Section {section_number}")
                    if distinct_phrases[index]:
                        st.write(" · ".join(distinct_phrases[index]))
                    else:
                        st.write("No distinct phrase found.")

            section_panels = []
            for index, (section_number, section_text) in enumerate(texts):
                highlighted_text = highlight_section_text(
                    section_text,
                    shared_concepts,
                    shared_phrases,
                    detector,
                    distinct_phrases[index],
                )
                section_panels.append(
                    f'<section class="comparison-section">'
                    f'<h4>Section {section_number} text</h4>'
                    f'<div class="comparison-section-text">{highlighted_text}</div>'
                    f'</section>'
                )
            st.markdown(
                '<div class="comparison-grid">' + "".join(section_panels) + '</div>',
                unsafe_allow_html=True,
            )

            st.caption("Was this pair useful?")
            useful_column, not_useful_column, _ = st.columns([1, 1, 5])
            feedback_key = f"{feedback_context}_{pair.group(1)}_{pair.group(2)}"
            with useful_column:
                if st.button("👍 Useful", key=f"useful_{feedback_key}"):
                    save_feedback(
                        pair.group(1), pair.group(2),
                        score.group(1) if score else "", "useful"
                    )
                    st.success("Feedback saved.")
            with not_useful_column:
                if st.button("👎 Not useful", key=f"not_useful_{feedback_key}"):
                    save_feedback(
                        pair.group(1), pair.group(2),
                        score.group(1) if score else "", "not useful"
                    )
                    st.success("Feedback saved.")


if st.button("Compare sections", key="compare_sections_button"):
    st.session_state.pop("section_comparison_result", None)
    if first_section == "Choose a section" or second_section == "Choose a section":
        st.warning("Choose both section numbers from the dropdowns.")
    else:
        with st.spinner("Comparing the two sections…"):
            detector = load_detector()
            comparison = detector.compare_sections(
                first_section.strip(), second_section.strip()
            )

        if comparison.startswith("ERROR:"):
            st.error(comparison.removeprefix("ERROR: "))
        else:
            st.session_state["section_comparison_result"] = comparison

if st.session_state.get("section_comparison_result"):
    comparison = st.session_state["section_comparison_result"]
    detector = load_detector()
    pair = re.search(r"^Section (\d+) <-> Section (\d+)$", comparison, re.MULTILINE)
    st.markdown(
        '<div class="results-label">Section comparison</div>',
        unsafe_allow_html=True,
    )
    st.download_button(
        label="Download comparison PDF",
        data=make_pdf_report(
            [comparison], detector, "Section Comparison Report", include_full_text=True
        ),
        file_name=f"sections_{pair.group(1)}_{pair.group(2)}_comparison.pdf",
        mime="application/pdf",
        key="download_section_comparison",
    )
    show_result_cards([comparison], detector, "compare")


if st.button("⚖️  Find related provisions"):
    with st.spinner("Comparing BNS provisions…"):
        detector = load_detector()
        output = detector.run_detector(section_number, minimum_similarity)

    blocks = re.split(
        r"(?=^Section \d+ <-> Section \d+)", output, flags=re.MULTILINE
    )
    number = section_number.strip()
    if number:
        blocks = [
            block for block in blocks
            if re.search(
                rf"^Section {number} <-> Section \d+|^Section \d+ <-> Section {number}$",
                block,
                re.MULTILINE,
            )
        ]
    st.session_state["related_result_blocks"] = [
        block for block in blocks
        if re.search(r"^Section \d+ <-> Section \d+$", block, re.MULTILINE)
    ]
    st.session_state["related_search_label"] = (
        f"Section {number}" if number else "All sections"
    )
    st.session_state["related_similarity_threshold"] = minimum_similarity

if "related_result_blocks" in st.session_state:
    visible_blocks = st.session_state["related_result_blocks"]
    detector = load_detector()
    st.markdown(
        '<div class="results-label">Detector results</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Last search: {st.session_state['related_search_label']} · "
        f"minimum similarity {st.session_state['related_similarity_threshold']:.2f}"
    )
    st.metric("Matching pairs", len(visible_blocks))
    if visible_blocks:
        st.download_button(
            label="Download results as PDF",
            data=make_pdf_report(
                visible_blocks, detector, "Related Provisions Report", include_full_text=True
            ),
            file_name="related_provisions.pdf",
            mime="application/pdf",
            key="download_related_results",
        )
        show_result_cards(visible_blocks, detector, "related")
    else:
        st.info("No related results found.")
