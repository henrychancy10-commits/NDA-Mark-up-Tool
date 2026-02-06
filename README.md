# NDA Markup Tool

Web application that analyzes NDA documents against markup guidelines using Claude AI and generates redlined Word documents with tracked changes.

## Features

- **Document Markup Engine**: Generates .docx files with simulated track changes
  - Red strikethrough for deletions
  - Blue underline for insertions
  - Word comments with rationale
- **Claude AI Analysis**: Analyzes NDAs against your markup guidelines
- **Three Markup Modes**: Full, balanced, or critical-only
- **Change Review UI**: Approve/reject individual changes before generating
- **Multiple Format Support**: Guidelines in PDF, Word, or plain text

## Architecture

```
backend/
  app/
    api/routes.py          # Flask REST API endpoints
    services/
      document_markup.py   # Core .docx markup engine (python-docx)
      claude_analyzer.py   # Claude API integration
      guideline_parser.py  # PDF/Word/text guideline extraction
    models/database.py     # SQLite models
  tests/                   # Unit and integration tests
  run.py                   # Flask entry point

frontend/
  src/
    components/            # React components (Layout, FileUpload, ChangeReview)
    pages/                 # HomePage, ProjectPage, DocumentPage
    services/api.js        # API client
```

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
python run.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### Running Tests

```bash
cd backend
PYTHONPATH=. python tests/test_document_markup.py
PYTHONPATH=. python tests/test_integration.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/projects` | Create project |
| GET | `/api/projects` | List projects |
| GET | `/api/projects/:id` | Get project with docs and guidelines |
| POST | `/api/projects/:id/guidelines` | Upload markup guidelines |
| POST | `/api/projects/:id/documents` | Upload NDA document |
| GET | `/api/documents/:id` | Get document with changes |
| POST | `/api/documents/:id/analyze` | Run Claude analysis |
| POST | `/api/documents/:id/generate` | Generate marked-up document |
| GET | `/api/documents/:id/download` | Download marked-up .docx |
| POST | `/api/changes/:id/approve` | Approve a change |
| POST | `/api/changes/:id/reject` | Reject a change |
| POST | `/api/quick-markup` | All-in-one: upload, analyze, generate |

## How It Works

1. **Upload guidelines** describing your markup rules
2. **Upload an NDA** (.docx) to analyze
3. **Claude analyzes** the NDA and produces structured change recommendations
4. **Review changes** - approve or reject each one individually
5. **Generate markup** - creates a .docx with visual track changes
6. **Download** the redlined document and open in Microsoft Word
