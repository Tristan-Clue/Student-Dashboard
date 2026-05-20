# 🚀 Student Productivity Dashboard — Setup & Running Guide

This is a complete AI-powered student productivity web application built with Python and Streamlit.

## ✨ Features

- 📚 **Document Upload** — Upload PDF, TXT, and DOCX files
- 🤖 **AI Processing** — Automatic summarization, concept extraction, and flashcard generation
- 🎴 **Interactive Flashcards** — Study with flip cards and track your progress
- 📊 **Dashboard** — View your study statistics and recent activity
- 🔐 **Authentication** — Secure login with bcrypt password hashing
- 💾 **Database** — SQLAlchemy ORM with SQLite storage

## 📋 Prerequisites

- **Python 3.11+** installed
- **pip** (Python package manager)
- An **OpenAI API key** (get it from https://platform.openai.com/account/api-keys)

## 🛠️ Installation

### Step 1: Clone or download the project

```bash
cd /path/to/Student-Dashboard
```

### Step 2: Create a virtual environment (recommended)

```bash
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set up environment variables

Copy the example `.env` file and add your OpenAI API key:

```bash
cp .env.example .env
```

Then edit `.env` and add your API key:

```
OPENAI_API_KEY=sk-your-actual-api-key-here
```

**⚠️ SECURITY:** Never commit `.env` to git. It's already in `.gitignore`.

### Step 5: Database initialization (automatic!)

The database is **created automatically** when you first run the app:
- Tables are created from SQLAlchemy models
- No manual `python init_db.py` needed
- Safe to run multiple times (only creates missing tables)
- SQLite file stored in `database/app.db`

## ▶️ Running the Application

### Start the Streamlit server:

```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`

**First run note:** On the first run, the app will automatically:
- Create the `database/` directory
- Create `database/app.db` (SQLite database)
- Create all necessary tables (users, uploads, summaries, flashcards, etc.)

This all happens automatically — just wait a moment for the app to load!

### From command line:

```bash
# Show the URL in terminal instead of opening browser
streamlit run app.py --logger.level=info

# Run on a specific port
streamlit run app.py --server.port 8502

# Disable file watcher (useful for remote servers)
streamlit run app.py --client.toolbarMode=minimal
```

## 🎯 First Steps

1. **Create an Account**
   - Click "Register" on the login screen
   - Enter username, email, and password (min 6 characters)

2. **Upload a Document**
   - Go to "📤 Upload Documents"
   - Select a PDF, TXT, or DOCX file
   - Click "⚙️ Process Document"

3. **Wait for AI Processing**
   - The app will:
     - Extract text from your document
     - Generate a summary
     - Extract key concepts
     - Create study flashcards
   - This takes 30-60 seconds depending on document length

4. **Study!**
   - Go to "🎴 Study Flashcards" to review cards
   - Go to "📝 View Summaries" to read summaries
   - Track your progress on the "📊 Dashboard"

## 📁 Project Structure

```
Student-Dashboard/
├── app.py                  # Main entry point & navigation
├── auth.py                 # Authentication & session management
├── database.py             # SQLAlchemy setup & connection
├── models.py               # Database models (User, Upload, etc.)
├── ai_engine.py            # OpenAI API integration
├── pdf_parser.py           # Document upload & text extraction
├── pages/
│   ├── dashboard.py        # Home page with stats
│   ├── upload.py           # Upload & process documents
│   ├── flashcards.py       # Study flashcards
│   ├── summaries.py        # View summaries
│   └── settings.py         # User settings
├── database/               # SQLite database file (created at runtime)
├── uploads/                # User-uploaded files (organized by user ID)
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (NEVER commit this!)
├── .env.example            # Example env file (safe to commit)
├── .gitignore              # Git ignore rules
└── README.md              # This file
```

## 🧪 Testing

### Test individual modules:

```bash
# Test database setup
python test_db.py

# Test AI engine (mocked API calls)
python test_ai_engine.py
```

Both test files use mocked API responses, so they run instantly without costs or API key.

## 🔑 Environment Variables

Create a `.env` file (copy from `.env.example`):

```
# Required
OPENAI_API_KEY=sk-your-key-here

# Optional
# DATABASE_PATH=/custom/path/to/database.db
# STREAMLIT_SERVER_PORT=8501
```

## 🚀 Deployment

### Streamlit Community Cloud (Recommended for students)

1. Push your code to GitHub (with `.env` in `.gitignore`)
2. Go to https://share.streamlit.io
3. Connect your GitHub account
4. Select this repo and main branch
5. Add your `OPENAI_API_KEY` in the "Secrets" section
6. Deploy! 🎉

### Other platforms (Heroku, Railway, Render, etc.)

1. Follow platform-specific deployment guides
2. Set environment variables in platform dashboard (never in code!)
3. Ensure Python 3.11+ is available
4. Run: `streamlit run app.py`

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'streamlit'"

→ Make sure you installed requirements: `pip install -r requirements.txt`

### "OpenAI API key not found"

→ Check that `.env` file exists and has `OPENAI_API_KEY=sk-...`
→ On Streamlit Cloud, add the key in the "Secrets" section

### "Database is locked"

→ This usually means multiple instances are accessing the DB
→ Close all running instances and try again
→ For production, consider using PostgreSQL instead of SQLite

### "CORS error" or "Connection refused"

→ Make sure Streamlit is running: `streamlit run app.py`
→ Check that port 8501 is not blocked by firewall

### Large PDFs take too long or timeout

→ The app chunks large documents automatically
→ Some PDFs with poor formatting extract text slowly
→ Consider reducing file size or using TXT format

## 📚 Code Quality

This project follows Python best practices:

- ✅ Clear, commented code suitable for a portfolio
- ✅ Modular architecture (separate files for each feature)
- ✅ Type hints for function arguments and returns
- ✅ Comprehensive error handling
- ✅ Security best practices (password hashing, env vars, no hardcoded secrets)

## 🤝 Contributing

This is a student portfolio project. Feel free to extend it with:

- Additional AI features (question generation, study plans)
- More export formats (PDF summaries, ANKI deck exports)
- Statistics and analytics
- Spaced repetition scheduling
- Dark mode / theme customization
- Mobile-friendly redesign

## 📄 License

This project is open source and available for educational use.

## ❓ FAQ

**Q: Can I use this for free?**
→ The Streamlit app is free, but you need an OpenAI API key. OpenAI offers $5 free credits for new users.

**Q: How much does it cost to run?**
→ Costs depend on API usage. A typical student using it 2-3 times per week might spend $2-5/month.

**Q: Can I add more file formats (Word, PowerPoint)?**
→ Yes! See `pdf_parser.py` and add extraction logic for additional formats.

**Q: How do I export flashcards?**
→ Currently they're stored in the database. You could add ANKI or CSV export features.

**Q: Can I host this myself?**
→ Yes! It works on any server with Python 3.11+. See deployment section above.

---

**Happy studying! 📚✨**
