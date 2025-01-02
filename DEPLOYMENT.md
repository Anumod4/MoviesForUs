# Render Deployment Guide for MoviesForUs

## Prerequisites
- GitHub account
- Render account
- Git repository with your project

## Deployment Steps
1. Push your code to a GitHub repository
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New Web Service"
4. Connect your GitHub repository
5. Configure settings:
   - Environment: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`

## Environment Variables
Set these in Render's dashboard:
- `SECRET_KEY`: Random secure string
- `FLASK_ENV`: `production`
- `DATABASE_URL`: Render-provided PostgreSQL connection string

## Troubleshooting
- Ensure all dependencies are in `requirements.txt`
- Check Python version compatibility
- Verify file paths are relative

## Post-Deployment
1. Initialize database (if needed)
2. Test all application routes
3. Set up custom domain (optional)

## Estimated Deployment Time
- Initial setup: 30-60 minutes
- Configuration: 15-30 minutes
- Testing: 15-30 minutes
