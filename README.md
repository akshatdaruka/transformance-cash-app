# Intelligent Cash Application Engine

## About The Project
Current finance workflows often involve manually checking a CSV bank feed against PDF invoices received via email. This is slow and error-prone. This MVP automates this using a Hybrid Parsing Engine:

1. Standard Engine: Uses rule-based logic (Regex) for known vendor formats. It is instant and accurate for fixed layouts.
2. Intelligent AI Engine: Uses Generative AI (Llama 3.2 Vision) to read unstructured, scanned, or unknown PDF formats just like a human would.

The system outputs validated Journal Entries ready for posting to an ERP system.

## Features
- Bank Ingestion: Parses standard CSV bank statements.
- Hybrid PDF Parsing: Automatically chooses between standard parsing and AI parsing based on user selection.
- Visual Reasoning: Uses Computer Vision to understand table structures in PDFs.
- Reconciliation Logic: Matches total amounts and generates split journal entries for multiple invoices in a single payment.
- Dockerized: Fully containerized for easy deployment.

## Prerequisites
Before running the application, ensure you have the following installed:

1. Docker Desktop (Recommended for easiest setup).
2. Ollama (Required for the AI features).
   - Download from the official Ollama website.
   - This application uses the llama3.2-vision model.
   - Run the following command in your terminal to prepare the model:
     ```bash
     ollama pull llama3.2-vision
     ```
   - Important: Ensure Ollama is running in the background (ollama serve).

## How to Run (Recommended: Docker)
This method ensures all dependencies (Python, Node.js, System Libraries) are isolated and correct.

1. Clone the Repository
   ```bash
   git clone <repository-url>
   cd transformance-cash-app
   ```

3. Start the Application
   Run the following command in the root directory:
   ```bash
   docker-compose up --build
   ```

5. Access the App
   - Frontend: Open http://localhost:5173 in your browser.
   - Backend API: Running on http://localhost:8000.

6. Debug Mode (Optional)
   If you want to attach a debugger (VS Code) to the running container:
   ```bash
   docker-compose -f docker-compose.yml -f docker-compose.debug.yml up
   ```

## How to Run (Manual / Without Docker)
If you prefer running it locally on your machine, follow these steps.

### 1. Backend Setup (Python)
- Navigate to the backend folder:
  ```bash
  cd backend
  ```

- Create a virtual environment:
  ```bash
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  ```

- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

- Run the server:
  ```bash
  uvicorn src.main:app --reload
  ```
  (The backend will start at http://127.0.0.1:8000)

### 2. Frontend Setup (React)
- Open a new terminal and navigate to the frontend folder:
  ```bash
  cd frontend
  ```

- Install dependencies:
  ```bash
  npm install
  ```

- Start the development server:
```bash
  npm run dev
```
  (The frontend will start at http://localhost:5173)

### 3. AI Configuration (Crucial)
If running without Docker, you must ensure the Backend can reach Ollama.
- Ensure Ollama is running.
- The default URL in src/parsers/ai_parser.py is configured for Docker (host.docker.internal).
- If running locally, you may need to update the base_url in that file to http://localhost:11434/v1.

## Usage Guide
1. Upload Bank Statement: Select the provided Sample Bank Statement.csv file.
2. Upload Remittance Advice: Select the provided Sample Payment Advice.pdf file.
3. Choose Mode:
   - Leave "Enable AI Parsing" unchecked to use the Standard Parser (Fast, for known layouts).
   - Check "Enable AI Parsing" to use the LLM (Slower, for unknown layouts).
4. Run: Click "Run Engine".
5. Review: See the generated Journal Entries in the table below.

## Future Scope
This project is currently an MVP. The following features are planned for the production version:

1. Database Integration: Implementing PostgreSQL to save tenant configurations, transaction history, and user roles.
2. Template Learning: A feedback loop where the AI learns the layout of a new vendor, creating a standard Regex template for future uploads to improve speed.
3. Math Guardrails: Adding strict deterministic checks to verify that the sum of extracted line items exactly matches the invoice total before processing.
4. Async Processing: Moving the PDF parsing to a background worker queue (Celery + Redis) to handle bulk uploads of files without freezing the user interface.
5. Order-to-Cash (O2C) Agent: A separate microservice to handle inbound email inquiries and disputes.
