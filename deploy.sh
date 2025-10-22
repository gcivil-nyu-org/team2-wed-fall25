#!/bin/bash
set -e

echo "🚀 Deploying to EC2..."

# Write Travis CI's deploy key to a temporary file
echo "$DEPLOY_KEY" > travis_temp_key
chmod 600 travis_temp_key

# SSH into EC2 and pull the latest code
ssh -o StrictHostKeyChecking=no -i travis_temp_key $EC2_USER@$EC2_HOST << 'EOF'
  cd ~/team2-wed-fall25-deploy
  git fetch origin LeBranch
  git reset --hard origin/LeBranch
  source venv/bin/activate || echo "no venv found"
  pip install -r requirements.txt
  python manage.py migrate --noinput || echo "no migrate step"
  python manage.py collectstatic --noinput || echo "no static step"
  sudo systemctl restart gunicorn || echo "gunicorn not restarted"
EOF

# Clean up key
rm -f travis_temp_key
