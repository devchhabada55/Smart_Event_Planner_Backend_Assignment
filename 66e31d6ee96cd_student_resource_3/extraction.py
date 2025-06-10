import os
import requests
import pandas as pd
from io import BytesIO
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from transformers import BlipProcessor, BlipForConditionalGeneration
from paddleocr import PaddleOCR
import torch

# Initialize PaddleOCR
ocr = PaddleOCR(lang='en',use_angle_cls=True)

# Initialize CLIP and BLIP
clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")

# Directory to save downloaded images
image_dir = 'images'
if not os.path.exists(image_dir):
    os.makedirs(image_dir)

# Load the dataset
data_path = 'C:\\Users\\HP\\OneDrive\\Desktop\\amazon\\trainin2000.xlsx'
data = pd.read_excel(data_path)

# Check if 'index' column exists and create it if not
if 'index' not in data.columns:
    data.reset_index(drop=True, inplace=True)
    data['index'] = data.index

# Function to download image from URL
def download_image(image_url, image_id):
    try:
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        image_path = os.path.join(image_dir, f'{image_id}.jpg')
        img.save(image_path)
        return image_path
    except Exception as e:
        print(f"Failed to download {image_url}: {e}")
        return None

# Function to apply PaddleOCR to extract text from the image
def extract_text_from_image(image_path):
    try:
        result = ocr.ocr(image_path)
        extracted_text = ""
        for line in result:
            extracted_text += " ".join([word[1][0] for word in line])
        return extracted_text
    except Exception as e:
        print(f"Failed to extract text from {image_path}: {e}")
        return ""

# Function to apply CLIP model to extract image features
def extract_clip_features(image_url):
    try:
        image = Image.open(requests.get(image_url, stream=True).raw)
        inputs = clip_processor(images=image, return_tensors="pt", padding=True)
        outputs = clip_model.get_image_features(**inputs)
        return outputs
    except Exception as e:
        print(f"Failed to extract CLIP features from {image_url}: {e}")
        return None

# Function to apply BLIP model to extract captions
def extract_blip_caption(image_url):
    try:
        image = Image.open(requests.get(image_url, stream=True).raw)
        inputs = blip_processor(images=image, return_tensors="pt")
        caption = blip_model.generate(**inputs)
        return blip_processor.decode(caption[0], skip_special_tokens=True)
    except Exception as e:
        print(f"Failed to extract BLIP caption from {image_url}: {e}")
        return ""

# Download the images and process them
data['image_path'] = data.apply(lambda row: download_image(row['image_link'], row['index']), axis=1)
data['ocr_text'] = data['image_path'].apply(lambda path: extract_text_from_image(path) if path else "")
data['clip_features'] = data['image_link'].apply(extract_clip_features)
data['blip_caption'] = data['image_link'].apply(extract_blip_caption)

# Combine features for training and prediction
def combine_features(row):
    return f"{row['ocr_text']} {row['blip_caption']}"

data['combined_features'] = data.apply(combine_features, axis=1)

# Example: Save processed DataFrame
data.to_csv('processed_data.csv', index=False)

print("Data processing complete and saved to 'processed_data.csv'.")
