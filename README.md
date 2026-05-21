# 📚 StudyAI — AI-Powered Student Productivity App

A full-stack Python web application that helps students study smarter
using AI. Upload your lecture notes or textbooks and get instant
summaries, key concepts, and flashcards powered by OpenAI GPT-4o.

---

## ✨ Features

- **User accounts** — register, login, logout with bcrypt password hashing
- **Document upload** — PDF, TXT, and DOCX support (up to 20 MB)
- **AI summaries** — GPT-4o condenses your documents into clear summaries
- **Key concepts** — automatically extracted topic terms
- **Flashcards** — AI-generated question/answer pairs with spaced repetition
- **Review sessions** — flip cards, mark correct/incorrect, track accuracy
- **Study statistics** — streak tracking, accuracy charts, topic breakdowns
- **Per-user isolation** — all data is private and scoped to your account

---

## 🗂️ Project Structure

```
student_productivity_app/
│
├── app.py                  # Streamlit entry point
├── auth.py                 # Registration, login, password hashing
├── database.py             # SQLAlchemy engine and session setup
├── models.py               # ORM table definitions
├── ai_engine.py            # OpenAI API integration
├── pdf_parser.py           # Document upload and text extraction
├── flashcards.py           # Flashcard logic and spaced repetition
├── dashboard.py            # Dashboard page
│
├── pages/
│   ├── __init__.py
│   ├── upload.py           # Upload page
│   ├── flashcard_review.py # Flashcard review page
│   ├── summaries.py        # Summaries page
│   └── settings.py         # Settings page
│
├── uploads/                # User-uploaded files (auto-created, gitignored)
├── database/               # SQLite database file (auto-created, gitignored)
│
├── .streamlit/
│   ├── config.toml         # Streamlit theme and server config
│   └── secrets.toml        # API keys for Streamlit Cloud (gitignored)
│
├── .env                    # Local development secrets (gitignored)
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Running Locally

### 1. Clone or download the project

```bash
git clone https://github.com/your-username/student-productivity-app.git
cd student-productivity-app
```

### 2. Create and activate a virtual environment

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your OpenAI API key

Open the `.env` file and replace the placeholder with your real key:

```
OPENAI_API_KEY=sk-your-real-key-here
```

Get a key at: https://platform.openai.com/api-keys

> **Note:** You need a paid OpenAI account with API access.
> New accounts get free credits to start with.

### 5. Run the app

```bash
streamlit run app.py
```

The app opens automatically at **http://localhost:8501**

The database and upload folders are created automatically on first run.

---

## 🧪 Running the Tests

Each module has a dedicated test script. Run them in order:

```bash
# Test database models
python test_db.py

# Test authentication
python test_auth.py

# Test PDF extraction (automated)
python test_pdf_parser.py

# Test PDF extraction (interactive — use a real file)
python test_pdf_interactive.py

# Test AI engine (uses mocked API calls — no key needed)
python test_ai_engine.py

# Test flashcard logic and spaced repetition
python test_flashcards.py
```

---

## ☁️ Deploying to Streamlit Community Cloud

Streamlit Community Cloud hosts Streamlit apps for free.

### 1. Push your code to GitHub

Make sure `.env`, `database/`, and `uploads/` are in `.gitignore`
(they already are). Then push:

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

### 2. Create a Streamlit Cloud account

Go to https://streamlit.io/cloud and sign in with GitHub.

### 3. Deploy the app

- Click **New app**
- Select your repository and branch
- Set **Main file path** to `app.py`
- Click **Deploy**

### 4. Add your secrets

- In your app dashboard, click **Settings → Secrets**
- Paste the following (with your real key):

```toml
OPENAI_API_KEY = "sk-your-real-key-here"
```

- Click **Save** — the app will restart automatically

> **Note on the database:** Streamlit Community Cloud has an
> ephemeral filesystem — the SQLite database resets on each
> redeploy. For a persistent production database, swap SQLite
> for PostgreSQL using the same SQLAlchemy models (just change
> the `DATABASE_URL` in `database.py`).

---

## 🔧 Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Frontend    | Streamlit 1.35                    |
| Backend     | Python 3.11+                      |
| Database    | SQLite via SQLAlchemy 2.0 ORM     |
| AI          | OpenAI GPT-4o API                 |
| PDF parsing | pdfplumber + pypdf (fallback)     |
| Auth        | bcrypt password hashing           |
| Config      | python-dotenv + st.secrets        |

---

## 📖 How to Use

1. **Register** an account on the login screen
2. **Upload** a PDF, TXT, or DOCX document on the Upload page
3. Click **Save & Extract Text** to parse the document
4. Click **Generate Summary & Flashcards** to run AI processing
5. Go to **Summaries** to read your AI summary and key concepts
6. Go to **Flashcard Review** to start a spaced-repetition session
7. Check your **Dashboard** to track streaks and progress

---

## 🔒 Security Notes

- Passwords are hashed with bcrypt (work factor 12) — never stored in plain text
- API keys are loaded from environment variables — never hardcoded
- All database queries are scoped to the logged-in `user_id` — users
  cannot access each other's data
- File uploads are validated for type and size before saving

---

## 🐛 Common Issues

**`ModuleNotFoundError: No module named 'pdfplumber'`**
→ Run `pip install -r requirements.txt` inside your virtual environment.

**`ValueError: OpenAI API key not found`**
→ Check your `.env` file has `OPENAI_API_KEY=sk-...` with no spaces around `=`.

**`streamlit: command not found`**
→ Make sure your virtual environment is activated: `source venv/bin/activate`

**PDF shows 0 words extracted**
→ The PDF may be image-based (scanned). These require OCR which is not
included. Try a text-based PDF instead.

**App resets data on Streamlit Cloud redeploy**
→ This is expected with SQLite on Streamlit Cloud's ephemeral filesystem.
See the deployment note above about switching to PostgreSQL.

---

## 🙏 Acknowledgements

Built with [Streamlit](https://streamlit.io), [OpenAI](https://openai.com),
[SQLAlchemy](https://sqlalchemy.org), [pdfplumber](https://github.com/jsvine/pdfplumber),
and [bcrypt](https://pypi.org/project/bcrypt/).
