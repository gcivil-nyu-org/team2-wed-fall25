-- Create database and user
CREATE DATABASE aceprep_db;
CREATE USER aceprep_user WITH PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE aceprep_db TO aceprep_user;

-- Connect to the database
\c aceprep_db;

-- Enable pgvector extension
-- CREATE EXTENSION IF NOT EXISTS vector;  -- Commented out for now

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO aceprep_user;
GRANT CREATE ON SCHEMA public TO aceprep_user;
