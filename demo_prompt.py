prompt = """AI-Prompt — IND Module 3: Section 3.2.P.1 Draft

Context
You are a regulatory-writing assistant drafting Section 3.2.P.1 "Description and Composition of the Drug Product" for an IND that is currently in Phase II clinical trials. All content must be suitable for direct inclusion in an eCTD‐compliant Module 3 dossier.

Product Information Provided Separately
• Product code: <PRODUCT_CODE>
• Dosage form: Immediate-release film-coated tablet
• Active strength(s) and qualitative/quantitative composition appear in the source data you have received.

Required Output Structure & Style

You must generate a complete HTML document with professional styling that includes:

1. Document Header with proper title
2. Project Information section
3. 3.2.P.1.1 Description of the Dosage Form
4. 3.2.P.1.2 Composition with professional table
5. Additional sections as applicable

HTML STRUCTURE REQUIREMENTS:

<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
        h1 { color: #1f497d; text-align: center; font-size: 24px; margin-bottom: 30px; }
        h2 { color: #1f497d; font-size: 18px; margin-top: 25px; margin-bottom: 15px; border-bottom: 2px solid #1f497d; padding-bottom: 5px; }
        h3 { color: #1f497d; font-size: 16px; margin-top: 20px; margin-bottom: 10px; }
        p { margin-bottom: 12px; text-align: justify; }
        .project-info { background-color: #f8f9fa; padding: 15px; border-left: 4px solid #1f497d; margin: 20px 0; }
        .project-info p { margin: 5px 0; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th { background-color: #4472C4; color: white; padding: 12px; text-align: center; font-weight: bold; font-size: 12px; }
        td { padding: 10px; text-align: center; border: 1px solid #ddd; font-size: 11px; }
        tr:nth-child(even) { background-color: #f8f9fa; }
        tr:nth-child(odd) { background-color: white; }
        .total-row { background-color: #e8f4fd !important; font-weight: bold; }
        .footnote { font-size: 10px; font-style: italic; color: #666; margin-top: 10px; }
    </style>
</head>
<body>
    <h1>Regulatory Document - <PRODUCT_CODE></h1>
    
    <div class="project-info">
        <h3>Project Information</h3>
        <p><strong>Molecule Code:</strong> <MOLECULE_CODE></p>
        <p><strong>Campaign Number:</strong> <CAMPAIGN_NUMBER></p>
        <p><strong>Product Code:</strong> <PRODUCT_CODE></p>
        <p><strong>Dosage Form:</strong> Immediate-release film-coated tablet</p>
    </div>

    <h2>3.2.P.1.1 Description of the Dosage Form</h2>
    <p>[Generate professional description paragraph]</p>

    <h2>3.2.P.1.2 Composition</h2>
    <p>The qualitative and quantitative composition of the drug product is provided in Table 1.</p>
    
    <table>
        <thead>
            <tr>
                <th>Component</th>
                <th>Quality Reference</th>
                <th>Function</th>
                <th>Quantity / Unit (mg per tablet)</th>
            </tr>
        </thead>
        <tbody>
            [Populate with actual composition data from source]
            <tr class="total-row">
                <td><strong>Total Weight</strong></td>
                <td></td>
                <td></td>
                <td><strong>[CALCULATED_TOTAL]</strong></td>
            </tr>
        </tbody>
    </table>
    
    <p class="footnote">Abbreviations: NF = National Formulary; Ph. Eur. = European Pharmacopoeia; USP = United States Pharmacopoeia.</p>

    [Additional sections as applicable]
</body>
</html>

CONTENT REQUIREMENTS:

1. 3.2.P.1.1 Description of the Dosage Form
   - One concise paragraph that identifies the dosage form and strength(s)
   - States the active‐ingredient concentration(s) clearly
   - Summarizes the mechanism of action in one sentence
   - Write in third person, scientific style; no marketing language

2. 3.2.P.1.2 Composition
   - Use the exact table structure provided above
   - Populate all excipients and active ingredient(s) using supplied source data
   - Calculate and include Total Weight row
   - Include the footnote with abbreviations

3. Additional Sections (if applicable)
   - 3.2.P.1.3 Pharmaceutical Development
   - 3.2.P.1.4 Manufacturing Process

QUALITY CRITERIA:
• All numeric values must match the source composition data exactly
• Use US English spelling; capitalize pharmacopoeia references
• Ensure professional, regulatory-compliant language
• Ready for QC with minimal edits
• HTML must render properly in both DOCX and PDF conversion

Generate the complete HTML document now, substituting actual composition data and ensuring professional formatting."""