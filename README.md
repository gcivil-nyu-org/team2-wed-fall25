# 🧠 AcePrep — AI-Powered Interview Preparation Platform

**AcePrep** is an AI-driven interview preparation portal designed to help candidates practice **coding**, **system design**, and **behavioral** interviews through personalized, company-specific experiences.  
Built with a modern tech stack combining **Django**, **PostgreSQL**, and **Google Gemini AI**, it offers intelligent evaluation, real-time feedback, and structured analytics for each interview round.

---

## 🚀 Features Overview

| Category | Key Features |
|-----------|---------------|
| 🧩 **Core Backend** | Django-based REST API with authentication, PostgreSQL ORM, and Celery for background jobs |
| 💻 **Frontend Dashboard** | Django Templates + Bootstrap UI for smooth navigation across interview stages |
| 🤖 **AI-Powered Evaluation** | Gemini AI integration for resume fit scoring, coding question evaluation, and rubric feedback |
| 🗣️ **Behavioral & System Design** | WebSocket-ready setup for live LLM-based interview simulations |
| ⚙️ **DevOps Integration** | Travis CI for build automation and AWS EC2 for deployment |
| 📊 **Analytics Dashboard** | Visual feedback on candidate performance and AI evaluation reports |

---

## 🏗️ System Architecture

Frontend (Bootstrap + JS)
↓
Django Backend (REST Framework)
↓
PostgreSQL ←→ Celery + Redis
↓
Google Gemini AI (via google-generativeai)

Each component interacts through REST APIs and WebSocket channels, ensuring real-time feedback and scalable performance.

---

## ⚙️ Tech Stack

### **Backend**
- Django 5.2.7  
- Django REST Framework 3.14.0  
- Django Channels 4.0.0 (ASGI + WebSocket)  
- PostgreSQL (psycopg2-binary 2.9.7)  
- Celery 5.3.4 + Redis 5.0.1  
- Daphne 4.0.0 (ASGI server)  

### **AI / ML**
- Google Gemini 2.5 Flash (Text + Audio Models)  
- OpenAI API (Configured, optional)  
- PyPDF2 for resume parsing  
- python-magic for file type validation  

### **Frontend**
- Django Templates  
- Bootstrap 5.3.0  
- Font Awesome 6.0.0  
- Vanilla JavaScript (WebSocket client + DOM handling)  

### **Deployment & DevOps**
- Travis CI (Build/Test)  
- AWS EC2 (Deployment)  
- WhiteNoise (Static file hosting)  
- python-decouple (Environment variables)  

---

## 🧩 Core Modules

| Module | Description |
|--------|--------------|
| `accounts/` | Custom User model, authentication, and JWT management |
| `interviews/` | Handles interview flow: coding, system design, and behavioral sessions |
| `resumes/` | Upload, parse, and analyze resumes using AI |
| `ai_feedback/` | AI evaluation, feedback, and scoring system |
| `companies/` | Company profiles, document uploads, and question generation |
| `core/` | Settings, Celery configuration, ASGI/WSGI apps |

---

## 🧠 AI Capabilities

| Feature | Description |
|----------|--------------|
| **Resume Analysis** | Extracts and evaluates resume content against job profiles |
| **Coding Evaluation** | Evaluates correctness, time complexity, and code quality |
| **Behavioral Interview** | Generates live, contextual questions with Gemini Audio |
| **System Design Review** | Analyzes architecture and scalability of user submissions |
| **Feedback Rubrics** | Produces detailed reports with strengths, weaknesses, and scores |

---

## 🧪 Example: Coding Evaluation Flow

**Question:**  
> Longest Substring with At Most K Distinct Characters  

**Evaluation Results:**  
- ✅ Correctness: **Passed**  
- 💡 Score: **95 / 100**  
- 💬 Feedback: “Excellent use of sliding window optimization and clear code structure.”  

**AI Notes:**  
- Robust against edge cases  
- Suggested improvements for C++ header modularity  

---

## 🗂️ Directory Structure

AcePrep/
├── accounts/
├── ai_feedback/
├── companies/
├── core/
├── interviews/
├── resumes/
├── static/
├── templates/
├── manage.py
├── requirements.txt
└── .travis.yml

---

---

## 🧰 Installation Guide

### 1. Clone the Repository
Clone the repository from GitHub and navigate to the project folder.

`git clone https://github.com/your-username/aceprep.git`  
`cd aceprep`

### 2. Create a Virtual Environment
Create a new Python virtual environment and activate it.

`python3 -m venv venv`  
`source venv/bin/activate`

### 3. Install Dependencies
Install all required dependencies from `requirements.txt`.

`pip install -r requirements.txt`

### 4. Configure Environment Variables
Create a `.env` file in the root directory with the following variables:
SECRET_KEY=your_secret_key
DEBUG=True
DB_NAME=aceprep_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=optional

### 5. Run Migrations
Apply database migrations to initialize your PostgreSQL schema.

`python manage.py migrate`

### 6. Start the Services
1. Start Redis  
   `redis-server`

2. Start Celery worker  
   `celery -A core worker -l info`

3. Start Django server  
   `python manage.py runserver`

The application will be available locally at:  
`http://127.0.0.1:8000`

---

## 🚀 Deployment Guide

### Travis CI Automation
- Lints code using `flake8` and `black`  
- Runs automated unit tests  
- Deploys to AWS EC2 on successful build  

### Manual Deployment
To manually deploy to AWS EC2:
1. Push code to the `main` branch  
   `git push origin main`
2. Restart server instance  
   `sudo systemctl restart aceprep`

Access the deployed instance via:  
`http://3.134.77.211:8001`

## 🧭 Project Progress (ZenHub Summary)

| Pipeline | Status |
|-----------|--------|
| ✅ **Done** | Backend setup, coding round, Travis CI integration |
| ⚙️ **In Progress** | Resume parsing, AI evaluation |
| 📝 **Sprint Backlog** | Feedback rubric system, dashboard UI |
| 🧊 **Icebox** | Behavioral + System Design interview modules |

## 🧾 License
This project is licensed under the [MIT License](LICENSE).


