# PDF Resume Upload Feature - Implementation Guide

## 📋 Overview

Adding PDF resume upload to Hammy the Hire Tracker is **straightforward** and would take approximately **1-2 hours** of development time.

## 🎯 What You'll Get

- Upload PDF resumes directly from the UI
- Automatic text extraction from PDFs
- Same resume management features as text resumes
- Support for multi-page resumes
- Error handling for corrupted/image-only PDFs

## 🛠️ Implementation Requirements

### Python Libraries Needed

Add to `requirements-local.txt`:
```txt
# PDF text extraction
pypdf>=3.17.0          # Recommended - modern, maintained
# OR
PyPDF2>=3.0.0          # Alternative - widely used
# OR
pdfplumber>=0.10.0     # Best for complex layouts
# OR
PyMuPDF>=1.23.0        # Fastest, most accurate (fitz)
```

**Recommended:** `pypdf` - It's modern, actively maintained, and handles most PDFs well.

### Backend Changes Needed

#### 1. Add PDF Upload Endpoint (`local_app.py`)

```python
from pypdf import PdfReader
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from PDF file."""
    try:
        reader = PdfReader(pdf_file)
        text = []
        for page in reader.pages:
            text.append(page.extract_text())
        return '\n\n'.join(text)
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")

@app.route('/api/resumes/upload', methods=['POST'])
def upload_resume():
    """Upload and process a PDF or text resume."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only PDF, TXT, MD allowed'}), 400

    try:
        filename = secure_filename(file.filename)

        # Extract text based on file type
        if filename.endswith('.pdf'):
            resume_text = extract_text_from_pdf(file)
        else:
            resume_text = file.read().decode('utf-8')

        # Get metadata from form
        name = request.form.get('name', filename.rsplit('.', 1)[0])
        focus_areas = request.form.get('focus_areas', '')
        target_roles = request.form.get('target_roles', '')

        # Save to database (same as text resume)
        resume_id = str(uuid.uuid4())
        conn = get_db()
        conn.execute('''
            INSERT INTO resumes (
                resume_id, name, focus_areas, target_roles,
                content, file_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            resume_id, name, focus_areas, target_roles,
            resume_text, filename,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        conn.commit()

        return jsonify({
            'success': True,
            'resume_id': resume_id,
            'name': name,
            'text_length': len(resume_text),
            'pages_extracted': resume_text.count('\n\n') + 1
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

#### 2. Update Database Schema (if needed)

Add `file_path` column to resumes table to track original filename:

```sql
ALTER TABLE resumes ADD COLUMN file_path TEXT;
```

### Frontend Changes Needed

#### Update `App.jsx` Resume Upload Modal

```jsx
// Add file input to ResumeUploadModal component
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Upload Resume File (PDF, TXT, MD)
  </label>
  <input
    type="file"
    accept=".pdf,.txt,.md"
    onChange={(e) => handleFileUpload(e.target.files[0])}
    className="w-full px-3 py-2 border rounded-lg"
  />
</div>

// OR manually paste text
<div>
  <label className="block text-sm font-medium text-gray-700 mb-1">
    Or Paste Resume Text *
  </label>
  <textarea
    placeholder="Paste your resume text here..."
    value={formData.content}
    onChange={(e) => setFormData({ ...formData, content: e.target.value })}
    className="w-full px-3 py-2 border rounded-lg font-mono text-sm"
    rows={12}
  />
</div>

// Handle file upload
const handleFileUpload = async (file) => {
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', formData.get('name') || file.name.replace(/\.[^.]+$/, ''));
  formData.append('focus_areas', formData.get('focus_areas') || '');
  formData.append('target_roles', formData.get('target_roles') || '');

  const response = await fetch('/api/resumes/upload', {
    method: 'POST',
    body: formData
  });

  const data = await response.json();

  if (data.success) {
    alert(`Resume uploaded! Extracted ${data.text_length} characters from ${data.pages_extracted} pages.`);
    onSave();
    onClose();
  }
};
```

## 🚀 Implementation Steps

### Step 1: Install PDF Library (5 minutes)
```bash
pip install pypdf
```

### Step 2: Add Backend Code (30 minutes)
- Add `extract_text_from_pdf()` function
- Create `/api/resumes/upload` endpoint
- Add file validation and error handling
- Test with sample PDF

### Step 3: Update Frontend (30 minutes)
- Add file input to ResumeUploadModal
- Implement file upload handler
- Add loading states and error messages
- Style the upload button

### Step 4: Testing (15 minutes)
- Test with various PDF formats
- Test with multi-page PDFs
- Test error handling (corrupted PDFs, image-only PDFs)
- Verify text extraction quality

## ⚠️ Limitations & Considerations

### PDF Text Extraction Challenges

1. **Image-only PDFs**: If resume is scanned as images, text extraction won't work
   - **Solution**: Use OCR library like `pytesseract` or `easyocr`
   - Adds 15-30 min development time

2. **Complex Layouts**: Some PDFs with columns/tables may extract text out of order
   - **Solution**: Use `pdfplumber` instead of `pypdf` (better layout preservation)
   - Same implementation time

3. **Password-Protected PDFs**: Won't work without password
   - **Solution**: Add password input field, pass to PDF reader
   - Adds 5-10 min development time

### Storage Considerations

- Extracted text is stored in database (not the PDF file itself)
- Original PDF filename is saved for reference
- If you want to store actual PDF files:
  - Create `uploads/` directory
  - Save PDFs with unique filenames
  - Add 10-15 min development time

## 📦 Library Comparison

| Library | Speed | Accuracy | Complexity | Recommendation |
|---------|-------|----------|------------|----------------|
| **pypdf** | Fast | Good | Low | ✅ **Best choice** - Modern, simple |
| PyPDF2 | Fast | Good | Low | ⚠️ Older, less maintained |
| pdfplumber | Medium | Excellent | Medium | ✅ Best for complex layouts |
| PyMuPDF (fitz) | Very Fast | Excellent | Medium | ✅ Best for performance |

## 🎨 UI Enhancement Ideas (Optional)

- Drag-and-drop PDF upload
- PDF preview before uploading
- Progress bar for large files
- Bulk PDF upload (upload multiple at once)
- Resume template suggestions based on extracted content

## 🔒 Security Considerations

- Validate file size (limit to 5-10MB)
- Sanitize filenames with `secure_filename()`
- Limit allowed file extensions
- Scan for malicious content (optional - use `python-magic`)
- Rate limit uploads to prevent abuse

## 💡 Recommended Implementation

```bash
# 1. Install library
pip install pypdf

# 2. Add to requirements-local.txt
echo "pypdf>=3.17.0" >> requirements-local.txt

# 3. Add backend endpoint (copy code from above)

# 4. Add frontend file input (copy code from above)

# 5. Test with your resume PDF

# Total time: ~1-2 hours
```

## 🎯 Next Steps After PDF Upload

Once PDF upload is working, you could add:

1. **Resume templates** - Provide sample resume formats
2. **AI resume analysis** - Let Claude review resume for improvements
3. **ATS optimization** - Check resume for ATS-friendly formatting
4. **Skills extraction** - Auto-populate focus_areas from resume text
5. **Resume comparison** - Compare multiple resume versions

---

**Difficulty:** ⭐⭐☆☆☆ (Easy)
**Time Required:** 1-2 hours
**Value Added:** High - Makes resume management much more convenient
