from flask import Flask, request, jsonify, send_file 
import pandas as pd
import io
import base64
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile
import os
from openai import OpenAI
from typing import Dict, List, Optional
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.io as pio
import numpy as np
import json
from werkzeug.utils import secure_filename
import logging
import threading
import time
from datetime import datetime
import requests
import urllib.parse
from flask_cors import CORS


# Try to import credentials, fall back to environment variables if not available
try:
    from credentials import DOMAIN, CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, ROOT_FOLDER
    EGNYTE_AVAILABLE = True
except ImportError:
    # Use environment variables for deployment
    DOMAIN = os.getenv('EGNYTE_DOMAIN')
    CLIENT_ID = os.getenv('EGNYTE_CLIENT_ID')
    CLIENT_SECRET = os.getenv('EGNYTE_CLIENT_SECRET')
    USERNAME = os.getenv('EGNYTE_USERNAME')
    PASSWORD = os.getenv('EGNYTE_PASSWORD')
    ROOT_FOLDER = os.getenv('EGNYTE_ROOT_FOLDER')
    EGNYTE_AVAILABLE = all([DOMAIN, CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, ROOT_FOLDER])

# Rate limiting configuration for Egnyte
# Egnyte limits: 2 calls per second, 1,000 calls per day
RATE_LIMIT_DELAY = 1.0  # Wait 1.0 seconds between calls (allows 1 call/sec, safely under 2/sec)

# Token caching to reduce authentication requests
_egnyte_token_cache = {
    'token': None,
    'expires_at': None
}

def rate_limit_delay():
    """Add delay to respect rate limits"""
    time.sleep(RATE_LIMIT_DELAY)

def clear_egnyte_token_cache():
    """Clear the cached Egnyte token"""
    global _egnyte_token_cache
    _egnyte_token_cache = {
        'token': None,
        'expires_at': None
    }
    logger.info("🗑️ Cleared Egnyte token cache")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
CORS(app) 

# In-memory storage for job results
job_results = {}
job_status = {}

# Egnyte API Functions
def get_egnyte_token():
    """Get Egnyte access token with rate limiting and retry logic"""
    if not EGNYTE_AVAILABLE:
        logger.error("Egnyte credentials not available")
        return None
    
    # Check if we have a cached token that's still valid
    current_time = time.time()
    if (_egnyte_token_cache['token'] and 
        _egnyte_token_cache['expires_at'] and 
        current_time < _egnyte_token_cache['expires_at']):
        logger.info("✅ Using cached Egnyte token")
        return _egnyte_token_cache['token']
    
    logger.info(f"🔐 Attempting Egnyte authentication...")
    logger.info(f"   Domain: {DOMAIN}")
    logger.info(f"   Username: {USERNAME}")
    logger.info(f"   Client ID: {CLIENT_ID}")
    logger.info(f"   Client Secret: {'*' * len(CLIENT_SECRET) if CLIENT_SECRET else 'None'}")
    logger.info(f"   Password: {'*' * len(PASSWORD) if PASSWORD else 'None'}")
        
    url = f"https://{DOMAIN}/puboauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    logger.info(f"🌐 Making request to: {url}")
    logger.info(f"📋 Request data: grant_type=password, username={USERNAME}, client_id={CLIENT_ID}, client_secret={'*' * len(CLIENT_SECRET) if CLIENT_SECRET else 'None'}")
    
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Add rate limiting delay before each attempt
            rate_limit_delay()
            
            # Use urllib.parse.urlencode to properly encode form data
            encoded_data = urllib.parse.urlencode(data)
            logger.info(f"🔧 Encoded data: {encoded_data.replace(PASSWORD, '*' * len(PASSWORD)).replace(CLIENT_SECRET, '*' * len(CLIENT_SECRET))}")
            
            response = requests.post(url, data=encoded_data, headers=headers)
            
            logger.info(f"📊 Response Status: {response.status_code}")
            logger.info(f"📋 Response Headers: {dict(response.headers)}")
            logger.info(f"📄 Response Body: {response.text}")
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)  # Default to 1 hour
                token_type = token_data.get("token_type", "unknown")
                
                # Cache the token with expiration
                _egnyte_token_cache['token'] = access_token
                _egnyte_token_cache['expires_at'] = current_time + expires_in - 300  # Expire 5 minutes early
                
                logger.info(f"✅ Authentication successful!")
                logger.info(f"   Token Type: {token_type}")
                logger.info(f"   Expires In: {expires_in} seconds")
                logger.info(f"   Access Token: {access_token[:20]}...")
                logger.info(f"   Token cached until: {datetime.fromtimestamp(_egnyte_token_cache['expires_at'])}")
                
                return access_token
            elif response.status_code == 429:
                # Handle rate limiting
                retry_after = response.headers.get('Retry-After', '30')
                try:
                    retry_seconds = int(retry_after.split(',')[0])  # Handle "2665, 30" format
                except (ValueError, IndexError):
                    retry_seconds = 30
                
                logger.warning(f"⚠️ Rate limit hit! Waiting {retry_seconds} seconds before retry {retry_count + 1}/{max_retries}")
                logger.warning(f"   Retry-After header: {retry_after}")
                
                # Wait for the specified time
                time.sleep(retry_seconds)
                retry_count += 1
                continue
            else:
                logger.error(f"❌ Authentication failed!")
                logger.error(f"   Status Code: {response.status_code}")
                logger.error(f"   Response Text: {response.text}")
                
                # Check for specific error types
                error_text = response.text.lower()
                if "invalid username" in error_text or "invalid password" in error_text:
                    logger.error(f"   Error Type: Invalid credentials")
                elif "rate limit" in error_text or "qps" in error_text:
                    logger.error(f"   Error Type: Rate limiting")
                elif "ip" in error_text or "restricted" in error_text:
                    logger.error(f"   Error Type: IP restriction")
                elif "locked" in error_text or "suspended" in error_text:
                    logger.error(f"   Error Type: Account locked/suspended")
                else:
                    logger.error(f"   Error Type: Unknown")
                
                # Check for specific headers that might indicate the issue
                if 'X-Mashery-Error-Code' in response.headers:
                    error_code = response.headers['X-Mashery-Error-Code']
                    logger.error(f"   Mashery Error Code: {error_code}")
                
                if 'Retry-After' in response.headers:
                    retry_after = response.headers['Retry-After']
                    logger.error(f"   Retry After: {retry_after} seconds")
                
                # For non-429 errors, don't retry
                return None
                
        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ Connection error: {e}")
            logger.error(f"   This might indicate network issues or domain problems")
            return None
        except requests.exceptions.Timeout as e:
            logger.error(f"❌ Timeout error: {e}")
            logger.error(f"   Request timed out - server might be slow or unreachable")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error: {e}")
            logger.error(f"   General request failure")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error getting Egnyte token: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            return None
    
    # If we've exhausted all retries
    logger.error(f"❌ Authentication failed after {max_retries} retries due to rate limiting")
    return None

