# Run OnCons in VS Code

Open this folder in VS Code:

```powershell
code H:\oncons-pro-fixed-run\oncons-pro-fixed-run\oncons-pro
```

## Easiest VS Code terminal run

Open a VS Code terminal in the project root and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\run-vscode.ps1
```

Then open `http://localhost:5500`.

## Manual terminal run

Backend:

```powershell
cd H:\oncons-pro-fixed-run\oncons-pro-fixed-run\oncons-pro\backend
.\.venv312\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal:

```powershell
cd H:\oncons-pro-fixed-run\oncons-pro-fixed-run\oncons-pro\frontend
..\backend\.venv312\Scripts\python.exe -m http.server 5500
```

Then open:

```text
http://localhost:5500
```

The project includes `backend\.venv312`, and these commands use it directly so Python 3.14 does not break the local run.
