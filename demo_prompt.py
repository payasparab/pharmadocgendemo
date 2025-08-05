prompt = """AI-Prompt — IND Module 3: Section 3.2.P.1 Draft

Context
You are a regulatory-writing assistant drafting Section 3.2.P.1 “Description and Composition of the Drug Product” for an IND that is currently in Phase II clinical trials. All content must be suitable for direct inclusion in an eCTD‐compliant Module 3 dossier.

Product Information Provided Separately
• Product code: <PRODUCT_CODE>
• Dosage form: Immediate-release film-coated tablet
• Active strength(s) and qualitative/quantitative composition appear in the source data you have received.

Required Output Structure & Style

1. 3.2.P.1.1 Description of the Dosage Form

o  One concise paragraph that:
– Identifies the dosage form and strength(s)
– States the active‐ingredient concentration(s) clearly.
– Summarises the mechanism of action in one sentence.

o  Write in the third person, scientific style; do not use marketing language.

2. 3.2.P.1.2 Composition

o  Introductory sentence: “The qualitative and quantitative composition of the is provided in Table 1.”

o  Table 1 – ‘Composition of the ’

§ Columns (exact wording):

1. Component

2. Quality Reference

3. Function

4. Quantity / Unit (mg per tablet)

§ Populate all excipients and active ingredient(s) as rows using the supplied source data.

§ Add a Total Weight row.

§ Place a footnote directly beneath the table:
“Abbreviations: NF = National Formulary; Ph. Eur. = European Pharmacopoeia; USP = United States Pharmacopoeia.”

Formatting Instructions
• Use standard IND section numbering and bold headings exactly as shown.
• Table should render in Word/PDF without manual re-formatting (plain grid, no shading).
• Do not add any content outside Sections 3.2.P.1.1 and 3.2.P.1.2.

Quality Criteria
• All numeric values must match the source composition data.
• Spelling per US English; pharmacopoeia references capitalised.
• Ready for QC with minimal edits.

Please draft the section now, substituting the actual composition data in Table 1."""