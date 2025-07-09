import streamlit as st
import pandas as pd
import io
import base64
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile
import os
from openai import OpenAI
from typing import Dict, List, Optional
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.io as pio
import numpy as np

# Page configuration
st.set_page_config(
    page_title="Regulatory Document Generator",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .stButton > button {
        width: 100%;
        margin-top: 1rem;
    }
    .regulatory-text {
        background-color: #f8f9fa;
        padding: 1rem;
        border-left: 4px solid #1f77b4;
        margin: 1rem 0;
    }
    .chart-container {
        border: 1px solid #ddd;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .drug-info {
        background-color: #e8f4fd;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Drug database
DRUG_DATABASE = {
    "Metformin": {
        "dosage_form": "Immediate-release film-coated tablet",
        "mechanism": "Metformin is a biguanide antihyperglycemic agent that improves glucose tolerance in patients with type 2 diabetes, lowering both basal and postprandial plasma glucose. Its pharmacologic mechanisms of action are different from other classes of oral antihyperglycemic agents.",
        "indication": "Type 2 diabetes mellitus",
        "strength": "500 mg, 850 mg, 1000 mg",
        "class": "Biguanide",
        "manufacturer": "Various"
    },
    "Atorvastatin": {
        "dosage_form": "Film-coated tablet",
        "mechanism": "Atorvastatin is a selective, competitive inhibitor of HMG-CoA reductase, the rate-limiting enzyme that converts 3-hydroxy-3-methylglutaryl-coenzyme A to mevalonate, a precursor of sterols, including cholesterol.",
        "indication": "Hypercholesterolemia and cardiovascular risk reduction",
        "strength": "10 mg, 20 mg, 40 mg, 80 mg",
        "class": "HMG-CoA reductase inhibitor (statin)",
        "manufacturer": "Various"
    },
    "Lisinopril": {
        "dosage_form": "Film-coated tablet",
        "mechanism": "Lisinopril is a competitive inhibitor of angiotensin-converting enzyme (ACE). ACE is a peptidyl dipeptidase that catalyzes the conversion of angiotensin I to the vasoconstrictor substance, angiotensin II.",
        "indication": "Hypertension, heart failure, myocardial infarction",
        "strength": "2.5 mg, 5 mg, 10 mg, 20 mg, 30 mg, 40 mg",
        "class": "ACE inhibitor",
        "manufacturer": "Various"
    },
    "Omeprazole": {
        "dosage_form": "Delayed-release capsule",
        "mechanism": "Omeprazole is a proton pump inhibitor that suppresses gastric acid secretion by specific inhibition of the H+/K+-ATPase in the gastric parietal cell.",
        "indication": "Gastroesophageal reflux disease, peptic ulcer disease",
        "strength": "10 mg, 20 mg, 40 mg",
        "class": "Proton pump inhibitor",
        "manufacturer": "Various"
    },
    "Custom Drug": {
        "dosage_form": "Immediate-release film-coated tablet",
        "mechanism": "The active ingredient selectively inhibits the target enzyme, leading to therapeutic effects in the treatment of the indicated condition.",
        "indication": "Custom indication",
        "strength": "25 mg",
        "class": "Custom class",
        "manufacturer": "Custom manufacturer"
    }
}

def load_openai_api_key():
    """Load OpenAI API key from credentials file"""
    try:
        # Try local credentials file
        import credentials
        return credentials.OPENAI_API_KEY
    except:
        return None

def initialize_openai():
    """Initialize OpenAI client"""
    api_key = load_openai_api_key()
    if api_key and api_key != "your-openai-api-key-here":
        try:
            client = OpenAI(api_key=api_key)
            return client
        except Exception as e:
            return None
    return None

def create_sample_pharma_data():
    """Create sample pharmaceutical composition data"""
    data = {
        'Component': [
            'Active Pharmaceutical Ingredient',
            'Microcrystalline Cellulose',
            'Lactose Monohydrate',
            'Croscarmellose Sodium',
            'Magnesium Stearate',
            'Opadry II White'
        ],
        'Quality_Reference': ['USP', 'NF', 'NF', 'NF', 'NF', 'NF'],
        'Function': [
            'Active Ingredient',
            'Tablet Diluent',
            'Tablet Diluent',
            'Disintegrant',
            'Lubricant',
            'Film Coating'
        ],
        'Quantity_mg_per_tablet': [25.0, 150.0, 100.0, 10.0, 2.0, 8.0]
    }
    return pd.DataFrame(data)

def create_charts(df):
    """Create both Plotly and Matplotlib charts. Return (plotly_charts, export_charts) dicts."""
    import plotly.express as px
    plotly_charts = {}
    export_charts = {}
    # Plotly: Bar chart - Component quantities
    fig_bar = px.bar(df, x='Component', y='Quantity_mg_per_tablet', 
                     title='Component Quantities per Tablet',
                     color='Function', color_discrete_sequence=px.colors.qualitative.Set3)
    plotly_charts['component_quantities'] = fig_bar
    # Matplotlib: Bar chart
    fig, ax = plt.subplots(figsize=(6,4))
    df.groupby('Component')['Quantity_mg_per_tablet'].sum().plot(kind='bar', ax=ax, color='skyblue')
    ax.set_title('Component Quantities per Tablet')
    ax.set_ylabel('Quantity (mg/tablet)')
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    buf.seek(0)
    export_charts['component_quantities'] = buf.read()
    plt.close(fig)
    # Plotly: Pie chart - Function distribution
    function_summary = df.groupby('Function')['Quantity_mg_per_tablet'].sum().reset_index()
    fig_pie = px.pie(function_summary, values='Quantity_mg_per_tablet', names='Function',
                     title='Distribution by Function', color_discrete_sequence=px.colors.qualitative.Set3)
    plotly_charts['function_distribution'] = fig_pie
    # Matplotlib: Pie chart
    fig, ax = plt.subplots(figsize=(6,4))
    function_summary2 = df.groupby('Function')['Quantity_mg_per_tablet'].sum()
    ax.pie(function_summary2, labels=function_summary2.index, autopct='%1.1f%%', startangle=90)
    ax.set_title('Distribution by Function')
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    buf.seek(0)
    export_charts['function_distribution'] = buf.read()
    plt.close(fig)
    # Plotly: Bar chart - Quality reference distribution
    quality_counts = df['Quality_Reference'].value_counts()
    fig_quality = px.bar(x=quality_counts.index, y=quality_counts.values,
                        title='Quality Reference Distribution',
                        labels={'x': 'Quality Reference', 'y': 'Count'},
                        color=quality_counts.index, color_discrete_sequence=px.colors.qualitative.Set3)
    plotly_charts['quality_references'] = fig_quality
    # Matplotlib: Bar chart
    fig, ax = plt.subplots(figsize=(6,4))
    quality_counts.plot(kind='bar', ax=ax, color='lightgreen')
    ax.set_title('Quality Reference Distribution')
    ax.set_ylabel('Count')
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    buf.seek(0)
    export_charts['quality_references'] = buf.read()
    plt.close(fig)
    # Plotly: Scatter plot - Component weight vs function
    fig_scatter = px.scatter(df, x='Function', y='Quantity_mg_per_tablet', 
                            size='Quantity_mg_per_tablet', color='Quality_Reference',
                            title='Component Weight vs Function',
                            hover_data=['Component'], color_discrete_sequence=px.colors.qualitative.Set3)
    plotly_charts['weight_vs_function'] = fig_scatter
    # Matplotlib: Scatter plot
    fig, ax = plt.subplots(figsize=(6,4))
    for func in df['Function'].unique():
        subset = df[df['Function'] == func]
        ax.scatter(subset['Function'], subset['Quantity_mg_per_tablet'], label=func, s=50)
    ax.set_title('Component Weight vs Function')
    ax.set_ylabel('Quantity (mg/tablet)')
    ax.legend()
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    buf.seek(0)
    export_charts['weight_vs_function'] = buf.read()
    plt.close(fig)
    return plotly_charts, export_charts

def save_chart_as_image(fig_or_bytes, chart_name):
    if isinstance(fig_or_bytes, bytes):
        return fig_or_bytes
    return None

def generate_regulatory_text_with_ai(product_code: str, dosage_form: str, 
                                   composition_data: pd.DataFrame, 
                                   mechanism_of_action: str,
                                   drug_info: Dict,
                                   additional_instructions: str = "") -> Dict[str, str]:
    """Generate regulatory text using OpenAI only. If OpenAI is not available, raise an error."""
    client = initialize_openai()
    if not client:
        raise RuntimeError("OpenAI API key not found or invalid. Please set your OpenAI API key.")
    try:
        # Prepare composition data for AI
        composition_text = ""
        total_weight = 0
        for _, row in composition_data.iterrows():
            component = row['Component']
            quality_ref = row['Quality_Reference']
            function = row['Function']
            quantity = row['Quantity_mg_per_tablet']
            total_weight += quantity
            composition_text += f"- {component} ({quality_ref}): {quantity} mg ({function})\n"
        composition_text += f"- Total Weight: {total_weight} mg"
        # Build prompt with additional instructions
        additional_prompt = ""
        if additional_instructions.strip():
            additional_prompt = f"\nAdditional Instructions: {additional_instructions}"
        prompt = f"""
You are a regulatory-writing assistant drafting Section 3.2.P.1 "Description and Composition of the Drug Product" for an IND that is currently in Phase II clinical trials. All content must be suitable for direct inclusion in an eCTD‐compliant Module 3 dossier.

Product Information:
- Product code: {product_code}
- Dosage form: {dosage_form}
- Drug class: {drug_info.get('class', 'Not specified')}
- Indication: {drug_info.get('indication', 'Not specified')}
- Mechanism of action: {mechanism_of_action}

Composition data:
{composition_text}{additional_prompt}

Required Output Structure:
1. 3.2.P.1.1 Description of the Dosage Form
   - One concise paragraph that identifies the dosage form and strength(s)
   - States the active‐ingredient concentration(s) clearly
   - Summarises the mechanism of action in one sentence
   - Write in the third person, scientific style; do not use marketing language

2. 3.2.P.1.2 Composition
   - Introductory sentence: "The qualitative and quantitative composition of the {product_code} is provided in Table 1."
   - Table 1 should be titled 'Composition of the {product_code}'
   - Include all components with their quality references, functions, and quantities
   - Do not include markdown or ASCII tables in the text. Only refer to the table by title or as Table 1.

3. 3.2.P.1.3 Pharmaceutical Development
   - Brief description of formulation development considerations
   - Reference to key excipient functions

4. 3.2.P.1.4 Manufacturing Process
   - Overview of the manufacturing process
   - Key process parameters and controls

Please provide the text in a structured format suitable for regulatory submission.
"""
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a pharmaceutical regulatory writing expert with deep knowledge of FDA and ICH guidelines for IND submissions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        ai_text = response.choices[0].message.content
        sections = parse_ai_response(ai_text, product_code)
        return sections
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")

def parse_ai_response(ai_text: str, product_code: str) -> Dict[str, str]:
    """Parse AI response into structured sections"""
    sections = {
        'description': '',
        'composition_intro': '',
        'pharmaceutical_development': '',
        'manufacturing_process': '',
        'table_title': f'Composition of the {product_code}'
    }
    
    # Simple parsing - in production, you might want more sophisticated parsing
    lines = ai_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Detect section headers
        if '3.2.P.1.1' in line or 'Description' in line:
            current_section = 'description'
            continue
        elif '3.2.P.1.2' in line or 'Composition' in line:
            current_section = 'composition_intro'
            continue
        elif '3.2.P.1.3' in line or 'Pharmaceutical Development' in line:
            current_section = 'pharmaceutical_development'
            continue
        elif '3.2.P.1.4' in line or 'Manufacturing Process' in line:
            current_section = 'manufacturing_process'
            continue
        elif line.startswith('Table') or line.startswith('The qualitative'):
            current_section = 'composition_intro'
        
        # Add content to appropriate section
        if current_section and line:
            if current_section == 'description':
                sections['description'] += line + ' '
            elif current_section == 'composition_intro':
                sections['composition_intro'] += line + ' '
            elif current_section == 'pharmaceutical_development':
                sections['pharmaceutical_development'] += line + ' '
            elif current_section == 'manufacturing_process':
                sections['manufacturing_process'] += line + ' '
    
    return sections

def export_to_word_regulatory(df: pd.DataFrame, sections: Dict[str, str], 
                             product_code: str, dosage_form: str,
                             uploaded_images: List, notes: str,
                             charts: Dict) -> Document:
    """Export regulatory document to Word format"""
    doc = Document()
    
    # Add title
    title = doc.add_heading('Section 3.2.P.1 Description and Composition of the Drug Product', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # Add description section
    doc.add_heading('3.2.P.1.1 Description of the Dosage Form', level=1)
    doc.add_paragraph(sections['description'])
    doc.add_paragraph()  # Add space
    
    # Add composition section
    doc.add_heading('3.2.P.1.2 Composition', level=1)
    doc.add_paragraph(sections['composition_intro'])
    doc.add_paragraph()  # Add space
    
    # Add table
    table = doc.add_table(rows=1, cols=4)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Add headers
    headers = ['Component', 'Quality Reference', 'Function', 'Quantity / Unit (mg per tablet)']
    header_cells = table.rows[0].cells
    for i, header in enumerate(headers):
        header_cells[i].text = header
    
    # Add data rows
    total_weight = 0
    for _, row in df.iterrows():
        row_cells = table.add_row().cells
        row_cells[0].text = str(row['Component'])
        row_cells[1].text = str(row['Quality_Reference'])
        row_cells[2].text = str(row['Function'])
        row_cells[3].text = str(row['Quantity_mg_per_tablet'])
        total_weight += row['Quantity_mg_per_tablet']
    
    # Add total weight row
    total_cells = table.add_row().cells
    total_cells[0].text = 'Total Weight'
    total_cells[1].text = ''
    total_cells[2].text = ''
    total_cells[3].text = f'{total_weight}'
    
    # Add footnote
    doc.add_paragraph("Abbreviations: NF = National Formulary; Ph. Eur. = European Pharmacopoeia; USP = United States Pharmacopoeia.")
    
    # Add pharmaceutical development
    if sections.get('pharmaceutical_development'):
        doc.add_heading('3.2.P.1.3 Pharmaceutical Development', level=1)
        doc.add_paragraph(sections['pharmaceutical_development'])
        doc.add_paragraph()
    
    # Add manufacturing process
    if sections.get('manufacturing_process'):
        doc.add_heading('3.2.P.1.4 Manufacturing Process', level=1)
        doc.add_paragraph(sections['manufacturing_process'])
        doc.add_paragraph()
    
    # Add charts as images based on selection
    chart_selections = {
        'component_quantities': getattr(st.session_state, 'include_component_quantities', True),
        'function_distribution': getattr(st.session_state, 'include_function_distribution', True),
        'quality_references': getattr(st.session_state, 'include_quality_references', True),
        'weight_vs_function': getattr(st.session_state, 'include_weight_vs_function', True)
    }
    
    included_charts = {name: fig for name, fig in charts.items() if chart_selections.get(name, True)}
    
    if included_charts:
        doc.add_heading('Data Visualizations', level=1)
        for chart_name, fig in included_charts.items():
            # Try to save chart as image
            img_bytes = save_chart_as_image(fig, chart_name)
            
            if img_bytes:
                # Add image to document
                img_stream = io.BytesIO(img_bytes)
                doc.add_picture(img_stream, width=Inches(6))
                doc.add_paragraph(f"Figure: {chart_name.replace('_', ' ').title()}")
                doc.add_paragraph()
            else:
                # Fallback: add text description
                doc.add_paragraph(f"Chart: {chart_name.replace('_', ' ').title()}")
                doc.add_paragraph("(Chart visualization available in interactive version)")
                doc.add_paragraph()
    
    # Add notes if provided
    if notes.strip():
        doc.add_heading('Additional Notes', level=1)
        doc.add_paragraph(notes)
    
    # Add images if provided
    if uploaded_images:
        doc.add_heading('Supporting Images', level=1)
        for i, img_data in enumerate(uploaded_images):
            try:
                img_stream = io.BytesIO(img_data)
                doc.add_picture(img_stream, width=Inches(4))
                doc.add_paragraph(f"Figure {i+1}")
            except Exception as e:
                doc.add_paragraph(f"Image {i+1} could not be added: {str(e)}")
    
    return doc

def export_to_pdf_regulatory(df: pd.DataFrame, sections: Dict[str, str], 
                            product_code: str, dosage_form: str,
                            uploaded_images: List, notes: str,
                            charts: Dict):
    """Export regulatory document to PDF format"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Add title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )
    story.append(Paragraph('Section 3.2.P.1 Description and Composition of the Drug Product', title_style))
    story.append(Spacer(1, 12))
    
    # Add description section
    story.append(Paragraph('3.2.P.1.1 Description of the Dosage Form', styles['Heading2']))
    story.append(Paragraph(sections['description'], styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Add composition section
    story.append(Paragraph('3.2.P.1.2 Composition', styles['Heading2']))
    story.append(Paragraph(sections['composition_intro'], styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Prepare table data
    headers = ['Component', 'Quality Reference', 'Function', 'Quantity / Unit (mg per tablet)']
    table_data = [headers]
    
    total_weight = 0
    for _, row in df.iterrows():
        table_data.append([
            str(row['Component']),
            str(row['Quality_Reference']),
            str(row['Function']),
            str(row['Quantity_mg_per_tablet'])
        ])
        total_weight += row['Quantity_mg_per_tablet']
    
    # Add total weight row
    table_data.append(['Total Weight', '', '', str(total_weight)])
    
    # Create table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 12))
    
    # Add footnote
    story.append(Paragraph("Abbreviations: NF = National Formulary; Ph. Eur. = European Pharmacopoeia; USP = United States Pharmacopoeia.", styles['Normal']))
    
    # Add pharmaceutical development
    if sections.get('pharmaceutical_development'):
        story.append(Paragraph('3.2.P.1.3 Pharmaceutical Development', styles['Heading2']))
        story.append(Paragraph(sections['pharmaceutical_development'], styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Add manufacturing process
    if sections.get('manufacturing_process'):
        story.append(Paragraph('3.2.P.1.4 Manufacturing Process', styles['Heading2']))
        story.append(Paragraph(sections['manufacturing_process'], styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Add charts as images based on selection
    chart_selections = {
        'component_quantities': getattr(st.session_state, 'include_component_quantities', True),
        'function_distribution': getattr(st.session_state, 'include_function_distribution', True),
        'quality_references': getattr(st.session_state, 'include_quality_references', True),
        'weight_vs_function': getattr(st.session_state, 'include_weight_vs_function', True)
    }
    
    included_charts = {name: fig for name, fig in charts.items() if chart_selections.get(name, True)}
    
    if included_charts:
        story.append(Paragraph('Data Visualizations', styles['Heading2']))
        for chart_name, fig in included_charts.items():
            # Try to save chart as image
            img_bytes = save_chart_as_image(fig, chart_name)
            
            if img_bytes:
                # Add image to PDF
                img_stream = io.BytesIO(img_bytes)
                img = RLImage(img_stream, width=5*inch, height=3*inch)
                story.append(img)
                story.append(Paragraph(f"Figure: {chart_name.replace('_', ' ').title()}", styles['Normal']))
                story.append(Spacer(1, 12))
            else:
                # Fallback: add text description
                story.append(Paragraph(f"Chart: {chart_name.replace('_', ' ').title()}", styles['Normal']))
                story.append(Paragraph("(Chart visualization available in interactive version)", styles['Normal']))
                story.append(Spacer(1, 12))
    
    # Add notes if provided
    if notes.strip():
        story.append(Paragraph('Additional Notes', styles['Heading2']))
        story.append(Paragraph(notes, styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Add images if provided
    if uploaded_images:
        story.append(Paragraph('Supporting Images', styles['Heading2']))
        for i, img_data in enumerate(uploaded_images):
            try:
                img_stream = io.BytesIO(img_data)
                img = RLImage(img_stream, width=3*inch, height=2*inch)
                story.append(img)
                story.append(Paragraph(f"Figure {i+1}", styles['Normal']))
                story.append(Spacer(1, 12))
            except Exception as e:
                story.append(Paragraph(f"Image {i+1} could not be added: {str(e)}", styles['Normal']))
    
    doc.build(story)
    return buffer

def main():
    # Header
    st.markdown('<h1 class="main-header">💊 Regulatory Document Generator</h1>', unsafe_allow_html=True)
    st.markdown("Generate Section 3.2.P.1 'Description and Composition of the Drug Product' for IND submissions")
    
    # Sidebar for configuration
    st.sidebar.header("Product Configuration")
    
    # Drug selection
    selected_drug = st.sidebar.selectbox("Select Drug", list(DRUG_DATABASE.keys()))
    drug_info = DRUG_DATABASE[selected_drug]
    
    # Display drug information
    st.sidebar.markdown('<div class="drug-info">', unsafe_allow_html=True)
    st.sidebar.write(f"**Drug Class:** {drug_info['class']}")
    st.sidebar.write(f"**Indication:** {drug_info['indication']}")
    st.sidebar.write(f"**Available Strengths:** {drug_info['strength']}")
    st.sidebar.write(f"**Manufacturer:** {drug_info['manufacturer']}")
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
    
    # Product information
    product_code = st.sidebar.text_input("Product Code", f"{selected_drug}-001")
    dosage_form = st.sidebar.text_input("Dosage Form", drug_info['dosage_form'])
    mechanism_of_action = st.sidebar.text_area("Mechanism of Action", drug_info['mechanism'])
    
    # AI configuration
    st.sidebar.header("AI Configuration")
    use_ai = st.sidebar.checkbox("Use AI for text generation", value=True)
    
    # Data input section
    st.markdown('<h2 class="section-header">📊 Composition Data</h2>', unsafe_allow_html=True)
    
    # Option to upload CSV or use sample data
    data_option = st.radio("Choose data source:", ["Use Sample Data", "Upload CSV File"])
    
    if data_option == "Upload CSV File":
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        if uploaded_file is not None:
            df = pd.read_csv(uploaded_file)
            st.success(f"✅ Loaded {len(df)} components")
        else:
            st.info("Please upload a CSV file or use sample data")
            df = None
    else:
        df = create_sample_pharma_data()
        st.success("✅ Using sample pharmaceutical data")
    
    if df is not None:
        # Display the composition data
        st.subheader("📋 Composition Table")
        st.dataframe(df, use_container_width=True)
        
        # Calculate total weight
        total_weight = df['Quantity_mg_per_tablet'].sum()
        st.info(f"📊 Total tablet weight: {total_weight} mg")
        
        # Create and display charts
        st.markdown('<h2 class="section-header">📈 Data Visualizations</h2>', unsafe_allow_html=True)
        plotly_charts, export_charts = create_charts(df)
        
        # Display charts in tabs
        chart_tabs = st.tabs(["Component Quantities", "Function Distribution", "Quality References", "Weight vs Function"])
        
        with chart_tabs[0]:
            st.plotly_chart(plotly_charts['component_quantities'], use_container_width=True)
            if 'include_component_quantities' in locals() and include_component_quantities:
                st.success("✅ This chart will be included in the report")
            else:
                st.info("ℹ️ Use the chart selection options to include this chart in the report")
        
        with chart_tabs[1]:
            st.plotly_chart(plotly_charts['function_distribution'], use_container_width=True)
            if 'include_function_distribution' in locals() and include_function_distribution:
                st.success("✅ This chart will be included in the report")
            else:
                st.info("ℹ️ Use the chart selection options to include this chart in the report")
        
        with chart_tabs[2]:
            st.plotly_chart(plotly_charts['quality_references'], use_container_width=True)
            if 'include_quality_references' in locals() and include_quality_references:
                st.success("✅ This chart will be included in the report")
            else:
                st.info("ℹ️ Use the chart selection options to include this chart in the report")
        
        with chart_tabs[3]:
            st.plotly_chart(plotly_charts['weight_vs_function'], use_container_width=True)
            if 'include_weight_vs_function' in locals() and include_weight_vs_function:
                st.success("✅ This chart will be included in the report")
            else:
                st.info("ℹ️ Use the chart selection options to include this chart in the report")
        
        # Additional content section
        st.markdown('<h2 class="section-header">📎 Additional Content</h2>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📷 Upload Images")
            uploaded_images = st.file_uploader("Upload supporting images", 
                                             type=['png', 'jpg', 'jpeg'], 
                                             accept_multiple_files=True)
            
            if uploaded_images:
                st.write(f"✅ {len(uploaded_images)} image(s) uploaded")
                for i, img in enumerate(uploaded_images):
                    st.image(img, caption=f"Image {i+1}: {img.name}", width=200)
        
        with col2:
            st.subheader("📝 Additional Notes")
            notes = st.text_area("Add any additional notes or comments for the document", 
                                height=150,
                                placeholder="Enter any additional information, observations, or notes...")
            
            st.subheader("🔧 Document Options")
            compliance_level = st.selectbox("Compliance level:", ["FDA", "EMA", "ICH", "Other"])
            document_version = st.text_input("Document version:", "1.0")
            
            st.subheader("📊 Chart Selection for Report")
            include_component_quantities = st.checkbox("Include Component Quantities Chart", value=True)
            include_function_distribution = st.checkbox("Include Function Distribution Chart", value=True)
            include_quality_references = st.checkbox("Include Quality References Chart", value=True)
            include_weight_vs_function = st.checkbox("Include Weight vs Function Chart", value=True)
        
        # Generate regulatory text
        st.markdown('<h2 class="section-header">📝 Generated Regulatory Text</h2>', unsafe_allow_html=True)
        
        if st.button("🔄 Generate Regulatory Text", type="primary"):
            with st.spinner("Generating regulatory text..."):
                if use_ai and initialize_openai():
                    sections = generate_regulatory_text_with_ai(
                        product_code, dosage_form, df, mechanism_of_action, drug_info
                    )
                else:
                    raise RuntimeError("OpenAI API key not found or invalid. Please set your OpenAI API key.")
                # Store in session state for export
                st.session_state.sections = sections
                st.session_state.df = df
                st.session_state.uploaded_images = uploaded_images if uploaded_images else []
                st.session_state.notes = notes
                st.session_state.charts = export_charts
                st.session_state.include_component_quantities = include_component_quantities
                st.session_state.include_function_distribution = include_function_distribution
                st.session_state.include_quality_references = include_quality_references
                st.session_state.include_weight_vs_function = include_weight_vs_function
                st.session_state.text_generated = True

        # Always display the current text if it exists
        if st.session_state.get('sections'):
            st.markdown('<div class="regulatory-text">', unsafe_allow_html=True)
            st.subheader("3.2.P.1.1 Description of the Dosage Form")
            st.write(st.session_state.sections.get('description', ''))
            if st.session_state.sections.get('composition_intro') and st.session_state.sections['composition_intro'].strip():
                st.subheader("3.2.P.1.2 Composition")
                st.write(st.session_state.sections['composition_intro'])
            if st.session_state.sections.get('pharmaceutical_development') and st.session_state.sections['pharmaceutical_development'].strip():
                st.subheader("3.2.P.1.3 Pharmaceutical Development")
                st.write(st.session_state.sections['pharmaceutical_development'])
            if st.session_state.sections.get('manufacturing_process') and st.session_state.sections['manufacturing_process'].strip():
                st.subheader("3.2.P.1.4 Manufacturing Process")
                st.write(st.session_state.sections['manufacturing_process'])
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Export section
        if 'sections' in st.session_state:
            st.markdown('<h2 class="section-header">💾 Export Document</h2>', unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Export to Word (.docx)")
                if st.button("📄 Generate Word Document", type="primary"):
                    with st.spinner("Generating Word document..."):
                        # Convert uploaded images to bytes
                        image_bytes = []
                        if st.session_state.uploaded_images:
                            for img in st.session_state.uploaded_images:
                                image_bytes.append(img.read())
                                img.seek(0)  # Reset file pointer
                        
                        doc = export_to_word_regulatory(
                            st.session_state.df, 
                            st.session_state.sections, 
                            product_code, 
                            dosage_form,
                            image_bytes,
                            st.session_state.notes,
                            st.session_state.charts
                        )
                        
                        # Save to bytes
                        doc_buffer = io.BytesIO()
                        doc.save(doc_buffer)
                        doc_buffer.seek(0)
                        
                        # Create download button
                        st.download_button(
                            label="📥 Download Word Document",
                            data=doc_buffer.getvalue(),
                            file_name=f"Section_3.2.P.1_{product_code}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
            
            with col2:
                st.subheader("Export to PDF")
                if st.button("📄 Generate PDF Document", type="primary"):
                    with st.spinner("Generating PDF document..."):
                        # Convert uploaded images to bytes
                        image_bytes = []
                        if st.session_state.uploaded_images:
                            for img in st.session_state.uploaded_images:
                                image_bytes.append(img.read())
                                img.seek(0)  # Reset file pointer
                        
                        pdf_buffer = export_to_pdf_regulatory(
                            st.session_state.df, 
                            st.session_state.sections, 
                            product_code, 
                            dosage_form,
                            image_bytes,
                            st.session_state.notes,
                            st.session_state.charts
                        )
                        pdf_buffer.seek(0)
                        
                        # Create download button
                        st.download_button(
                            label="📥 Download PDF Document",
                            data=pdf_buffer.getvalue(),
                            file_name=f"Section_3.2.P.1_{product_code}.pdf",
                            mime="application/pdf"
                        )

if __name__ == "__main__":
    main()
