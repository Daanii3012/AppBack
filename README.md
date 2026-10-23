# Split expenses app

FastAPI application to manage shared costs groups.

## Features
- User registration and login
- Group creation
- Membership invitations
- Expense tracking with share percentages
- Debt/balance summary
- Group chat messages

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Environment
Copy `.env.example` to `.env` and update values as needed.
