from flask import Flask, request, render_template, send_file
import os
import fitz
from openai import AzureOpenAI
from dotenv import load_dotenv
import tempfile

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
        
        # Create new page with same dimensions
        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
        
        # Copy the original page content (preserves images, backgrounds, etc.)
        new_page.show_pdf_page(new_page.rect, doc, page_num)
        
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
        
        # Overlay translated text
        for block in text_dict['blocks']:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    for span in line['spans']:
                        text = span['text']
                        bbox = span['bbox']
                        font_size = span['size']
                        
                        # Translate text
                        translated_text = translate_text(text, target_lang)
                        
                        # Cover original text with white rectangle
                        rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                        new_page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                        
                        # Insert translated text in the same bounding box
                        new_page.insert_textbox(rect, translated_text, fontsize=font_size, align=0)
    
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
