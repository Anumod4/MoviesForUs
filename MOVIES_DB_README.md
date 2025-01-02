# MoviesForUs Database Setup Guide

## Database Schema Overview

The MoviesForUs database is designed to support a movie streaming and sharing platform with the following key tables:

### Tables
1. **users**: User account information
   - Tracks user roles, login details, and profile information

2. **movies**: Movie upload details
   - Stores information about uploaded movies
   - Tracks upload status, views, and downloads

3. **movie_languages**: Movie language metadata
   - Supports multiple languages per movie

4. **movie_genres**: Movie genre classification
   - Allows multiple genres per movie

5. **movie_ratings**: User ratings and reviews
   - Enables user feedback and rating system

### Enums
- **user_role**: Defines user permission levels (user, admin, moderator)
- **movie_status**: Tracks movie approval status (pending, approved, rejected)

## Import Instructions

### Prerequisites
- PostgreSQL 12 or higher
- `psql` command-line tool
- Aiven PostgreSQL connection details

### Connection Command
```bash
psql "postgresql://username:password@host:port/database"
```

### Import Methods

#### Method 1: Direct SQL Import
```bash
# Connect to your database
psql -h [host] -p [port] -U [username] -d [database]

# Import the schema
\i moviesforUs_schema.sql
```

#### Method 2: Command Line
```bash
psql -h [host] -p [port] -U [username] -d [database] -f moviesforUs_schema.sql
```

## Sample Credentials

### Default Users
- **Admin**
  - Username: admin
  - Password: default_password

- **Regular Users**
  - Username: moviefan
  - Username: cinephile
  - Password for both: default_password

**Note**: Change these passwords immediately after first login!

## Customization
- Modify the SQL script to add more sample data
- Adjust user roles and permissions as needed
- Update genre and language lists to match your platform

## Troubleshooting
- Ensure all connection details are correct
- Check PostgreSQL version compatibility
- Verify network access to the database

## Security Recommendations
- Use environment variables for sensitive information
- Implement strong password policies
- Regularly update and rotate credentials
