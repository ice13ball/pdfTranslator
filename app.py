from flask import Flask, request, render_template, send_file
import os
import fitz
from openai import AzureOpenAI
from dotenv import load_dotenv
import tempfile
from typing import Optional
import logging
import re

load_dotenv()

app = Flask(__name__)

# Logging configuration (set LOG_LEVEL=DEBUG in .env to increase verbosity)
logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
                    format='[%(levelname)s] %(message)s')
logger = logging.getLogger("pdfTranslator")

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
    logger.info(f"Starting PDF translation for {pdf_path} to {target_lang}")
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
        logger.info(f"Page {page_num}: total extracted text length = {len(total_text)} characters")
        if len(total_text) == 0:
            logger.warning("No text extracted from this page. The PDF may be image-based or scanned.")
        
        # Render a pixmap once for background color sampling
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)

        # Create a new page and copy original content (images/background preserved)
        new_page = new_doc.new_page(width=page_rect.width, height=page_rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page_num)

        # Overlay translated text and hide source text with locally matched background
        for block in text_dict['blocks']:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    # Collect text
                    line_text = ''.join(span['text'] for span in line['spans'])
                    if not line_text.strip():
                        continue

                    # Translate and sanitize bullets that may appear as '?'
                    translated_line = translate_text(line_text, target_lang)
                    translated_line = translated_line.lstrip('•◦·-–—*? \t').rstrip()
                    if re.match(r"^(sure|certainly|here's|here is|ok|okay)[\s,]", translated_line, flags=re.I):
                        logger.debug(f"Sanitizing assistant preamble on page {page_num}")
                        translated_line = re.sub(r"^(sure|certainly|here's|here is|ok|okay)[\s,:-]+", "", translated_line, flags=re.I)

                    # Choose spans used to compute rects
                    valid_spans = [
                        s for s in line['spans']
                        if s.get('text', '').strip() and s.get('size', 0) >= 5
                    ]
                    if not valid_spans:
                        valid_spans = line['spans']

                    # Group spans to avoid painting long bars
                    groups = []
                    current = [valid_spans[0]] if valid_spans else []
                    for s in valid_spans[1:]:
                        gap = s['bbox'][0] - current[-1]['bbox'][2]
                        if gap > 3:
                            groups.append(current)
                            current = [s]
                        else:
                            current.append(s)
                    if current:
                        groups.append(current)

                    # Helper for sampling background color
                    def sample_rgb(px, py):
                        px = min(max(0, px), pix.width - 1)
                        py = min(max(0, py), pix.height - 1)
                        base = (py * pix.width + px) * pix.n
                        return (
                            pix.samples[base] / 255.0,
                            pix.samples[base + 1] / 255.0,
                            pix.samples[base + 2] / 255.0,
                        )

                    scale_x = pix.width / page_rect.width
                    scale_y = pix.height / page_rect.height
                    pad = 0.3

                    # Paint per-span with local sampling to hide original text
                    for g in groups:
                        for sp in g:
                            sx0, sy0, sx1, sy1 = sp['bbox']
                            if sx1 - sx0 < 1 or sy1 - sy0 < 1:
                                continue
                            srect = fitz.Rect(sx0, sy0 - pad, sx1, sy1 + pad)
                            try:
                                tx1 = int(max(0, (srect.x0 - 1) * scale_x))
                                ty1 = int(max(0, (srect.y0 - 1) * scale_y))
                                tx2 = int(min(pix.width - 1, (srect.x1 + 1) * scale_x))
                                ty2 = int(min(pix.height - 1, (srect.y1 + 1) * scale_y))
                                mx = int(((srect.x0 + srect.x1) / 2) * scale_x)
                                my = int(((srect.y0 + srect.y1) / 2) * scale_y)
                                smps = [
                                    sample_rgb(tx1, ty1), sample_rgb(tx2, ty1),
                                    sample_rgb(tx1, ty2), sample_rgb(tx2, ty2),
                                    sample_rgb(mx, my)
                                ]
                                rr = sum(v[0] for v in smps) / len(smps)
                                gg = sum(v[1] for v in smps) / len(smps)
                                bb = sum(v[2] for v in smps) / len(smps)
                                span_bg = (rr, gg, bb)
                            except Exception:
                                span_bg = (1, 1, 1)
                            new_page.draw_rect(srect, color=span_bg, fill=span_bg, width=0)
                            logger.debug(f"Paint span rect {srect} bg={span_bg}")

                    # Write translated text inside the line bbox with auto-fit
                    x0 = min(s['bbox'][0] for s in valid_spans)
                    y0 = min(s['bbox'][1] for s in valid_spans)
                    x1 = max(s['bbox'][2] for s in valid_spans)
                    y1 = max(s['bbox'][3] for s in valid_spans)
                    lrect = fitz.Rect(x0, y0 - 0.2, x1, y1 + 0.2)
                    base_size = valid_spans[0]['size'] if valid_spans else 12
                    size = base_size
                    rv = -1.0
                    for _ in range(8):
                        kwargs = dict(fontsize=size, color=(0,0,0), lineheight=1.05, align=0)
                        if FONT_PATH:
                            kwargs["fontfile"] = FONT_PATH
                        rv = new_page.insert_textbox(lrect, translated_line, **kwargs)
                        logger.debug(f"insert_textbox rv={rv} size={size} rect={lrect}")
                        if rv >= 0:
                            break
                        size *= 0.9
                    if rv < 0:
                        size = max(6, base_size * 0.6)
                        if FONT_PATH:
                            new_page.insert_text((lrect.x0, lrect.y1 - 0.2), translated_line, fontsize=size, color=(0,0,0), fontfile=FONT_PATH)
                        else:
                            new_page.insert_text((lrect.x0, lrect.y1 - 0.2), translated_line, fontsize=size, color=(0,0,0))
                        logger.debug(f"Fallback insert_text size={size} at ({lrect.x0}, {lrect.y1 - 0.2})")
    
    # Use tempfile for output
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    output_path = output_file.name
    output_file.close()
    
    new_doc.save(output_path)
    new_doc.close()
    doc.close()
    logger.info(f"Translation completed, output saved to {output_path}")
    return output_path

def translate_text(text, target_lang):
    if not text.strip():
        return text

    logger.debug(f"Translating to {target_lang}: len={len(text)} sample='{text[:60].replace('\n',' ')}'")
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": (
                    f"You are a professional translator. Translate the user's text to {target_lang}. "
                    "Return ONLY the translated text with no quotes, no explanations, no preface, no bullets added. "
                    "Preserve punctuation; keep line breaks and list markers if present."
                )},
                {"role": "user", "content": text}
            ],
            max_tokens=1000
        )
        translated = response.choices[0].message.content.strip()
        logger.debug(f"Translated len={len(translated)} sample='{translated[:60].replace('\n',' ')}'")
        return translated
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text  # Return original if translation fails

if __name__ == '__main__':
    app.run(debug=True)