def create_egnyte_folder(access_token, parent_folder_id, folder_name):
    """Create a new folder in Egnyte"""
    url = f"https://{DOMAIN}/pubapi/v1/fs/ids/folder/{parent_folder_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "action": "add_folder",
        "name": folder_name
    }
    
    try:
        # Add rate limiting delay
        rate_limit_delay()
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        error_text = e.response.text.lower()
        
        # Check for folder already exists error
        if "already exists" in error_text or "duplicate" in error_text or "exists" in error_text:
            logger.info(f"Folder '{folder_name}' already exists, checking for existing folder...")
            # Try to find the existing folder
            existing_folder = find_existing_folder(access_token, parent_folder_id, folder_name)
            if existing_folder:
                logger.info(f"Found existing folder: {existing_folder.get('name')}")
                return existing_folder
            else:
                logger.error(f"Folder '{folder_name}' already exists but couldn't find it")
                return None
        
        # Check for rate limiting
        elif "developer over qps" in error_text or "rate limit" in error_text or "qps" in error_text:
            logger.warning(f"Rate limit hit, waiting 3 seconds before retry...")
            time.sleep(3)  # Longer wait for rate limit recovery
            try:
                rate_limit_delay()  # Add rate limiting before retry
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as retry_e:
                logger.error(f"Failed to create folder on retry: {retry_e}")
                return None
        
        # Check for permission errors
        elif e.response.status_code == 403:
            logger.error(f"Permission denied creating folder '{folder_name}': {e.response.text}")
            return None
        
        else:
            logger.error(f"Failed to create folder '{folder_name}': {e.response.text}")
            return None
    except Exception as e:
        logger.error(f"Error creating Egnyte folder '{folder_name}': {e}")
        return None

def find_existing_folder(access_token, parent_folder_id, folder_name):
    """Find an existing folder by name in the parent folder"""
    try:
        folder_data = list_egnyte_folder_contents(access_token, parent_folder_id)
        if folder_data and isinstance(folder_data, dict):
            folders = folder_data.get("folders", [])
            for folder in folders:
                if folder.get('name') == folder_name:
                    return folder
        return None
    except Exception as e:
        logger.error(f"Error finding existing folder: {e}")
        return None

def get_egnyte_folder_details(access_token, folder_id):
    """Get folder details"""
    url = f"https://{DOMAIN}/pubapi/v1/fs/ids/folder/{folder_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Add rate limiting delay
        rate_limit_delay()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        if "Developer Over Qps" in e.response.text:
            logger.warning(f"Rate limit hit, waiting 3 seconds before retry...")
            time.sleep(3)  # Longer wait for rate limit recovery
            try:
                rate_limit_delay()  # Add rate limiting before retry
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as retry_e:
                logger.error(f"Failed to get folder details on retry: {retry_e}")
                return None
        else:
            logger.error(f"Failed to get folder details: {e}")
            return None
    except Exception as e:
        logger.error(f"Error getting Egnyte folder details: {e}")
        return None

def list_egnyte_folder_contents(access_token, folder_id):
    """List folder contents"""
    url = f"https://{DOMAIN}/pubapi/v1/fs/ids/folder/{folder_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "list_content": "true",
        "count": "100"
    }
    
    try:
        # Add rate limiting delay
        rate_limit_delay()
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        if "Developer Over Qps" in e.response.text:
            logger.warning(f"Rate limit hit, waiting 3 seconds before retry...")
            time.sleep(3)  # Longer wait for rate limit recovery
            try:
                rate_limit_delay()  # Add rate limiting before retry
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
            except requests.HTTPError as retry_e:
                logger.error(f"Failed to list folder contents on retry: {retry_e}")
                return None
        else:
            logger.error(f"Failed to list folder contents: {e}")
            return None
    except Exception as e:
        logger.error(f"Error listing Egnyte folder contents: {e}")
        return None

