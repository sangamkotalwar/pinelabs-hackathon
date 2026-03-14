# PayChat — B2B Telegram Payment System

> Hackathon project: A Telegram-based B2B payment bot where businesses can collect and pay invoices using Pine Labs.

---

## Architecture

```
Telegram Bot
    ↓
FastAPI Backend (Python)
    ↓
├── Invoice Service (+ AWS Bedrock OCR for handwritten invoices)
├── Payment Service (Pine Labs UAT)
├── Refund Service
└── Webhook Service (Telegram notifications)
    ↓
SQLite Database
    ↓
Flutter Dashboard (Web/Mobile)
```

---

## Features

### For Merchant (Invoice Sender)
- Upload handwritten or printed invoice images → AWS Bedrock reads them automatically
- Create invoices manually with amount and description
- Send payment requests to vendors via Telegram
- View all sent invoices and their status
- Issue refunds on paid invoices
- Resend payment links
- View balance dashboard

### For Vendor (Invoice Receiver)
- Receive Telegram notifications when invoices are sent
- Click payment link to pay via Pine Labs
- View pending payments with `/pending` command
- See confirmation upon payment

### Demo Mode
- `POST /demo/pay/{invoice_number}` — Simulate a payment success
- Demo payment page at `GET /demo/pay/{invoice_number}`

---

## Project Structure

```
paychat/
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app + all API routes
│   │   ├── database.py         # SQLAlchemy + SQLite setup
│   │   ├── models.py           # DB models: Merchant, Invoice, Payment, Refund
│   │   ├── telegram_bot.py     # Telegram bot long-polling handler
│   │   ├── invoice_service.py  # Invoice CRUD + balance logic
│   │   ├── payment_service.py  # Pine Labs payment link generation
│   │   ├── refund_service.py   # Refund flow
│   │   ├── webhook_service.py  # Telegram notification helpers
│   │   ├── pinelabs_client.py  # Pine Labs UAT API client
│   │   └── bedrock_client.py   # AWS Bedrock Claude OCR client
│   ├── requirements.txt
│   └── .env.example
│
└── frontend/
    └── paychat_dashboard/      # Flutter app
        ├── lib/
        │   ├── main.dart
        │   ├── config.dart
        │   ├── models/
        │   ├── services/
        │   └── screens/
        │       ├── login_screen.dart
        │       ├── dashboard_screen.dart
        │       ├── invoice_list_screen.dart
        │       ├── create_invoice_screen.dart
        │       ├── payment_status_screen.dart
        │       └── refund_screen.dart
        └── pubspec.yaml
```

---

## Setup & Run

### Prerequisites
- Python 3.10+
- Flutter 3.x (for dashboard)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Pine Labs UAT credentials
- AWS credentials with Bedrock access (Claude 3 Sonnet)

### Backend

```bash
cd backend

# Copy and fill environment variables
cp .env.example .env
# Edit .env with your actual credentials

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API docs will be available at: http://localhost:8000/docs

### Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `PINELABS_BASE_URL` | Pine Labs UAT: `https://uat.pinelabs.com` |
| `PINELABS_CLIENT_ID` | Pine Labs client ID |
| `PINELABS_CLIENT_SECRET` | Pine Labs client secret |
| `PINELABS_MERCHANT_ID` | Pine Labs merchant ID |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `BEDROCK_MODEL_ID` | Bedrock model (default: `anthropic.claude-3-sonnet-20240229-v1:0`) |
| `APP_BASE_URL` | Public URL for webhooks/payment links |

### Flutter Dashboard

```bash
cd frontend/paychat_dashboard

# Get dependencies
flutter pub get

# Run (web for hackathon demo)
flutter run -d web-server --web-port 3000

# Or build web
flutter build web
```

Configure API URL via `--dart-define`:
```bash
flutter run --dart-define=API_BASE_URL=http://your-server:8000
```

---

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Register and see welcome message |
| `/myid` | Get your Telegram Chat ID |
| `/register BusinessName [email] [phone]` | Update business profile |
| `/invoice <vendor_chat_id> <amount> [description]` | Create manual invoice |
| `/pending` | View pending invoices (to pay) |
| `/balance` | View balance summary |
| `/refund [invoice_id] [reason]` | Issue a refund |

Upload a photo/document directly to the bot to auto-parse an invoice with AI.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/merchant/register` | Register a merchant |
| GET | `/merchant/{chat_id}` | Get merchant info |
| GET | `/merchants` | List all merchants |
| POST | `/invoice/create` | Create invoice manually |
| POST | `/invoice/upload` | Upload invoice image (OCR) |
| GET | `/invoice/pending?chat_id=` | Get pending invoices |
| GET | `/invoice/sent?chat_id=` | Get sent invoices |
| GET | `/invoice/balance/{chat_id}` | Get balance summary |
| GET | `/invoice/{id}` | Get invoice details |
| POST | `/invoice/refund` | Issue a refund |
| POST | `/payment/webhook` | Pine Labs payment webhook |
| POST | `/payment/resend` | Resend payment link |
| POST | `/demo/pay/{ref}` | Simulate payment (demo) |
| GET | `/demo/pay/{ref}` | Demo payment page |
| GET | `/dashboard/{chat_id}` | Full dashboard data |
| GET | `/health` | Health check |

---

## Demo Flow (Hackathon)

1. Start the backend: `uvicorn app.main:app --reload`
2. Register two merchants via Telegram (`/start`) or API
3. Merchant1 uploads or creates an invoice for Merchant2
4. Payment link is generated and sent via Telegram
5. Simulate payment: `POST /demo/pay/{invoice_number}` or visit `GET /demo/pay/{invoice_number}`
6. Both merchants receive Telegram confirmation
7. View on Flutter dashboard

---

## Payment Flow

```
Merchant uploads invoice
        ↓
AWS Bedrock reads invoice (OCR)
        ↓
Invoice record created in DB
        ↓
Pine Labs payment link generated
        ↓
Vendor receives Telegram message with Pay Now link
        ↓
Vendor clicks → Pine Labs checkout page
        ↓
Payment success → webhook fires
        ↓
Invoice marked as PAID in DB
        ↓
Both parties receive Telegram confirmation
        ↓
Dashboard updated in real-time
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python FastAPI + Uvicorn |
| Bot | python-telegram-bot (long-polling) |
| Database | SQLite + SQLAlchemy ORM |
| OCR | AWS Bedrock (Claude 3 Sonnet) |
| Payments | Pine Labs UAT APIs |
| Frontend | Flutter (Material 3) |
| Notifications | Telegram Bot API |


Contributors
[@sangamkotalwar](https://github.com/sangamkotalwar)
[@manojpant](https://github.com/manojpant)
[@vimalkaurani](https://github.com/vimalkaurani)
