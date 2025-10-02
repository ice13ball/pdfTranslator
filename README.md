# PDF Translator

A simple Python web app to translate PDF files while preserving their format using Azure OpenAI GPT-4.

## Requirements

- Python 3.12 (Python 3.13 not yet supported by PyMuPDF)
- Cross-platform compatible (works on Windows, macOS, Linux)

## Setup

### Quick Setup (Windows)
Run the PowerShell script:
```powershell
.\install.ps1
```

### Manual Setup

1. Create a virtual environment with Python 3.12:
   ```bash
   python3.12 -m venv venv
   ```

2. Activate the virtual environment:
   ```bash
   # On macOS/Linux:
   source venv/bin/activate
   
   # On Windows:
   venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables. Create a `.env` file with:
   ```
   AZURE_OPENAI_API_KEY=your_api_key
   AZURE_OPENAI_ENDPOINT=your_endpoint
   AZURE_OPENAI_API_VERSION=2024-10-21
   AZURE_OPENAI_DEPLOYMENT_NAME=gpt4
   ```

5. Run the app:
   ```bash
   python app.py
   ```

6. Open http://127.0.0.1:5000 in your browser.

## Usage

1. Select a PDF file by dragging and dropping or clicking the upload area.
2. Choose the target language from the dropdown.
4. Download the translated PDF.

## Limitations and Intended Use

- **Internal use only**. This tool is intended for non-production, internal workflows (review, drafts, enablement). Do not use for customer-facing deliverables without manual QA.
- **No OCR**. Scanned/image-only PDFs are not translated because text cannot be extracted. Use OCR first to convert to selectable text.
- **Layout fidelity**. The app tries to preserve layout, but some text may be slightly re-positioned or appear with background patches. Long lines may be auto-shrunk to fit.
- **Images and graphics**. Images are preserved; complex vector elements behind text can cause minor artifacts in some slides.
- **Fonts and glyphs**. The app embeds a Unicode font (DejaVu Sans) for overlays. Rare glyphs may still render differently from the original.
- **Performance and size**. Very large PDFs or pages with many images will take longer and may increase output size slightly.
- **Privacy & data**. Do not upload confidential or regulated data. Content is sent to Azure OpenAI according to your Azure subscription/data policies.
- **Copyright**. Ensure you have the right to translate the PDF content.

> Note: This project is provided as-is without warranty. Validate all outputs before sharing externally.

# pdfTranslator
