from PIL import Image, ImageDraw, ImageFont
import os

# Create a default thumbnail
def create_default_thumbnail(output_path):
    # Create a new image with a light gray background
    img = Image.new('RGB', (320, 240), color='lightgray')
    
    # Create a drawing context
    draw = ImageDraw.Draw(img)
    
    # Try to use a default system font
    try:
        font = ImageFont.truetype("Arial.ttf", 20)
    except IOError:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Draw text
    draw.text((100, 120), "No Thumbnail", fill='black', font=font)
    
    # Save the image
    img.save(output_path)
    print(f"Default thumbnail created at {output_path}")

# Ensure static directory exists
static_dir = '/Users/anumod/CascadeProjects/movie_stream_app/static'
os.makedirs(static_dir, exist_ok=True)

# Create the default thumbnail
create_default_thumbnail(os.path.join(static_dir, 'default_thumbnail.jpg'))
