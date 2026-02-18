# 🔑 Dhan API Token - Automatic Refresh Setup

## 📋 Overview

Your trading dashboard now supports **automatic token refresh**! No more daily manual updates. The system will:

✅ **Auto-detect** token expiry (1 hour before expiration)  
✅ **Auto-refresh** using your API credentials  
✅ **Auto-update** `.env` file with new token  
✅ **Auto-retry** failed API calls after token refresh  

---

## 🚀 Quick Setup (First Time)

### 1️⃣ Generate Initial Token

Visit Dhan API Portal: https://api.dhan.co/

1. Login to your Dhan account
2. Go to API section
3. Generate new access token
4. Copy the following values:
   - Client ID
   - API Key
   - API Secret
   - Access Token

### 2️⃣ Update `.env` File

```bash
DHAN_CLIENT_ID=your_client_id_here
DHAN_API_KEY=your_api_key_here
DHAN_API_SECRET=your_api_secret_here
DHAN_ACCESS_TOKEN=your_access_token_here
DHAN_TOKEN_EXPIRY=2026-02-11T10:00:00  # Optional but recommended
```

**Important:** Set `DHAN_TOKEN_EXPIRY` to when your current token expires (usually 24 hours from generation time). Format: `YYYY-MM-DDTHH:MM:SS`

Example:
```bash
# If token generated on Feb 10, 2026 at 10:00 AM
DHAN_TOKEN_EXPIRY=2026-02-11T10:00:00
```

### 3️⃣ Start Dashboard

```bash
# Double-click this file
START_DASHBOARD.bat
```

That's it! 🎉

---

## 🔄 How Automatic Refresh Works

### Startup Check
When you start the dashboard, it checks:
- If token expiry time is set
- If token is expired or expiring within 1 hour
- If yes → **automatic refresh happens immediately**

### Runtime Check  
During operation:
- If API returns `401 Unauthorized` error
- System automatically refreshes token
- Retries the failed request with new token
- Updates `.env` file with new token & expiry

### Logs You'll See

✅ **Success:**
```
✅ Token refreshed successfully! Valid until 2026-02-11 10:00:00
```

⚠️ **Manual Action Needed:**
```
⚠️ Token refresh failed - manual intervention required
⚠️ Please manually generate token from Dhan portal and update .env
```

---

## 🛠️ Manual Token Update (If Needed)

If automatic refresh fails (e.g., API credentials changed):

### Option 1: Update via Dhan Portal
1. Visit https://api.dhan.co/
2. Generate new token
3. Update only `DHAN_ACCESS_TOKEN` in `.env`
4. Update `DHAN_TOKEN_EXPIRY` (24 hours from now)

### Option 2: Edit `.env` Directly
```bash
# Open .env file in notepad
notepad .env

# Update these lines:
DHAN_ACCESS_TOKEN=new_token_here
DHAN_TOKEN_EXPIRY=2026-02-12T10:00:00
```

---

## 📊 Token Lifecycle

```
Day 0, 10:00 AM → Token Generated
                   ↓
Day 1, 09:00 AM → Auto-refresh triggered (1 hour before expiry)
                   ↓
Day 1, 09:00 AM → New token saved to .env
                   ↓
Day 2, 09:00 AM → Next auto-refresh
                   ↓
                  ... (continues forever)
```

---

## ❓ FAQ

### Q: எத்தனை நாள்ல token expire ஆகும்?
**A:** Dhan tokens usually expire in **24 hours**. But with auto-refresh, you don't need to worry!

### Q: நான் daily login பண்ணனுமா?
**A:** இல்லை! Once configured, system handles everything automatically.

### Q: Auto-refresh fail ஆனா என்ன பண்றது?
**A:** System will log warning messages. Manually generate new token from Dhan portal and update `.env`.

### Q: Token expiry time தெரியலைன்னா?
**A:** No problem! System will still work. Just won't refresh preemptively. Will refresh when API returns 401 error.

### Q: Multiple trading bots run பண்ணலாமா same token-ல?
**A:** Yes, but they'll all share same token. One bot's refresh will update for all.

---

## 🔐 Security Best Practices

✅ **Never commit `.env` file to git**  
✅ **Keep API Secret safe** (needed for auto-refresh)  
✅ **Use `.env.example` for templates only**  
✅ **Don't share access tokens publicly**  

---

## 🐛 Troubleshooting

### Problem: "Token refresh failed: 401"
**Solution:** Your API credentials (Client ID, API Key, API Secret) might be wrong. Verify them in Dhan portal.

### Problem: "Missing environment variables"
**Solution:** Check if `.env` file exists and has all required fields.

### Problem: "Token expiry not set"
**Solution:** Add `DHAN_TOKEN_EXPIRY` to `.env` file. Format: `YYYY-MM-DDTHH:MM:SS`

### Problem: Server not starting
**Solution:** Check terminal output for errors. Common issues:
- Wrong Python environment
- Missing dependencies: `pip install -r requirements.txt`
- Port 8000 already in use

---

## 📞 Support

If automatic refresh doesn't work:
1. Check server logs in terminal
2. Verify API credentials in Dhan portal
3. Try manual token generation once
4. Restart dashboard with `START_DASHBOARD.bat`

---

**Happy Trading! 📈💰**
