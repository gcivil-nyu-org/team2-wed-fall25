# 🚀 AcePrep Setup & Run Guide

This guide will walk you through installing all dependencies and running the AcePrep Django application.

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software:
1. **Python 3.8+** - Check with: `python3 --version`
2. **PostgreSQL** - Database server
3. **Redis** - For Celery task queue
4. **pip** - Python package manager (usually comes with Python)

---

## 🔧 Installation Steps

### Step 1: Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download and install from: https://www.postgresql.org/download/windows/

### Step 2: Install Redis

**macOS (using Homebrew):**
```bash
brew install redis
brew services start redis
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
```

**Windows:**
Download from: https://redis.io/download or use WSL

### Step 3: Set Up PostgreSQL Database

1. **Access PostgreSQL:**
   ```bash
   psql postgres
   ```

2. **Create database and user:**
   ```sql
   CREATE DATABASE team2db;
   CREATE USER team2user WITH PASSWORD 'team2pass';
   GRANT ALL PRIVILEGES ON DATABASE team2db TO team2user;
   \q
   ```

   **Note:** The project uses these credentials by default (as seen in `core/settings.py`). If you want different credentials, you'll need to update `settings.py` or use environment variables.

### Step 4: Set Up Python Virtual Environment

1. **Navigate to project directory:**
   ```bash
   cd "/Users/pranavmotarwar/Downloads/team2-wed-fall25-sahil_feature_branch 2"
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   ```

3. **Activate virtual environment:**
   
   **macOS/Linux:**
   ```bash
   source venv/bin/activate
   ```
   
   **Windows:**
   ```bash
   venv\Scripts\activate
   ```

   You should see `(venv)` in your terminal prompt.

### Step 5: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Note:** This may take a few minutes as it installs all required packages including Django, PostgreSQL drivers, Celery, Redis, and AI libraries.

### Step 6: Configure Environment Variables

1. **Create a `.env` file in the project root:**
   ```bash
   touch .env
   ```

2. **Add the following content to `.env`:**
   ```env
   SECRET_KEY=django-insecure-^z2)4q#x5)k-qkzg4i%y-=6a%71f_44%8pbegpur82ic1f=pr=
   DEBUG=True
   
   DB_NAME=team2db
   DB_USER=team2user
   DB_PASSWORD=team2pass
   DB_HOST=localhost
   DB_PORT=5432
   
   REDIS_URL=redis://localhost:6379/0
   
   GEMINI_API_KEY=your_gemini_api_key_here
   OPENAI_API_KEY=your_openai_api_key_here_optional
   ```

   **Important:** 
   - Replace `your_gemini_api_key_here` with your actual Google Gemini API key (get it from https://makersuite.google.com/app/apikey)
   - The OpenAI API key is optional
   - The database credentials match what we set up in Step 3

### Step 7: Run Database Migrations

```bash
python manage.py migrate
```

This creates all the necessary database tables.

### Step 8: Create a Superuser (Optional but Recommended)

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account. This allows you to access the Django admin panel at `http://127.0.0.1:8000/admin/`.

---

## 🏃 Running the Application

The application requires **3 separate services** to run simultaneously. You'll need **3 terminal windows/tabs**.

### Terminal 1: Start Redis

```bash
redis-server
```

Keep this running. You should see Redis start successfully.

### Terminal 2: Start Celery Worker

Make sure your virtual environment is activated, then:

```bash
cd "/Users/pranavmotarwar/Downloads/team2-wed-fall25-sahil_feature_branch 2"
source venv/bin/activate  # If not already activated
celery -A core worker -l info
```

Keep this running. You should see Celery worker start and wait for tasks.

### Terminal 3: Start Django Server

Make sure your virtual environment is activated, then:

```bash
cd "/Users/pranavmotarwar/Downloads/team2-wed-fall25-sahil_feature_branch 2"
source venv/bin/activate  # If not already activated
python manage.py runserver
```

You should see output like:
```
Starting development server at http://127.0.0.1:8000/
```

---

## ✅ Verify Installation

1. **Open your browser** and navigate to: `http://127.0.0.1:8000`
2. You should see the AcePrep homepage
3. Try accessing the admin panel: `http://127.0.0.1:8000/admin/` (if you created a superuser)

---

## 🛠️ Troubleshooting

### Issue: PostgreSQL connection error
- **Solution:** Make sure PostgreSQL is running: `brew services list` (macOS) or `sudo systemctl status postgresql` (Linux)
- Verify database exists: `psql -U team2user -d team2db`

### Issue: Redis connection error
- **Solution:** Make sure Redis is running: `redis-cli ping` (should return `PONG`)
- Start Redis: `redis-server` or `brew services start redis`

### Issue: Module not found errors
- **Solution:** Make sure virtual environment is activated and dependencies are installed:
  ```bash
  source venv/bin/activate
  pip install -r requirements.txt
  ```

### Issue: Port 8000 already in use
- **Solution:** Use a different port:
  ```bash
  python manage.py runserver 8001
  ```

### Issue: Database migration errors
- **Solution:** Reset migrations (⚠️ **WARNING:** This deletes all data):
  ```bash
  python manage.py flush
  python manage.py migrate
  ```

---

## 📝 Additional Commands

### Collect Static Files (for production)
```bash
python manage.py collectstatic
```

### Run Tests
```bash
python manage.py test
```

### Access Django Shell
```bash
python manage.py shell
```

### View Database in Admin Panel
- Navigate to: `http://127.0.0.1:8000/admin/`
- Login with superuser credentials

---

## 🎯 Quick Start Summary

Once everything is set up, to run the application:

1. **Terminal 1:** `redis-server`
2. **Terminal 2:** `celery -A core worker -l info` (with venv activated)
3. **Terminal 3:** `python manage.py runserver` (with venv activated)

Access the app at: **http://127.0.0.1:8000**

---

## 📚 Additional Resources

- Django Documentation: https://docs.djangoproject.com/
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- Redis Documentation: https://redis.io/documentation
- Google Gemini API: https://ai.google.dev/

---

**Need Help?** Check the main `README.md` file for more project-specific information.

