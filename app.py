from flask import Flask, request, render_template, send_file
import os
import fitz
from openai import AzureOpenAI
from dotenv import load_dotenv

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
    
    # Save uploaded file temporarily
    temp_path = "/tmp/upload.pdf"
    file.save(temp_path)
    
    # Translate PDF
    translated_pdf_path = translate_pdf(temp_path, lang)
    
    # Clean up temp file
    os.remove(temp_path)
    
    # Send translated PDF
    return send_file(translated_pdf_path, as_attachment=True, download_name="translated.pdf")

def translate_pdf(pdf_path, target_lang):
    doc = fitz.open(pdf_path)
    new_doc = fitz.open()
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text_dict = page.get_text("dict")
        
        # Create new page with same dimensions
        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
        
        # Copy text blocks with translation
        for block in text_dict['blocks']:
            if block['type'] == 0:  # Text block
                for line in block['lines']:
                    for span in line['spans']:
                        text = span['text']
                        bbox = span['bbox']
                        font_size = span['size']
                        
                        # Translate text
                        translated_text = translate_text(text, target_lang)
                        
                        # Insert translated text at original position
                        new_page.insert_text(
                            (bbox[0], bbox[3]),  # Bottom-left of bbox
                            translated_text, 
                            fontsize=font_size
                        )
    
    output_path = "/tmp/translated.pdf"
    new_doc.save(output_path)
    new_doc.close()
    doc.close()
    return output_path

def translate_text(text, target_lang):
    if not text.strip():
        return text
    
    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": f"You are a professional translator. Translate the following text to {target_lang}. Maintain the original meaning, tone, and formatting as much as possible."},
                {"role": "user", "content": text}
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return original if translation fails

if __name__ == '__main__':
    app.run(debug=True)
