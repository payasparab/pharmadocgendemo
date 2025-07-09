# Regulatory Document Generator - Streamlit App

A comprehensive Streamlit application for generating pharmaceutical regulatory documents, specifically Section 3.2.P.1 "Description and Composition of the Drug Product" for IND submissions. The app supports AI-powered text generation and exports to Word (.docx) or PDF formats.

## Features

- 💊 **Pharmaceutical Focus**: Specifically designed for IND regulatory submissions
- 🤖 **AI-Powered Generation**: Uses OpenAI GPT-4 for regulatory text generation
- 📊 **Composition Data**: Upload CSV files or use sample pharmaceutical data
- 📄 **Word Export**: Generate professional Word documents with regulatory formatting
- 📋 **PDF Export**: Create PDF documents compliant with eCTD standards
- 🎨 **Customization**: Configure product codes, dosage forms, and mechanisms of action
- ✅ **Validation**: Built-in regulatory compliance checklist
- 📱 **Responsive Design**: Modern, user-friendly interface

## Installation

1. **Clone or download the project files**

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure OpenAI API**:
   - Option 1: Create `.streamlit/secrets.toml`:
     ```toml
     [openai]
     api_key = "your-openai-api-key-here"
     ```
   - Option 2: Update `credentials.py` with your API key

4. **Run the application**:
   ```bash
   streamlit run app.py
   ```

## Usage

### 1. Product Configuration
- Enter Product Code (e.g., "ABC-123")
- Specify Dosage Form (e.g., "Immediate-release film-coated tablet")
- Describe Mechanism of Action

### 2. Composition Data
- Upload CSV file with columns: Component, Quality_Reference, Function, Quantity_mg_per_tablet
- Or use the built-in sample pharmaceutical data
- View composition table and total weight calculation

### 3. AI Text Generation
- Enable AI generation for regulatory text
- Generate Section 3.2.P.1.1 (Description) and 3.2.P.1.2 (Composition)
- Review generated text in formatted display

### 4. Document Export
- **Word Export**: Generate .docx files with proper regulatory formatting
- **PDF Export**: Create PDF documents with tables and compliance elements
- Download buttons appear after generation

### 5. Validation & Settings
- Review regulatory compliance checklist
- Configure document settings and compliance levels
- Validate all required elements are present

## Supported Data Format

### CSV Structure
```csv
Component,Quality_Reference,Function,Quantity_mg_per_tablet
Active Pharmaceutical Ingredient,USP,Active Ingredient,25.0
Microcrystalline Cellulose,NF,Tablet Diluent,150.0
Lactose Monohydrate,NF,Tablet Diluent,100.0
Croscarmellose Sodium,NF,Disintegrant,10.0
Magnesium Stearate,NF,Lubricant,2.0
Opadry II White,NF,Film Coating,8.0
```

### Quality References
- USP = United States Pharmacopoeia
- NF = National Formulary
- Ph. Eur. = European Pharmacopoeia

## Regulatory Compliance

The app generates documents compliant with:
- FDA IND submission requirements
- ICH guidelines
- eCTD Module 3 structure
- 21 CFR Part 312 requirements

## File Structure

```
documentgenerationdemo/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
├── README.md                # This file
├── credentials.py           # OpenAI API configuration template
├── .gitignore              # Git ignore file
├── pharma_sample_data.csv   # Sample pharmaceutical composition data
└── sample_data.csv         # General sample data (legacy)
```

## Requirements

- Python 3.8+
- Streamlit
- Pandas
- python-docx
- reportlab
- openai
- matplotlib
- seaborn

## Configuration

### OpenAI API Setup
1. Get an API key from [OpenAI](https://platform.openai.com/)
2. Configure in Streamlit secrets or credentials.py
3. The app will fall back to template text if AI is unavailable

### Streamlit Secrets (Recommended)
Create `.streamlit/secrets.toml`:
```toml
[openai]
api_key = "sk-your-actual-api-key-here"
```

### Local Credentials
Update `credentials.py`:
```python
OPENAI_API_KEY = "sk-your-actual-api-key-here"
```

## Troubleshooting

### Common Issues

1. **OpenAI API errors**: Check API key configuration and billing status
2. **CSV upload issues**: Ensure correct column names and data format
3. **PDF generation errors**: Verify reportlab installation
4. **Word document issues**: Check python-docx installation

### Performance Tips

- Use appropriate data sizes for optimal performance
- Ensure stable internet connection for AI generation
- Close other applications to free up memory

## Customization

### Adding New Regulatory Sections
1. Modify the AI prompt in `generate_regulatory_text_with_ai()`
2. Update the parsing logic in `parse_ai_response()`
3. Add new export functions for different document types

### Modifying Export Formats
1. Edit `export_to_word_regulatory()` and `export_to_pdf_regulatory()`
2. Customize styling and compliance elements
3. Add new regulatory document types

## Security Notes

- Never commit API keys to version control
- Use environment variables or Streamlit secrets
- The `.gitignore` file excludes sensitive files

## License

This project is open source and available under the MIT License.

## Contributing

Feel free to submit issues, feature requests, or pull requests to improve the regulatory document generation capabilities. 