# AWS Deployment Guide for Forums Feature

## Issue: Unable to Add Forums or Case Studies

### Problem Analysis
1. **Forums** can only be created by administrators through Django Admin (not through the public UI)
2. **Topics** can be created by any logged-in user
3. **Case Studies** are posts marked with the `is_case_study` flag

### Solution Steps

## Step 1: Run Migrations on AWS

SSH into your AWS EC2 instance and run:

```bash
cd /path/to/your/project
source venv/bin/activate  # or your virtual environment path
python manage.py migrate
```

This ensures all forum tables are created in the database.

## Step 2: Seed Sample Forums

Run the seed_forums management command:

```bash
python manage.py seed_forums
```

This will create 5 sample forums:
- SWE Interview Prep
- PM Interview Prep  
- General Discussion
- Case Studies
- Success Stories

## Step 3: Create Forums via Django Admin

1. **Access Admin Panel**: Go to `http://3.134.77.211:8000/admin/`
2. **Login** with your superuser credentials
3. **Navigate to Forums section**
4. **Click "Add Forum"**
5. **Fill in the form**:
   - Name: e.g., "System Design Discussions"
   - Description: Brief description
   - Icon: Font Awesome class (e.g., "fa-server")
   - User Type: Leave blank for all users, or select specific type
   - Is Active: Check this box
6. **Click "Save"**

## Step 4: Create Topics (Public Users Can Do This)

Once forums exist, logged-in users can:
1. Go to `/forums/`
2. Click on a forum
3. Click "New Topic" button
4. Fill in title and description
5. Submit

## Step 5: Create Case Studies

Case studies are posts marked with a flag:
1. Create a topic or reply to an existing topic
2. When creating a post/reply, check the "Mark as Case Study" checkbox
3. Submit the post

## Troubleshooting

### If forums don't appear:

1. **Check if you're logged in**: Some forums are user-type specific
2. **Check database**: Verify forums exist:
   ```bash
   python manage.py shell
   >>> from forums.models import Forum
   >>> Forum.objects.all()
   >>> Forum.objects.filter(is_active=True)
   ```

3. **Check user type**: If forums have `user_type` set, only matching users can see them
4. **Check is_active flag**: Only active forums are displayed

### If you can't create topics:

1. **Ensure you're logged in**: Topics require authentication
2. **Check forum access**: Some forums are restricted by user type
3. **Check forum exists**: Verify the forum ID in the URL is valid

### If case studies don't show:

1. **Check the filter**: Go to `/forums/case-studies/`
2. **Verify posts are marked**: Posts must have `is_case_study=True`
3. **Check database**:
   ```bash
   python manage.py shell
   >>> from forums.models import Post
   >>> Post.objects.filter(is_case_study=True)
   ```

## Quick Setup Script for AWS

Create a file `setup_forums.sh` on your AWS server:

```bash
#!/bin/bash
cd /path/to/your/project
source venv/bin/activate
python manage.py migrate forums
python manage.py seed_forums
echo "Forums setup complete!"
```

Make it executable:
```bash
chmod +x setup_forums.sh
./setup_forums.sh
```

## Admin Access

If you need to create a superuser on AWS:

```bash
python manage.py createsuperuser
```

Then access admin at: `http://3.134.77.211:8000/admin/`

