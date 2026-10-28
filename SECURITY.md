# MYEXA Security Guidelines

## 🔐 Sensitive Data Protection

### What's Protected in .gitignore

**API Keys & Credentials:**
- `.env` - Environment variables with API keys
- `.env.local` - Local environment overrides
- `.env.*.local` - Environment-specific configs
- `*.key` - Private keys
- `*.pem` - Certificate files
- `credentials.json` - Service account credentials
- `secrets.json` - Application secrets

**Database & Backups:**
- `*.db` - SQLite databases
- `*.db-backup` - Database backups
- `*.db-journal` - Database journals
- `*.sqlite-backup` - SQLite backups

**Cloud & Infrastructure:**
- `.aws/` - AWS credentials
- `.gcp/` - Google Cloud credentials
- `.azure/` - Azure credentials
- `*.p12`, `*.pfx` - Certificate files

**Tokens & Authentication:**
- `API_KEY` - API key files
- `api_key.txt` - API key text files
- `token.txt` - Authentication tokens
- `*.token` - Token files
- `.tokens/` - Token directory

---

## ⚠️ Critical: Never Commit

**NEVER commit these files:**
```
❌ .env (contains EXA_API_KEY)
❌ credentials.json
❌ secrets.json
❌ *.key, *.pem
❌ Database files (*.db)
❌ API keys in any form
❌ Authentication tokens
❌ Private certificates
```

---

## ✅ Safe to Commit

**These files are safe:**
```
✅ .env.example (template only, no real values)
✅ Source code (*.py, *.js, *.html, *.css)
✅ Documentation (*.md)
✅ Configuration templates
✅ Public configuration
✅ Requirements files (requirements.txt)
```

---

## 🔑 Environment Variables Setup

### Create .env from template
```bash
cp .env.example .env
```

### Edit .env with your values
```
EXA_API_KEY=your_actual_api_key_here
DATABASE_PATH=./database/myexa.db
LOG_LEVEL=INFO
PORT=3005
HOST=127.0.0.1
TESSERACT_PATH=tesseract

# HOST=127.0.0.1 keeps the unauthenticated API local-only.
# Set HOST=0.0.0.0 ONLY if you deliberately want LAN access.
```

### .env is automatically ignored
- Git will NOT track `.env`
- Your API key stays local
- Safe to commit other files

---

## 🛡️ Security Best Practices

### 0. Protections already implemented in the code

- **Loopback bind by default** — `HOST=127.0.0.1`; the unauthenticated API is not exposed to the network unless explicitly configured
- **Input validation** — blank queries, unsupported languages and `num_results` outside 1–50 are rejected with 422 before any external API call
- **Upload limits** — OCR enforces the real 50MB body size (not just the declared header) and rejects PDFs over 50 pages before rendering
- **Generic error responses** — 500s return `"Internal server error"` only; stack traces stay in the server log
- **Domain-authority matching by hostname** — look-alike hosts (`github.com.evil.example`) and path-based spoofing don't get trust scores
- **Bounded translation cache** — LRU, 1024 entries
- **Parameterized SQL everywhere** — no string-concatenated queries
- **CORS allowlist** — `http://localhost:3005` only

### 1. API Key Management
```python
# ✅ CORRECT - Load from .env
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("EXA_API_KEY")

# ❌ WRONG - Hardcoded key
api_key = "<hardcoded-secret>"
```

### 2. Never Log Sensitive Data
```python
# ❌ WRONG
print(f"API Key: {api_key}")
logger.info(f"Using key: {api_key}")

# ✅ CORRECT
logger.info("API initialized")
print("API key loaded from environment")
```

### 3. Secure Configuration
```python
# ✅ CORRECT - Use environment variables
class Config:
    EXA_API_KEY = os.getenv("EXA_API_KEY")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./database/myexa.db")
    
# ❌ WRONG - Hardcoded values
class Config:
    EXA_API_KEY = "<hardcoded-secret>"
```

---

## 🔍 Check What's Tracked

### See all tracked files
```bash
git ls-files
```

### Check if .env is tracked
```bash
git ls-files | grep .env
```
Should return nothing (empty)

### See what would be committed
```bash
git status
```

---

## 🚨 If You Accidentally Committed Sensitive Data

### 1. Immediately revoke the key
- Go to Exa dashboard
- Regenerate API key
- Update `.env` with new key

### 2. Remove from git history
```bash
# Remove file from history (careful!)
git filter-branch --tree-filter 'rm -f .env' HEAD

# Or use BFG Repo-Cleaner (recommended)
bfg --delete-files .env
```

