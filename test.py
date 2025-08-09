import requests
import os
import shutil
from urllib.parse import urlparse

# --- Configuration ---
API_URL = "http://127.0.0.1:8000/submit"
TEMP_DOWNLOAD_DIR = "temp_image_downloads"

# --- Data to Upload ---

# An expanded list of 30 text data entries
TEXT_DATA = [
    "Simplicity", "Complexity", "Ephemeral", "Serendipity", "Resilience",
    "The sun rises in the east.", "Artificial intelligence is transforming industries.",
    "What is the meaning of life?", "To be or not to be, that is the question.",
    "A lone wolf howls at the moon.", "Ancient ruins whisper tales of the past.",
    "Starlight travels for millions of years to reach us.", "The deep ocean remains largely unexplored.",
    "Creativity is intelligence having fun.", "Change is the only constant.", "Knowledge is power.",
    "Technology", "Nature", "Art", "Science", "History", "Philosophy",
    "A cup of coffee on a rainy day.", "The sound of laughter is timeless.",
    "Every exit is an entry somewhere else.", "The rustle of leaves in the autumn wind.",
    "A city that never sleeps.", "Silence can be the loudest sound.",
    "What is love?", "The pursuit of happiness."
]

# An expanded list of 30 royalty-free image URLs
IMAGE_URLS = [
    # Animals
    "https://images.pexels.com/photos/45201/kitty-cat-kitten-pet-45201.jpeg",      # Cat
    "https://images.pexels.com/photos/1108099/pexels-photo-1108099.jpeg",     # Dogs
    "https://images.pexels.com/photos/39571/gorilla-silverback-animal-silvery-grey-39571.jpeg", # Gorilla
    "https://images.pexels.com/photos/66898/elephant-cub-tsavo-kenya-66898.jpeg",       # Elephant
    "https://images.pexels.com/photos/34937/pexels-photo.jpg",                 # Fox
    "https://images.pexels.com/photos/47547/red-fox-wildlife-animal-47547.jpeg", # Red Fox
    "https://images.pexels.com/photos/133459/pexels-photo-133459.jpeg",      # Owl
    "https://images.pexels.com/photos/792381/pexels-photo-792381.jpeg",       # Tiger
    "https://images.pexels.com/photos/326012/pexels-photo-326012.jpeg",       # Jellyfish
    "https://images.pexels.com/photos/46667/jellyfish-sea-water-ocean-46667.jpeg", # Another Jellyfish
    
    # Landscapes
    "https://images.pexels.com/photos/1528640/pexels-photo-1528640.jpeg",     # Forest Path
    "https://images.pexels.com/photos/3225517/pexels-photo-3225517.jpeg",     # Tropical Beach
    "https://images.pexels.com/photos/2559941/pexels-photo-2559941.jpeg",     # Mountain Road
    "https://images.pexels.com/photos/3408744/pexels-photo-3408744.jpeg",     # Aurora Borealis
    "https://images.pexels.com/photos/531880/pexels-photo-531880.jpeg",       # Rainy Window
    "https://images.pexels.com/photos/210186/pexels-photo-210186.jpeg",       # Waterfall
    "https://images.pexels.com/photos/167699/pexels-photo-167699.jpeg",       # Misty Forest
    "https://images.pexels.com/photos/302804/pexels-photo-302804.jpeg",       # Desert Dunes
    
    # Objects & Architecture
    "https://images.pexels.com/photos/37347/office-sitting-room-executive-sitting.jpg", # Modern Office
    "https://images.pexels.com/photos/1029604/pexels-photo-1029604.jpeg",     # Vintage Camera
    "https://images.pexels.com/photos/355988/pexels-photo-355988.jpeg",       # Old Books
    "https://images.pexels.com/photos/276583/pexels-photo-276583.jpeg",       # Bicycle
    "https://images.pexels.com/photos/164595/pexels-photo-164595.jpeg",       # Hotel Room
    "https://images.pexels.com/photos/186077/pexels-photo-186077.jpeg",       # Modern House
    
    # Abstract & Concepts
    "https://images.pexels.com/photos/1191531/pexels-photo-1191531.jpeg",     # Light Trails
    "https://images.pexels.com/photos/355887/pexels-photo-355887.jpeg",       # Ink in Water
    "https://images.pexels.com/photos/998641/pexels-photo-998641.jpeg",       # Geometric Shapes
    "https://images.pexels.com/photos/1287145/pexels-photo-1287145.jpeg",     # Colorful Smoke
    "https://images.pexels.com/photos/268533/pexels-photo-268533.jpeg",       # Earth from Space
    "https://images.pexels.com/photos/36717/amazing-animal-beautiful-beautifull.jpg" # Sunset Reflection
]

def upload_text(session, text_content):
    """Submits a single piece of text data."""
    try:
        print(f"Submitting text: '{text_content[:40]}...'")
        payload = {"type": "text", "data": text_content}
        response = session.post(API_URL, data=payload, timeout=15)
        response.raise_for_status()
        print(f"✅ Success: Server responded with {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR submitting text. Reason: {e}")

def upload_image_from_url(session, url):
    """Downloads an image from a URL and submits it."""
    try:
        print(f"Downloading image from: {url}")
        # Get the image data from the URL
        image_response = requests.get(url, stream=True, timeout=15)
        image_response.raise_for_status()

        # Extract filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)

        # Save the image temporarily
        temp_path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
        with open(temp_path, 'wb') as f:
            shutil.copyfileobj(image_response.raw, f)
        
        print(f"Submitting image: {filename}")
        with open(temp_path, "rb") as f:
            files = {"file": (filename, f, f"image/{os.path.splitext(filename)[1][1:]}")}
            payload = {"type": "image"}
            submit_response = session.post(API_URL, data=payload, files=files, timeout=15)
        
        submit_response.raise_for_status()
        print(f"✅ Success: Server responded with {submit_response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR processing image {url}. Reason: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred with {url}: {e}")


def main():
    """
    Main function to run the bulk upload process.
    """
    # Create a temporary directory for downloaded images
    if not os.path.exists(TEMP_DOWNLOAD_DIR):
        os.makedirs(TEMP_DOWNLOAD_DIR)

    # Use a session object for connection pooling
    with requests.Session() as session:
        # --- Upload Text Data ---
        print("\n--- Starting Text Uploads ---")
        for text in TEXT_DATA:
            upload_text(session, text)
        
        # --- Upload Image Data ---
        print("\n--- Starting Image Uploads ---")
        for url in IMAGE_URLS:
            upload_image_from_url(session, url)

    # Clean up the temporary directory
    try:
        shutil.rmtree(TEMP_DOWNLOAD_DIR)
        print(f"\n🧹 Cleaned up temporary directory: {TEMP_DOWNLOAD_DIR}")
    except OSError as e:
        print(f"Error removing directory {TEMP_DOWNLOAD_DIR}: {e.strerror}")

    print("\n--- Bulk Upload Complete ---")


if __name__ == "__main__":
    main()