def background_create_egnyte_folders(molecule_code: str, campaign_number: str):
    """Background function to create Egnyte folder structure"""
    job_key = f"egnyte_{molecule_code}_{campaign_number}"
    
    logger.info(f"BACKGROUND: Starting Egnyte folder creation for {job_key}")
    
    try:
        # Update status to running
        job_status[job_key] = {
            "status": "running",
            "message": "Creating Egnyte folder structure...",
            "started_at": datetime.now().isoformat(),
            "progress": 0
        }
        
        # Get access token
        access_token = get_egnyte_token()
        if not access_token:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to get Egnyte access token",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Update progress
        job_status[job_key]["progress"] = 20
        job_status[job_key]["message"] = "Creating project folder..."
        
        # Check if project folder already exists
        project_folder_name = f"Project; Molecule {molecule_code}"
        
        # First, try to list existing folders to check for duplicates
        existing_folders_data = list_egnyte_folder_contents(access_token, ROOT_FOLDER)
        if existing_folders_data and isinstance(existing_folders_data, dict):
            existing_folders = existing_folders_data.get("folders", [])
            for folder in existing_folders:
                if folder.get('name') == project_folder_name:
                    # Check if campaign folder already exists
                    campaign_folder_name = f"Project {molecule_code} (Campaign #{campaign_number})"
                    campaign_contents_data = list_egnyte_folder_contents(access_token, folder.get('folder_id'))
                    if campaign_contents_data and isinstance(campaign_contents_data, dict):
                        campaign_folders = campaign_contents_data.get("folders", [])
                        for campaign_folder in campaign_folders:
                            if campaign_folder.get('name') == campaign_folder_name:
                                job_status[job_key] = {
                                    "status": "failed",
                                    "message": f"Project {molecule_code} Campaign {campaign_number} already exists",
                                    "started_at": job_status[job_key]["started_at"],
                                    "completed_at": datetime.now().isoformat()
                                }
                                return
        
        # Create project folder
        project_folder = create_egnyte_folder(access_token, ROOT_FOLDER, project_folder_name)
        
        if not project_folder or not isinstance(project_folder, dict):
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to create project folder",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        project_folder_id = project_folder.get('folder_id')
        
        # Update progress
        job_status[job_key]["progress"] = 40
        job_status[job_key]["message"] = "Creating campaign folder..."
        
        # Create campaign folder
        campaign_folder_name = f"Project {molecule_code} (Campaign #{campaign_number})"
        campaign_folder = create_egnyte_folder(access_token, project_folder_id, campaign_folder_name)
        
        if not campaign_folder or not isinstance(campaign_folder, dict):
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to create campaign folder",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        campaign_folder_id = campaign_folder.get('folder_id')
        
        # Update progress
        job_status[job_key]["progress"] = 60
        job_status[job_key]["message"] = "Creating Pre and Post folders..."
        
        # Create Pre and Post folders
        pre_folder = create_egnyte_folder(access_token, campaign_folder_id, "Pre")
        post_folder = create_egnyte_folder(access_token, campaign_folder_id, "Post")
        
        if not pre_folder or not isinstance(pre_folder, dict) or not post_folder or not isinstance(post_folder, dict):
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to create Pre/Post folders",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Create department folders under Pre and Post
        departments = ["mfg", "Anal", "Stability", "CTM"]
        statuses = ["Draft", "Review", "Approved"]
        
        job_status[job_key]["progress"] = 65
        job_status[job_key]["message"] = "Creating department folders..."
        
        for phase_name, phase_folder in [("Pre", pre_folder), ("Post", post_folder)]:
            phase_folder_id = phase_folder.get('folder_id')
            
            for dept in departments:
                dept_folder = create_egnyte_folder(access_token, phase_folder_id, dept)
                if dept_folder and isinstance(dept_folder, dict):
                    dept_folder_id = dept_folder.get('folder_id')
                    
                    # Create status folders under each department
                    for status in statuses:
                        create_egnyte_folder(access_token, dept_folder_id, status)
        
        # Update progress
        job_status[job_key]["progress"] = 80
        job_status[job_key]["message"] = "Creating Draft AI Reg Document folder..."
        
        # Create Draft AI Reg Document folder under project
        reg_doc_folder = create_egnyte_folder(access_token, project_folder_id, "Draft AI Reg Document")
        if not reg_doc_folder or not isinstance(reg_doc_folder, dict):
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to create Draft AI Reg Document folder",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        reg_doc_folder_id = reg_doc_folder.get('folder_id')
        
        # Update progress
        job_status[job_key]["progress"] = 85
        job_status[job_key]["message"] = "Creating regulatory document folders..."
        
        # Create regulatory document folders under Draft AI Reg Document
        reg_types = ["IND", "IMPD", "Canada"]
        for reg_type in reg_types:
            reg_type_folder = create_egnyte_folder(access_token, reg_doc_folder_id, reg_type)
            if reg_type_folder and isinstance(reg_type_folder, dict):
                reg_type_folder_id = reg_type_folder.get('folder_id')
                
                for status in statuses:
                    create_egnyte_folder(access_token, reg_type_folder_id, status)
        
        # Store the result with URLs
        job_results[job_key] = {
            "project_folder": {
                "id": project_folder.get('folder_id'),
                "name": project_folder.get('name'),
                "path": project_folder.get('path'),
                "url": f"https://{DOMAIN}/app/index.do#storage/files/1{project_folder.get('path', '')}"
            },
            "campaign_folder": {
                "id": campaign_folder.get('folder_id'),
                "name": campaign_folder.get('name'),
                "path": campaign_folder.get('path'),
                "url": f"https://{DOMAIN}/app/index.do#storage/files/1{campaign_folder.get('path', '')}"
            },
            "reg_doc_folder": {
                "id": reg_doc_folder.get('folder_id'),
                "name": reg_doc_folder.get('name'),
                "path": reg_doc_folder.get('path'),
                "url": f"https://{DOMAIN}/app/index.do#storage/files/1{reg_doc_folder.get('path', '')}"
            },
            "molecule_code": molecule_code,
            "campaign_number": campaign_number,
            "folder_structure": {
                "project_name": project_folder.get('name'),
                "campaign_name": campaign_folder.get('name'),
                "reg_doc_name": reg_doc_folder.get('name'),
                "project_url": f"https://{DOMAIN}/app/index.do#storage/files/1{project_folder.get('path', '')}",
                "campaign_url": f"https://{DOMAIN}/app/index.do#storage/files/1{campaign_folder.get('path', '')}",
                "reg_doc_url": f"https://{DOMAIN}/app/index.do#storage/files/1{reg_doc_folder.get('path', '')}"
            }
        }
        
        # Update status to completed
        job_status[job_key] = {
            "status": "completed",
            "message": "Egnyte folder structure created successfully",
            "started_at": job_status[job_key]["started_at"],
            "completed_at": datetime.now().isoformat(),
            "progress": 100
        }
        
        logger.info(f"Background Egnyte job completed for {job_key}")
        
    except Exception as e:
        logger.error(f"Background Egnyte job failed for {job_key}: {e}")
        job_status[job_key] = {
            "status": "failed",
            "message": f"Error: {str(e)}",
            "started_at": job_status[job_key]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

def load_openai_api_key():
    """Load OpenAI API key from environment variable"""
    return os.getenv('OPENAI_API_KEY')

def initialize_openai():
    """Initialize OpenAI client"""
    api_key = load_openai_api_key()
    if api_key and api_key != "your-openai-api-key-here":
        try:
            client = OpenAI(api_key=api_key)
            return client
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {e}")
            return None
    return None

def create_sample_pharma_data():
    """Create sample pharmaceutical composition data"""
    data = {
        'Component': [
            'Active Pharmaceutical Ingredient',
            'Microcrystalline Cellulose',
            'Lactose Monohydrate',
            'Croscarmellose Sodium',
            'Magnesium Stearate',
            'Opadry II White'
        ],
        'Quality_Reference': ['USP', 'NF', 'NF', 'NF', 'NF', 'NF'],
        'Function': [
            'Active Ingredient',
            'Tablet Diluent',
            'Tablet Diluent',
            'Disintegrant',
            'Lubricant',
            'Film Coating'
        ],
        'Quantity_mg_per_tablet': [25.0, 150.0, 100.0, 10.0, 2.0, 8.0]
    }
    return pd.DataFrame(data)

def generate_regulatory_text_with_ai(product_code: str, dosage_form: str, 
                                   composition_data: pd.DataFrame, 
                                   mechanism_of_action: str,
                                   drug_info: Dict,
                                   additional_instructions: str = "") -> Dict[str, str]:
    """Generate regulatory text using OpenAI"""
    client = initialize_openai()
    if not client:
        raise RuntimeError("OpenAI API key not found or invalid.")
    
    try:
        # Prepare composition data for AI
        composition_text = ""
        total_weight = 0
        for _, row in composition_data.iterrows():
            component = row['Component']
            quality_ref = row['Quality_Reference']
            function = row['Function']
            quantity = row['Quantity_mg_per_tablet']
            total_weight += quantity
            composition_text += f"- {component} ({quality_ref}): {quantity} mg ({function})\n"
        composition_text += f"- Total Weight: {total_weight} mg"
        
        # Build prompt
        additional_prompt = ""
        if additional_instructions.strip():
            additional_prompt = f"\nAdditional Instructions: {additional_instructions}"
        
        prompt = f"""
You are a regulatory-writing assistant drafting Section 3.2.P.1 "Description and Composition of the Drug Product" for an IND that is currently in Phase II clinical trials. All content must be suitable for direct inclusion in an eCTD‐compliant Module 3 dossier.

Product Information:
- Product code: {product_code}
- Dosage form: {dosage_form}
- Drug class: {drug_info.get('class', 'Not specified')}
- Indication: {drug_info.get('indication', 'Not specified')}
- Mechanism of action: {mechanism_of_action}

Composition data:
{composition_text}{additional_prompt}

Required Output Structure:
1. 3.2.P.1.1 Description of the Dosage Form
   - One concise paragraph that identifies the dosage form and strength(s)
   - States the active‐ingredient concentration(s) clearly
   - Summarises the mechanism of action in one sentence
   - Write in the third person, scientific style; do not use marketing language

2. 3.2.P.1.2 Composition
   - Introductory sentence: "The qualitative and quantitative composition of the {product_code} is provided in Table 1."
   - Table 1 should be titled 'Composition of the {product_code}'
   - Include all components with their quality references, functions, and quantities
   - Do not include markdown or ASCII tables in the text. Only refer to the table by title or as Table 1.

3. 3.2.P.1.3 Pharmaceutical Development
   - Brief description of formulation development considerations
   - Reference to key excipient functions

4. 3.2.P.1.4 Manufacturing Process
   - Overview of the manufacturing process
   - Key process parameters and controls

Please provide the text in a structured format suitable for regulatory submission.
"""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a pharmaceutical regulatory writing expert with deep knowledge of FDA and ICH guidelines for IND submissions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.3
        )
        
        ai_text = response.choices[0].message.content
        sections = parse_ai_response(ai_text, product_code)
        return sections
        
    except Exception as e:
        raise RuntimeError(f"OpenAI API request failed: {e}")