### 3. Force push (only if local repo)
```bash
git push origin master --force
```

---

## 📋 Sensitive Data Checklist

Before committing, verify:

- [ ] `.env` file is NOT staged
- [ ] No API keys in source code
- [ ] No credentials in comments
- [ ] No tokens in configuration files
- [ ] No passwords in documentation
- [ ] Database files are ignored
- [ ] Private keys are ignored
- [ ] Cloud credentials are ignored

---

## 🔐 Production Security

### For Production Deployment

**Use environment variables:**
```bash
export EXA_API_KEY="your_production_key"
export DATABASE_PATH="/var/lib/myexa/myexa.db"
export LOG_LEVEL="WARNING"
```

**Or use secrets management:**
- AWS Secrets Manager
- Google Cloud Secret Manager
- Azure Key Vault
- HashiCorp Vault

**Never use .env in production**
- Use container secrets
- Use environment variables
- Use secrets management service

---

## 📝 .gitignore Patterns Explained

```gitignore
# Ignore all .env files
.env
.env.local
.env.*.local

# Ignore all private keys
*.key
*.pem

# Ignore all databases
*.db
*.db-backup

# Ignore credentials
credentials.json
secrets.json

# Ignore cloud configs
.aws/
.gcp/
.azure/

# Ignore tokens
*.token
.tokens/
```

---

## 🔄 Git Workflow with Secrets

### Safe workflow:
```bash
# 1. Clone repository
git clone <repo>

# 2. Create .env from template
cp .env.example .env

# 3. Add your secrets to .env
# Edit .env with your API key

# 4. Make changes to code
# Edit source files

# 5. Stage only safe files
git add backend/app.py
git add frontend/index.html

# 6. Verify nothing sensitive is staged
git status

# 7. Commit
git commit -m "Your message"

# 8. Push
git push origin master
```

---

## 🚫 What NOT to Do

```bash
# ❌ DON'T add .env
git add .env

# ❌ DON'T commit credentials
git add credentials.json

# ❌ DON'T hardcode API keys
EXA_API_KEY = "<hardcoded-secret>"

# ❌ DON'T log sensitive data
print(f"Key: {api_key}")

# ❌ DON'T push to public repo with secrets
git push origin master  # (if .env was committed)
```

---

## ✅ What TO Do

```bash
# ✅ DO use .env.example
git add .env.example

# ✅ DO load from environment
api_key = os.getenv("EXA_API_KEY")

# ✅ DO verify before committing
git status

# ✅ DO use .gitignore
# (already configured)

# ✅ DO rotate keys regularly
# Update EXA_API_KEY in .env
```

---

## 📞 Security Incident Response

**If you suspect a security breach:**

1. **Immediately revoke compromised keys**
   - Exa API: Regenerate API key
   - Any other services: Revoke tokens

2. **Check git history**
   ```bash
   git log --all --full-history -- .env
   ```

3. **Remove from history if needed**
   ```bash
   git filter-branch --tree-filter 'rm -f .env' HEAD
   ```

4. **Force push (local repo only)**
   ```bash
   git push origin master --force
   ```

5. **Notify team members**
   - Share new credentials securely
   - Update documentation

---

## 🔐 Additional Security Measures

### 1. Use HTTPS for Git
```bash
# ✅ CORRECT
git clone https://github.com/user/repo.git

# ❌ AVOID (if possible)
git clone git@github.com:user/repo.git
```

### 2. Enable 2FA on GitHub
- Account Settings → Security
- Enable Two-Factor Authentication

### 3. Use SSH Keys
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"

# Add to GitHub
cat ~/.ssh/id_ed25519.pub
```

### 4. Sign Commits
```bash
# Configure GPG signing
git config --global user.signingkey <key-id>

# Sign commits
git commit -S -m "Your message"
```

---

## 📚 Resources

- [GitHub - Removing Sensitive Data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)
- [OWASP - Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Exa API - Security](https://docs.exa.ai/reference/authentication)

---

## ✅ Security Checklist for MYEXA

- ✅ `.env` in `.gitignore`
- ✅ `.env.example` as template
- ✅ No hardcoded API keys
- ✅ No credentials in source code
- ✅ Database files ignored
- ✅ Private keys ignored
- ✅ Cloud configs ignored
- ✅ Tokens ignored
- ✅ Logs ignored
- ✅ Safe to commit

---

**Last Updated**: 2026-04-08  
**Status**: 🟢 Secure Configuration

Remember: **Never commit `.env` file!**
