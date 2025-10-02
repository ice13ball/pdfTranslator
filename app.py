from flask import Flask, request, render_template, send_file
import os
import fitz
from openai import AzureOpenAI
from dotenv import load_dotenv
import tempfile
from typing import Optional

load_dotenv()

app = Flask(__name__)

# Azure OpenAI setup
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

# Supported languages for GPT-4o
LANGUAGES = [
    "Afrikaans", "Arabic", "Bengali", "Bulgarian", "Catalan", "Chinese (Simplified)", 
    "Chinese (Traditional)", "Croatian", "Czech", "Danish", "Dutch", "English", 
    "Estonian", "Finnish", "French", "German", "Greek", "Gujarati", "Hebrew", 
    "Hindi", "Hungarian", "Icelandic", "Indonesian", "Italian", "Japanese", 
    "Kannada", "Kazakh", "Korean", "Latvian", "Lithuanian", "Malay", "Malayalam", 
    "Marathi", "Norwegian", "Persian", "Polish", "Portuguese", "Romanian", 
    "Russian", "Sanskrit", "Serbian", "Slovak", "Slovenian", "Spanish", "Swahili", 
    "Swedish", "Tamil", "Telugu", "Thai", "Turkish", "Ukrainian", "Urdu", 
    "Vietnamese", "Welsh", "Xhosa", "Zulu"
]