def parse_ai_response(ai_text: str, product_code: str) -> Dict[str, str]:
    """Parse AI response into structured sections"""
    sections = {
        'description': '',
        'composition_intro': '',
        'pharmaceutical_development': '',
        'manufacturing_process': '',
        'table_title': f'Composition of the {product_code}'
    }
    
    lines = ai_text.split('\n')
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        # Detect section headers
        if '3.2.P.1.1' in line or 'Description' in line:
            current_section = 'description'
            continue
        elif '3.2.P.1.2' in line or 'Composition' in line:
            current_section = 'composition_intro'
            continue
        elif '3.2.P.1.3' in line or 'Pharmaceutical Development' in line:
            current_section = 'pharmaceutical_development'
            continue
        elif '3.2.P.1.4' in line or 'Manufacturing Process' in line:
            current_section = 'manufacturing_process'
            continue
        elif line.startswith('Table') or line.startswith('The qualitative'):
            current_section = 'composition_intro'
        
        # Add content to appropriate section
        if current_section and line:
            if current_section == 'description':
                sections['description'] += line + ' '
            elif current_section == 'composition_intro':
                sections['composition_intro'] += line + ' '
            elif current_section == 'pharmaceutical_development':
                sections['pharmaceutical_development'] += line + ' '
            elif current_section == 'manufacturing_process':
                sections['manufacturing_process'] += line + ' '
    
    return sections

