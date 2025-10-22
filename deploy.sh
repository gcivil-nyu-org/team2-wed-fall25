#!/bin/bash
set -e
set -x   # <--- enables verbose mode

echo "🚀 Deploying to EC2..."
echo "Testing SSH connection..."
echo "$DEPLOY_KEY" > travis_temp_key
chmod 600 travis_temp_key

ssh -o StrictHostKeyChecking=no -i travis_temp_key $EC2_USER@$EC2_HOST "echo '✅ SSH connected successfully'" || echo "❌ SSH connection failed"

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

rm -f travis_temp_key
