#!/bin/bash
cd /Users/anumod/CascadeProjects/movie_stream_app
source venv/bin/activate
pip install Pillow
python3 create_default_thumbnail.py
deactivate