def export_to_pdf_regulatory(df: pd.DataFrame, sections: Dict[str, str], 
                            product_code: str, dosage_form: str,
                            molecule_code: str = None, campaign_number: str = None):
    """Export regulatory document to PDF format"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Add title with campaign information
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=1
    )
    title_text = 'Section 3.2.P.1 Description and Composition of the Drug Product'
    if molecule_code and campaign_number:
        title_text += f' - Molecule {molecule_code} Campaign {campaign_number}'
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 12))
    
    # Add campaign information header
    if molecule_code and campaign_number:
        story.append(Paragraph('Project Information', styles['Heading2']))
        story.append(Paragraph(f'Molecule Code: {molecule_code}', styles['Normal']))
        story.append(Paragraph(f'Campaign Number: {campaign_number}', styles['Normal']))
        story.append(Paragraph(f'Product Code: {product_code}', styles['Normal']))
        story.append(Paragraph(f'Dosage Form: {dosage_form}', styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Add description section
    story.append(Paragraph('3.2.P.1.1 Description of the Dosage Form', styles['Heading2']))
    story.append(Paragraph(sections['description'], styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Add composition section
    story.append(Paragraph('3.2.P.1.2 Composition', styles['Heading2']))
    story.append(Paragraph(sections['composition_intro'], styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Prepare table data
    headers = ['Component', 'Quality Reference', 'Function', 'Quantity / Unit (mg per tablet)']
    table_data = [headers]
    
    total_weight = 0
    for _, row in df.iterrows():
        table_data.append([
            str(row['Component']),
            str(row['Quality_Reference']),
            str(row['Function']),
            str(row['Quantity_mg_per_tablet'])
        ])
        total_weight += row['Quantity_mg_per_tablet']
    
    # Add total weight row
    table_data.append(['Total Weight', '', '', str(total_weight)])
    
    # Create table
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 12))
    
    # Add footnote
    story.append(Paragraph("Abbreviations: NF = National Formulary; Ph. Eur. = European Pharmacopoeia; USP = United States Pharmacopoeia.", styles['Normal']))
    
    # Add pharmaceutical development
    if sections.get('pharmaceutical_development'):
        story.append(Paragraph('3.2.P.1.3 Pharmaceutical Development', styles['Heading2']))
        story.append(Paragraph(sections['pharmaceutical_development'], styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Add manufacturing process
    if sections.get('manufacturing_process'):
        story.append(Paragraph('3.2.P.1.4 Manufacturing Process', styles['Heading2']))
        story.append(Paragraph(sections['manufacturing_process'], styles['Normal']))
        story.append(Spacer(1, 12))
    
    doc.build(story)
    return buffer


@app.route('/test-thread', methods=['GET'])
def test_thread():
    """Test endpoint to verify threading works"""
    import time
    
    def background_test():
        logger.info("BACKGROUND TEST: Starting sleep...")
        time.sleep(10)  # Sleep for 10 seconds
        logger.info("BACKGROUND TEST: Sleep completed!")
    
    logger.info("TEST: Starting background thread test")
    thread = threading.Thread(target=background_test, daemon=True)
    thread.start()
    logger.info("TEST: Background thread started, returning immediately")
    
    return jsonify({
        "status": "success",
        "message": "Background thread test started",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/folder-status', methods=['GET'])
def folder_status():
    """Check the status of a folder creation job"""
    try:
        molecule_code = request.args.get('molecule_code')
        campaign_number = request.args.get('campaign_number')
        
        if not molecule_code or not campaign_number:
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        job_key = f"{molecule_code}_{campaign_number}"
        
        if job_key not in job_status:
            return jsonify({
                "status": "not_found",
                "message": "No job found for this molecule and campaign",
                "job_key": job_key
            })
        
        status_info = job_status[job_key]
        
        response = {
            "status": status_info["status"],
            "message": status_info["message"],
            "job_key": job_key,
            "started_at": status_info["started_at"]
        }
        
        # Add progress if available
        if "progress" in status_info:
            response["progress"] = status_info["progress"]
        
        # Add completion time if available
        if "completed_at" in status_info:
            response["completed_at"] = status_info["completed_at"]
        
        # Add result data if completed
        if status_info["status"] == "completed" and job_key in job_results:
            response["data"] = job_results[job_key]
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in folder_status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/generate-document', methods=['POST'])
def generate_document():
    """Start background job to generate regulatory document"""
    try:
        logger.info("START: generate_document route")
        
        data = request.get_json()
        
        if not data:
            logger.error("No JSON data provided")
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Extract required parameters
        molecule_code = data.get('molecule_code')
        campaign_number = data.get('campaign_number')
        product_code = data.get('product_code', 'DRUG-001')
        dosage_form = data.get('dosage_form', 'Immediate-release film-coated tablet')
        mechanism_of_action = data.get('mechanism_of_action', 'Standard mechanism of action')
        drug_class = data.get('drug_class', 'Standard class')
        indication = data.get('indication', 'Standard indication')
        
        # Optional parameters
        composition_data = data.get('composition_data')
        additional_instructions = data.get('additional_instructions', '')
        
        if not molecule_code or not campaign_number:
            logger.error("Missing required parameters")
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        logger.info(f"Processing document generation for molecule: {molecule_code}, campaign: {campaign_number}")
        
        job_key = f"doc_{molecule_code}_{campaign_number}"
        
        # Check if job is already running
        if job_key in job_status and job_status[job_key]["status"] == "running":
            logger.info(f"Document generation job already running for {job_key}")
            return jsonify({
                "status": "already_running",
                "message": "Document generation job is already running",
                "job_key": job_key
            })
        
        # Check if job is already completed
        if job_key in job_status and job_status[job_key]["status"] == "completed":
            logger.info(f"Document generation job already completed for {job_key}")
            return jsonify({
                "status": "already_completed",
                "message": "Document already exists",
                "job_key": job_key,
                "data": job_results.get(job_key)
            })
        
        logger.info(f"Starting background thread for {job_key}")
        
        # Start background thread
        thread = threading.Thread(
            target=background_generate_document,
            args=(molecule_code, campaign_number, product_code, dosage_form, 
                  mechanism_of_action, drug_class, indication, additional_instructions, composition_data),
            daemon=True
        )
        thread.start()
        
        logger.info(f"RETURNING: Background document generation job started for {job_key}")
        
        return jsonify({
            "status": "started",
            "message": "Document generation job started",
            "job_key": job_key,
            "poll_url": f"/document-status?molecule_code={molecule_code}&campaign_number={campaign_number}"
        })
        
    except Exception as e:
        logger.error(f"Error in generate_document: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/document-status', methods=['GET'])
def document_status():
    """Check the status of a document generation job"""
    try:
        molecule_code = request.args.get('molecule_code')
        campaign_number = request.args.get('campaign_number')
        
        if not molecule_code or not campaign_number:
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        job_key = f"doc_{molecule_code}_{campaign_number}"
        
        if job_key not in job_status:
            return jsonify({
                "status": "not_found",
                "message": "No document generation job found for this molecule and campaign",
                "job_key": job_key
            })
        
        status_info = job_status[job_key]
        
        response = {
            "status": status_info["status"],
            "message": status_info["message"],
            "job_key": job_key,
            "started_at": status_info["started_at"]
        }
        
        # Add progress if available
        if "progress" in status_info:
            response["progress"] = status_info["progress"]
        
        # Add completion time if available
        if "completed_at" in status_info:
            response["completed_at"] = status_info["completed_at"]
        
        # Add result data if completed
        if status_info["status"] == "completed" and job_key in job_results:
            response["data"] = job_results[job_key]
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in document_status: {e}")
        return jsonify({"error": str(e)}), 500

# Egnyte API Routes
@app.route('/egnyte-generate-folder-structure', methods=['POST'])
def egnyte_generate_folder_structure():
    """Start background job to generate Egnyte folder structure"""
    if not EGNYTE_AVAILABLE:
        return jsonify({"error": "Egnyte integration not available. Please configure Egnyte credentials."}), 503
        
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        molecule_code = data.get('molecule_code')
        campaign_number = data.get('campaign_number')
        
        if not molecule_code or not campaign_number:
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        job_key = f"egnyte_{molecule_code}_{campaign_number}"
        
        # Check if job is already running
        if job_key in job_status and job_status[job_key]["status"] == "running":
            return jsonify({
                "status": "already_running",
                "message": "Egnyte folder creation job is already running",
                "job_key": job_key
            })
        
        # Check if job is already completed
        if job_key in job_status and job_status[job_key]["status"] == "completed":
            return jsonify({
                "status": "already_completed",
                "message": "Egnyte folder structure already exists",
                "job_key": job_key,
                "data": job_results.get(job_key)
            })
        
        # Start background thread
        thread = threading.Thread(
            target=background_create_egnyte_folders,
            args=(molecule_code, campaign_number),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "status": "started",
            "message": "Egnyte folder creation job started",
            "job_key": job_key,
            "poll_url": f"/egnyte-folder-status?molecule_code={molecule_code}&campaign_number={campaign_number}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-folder-status', methods=['GET'])
def egnyte_folder_status():
    """Check the status of an Egnyte folder creation job"""
    try:
        molecule_code = request.args.get('molecule_code')
        campaign_number = request.args.get('campaign_number')
        
        if not molecule_code or not campaign_number:
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        job_key = f"egnyte_{molecule_code}_{campaign_number}"
        
        if job_key not in job_status:
            return jsonify({
                "status": "not_found",
                "message": "No Egnyte job found for this molecule and campaign",
                "job_key": job_key
            })
        
        status_info = job_status[job_key]
        
        response = {
            "status": status_info["status"],
            "message": status_info["message"],
            "job_key": job_key,
            "started_at": status_info["started_at"]
        }
        
        # Add progress if available
        if "progress" in status_info:
            response["progress"] = status_info["progress"]
        
        # Add completion time if available
        if "completed_at" in status_info:
            response["completed_at"] = status_info["completed_at"]
        
        # Add result data if completed
        if status_info["status"] == "completed" and job_key in job_results:
            response["data"] = job_results[job_key]
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-list-folder', methods=['GET'])
def egnyte_list_folder():
    """List contents of an Egnyte folder"""
    if not EGNYTE_AVAILABLE:
        return jsonify({"error": "Egnyte integration not available. Please configure Egnyte credentials."}), 503
        
    try:
        folder_id = request.args.get('folder_id', ROOT_FOLDER)
        
        access_token = get_egnyte_token()
        if not access_token:
            return jsonify({"error": "Failed to get Egnyte access token"}), 500
        
        folder_data = list_egnyte_folder_contents(access_token, folder_id)
        if not folder_data:
            return jsonify({"error": "Failed to list folder contents"}), 500
        
        return jsonify({
            "status": "success",
            "folder_id": folder_id,
            "folders": folder_data.get("folders", []),
            "files": folder_data.get("files", []),
            "total_folders": len(folder_data.get("folders", [])),
            "total_files": len(folder_data.get("files", []))
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-create-folder', methods=['POST'])
def egnyte_create_folder():
    """Create a new folder in Egnyte"""
    if not EGNYTE_AVAILABLE:
        return jsonify({"error": "Egnyte integration not available. Please configure Egnyte credentials."}), 503
        
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        parent_folder_id = data.get('parent_folder_id', ROOT_FOLDER)
        folder_name = data.get('folder_name')
        
        if not folder_name:
            return jsonify({"error": "folder_name is required"}), 400
        
        access_token = get_egnyte_token()
        if not access_token:
            return jsonify({"error": "Failed to get Egnyte access token"}), 500
        
        result = create_egnyte_folder(access_token, parent_folder_id, folder_name)
        if not result:
            return jsonify({"error": "Failed to create folder"}), 500
        
        return jsonify({
            "status": "success",
            "message": "Folder created successfully",
            "data": {
                "folder_id": result.get('folder_id'),
                "name": result.get('name'),
                "path": result.get('path'),
                "url": f"https://{DOMAIN}/app/index.do#storage/files/1{result.get('path', '')}"
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-list-templates', methods=['GET'])
def egnyte_list_templates():
    """List all items in the templates folder"""
    if not EGNYTE_AVAILABLE:
        return jsonify({"error": "Egnyte integration not available. Please configure Egnyte credentials."}), 503
        
    try:
        templates_folder_id = "966281ab-54c3-47ea-b20f-b38ed2ef9b30"
        
        access_token = get_egnyte_token()
        if not access_token:
            return jsonify({"error": "Failed to get Egnyte access token"}), 500
        
        folder_data = list_egnyte_folder_contents(access_token, templates_folder_id)
        if not folder_data:
            return jsonify({"error": "Failed to list templates folder contents"}), 500
        
        return jsonify({
            "status": "success",
            "folder_id": templates_folder_id,
            "templates": folder_data.get("files", []),
            "folders": folder_data.get("folders", []),
            "total_templates": len(folder_data.get("files", [])),
            "total_folders": len(folder_data.get("folders", []))
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-list-source-documents', methods=['GET'])
def egnyte_list_source_documents():
    """List all items in the source documents folder"""
    if not EGNYTE_AVAILABLE:
        return jsonify({"error": "Egnyte integration not available. Please configure Egnyte credentials."}), 503
        
    try:
        source_docs_folder_id = "56545792-6b5d-4fc3-8e78-31d401bd7088"
        
        access_token = get_egnyte_token()
        if not access_token:
            return jsonify({"error": "Failed to get Egnyte access token"}), 500
        
        folder_data = list_egnyte_folder_contents(access_token, source_docs_folder_id)
        if not folder_data:
            return jsonify({"error": "Failed to list source documents folder contents"}), 500
        
        return jsonify({
            "status": "success",
            "folder_id": source_docs_folder_id,
            "documents": folder_data.get("files", []),
            "folders": folder_data.get("folders", []),
            "total_documents": len(folder_data.get("files", [])),
            "total_folders": len(folder_data.get("folders", []))
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-download-file', methods=['POST'])
def egnyte_download_file():
    """Download a file from Egnyte"""
    if not EGNYTE_AVAILABLE:
        return jsonify({"error": "Egnyte integration not available. Please configure Egnyte credentials."}), 503
        
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        file_id = data.get('file_id')
        
        if not file_id:
            return jsonify({"error": "file_id is required"}), 400
        
        access_token = get_egnyte_token()
        if not access_token:
            return jsonify({"error": "Failed to get Egnyte access token"}), 500
        
        # Download the file
        url = f"https://{DOMAIN}/pubapi/v1/fs-content/ids/file/{file_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        try:
            rate_limit_delay()
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Return the file content as base64
            file_content = base64.b64encode(response.content).decode('utf-8')
            
            return jsonify({
                "status": "success",
                "file_id": file_id,
                "content": file_content,
                "content_type": response.headers.get('content-type', 'application/octet-stream'),
                "size": len(response.content)
            })
            
        except requests.HTTPError as e:
            logger.error(f"Failed to download file {file_id}: {e}")
            return jsonify({"error": f"Failed to download file: {e}"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-generate-document', methods=['POST'])
def egnyte_generate_document():
    """Generate a new document using OpenAI and save to Egnyte"""
    if not EGNYTE_AVAILABLE:
        return jsonify({"error": "Egnyte integration not available. Please configure Egnyte credentials."}), 503
        
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        template_file_id = data.get('template_file_id')
        source_document_ids = data.get('source_document_ids', [])
        molecule_code = data.get('molecule_code')
        campaign_number = data.get('campaign_number')
        document_name = data.get('document_name', 'Generated Document')
        
        if not template_file_id:
            return jsonify({"error": "template_file_id is required"}), 400
        
        if not source_document_ids:
            return jsonify({"error": "source_document_ids is required"}), 400
        
        if not molecule_code or not campaign_number:
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        # Create job key for tracking
        job_key = f"doc_gen_{molecule_code}_{campaign_number}_{int(time.time())}"
        
        # Start background thread
        thread = threading.Thread(
            target=background_generate_egnyte_document,
            args=(template_file_id, source_document_ids, molecule_code, campaign_number, document_name, job_key),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            "status": "started",
            "message": "Document generation job started",
            "job_key": job_key,
            "poll_url": f"/egnyte-document-status?job_key={job_key}"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/egnyte-document-status', methods=['GET'])
def egnyte_document_status():
    """Check the status of a document generation job"""
    try:
        job_key = request.args.get('job_key')
        
        if not job_key:
            return jsonify({"error": "job_key is required"}), 400
        
        if job_key not in job_status:
            return jsonify({
                "status": "not_found",
                "message": "No document generation job found",
                "job_key": job_key
            })
        
        status_info = job_status[job_key]
        
        response = {
            "status": status_info["status"],
            "message": status_info["message"],
            "job_key": job_key,
            "started_at": status_info["started_at"]
        }
        
        # Add progress if available
        if "progress" in status_info:
            response["progress"] = status_info["progress"]
        
        # Add completion time if available
        if "completed_at" in status_info:
            response["completed_at"] = status_info["completed_at"]
        
        # Add result data if completed
        if status_info["status"] == "completed" and job_key in job_results:
            response["data"] = job_results[job_key]
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def background_generate_egnyte_document(template_file_id, source_document_ids, molecule_code, campaign_number, document_name, job_key):
    """Background function to generate document using OpenAI and save to Egnyte"""
    logger.info(f"BACKGROUND: Starting document generation for {job_key}")
    
    try:
        # Update status to running
        job_status[job_key] = {
            "status": "running",
            "message": "Starting document generation...",
            "started_at": datetime.now().isoformat(),
            "progress": 0
        }
        
        # Get access token
        access_token = get_egnyte_token()
        if not access_token:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to get Egnyte access token",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Update progress
        job_status[job_key]["progress"] = 10
        job_status[job_key]["message"] = "Downloading template file..."
        
        # Download template file
        template_content = download_egnyte_file(access_token, template_file_id)
        if not template_content:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to download template file",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Update progress
        job_status[job_key]["progress"] = 20
        job_status[job_key]["message"] = "Downloading source documents..."
        
        # Download source documents
        source_contents = []
        for i, doc_id in enumerate(source_document_ids):
            content = download_egnyte_file(access_token, doc_id)
            if content:
                source_contents.append(content)
            
            # Update progress for each document
            progress = 20 + (i + 1) * 20 // len(source_document_ids)
            job_status[job_key]["progress"] = progress
            job_status[job_key]["message"] = f"Downloaded {i + 1}/{len(source_document_ids)} source documents..."
        
        if not source_contents:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to download any source documents",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Update progress
        job_status[job_key]["progress"] = 60
        job_status[job_key]["message"] = "Generating document with OpenAI..."
        
        # Generate document using OpenAI
        generated_content = generate_document_with_openai(template_content, source_contents, document_name)
        if not generated_content:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to generate document with OpenAI",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Update progress
        job_status[job_key]["progress"] = 80
        job_status[job_key]["message"] = "Saving document to Egnyte..."
        
        # Find the target folder in Egnyte
        target_folder_id = find_egnyte_target_folder(access_token, molecule_code, campaign_number)
        if not target_folder_id:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to find target folder in Egnyte",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Upload the generated document
        file_name = f"{document_name}_{molecule_code}_Campaign_{campaign_number}.docx"
        uploaded_file = upload_file_to_egnyte(access_token, target_folder_id, file_name, generated_content)
        if not uploaded_file:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to upload document to Egnyte",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Store the result
        job_results[job_key] = {
            "status": "success",
            "file_name": file_name,
            "file_id": uploaded_file.get('entry_id'),
            "file_url": f"https://{DOMAIN}/app/index.do#storage/files/1{uploaded_file.get('path', '')}",
            "molecule_code": molecule_code,
            "campaign_number": campaign_number,
            "document_name": document_name
        }
        
        # Update status to completed
        job_status[job_key] = {
            "status": "completed",
            "message": "Document generated and saved successfully",
            "started_at": job_status[job_key]["started_at"],
            "completed_at": datetime.now().isoformat(),
            "progress": 100
        }
        
        logger.info(f"Background document generation completed for {job_key}")
        
    except Exception as e:
        logger.error(f"Background document generation failed for {job_key}: {e}")
        job_status[job_key] = {
            "status": "failed",
            "message": f"Error: {str(e)}",
            "started_at": job_status[job_key]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

def download_egnyte_file(access_token, file_id):
    """Download a file from Egnyte and return its content"""
    try:
        url = f"https://{DOMAIN}/pubapi/v1/fs-content/ids/file/{file_id}"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        rate_limit_delay()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error downloading file {file_id}: {e}")
        return None

def find_egnyte_target_folder(access_token, molecule_code, campaign_number):
    """Find the target folder in Egnyte for the generated document"""
    try:
        # First, find the project folder
        project_folder_name = f"Project; Molecule {molecule_code}"
        project_folder = find_folder_by_name(access_token, ROOT_FOLDER, project_folder_name)
        
        if not project_folder:
            logger.error(f"Project folder not found: {project_folder_name}")
            return None
        
        # Find the campaign folder
        campaign_folder_name = f"Project {molecule_code} (Campaign #{campaign_number})"
        campaign_folder = find_folder_by_name(access_token, project_folder.get('folder_id'), campaign_folder_name)
        
        if not campaign_folder:
            logger.error(f"Campaign folder not found: {campaign_folder_name}")
            return None
        
        # Find the Draft AI Reg Document folder
        reg_doc_folder = find_folder_by_name(access_token, project_folder.get('folder_id'), "Draft AI Reg Document")
        
        if not reg_doc_folder:
            logger.error("Draft AI Reg Document folder not found")
            return None
        
        return reg_doc_folder.get('folder_id')
        
    except Exception as e:
        logger.error(f"Error finding target folder: {e}")
        return None

def find_folder_by_name(access_token, parent_folder_id, folder_name):
    """Find a folder by name in a parent folder"""
    try:
        folder_data = list_egnyte_folder_contents(access_token, parent_folder_id)
        if folder_data and isinstance(folder_data, dict):
            folders = folder_data.get("folders", [])
            for folder in folders:
                if folder.get('name') == folder_name:
                    return folder
        return None
    except Exception as e:
        logger.error(f"Error finding folder by name: {e}")
        return None

def upload_file_to_egnyte(access_token, folder_id, file_name, file_content):
    """Upload a file to Egnyte"""
    try:
        url = f"https://{DOMAIN}/pubapi/v1/fs-content/ids/folder/{folder_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        }
        
        files = {
            'file': (file_name, file_content, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        }
        
        rate_limit_delay()
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        logger.error(f"Error uploading file to Egnyte: {e}")
        return None

def generate_document_with_openai(template_content, source_contents, document_name):
    """Generate a document using OpenAI based on template and source documents"""
    try:
        # Initialize OpenAI
        client = initialize_openai()
        if not client:
            logger.error("Failed to initialize OpenAI")
            return None
        
        # Convert template content to text (assuming it's a Word document)
        template_text = extract_text_from_docx(template_content)
        
        # Convert source documents to text
        source_texts = []
        for content in source_contents:
            text = extract_text_from_docx(content)
            if text:
                source_texts.append(text)
        
        # Create the prompt for OpenAI
        prompt = f"""
        You are a document generation assistant. Please create a new document based on the following:

        TEMPLATE DOCUMENT:
        {template_text}

        SOURCE DOCUMENTS:
        {chr(10).join([f"Document {i+1}: {text}" for i, text in enumerate(source_texts)])}

        INSTRUCTIONS:
        1. Use the template document as the structure and format
        2. Incorporate relevant information from the source documents
        3. Create a comprehensive, well-structured document
        4. Maintain professional tone and formatting
        5. Document name: {document_name}

        Please generate the complete document content.
        """
        
        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional document generation assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.7
        )
        
        generated_text = response.choices[0].message.content
        
        # Convert the generated text back to a Word document
        doc = Document()
        
        # Add title
        title = doc.add_heading(document_name, 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Add content
        paragraphs = generated_text.split('\n\n')
        for paragraph in paragraphs:
            if paragraph.strip():
                doc.add_paragraph(paragraph.strip())
        
        # Save to bytes
        doc_bytes = io.BytesIO()
        doc.save(doc_bytes)
        doc_bytes.seek(0)
        
        return doc_bytes.getvalue()
        
    except Exception as e:
        logger.error(f"Error generating document with OpenAI: {e}")
        return None

def extract_text_from_docx(docx_content):
    """Extract text from a Word document"""
    try:
        doc = Document(io.BytesIO(docx_content))
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text.strip())
        return '\n\n'.join(text)
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        return ""

@app.route('/egnyte-clear-cache', methods=['POST'])
def egnyte_clear_cache():
    """Clear the Egnyte token cache"""
    try:
        clear_egnyte_token_cache()
        return jsonify({
            "status": "success",
            "message": "Egnyte token cache cleared"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/reg-docs-bulk-request', methods=['POST'])
def reg_docs_bulk_request():
    """Bulk request for regulatory documents"""
    try:
        data = request.get_json()
        timestamp_clean = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        request_df = pd.DataFrame(data)
        print(request_df.columns)
        
        # Check that request contains docs 
        if len(request_df) == 0:
            return jsonify({"status": "error", "message": "No requests from campaign folder received"}), 400
        
        print("Received bulk request from Retool at ", timestamp_clean)
        return jsonify({"status": "success", "message": "Bulk request received"}), 200
    except Exception as e:
        logger.error(f"Error in folder_status: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000) 