# Try to locate a Unicode-capable font (DejaVu Sans) for overlays
def _find_font_path() -> Optional[str]:
    here = os.path.dirname(__file__)
    candidates = [
        os.path.join(here, "fonts", "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/DejaVuSans.ttf",
        "/Library/Fonts/DejaVu Sans.ttf",
        "C\\\Windows\\Fonts\\DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            continue
    return None

FONT_PATH = _find_font_path()

@app.route('/')
def index():
    return render_template('index.html', languages=LANGUAGES)

@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf' not in request.files:
        return "No file uploaded", 400
    file = request.files['pdf']
    lang = request.form.get('language')
    if not lang:
        return "No language selected", 400
    
    print(f"Uploaded file: {file.filename}, Target language: {lang}")
    
    # Save uploaded file temporarily
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    temp_path = temp_file.name
    temp_file.close()
    file.save(temp_path)
    
    try:
        # Translate PDF
        translated_pdf_path = translate_pdf(temp_path, lang)
        
        # Send translated PDF
        response = send_file(translated_pdf_path, as_attachment=True, download_name="translated.pdf")
        
        # Clean up files after sending
        @response.call_on_close
        def cleanup():
            os.unlink(temp_path)
            os.unlink(translated_pdf_path)
        
        return response
    except Exception as e:
        # Clean up on error
        os.unlink(temp_path)
        print(f"Error during translation: {e}")
        return str(e), 500

def translate_pdf(pdf_path, target_lang):
    print(f"Starting PDF translation for {pdf_path} to {target_lang}")
    doc = fitz.open(pdf_path)
    new_doc = fitz.open()
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        page_rect = page.rect
        
        text_dict = page.get_text("dict")
        print(f"Page {page_num}: extracted {len(text_dict['blocks'])} text blocks")
        
        total_text = ""
        for block in text_dict['blocks']:
            if block['type'] == 0:
                for line in block['lines']:
                    for span in line['spans']:
                        total_text += span['text']
        print(f"Total extracted text length: {len(total_text)} characters")
        if len(total_text) == 0:
            print("Warning: No text extracted from this page. The PDF may be image-based or scanned.")
        
        # First pass: add redaction annotations to remove original text cleanly
        redaction_rects = []
        for block in text_dict['blocks']:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    # Collect all text in the line
                    line_text = ''.join(span['text'] for span in line['spans'])
                    line_bbox = line['bbox']
                    
                    if line_text.strip():
                        # Compute a tight rectangle around actual text spans (ignore tiny spans)
                        valid_spans = [
                            s for s in line['spans']
                            if s.get('text', '').strip() and s.get('size', 0) >= 5
                        ]
                        if not valid_spans:
                            valid_spans = line['spans']

                        x0 = min(s['bbox'][0] for s in valid_spans)
                        y0 = min(s['bbox'][1] for s in valid_spans)
                        x1 = max(s['bbox'][2] for s in valid_spans)
                        y1 = max(s['bbox'][3] for s in valid_spans)
                        pad = 0.4
                        rect = fitz.Rect(x0, y0 - pad, x1, y1 + pad)
                        redaction_rects.append(rect)
        # Apply redactions (remove original text) on the source page
        for r in redaction_rects:
            page.add_redact_annot(r, fill=None, cross_out=False)
        try:
            page.apply_redactions(images=2, graphics=0, text=1)
        except Exception as e:
            print(f"Redaction apply failed on page {page_num}: {e}")

        # Now create the output page and copy the redacted content as a raster background
        # This avoids vector artifacts and guarantees original text is gone
        new_page = new_doc.new_page(width=page_rect.width, height=page_rect.height)
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            new_page.insert_image(new_page.rect, pixmap=pix)
        except Exception as e:
            print(f"Pixmap render failed on page {page_num}, falling back to vector copy: {e}")
            new_page.show_pdf_page(new_page.rect, doc, page_num)

        # Second pass: draw translated text only (no painting)
        for block in text_dict['blocks']:
            if block['type'] == 0:
                for line in block['lines']:
                    line_text = ''.join(span['text'] for span in line['spans'])
                    if not line_text.strip():
                        continue
                    # Translate and sanitize
                    translated_line = translate_text(line_text, target_lang)
                    translated_line = translated_line.lstrip('•◦·-–—*? \t').rstrip()

                    # Fit into the line bbox
                    valid_spans = [s for s in line['spans'] if s.get('text','').strip() and s.get('size',0)>=5]
                    if not valid_spans:
                        valid_spans = line['spans']
                    x0 = min(s['bbox'][0] for s in valid_spans)
                    y0 = min(s['bbox'][1] for s in valid_spans)
                    x1 = max(s['bbox'][2] for s in valid_spans)
                    y1 = max(s['bbox'][3] for s in valid_spans)
                    rect = fitz.Rect(x0, y0 - 0.2, x1, y1 + 0.2)
                    base_size = valid_spans[0]['size'] if valid_spans else 12
                    size = base_size
                    rv = -1.0
                    for _ in range(8):
                        kwargs = dict(fontsize=size, color=(0,0,0), lineheight=1.05, align=0)
                        if FONT_PATH:
                            kwargs["fontfile"] = FONT_PATH
                        rv = new_page.insert_textbox(rect, translated_line, **kwargs)
                        if rv >= 0:
                            break
                        size *= 0.9
                    if rv < 0:
                        size = max(6, base_size * 0.6)
                        if FONT_PATH:
                            new_page.insert_text((rect.x0, rect.y1 - 0.2), translated_line, fontsize=size, color=(0,0,0), fontfile=FONT_PATH)
                        else:
                            new_page.insert_text((rect.x0, rect.y1 - 0.2), translated_line, fontsize=size, color=(0,0,0))
    
    # Use tempfile for output
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    output_path = output_file.name
    output_file.close()
    
    new_doc.save(output_path)
    new_doc.close()
    doc.close()
    print(f"Translation completed, output saved to {output_path}")
    return output_path

def translate_text(text, target_lang):
    if not text.strip():
        return text
    
    print(f"Translating text: '{text}' to {target_lang}")
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_lang}. Maintain the original meaning, tone, and formatting as much as possible."},
                {"role": "user", "content": text}
            ],
            max_tokens=1000
        )
        translated = response.choices[0].message.content.strip()
        print(f"Translated to: '{translated}'")
        return translated
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return original if translation fails

if __name__ == '__main__':
    app.run(debug=True)
