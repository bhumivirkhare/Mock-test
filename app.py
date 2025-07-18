from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import os
import docx
import PyPDF2
import google.generativeai as genai

# --- CONFIG ---
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  # or hardcode like: "genai.configure(api_key='your-key')"

# --- APP SETUP ---
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- HELPERS ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    if ext == 'txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    elif ext == 'docx':
        doc = docx.Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])
    elif ext == 'pdf':
        text = ""
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    return ""

def ask_gemini(policy_text, user_input):
    prompt = f"""
You are an insurance advisor AI. Based on the user's request, match the most relevant section in the insurance policy and return a structured JSON object with the following:

- decision: "approved" or "denied"
- amount: covered amount or null
- justification: brief summary based on the matched section

### POLICY TEXT ###
{policy_text[:3000]}

### USER INPUT ###
{user_input}

### RESPONSE FORMAT ###
{{
  "decision": "...",
  "amount": "...",
  "justification": "..."
}}
"""

    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(prompt)
    return response.text.strip()

# --- ROUTES ---
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    if 'file' not in request.files or 'user_input' not in request.form:
        return jsonify({"error": "Missing file or user input"}), 400

    file = request.files['file']
    user_input = request.form['user_input']

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        policy_text = extract_text(filepath)
        response_json = ask_gemini(policy_text, user_input)
        return jsonify(eval(response_json))  # assumes Gemini returns clean JSON string
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- MAIN ---
if __name__ == "__main__":
    app.run(debug=True)
