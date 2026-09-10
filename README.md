# 🛡️ Global Lost & Found System with AI Anti-Scam Blind Verification

An intelligent item recovery web platform built with **Python Django** and clean, modern, lightweight **HTML, CSS, and vanilla JavaScript** (no Bootstrap or external CSS bloat).

---

## 🌟 Key Features & Anti-Scam Innovation

1. **Email OTP Verification**: Prevents bots and throwaway accounts from spamming fake claims.
2. **Hidden Details (Blind Escrow)**:
   - When finders post an item, they log secret identifying details (e.g., lockscreen wallpaper, internal pocket items, specific scratches, partial serial number).
   - These details are **strictly concealed** from the public and other users.
3. **Blind Challenge Verification**:
   - Claimants must answer the finder's challenge question blindly without seeing the answers in advance.
4. **AI Ownership Verification & Scoring**:
   - Compares claimant's answers against the finder's hidden details.
   - Powered by **Google Gemini API** (`gemini-2.5-flash`) with an **automatic local NLP heuristic fallback** (so it works 100% offline or without an API key).
   - Generates a **0–100% Match Score**, confidence classification (`HIGH`, `MODERATE`, `LOW`, `FRAUD_ALERT`), and itemized match/discrepancy reports.
5. **Safe Handover OTP**:
   - When a claim is accepted, the platform generates a unique 6-digit Handover PIN.
   - The finder enters this PIN at the physical exchange to officially mark the item as returned and award community reputation points.

---

## 🚀 Quick Start

### 1. Activate Environment & Run Server

```powershell
# From d:\SIH\CODE
.\.venv\Scripts\python manage.py runserver
```

Open your browser at `http://127.0.0.1:8000/`.

---

## 🔑 Demo Accounts (Pre-Seeded)

The database is pre-seeded with sample users and realistic items:

| Role | Username | Password | Email | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | `admin@lostandfound.local` | Verified Superuser |
| **Finder** | `priya_finder` | `testpass123` | `priya@example.com` | Verified User |
| **Claimant / Owner** | `rahul_owner` | `testpass123` | `rahul@example.com` | Verified User |

---

## 🧪 Testing the Anti-Scam AI Verification

1. **Log in as Finder (`priya_finder`)**:
   - Check the **Brown Leather Wildhorn Wallet** listing. Notice that you can see your private hidden details (SBI card number, photo of elderly couple).
2. **Log in as Claimant (`rahul_owner`)** (or create a new user):
   - Browse listings, click on the **Brown Leather Wallet**.
   - Notice the private details are **completely hidden**.
   - Click **"Submit Ownership Claim"**.
   - **Test High Match**: Enter *"The wallet has an SBI debit card ending in 4102 and a photo of an elderly couple in the slot."* -> **AI Score: 85-95% (HIGH)**.
   - **Test Scammer Match**: Enter *"It is my wallet with 2000 rupees and a gym card."* -> **AI Score: 10-25% (LOW / FRAUD ALERT)**.
3. **Finder Reviews Claim**:
   - Log back in as `priya_finder`.
   - Go to your Dashboard (`/accounts/profile/`), review the AI report, and click **Accept Claim**.
   - Use the claimant's 6-digit Handover PIN to officially finalize the return!

---

## 🧪 Automated Tests

Run the test suite at any time:

```powershell
.\.venv\Scripts\python manage.py test
```
