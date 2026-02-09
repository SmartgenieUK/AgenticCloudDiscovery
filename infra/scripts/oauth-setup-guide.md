# OAuth Application Setup Guide

This guide walks you through setting up OAuth applications for Google and Microsoft authentication.

## Prerequisites

- Azure subscription set up (run `setup-azure.ps1` first)
- Access to Google Cloud Console and Azure Portal

---

## Part 1: Google OAuth Setup

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter project name: `Agentic Cloud Discovery`
4. Click **Create**

### Step 2: Enable Google+ API

1. In the left sidebar, go to **APIs & Services** → **Library**
2. Search for `Google+ API`
3. Click **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** (for testing with personal accounts)
3. Click **Create**
4. Fill in the form:
   - **App name**: `Agentic Cloud Discovery`
   - **User support email**: Your email
   - **Developer contact**: Your email
5. Click **Save and Continue**
6. On **Scopes** page, click **Add or Remove Scopes**
   - Add: `openid`, `email`, `profile`
7. Click **Save and Continue**
8. On **Test users** page, add your email address
9. Click **Save and Continue**

### Step 4: Create OAuth Client ID

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `Agentic Cloud Discovery Web`
5. **Authorized redirect URIs**: Add these URLs:
   ```
   http://localhost:8000/auth/oauth/google/callback
   https://<your-orchestrator-url>/auth/oauth/google/callback
   ```
   *(Replace `<your-orchestrator-url>` with your Azure Container App URL after Phase 3)*
6. Click **Create**
7. **Copy the Client ID and Client Secret** - you'll need these next

### Step 5: Save Google Credentials

Copy your credentials for the next step:
```
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<your-client-secret>
```

---

## Part 2: Microsoft OAuth Setup

### Step 1: Register Application in Azure AD

1. Go to [Azure Portal](https://portal.azure.com/)
2. Search for **Azure Active Directory** (or **Entra ID**)
3. Click **App registrations** → **New registration**
4. Fill in the form:
   - **Name**: `Agentic Cloud Discovery`
   - **Supported account types**: `Accounts in any organizational directory and personal Microsoft accounts`
   - **Redirect URI**: Select **Web** and enter:
     ```
     http://localhost:8000/auth/oauth/microsoft/callback
     ```
5. Click **Register**

### Step 2: Add Additional Redirect URIs

1. In your app registration, go to **Authentication**
2. Under **Web** → **Redirect URIs**, click **Add URI**
3. Add your production URL:
   ```
   https://<your-orchestrator-url>/auth/oauth/microsoft/callback
   ```
4. Under **Implicit grant and hybrid flows**, check:
   - ✅ **ID tokens**
5. Click **Save**

### Step 3: Create Client Secret

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Description: `Orchestrator Secret`
4. Expires: `24 months` (recommended)
5. Click **Add**
6. **Copy the secret VALUE immediately** (you can't view it again!)

### Step 4: Configure API Permissions

1. Go to **API permissions**
2. Verify these permissions are present (they should be by default):
   - `User.Read` (Microsoft Graph)
   - `openid`
   - `profile`
   - `email`
3. If not, click **Add a permission** → **Microsoft Graph** → **Delegated permissions** and add them

### Step 5: Save Microsoft Credentials

Copy your credentials:
```
MICROSOFT_CLIENT_ID=<your-application-id>
MICROSOFT_CLIENT_SECRET=<your-client-secret-value>
```

You can find the Application (client) ID on the **Overview** page.

---

## Part 3: Store Secrets in Azure Key Vault

Now that you have both OAuth credentials, store them securely in Key Vault.

### Option A: Using PowerShell Script

Run the provided script:
```powershell
.\infra\scripts\store-secrets.ps1
```

When prompted, enter your Google and Microsoft credentials.

### Option B: Manual Azure CLI

```bash
# Get your Key Vault name from setup
KEY_VAULT_NAME=<your-keyvault-name>

# Store Google secrets
az keyvault secret set --vault-name $KEY_VAULT_NAME --name google-client-id --value "<your-google-client-id>"
az keyvault secret set --vault-name $KEY_VAULT_NAME --name google-client-secret --value "<your-google-client-secret>"

# Store Microsoft secrets
az keyvault secret set --vault-name $KEY_VAULT_NAME --name microsoft-client-id --value "<your-microsoft-client-id>"
az keyvault secret set --vault-name $KEY_VAULT_NAME --name microsoft-client-secret --value "<your-microsoft-client-secret>"

# Generate a random auth secret key (256-bit base64)
AUTH_SECRET=$(openssl rand -base64 32)
az keyvault secret set --vault-name $KEY_VAULT_NAME --name auth-secret-key --value "$AUTH_SECRET"
```

---

## Part 4: Update Local .env File (for Development)

Update your `.env` file with the credentials for local testing:

```bash
# OAuth (configure real values)
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/oauth/google/callback

MICROSOFT_CLIENT_ID=<your-microsoft-client-id>
MICROSOFT_CLIENT_SECRET=<your-microsoft-client-secret>
MICROSOFT_REDIRECT_URI=http://localhost:8000/auth/oauth/microsoft/callback
```

---

## Verification

### Test Google OAuth Flow

1. Start your orchestrator: `uvicorn main:app --app-dir agent-orchestrator --reload --port 8000`
2. Start your frontend: `cd client-ui && npm run dev`
3. Navigate to http://localhost:5173
4. Click **Sign in with Google**
5. You should see the Google consent screen
6. After approving, you should be redirected back and logged in

### Test Microsoft OAuth Flow

1. Same setup as above
2. Click **Sign in with Microsoft**
3. You should see the Microsoft consent screen
4. After approving, you should be redirected back and logged in

---

## Troubleshooting

### Common Issues

**"redirect_uri_mismatch" error:**
- Check that your redirect URI in the OAuth app exactly matches the one in your .env file
- Make sure there are no trailing slashes
- Verify the protocol (http vs https)

**"invalid_client" error:**
- Double-check your CLIENT_ID and CLIENT_SECRET
- Make sure you copied the secret VALUE (not the secret ID) from Microsoft
- Ensure secrets don't have extra whitespace

**"access_denied" error:**
- For Google: Make sure your email is added to Test Users
- For Microsoft: Check that the app supports personal accounts if using a personal email

**"The reply URL specified in the request does not match":**
- Add the exact redirect URI to your app registration
- Wait a few minutes for changes to propagate

---

## Next Steps

Once OAuth is configured:
1. ✅ Run `setup-azure.ps1` to create Azure resources
2. ✅ Follow this guide to configure OAuth
3. ✅ Run `store-secrets.ps1` to save secrets to Key Vault
4. ⏭️ Ready for Phase 3: Deploy Bicep templates with `deploy.ps1`

---

## Security Notes

- **Never commit OAuth secrets to git**
- Use Key Vault references in production (not environment variables)
- Rotate secrets regularly (every 6-12 months)
- Use separate OAuth apps for dev, staging, and production
- Restrict redirect URIs to known domains only
