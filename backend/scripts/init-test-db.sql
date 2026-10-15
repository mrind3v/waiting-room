SELECT 'CREATE DATABASE waitingroom_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'waitingroom_test')\gexec
