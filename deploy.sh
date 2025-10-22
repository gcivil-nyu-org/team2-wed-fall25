#!/bin/bash
set -e   # Exit immediately if any command fails
set -x   # Print each command as it runs

echo "🚀 Starting deployment to EC2..."

# Decode the base64 deploy key and set permissions
echo "$DEPLOY_KEY" | base64 -d > travis_temp_key
chmod 600 travis_temp_key

# Test SSH connection
echo "🔑 Testing SSH connection..."
ssh -o StrictHostKeyChecking=no -i travis_temp_key $EC2_USER@$EC2_HOST "echo '✅ SSH connection successful'" 

# Run deployment commands on EC2
ssh -o StrictHostKeyChecking=no -i travis_temp_key $EC2_USER@$EC2_HOST << EOF
  echo "📂 Navigating to project directory..."
  cd ~/team2-wed-fall25-deploy || { echo "❌ Directory not found"; exit 1; }

  echo "🔄 Pulling latest code from LeBranch..."
  git fetch origin LeBranch
  git reset --hard origin/LeBranch

  echo "🐍 Activating virtual environment..."
  if [ -f "venv/bin/activate" ]; then
      source venv/bin/activate
      echo "✅ Virtualenv activated"
  else
      echo "❌ Virtualenv not found, exiting"
      exit 1
  fi

  echo "📦 Installing dependencies..."
  pip install -r requirements.txt

  echo "🗄️ Applying migrations..."
  python manage.py migrate --noinput

  echo "🖼️ Collecting static files..."
  python manage.py collectstatic --noinput

  echo "🔁 Restarting Gunicorn..."
  sudo systemctl restart gunicorn
  echo "✅ Deployment finished successfully"
EOF

# Cleanup: remove the temporary key
rm -f travis_temp_key
echo "🧹 Temporary key removed"
