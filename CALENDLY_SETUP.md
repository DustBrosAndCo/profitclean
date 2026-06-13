# Calendly Integration Setup Guide

## Overview
This guide helps you set up Calendly OAuth integration for ProfitClean. Once configured, all users in your company can sync their Calendly bookings directly into the app.

---

## Part 1: Get Calendly OAuth Credentials

### Prerequisites
- Calendly account (any plan)
- Access to Calendly integrations

### Steps

1. **Go to Calendly Applications**
   - Open https://calendly.com/integrations/applications
   - Sign in if prompted

2. **Create a New Application**
   - Click "Create New Application"
   - Fill in the form:
     - **Application Name**: "ProfitClean"
     - **Description**: "Syncs bookings with ProfitClean"
     - **Logo**: (optional)

3. **Set Redirect URI**
   - This is where Calendly sends users after they authorize
   - **For Local Development**: `http://localhost:8501`
   - **For Streamlit Cloud**: `https://profitclean-xxxx.streamlit.app` (your exact app URL)

4. **Copy Your Credentials**
   - After creating, you'll see:
     - **Client ID** (looks like: `abc123def456`)
     - **Client Secret** (looks like: `xyz789uvw012`)
   - Keep these safe - don't share publicly

---

## Part 2: Configure ProfitClean

### Option A: Local Development

1. **Create secrets file**
   ```bash
   cd d:\DBAPP
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml
   ```

2. **Edit `.streamlit/secrets.toml`**
   ```toml
   CALENDLY_CLIENT_ID = "your_client_id_from_step_1_part_4"
   CALENDLY_CLIENT_SECRET = "your_client_secret_from_step_1_part_4"
   CALENDLY_REDIRECT_URI = "http://localhost:8501"
   ```

3. **Restart Streamlit**
   ```bash
   streamlit run app.py
   ```

### Option B: Streamlit Cloud (Production)

1. **Go to your app settings**
   - Click "Manage app" (bottom right)
   - Select "Settings"
   - Go to "Secrets"

2. **Add three secrets**
   ```
   CALENDLY_CLIENT_ID = "your_client_id"
   CALENDLY_CLIENT_SECRET = "your_client_secret"
   CALENDLY_REDIRECT_URI = "https://profitclean-xxxx.streamlit.app"
   ```

3. **Save and wait for redeploy**
   - Changes take effect automatically

---

## Part 3: Test the Integration

1. **Go to Integration Hub**
   - Log in to ProfitClean
   - Click "🔌 Integration Hub"

2. **Connect Calendly**
   - Find the Calendly card
   - Click "🔌 Connect Calendly"

3. **Authorize**
   - You'll be redirected to Calendly
   - Click "Allow"
   - You'll return to ProfitClean automatically

4. **Verify Connection**
   - You should see "✅ Connected"
   - Last sync timestamp will appear

---

## Troubleshooting

### "Calendly OAuth is not configured"
- Check `.streamlit/secrets.toml` exists and has all three values
- Restart Streamlit: `Ctrl+C` then `streamlit run app.py`
- Verify values don't have extra spaces

### "OAuth failed: 401"
- Check Client ID and Secret are correct
- Make sure you copied the entire values (no partial copies)

### "redirect_uri mismatch"
- Your `CALENDLY_REDIRECT_URI` must match exactly what you set in Calendly
- Include the protocol (`http://` or `https://`)
- For localhost, use `http://localhost:8501` (not `http://127.0.0.1:8501`)

### Connection succeeds but no bookings import
- Calendly needs at least one scheduled event to sync
- Give the sync 10-20 seconds to fetch from Calendly API
- Check Integration Hub → "🔄 Sync" button

---

## Security Notes

✅ **Tokens are encrypted** - All Calendly tokens stored in database are encrypted  
✅ **Company-isolated** - Users can only see their company's Calendly calendar  
✅ **No calendar access** - ProfitClean only sees booking details, not full calendar  
✅ **Revokable** - Users can disconnect at any time  

To revoke access:
1. Go to https://calendly.com/settings/integrations
2. Find ProfitClean
3. Click "Disconnect"

---

## Next Steps

Once Calendly is working:
- Set up additional integrations (Acuity, Google Calendar, Stripe)
- Configure email syncing
- Set up automated booking follow-ups

For help: Check app logs or contact support
