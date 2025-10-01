# PDF Translator

A simple Python web app to translate PDF files while preserving their format using Azure OpenAI GPT-4.

## Requirements

- Python 3.12 (Python 3.13 not yet supported by PyMuPDF)

## Setup

1. Create a virtual environment with Python 3.12:
   ```bash
   python3.12 -m venv venv
   ```

2. Activate the virtual environment:
   ```bash
   source venv/bin/activate
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

## Limitations

- Works best with text-based PDFs. Complex layouts with images may not preserve all formatting.
- Translation quality depends on the input PDF's text extraction accuracy.
- Large PDFs may take longer to process.
# pdfTranslator
