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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from werkzeug.utils import secure_filename
import logging
import threading
import time
from datetime import datetime
import requests

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
RATE_LIMIT_DELAY = 0.6  # Wait 0.6 seconds between calls (allows ~1.67 calls/sec, safely under 2/sec)

def rate_limit_delay():
    """Add delay to respect rate limits"""
    time.sleep(RATE_LIMIT_DELAY)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# In-memory storage for job results
job_results = {}
job_status = {}

# Drug database
DRUG_DATABASE = {
    "Metformin": {
        "dosage_form": "Immediate-release film-coated tablet",
        "mechanism": "Metformin is a biguanide antihyperglycemic agent that improves glucose tolerance in patients with type 2 diabetes, lowering both basal and postprandial plasma glucose. Its pharmacologic mechanisms of action are different from other classes of oral antihyperglycemic agents.",
        "indication": "Type 2 diabetes mellitus",
        "strength": "500 mg, 850 mg, 1000 mg",
        "class": "Biguanide",
        "manufacturer": "Various"
    },
    "Atorvastatin": {
        "dosage_form": "Film-coated tablet",
        "mechanism": "Atorvastatin is a selective, competitive inhibitor of HMG-CoA reductase, the rate-limiting enzyme that converts 3-hydroxy-3-methylglutaryl-coenzyme A to mevalonate, a precursor of sterols, including cholesterol.",
        "indication": "Hypercholesterolemia and cardiovascular risk reduction",
        "strength": "10 mg, 20 mg, 40 mg, 80 mg",
        "class": "HMG-CoA reductase inhibitor (statin)",
        "manufacturer": "Various"
    },
    "Lisinopril": {
        "dosage_form": "Film-coated tablet",
        "mechanism": "Lisinopril is a competitive inhibitor of angiotensin-converting enzyme (ACE). ACE is a peptidyl dipeptidase that catalyzes the conversion of angiotensin I to the vasoconstrictor substance, angiotensin II.",
        "indication": "Hypertension, heart failure, myocardial infarction",
        "strength": "2.5 mg, 5 mg, 10 mg, 20 mg, 30 mg, 40 mg",
        "class": "ACE inhibitor",
        "manufacturer": "Various"
    },
    "Omeprazole": {
        "dosage_form": "Delayed-release capsule",
        "mechanism": "Omeprazole is a proton pump inhibitor that suppresses gastric acid secretion by specific inhibition of the H+/K+-ATPase in the gastric parietal cell.",
        "indication": "Gastroesophageal reflux disease, peptic ulcer disease",
        "strength": "10 mg, 20 mg, 40 mg",
        "class": "Proton pump inhibitor",
        "manufacturer": "Various"
    },
    "Custom Drug": {
        "dosage_form": "Immediate-release film-coated tablet",
        "mechanism": "The active ingredient selectively inhibits the target enzyme, leading to therapeutic effects in the treatment of the indicated condition.",
        "indication": "Custom indication",
        "strength": "25 mg",
        "class": "Custom class",
        "manufacturer": "Custom manufacturer"
    }
}

# Egnyte API Functions
def get_egnyte_token():
    """Get Egnyte access token"""
    if not EGNYTE_AVAILABLE:
        logger.error("Egnyte credentials not available")
        return None
        
    url = f"https://{DOMAIN}/puboauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    try:
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        return token_data["access_token"]
    except Exception as e:
        logger.error(f"Error getting Egnyte token: {e}")
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
        existing_folders = list_egnyte_folder_contents(access_token, ROOT_FOLDER)
        if existing_folders:
            for folder in existing_folders:
                if folder.get('name') == project_folder_name:
                    # Check if campaign folder already exists
                    campaign_folder_name = f"Project {molecule_code} (Campaign #{campaign_number})"
                    campaign_contents = list_egnyte_folder_contents(access_token, folder.get('folder_id'))
                    if campaign_contents:
                        for campaign_folder in campaign_contents:
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
        
        if not project_folder:
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
        
        if not campaign_folder:
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
        
        if not pre_folder or not post_folder:
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
                if dept_folder:
                    dept_folder_id = dept_folder.get('folder_id')
                    
                    # Create status folders under each department
                    for status in statuses:
                        create_egnyte_folder(access_token, dept_folder_id, status)
        
        # Update progress
        job_status[job_key]["progress"] = 80
        job_status[job_key]["message"] = "Creating Draft AI Reg Document folder..."
        
        # Create Draft AI Reg Document folder under project
        reg_doc_folder = create_egnyte_folder(access_token, project_folder_id, "Draft AI Reg Document")
        if not reg_doc_folder:
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
            if reg_type_folder:
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

def load_google_drive_credentials():
    """Load Google Drive API credentials from environment variables or JSON file"""
    try:
        # Try to load from environment variables first
        credentials_dict = {
            "type": os.getenv('GOOGLE_DRIVE_TYPE'),
            "project_id": os.getenv('GOOGLE_DRIVE_PROJECT_ID'),
            "private_key_id": os.getenv('GOOGLE_DRIVE_PRIVATE_KEY_ID'),
            "private_key": os.getenv('GOOGLE_DRIVE_PRIVATE_KEY'),
            "client_email": os.getenv('GOOGLE_DRIVE_CLIENT_EMAIL'),
            "client_id": os.getenv('GOOGLE_DRIVE_CLIENT_ID'),
            "auth_uri": os.getenv('GOOGLE_DRIVE_AUTH_URI'),
            "token_uri": os.getenv('GOOGLE_DRIVE_TOKEN_URI'),
            "auth_provider_x509_cert_url": os.getenv('GOOGLE_DRIVE_AUTH_PROVIDER_X509_CERT_URL'),
            "client_x509_cert_url": os.getenv('GOOGLE_DRIVE_CLIENT_X509_CERT_URL')
        }
        
        # Check if all required fields are present
        if all(credentials_dict.values()):
            creds = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            return creds
        
        # If not in environment, try to load from local JSON file
        json_file_path = 'aaitdemoharmony-3945571299f1.json'
        if os.path.exists(json_file_path):
            creds = service_account.Credentials.from_service_account_file(
                json_file_path, 
                scopes=['https://www.googleapis.com/auth/drive']
            )
            return creds
        
        return None
        
    except Exception as e:
        logger.error(f"Error loading Google Drive credentials: {e}")
        return None

def get_shared_drive_id(service):
    """Get the first available shared drive ID"""
    try:
        drives = service.drives().list(pageSize=10).execute()
        shared_drives = drives.get('drives', [])
        
        if shared_drives:
            return shared_drives[0]['id']
        else:
            logger.warning("No shared drives found")
            return None
    except Exception as e:
        logger.error(f"Error accessing shared drives: {e}")
        return None

def initialize_google_drive_service():
    """Initialize Google Drive service with credentials"""
    creds = load_google_drive_credentials()
    if creds:
        try:
            service = build('drive', 'v3', credentials=creds)
            return service
        except Exception as e:
            logger.error(f"Error initializing Google Drive service: {e}")
            return None
    return None

def create_google_drive_folder(service, folder_name: str, parent_folder_id: str = None, shared_drive_id: str = None):
    """Create a new folder in Google Drive"""
    try:
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_folder_id:
            folder_metadata['parents'] = [parent_folder_id]
        
        if shared_drive_id:
            folder = service.files().create(
                body=folder_metadata, 
                fields='id, name, webViewLink',
                supportsAllDrives=True,
                supportsTeamDrives=True
            ).execute()
        else:
            folder = service.files().create(
                body=folder_metadata, 
                fields='id, name, webViewLink'
            ).execute()
        
        return folder
    except Exception as e:
        logger.error(f"Error creating folder '{folder_name}': {e}")
        return None

def check_existing_project_folder(service, molecule_code: str, parent_folder_id: str = None):
    """Check if a project folder with the same molecule code already exists"""
    try:
        project_folder_name = f"Project; Molecule {molecule_code}"
        
        if parent_folder_id:
            query = f"'{parent_folder_id}' in parents and name = '{project_folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        else:
            query = f"'{parent_folder_id or '0ALsvNdCE73XrUk9PVA'}' in parents and name = '{project_folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        
        results = service.files().list(
            q=query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            supportsTeamDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        existing_folders = results.get('files', [])
        
        return existing_folders[0] if existing_folders else None
    except Exception as e:
        logger.error(f"Error checking existing project folder: {e}")
        return None

def upload_file_to_google_drive(service, file_data: bytes, file_name: str, mime_type: str, folder_id: str = None, shared_drive_id: str = None):
    """Upload a file to Google Drive"""
    try:
        file_metadata = {
            'name': file_name
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        file_stream = io.BytesIO(file_data)
        
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(
            file_stream,
            mimetype=mime_type,
            resumable=True
        )
        
        if shared_drive_id:
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink',
                supportsAllDrives=True,
                supportsTeamDrives=True
            ).execute()
        else:
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink'
            ).execute()
        
        return file
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        return None

def find_target_folder(service, molecule_code: str, campaign_number: str = None):
    """Find the Draft AI Reg Document -> IND -> Draft folder for the specified project"""
    try:
        # Find the project folder
        project_folder = check_existing_project_folder(service, molecule_code, '0ALsvNdCE73XrUk9PVA')
        if not project_folder:
            return None, None
        
        # Find Draft AI Reg Document folder
        reg_doc_query = f"'{project_folder['id']}' in parents and name = 'Draft AI Reg Document' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        reg_doc_results = service.files().list(
            q=reg_doc_query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            supportsTeamDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        reg_doc_folders = reg_doc_results.get('files', [])
        
        if not reg_doc_folders:
            return None, None
        
        reg_doc_folder = reg_doc_folders[0]
        
        # Find IND folder
        ind_query = f"'{reg_doc_folder['id']}' in parents and name = 'IND' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        ind_results = service.files().list(
            q=ind_query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            supportsTeamDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        ind_folders = ind_results.get('files', [])
        
        if not ind_folders:
            return None, None
        
        ind_folder = ind_folders[0]
        
        # Find Draft folder
        draft_query = f"'{ind_folder['id']}' in parents and name = 'Draft' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        draft_results = service.files().list(
            q=draft_query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            supportsTeamDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        draft_folders = draft_results.get('files', [])
        
        if not draft_folders:
            return None, None
        
        draft_folder = draft_folders[0]
        
        full_path = f"Project; Molecule {molecule_code} → Draft AI Reg Document → IND → Draft"
        
        return draft_folder, full_path
        
    except Exception as e:
        logger.error(f"Error finding target folder: {e}")
        return None, None

def create_campaign_folder_structure(service, campaign_name: str, molecule_code: str, parent_folder_id: str = None, shared_drive_id: str = None):
    """Create the complete campaign folder structure"""
    try:
        if not parent_folder_id:
            parent_folder_id = '0ALsvNdCE73XrUk9PVA'
        
        # Check if project folder already exists
        existing_project = check_existing_project_folder(service, molecule_code, parent_folder_id)
        
        if existing_project:
            project_folder = existing_project
            logger.info(f"Using existing project folder: {project_folder['name']}")
        else:
            project_folder_name = f"Project; Molecule {molecule_code}"
            project_folder = create_google_drive_folder(service, project_folder_name, parent_folder_id, shared_drive_id)
            if not project_folder:
                return None
            logger.info(f"Created new project folder: {project_folder['name']}")
        
        # Check if campaign folder already exists
        campaign_folder_name = f"Project {molecule_code} (Campaign #{campaign_name})"
        campaign_query = f"'{project_folder['id']}' in parents and name = '{campaign_folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        campaign_results = service.files().list(
            q=campaign_query,
            fields="files(id, name)",
            supportsAllDrives=True,
            supportsTeamDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        existing_campaigns = campaign_results.get('files', [])
        
        if existing_campaigns:
            logger.warning(f"Campaign folder '{campaign_folder_name}' already exists!")
            return None
        
        # Create campaign folder
        campaign_folder = create_google_drive_folder(service, campaign_folder_name, project_folder['id'], shared_drive_id)
        if not campaign_folder:
            return None
        
        # Check if Draft AI Reg Document folder exists, create if not
        reg_doc_query = f"'{project_folder['id']}' in parents and name = 'Draft AI Reg Document' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        reg_doc_results = service.files().list(
            q=reg_doc_query,
            fields="files(id, name)",
            supportsAllDrives=True,
            supportsTeamDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        existing_reg_docs = reg_doc_results.get('files', [])
        
        if existing_reg_docs:
            reg_doc_folder = existing_reg_docs[0]
            logger.info("Using existing Draft AI Reg Document folder")
        else:
            reg_doc_folder = create_google_drive_folder(service, "Draft AI Reg Document", project_folder['id'], shared_drive_id)
            if not reg_doc_folder:
                return None
            logger.info("Created new Draft AI Reg Document folder")
        
        # Create Pre and Post folders under campaign
        pre_folder = create_google_drive_folder(service, "Pre", campaign_folder['id'], shared_drive_id)
        post_folder = create_google_drive_folder(service, "Post", campaign_folder['id'], shared_drive_id)
        
        # Create department folders under Pre and Post
        departments = ["mfg", "Anal", "Stability", "CTM"]
        statuses = ["Draft", "Review", "Approved"]
        
        for phase_folder in [pre_folder, post_folder]:
            if phase_folder:
                for dept in departments:
                    dept_folder = create_google_drive_folder(service, dept, phase_folder['id'], shared_drive_id)
                    if dept_folder:
                        for status in statuses:
                            create_google_drive_folder(service, status, dept_folder['id'], shared_drive_id)
        
        # Create regulatory document folders
        reg_types = ["IND", "IMPD", "Canada"]
        for reg_type in reg_types:
            reg_type_query = f"'{reg_doc_folder['id']}' in parents and name = '{reg_type}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            reg_type_results = service.files().list(
                q=reg_type_query,
                fields="files(id, name)",
                supportsAllDrives=True,
                supportsTeamDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            existing_reg_types = reg_type_results.get('files', [])
            
            if existing_reg_types:
                reg_type_folder = existing_reg_types[0]
            else:
                reg_type_folder = create_google_drive_folder(service, reg_type, reg_doc_folder['id'], shared_drive_id)
            
            if reg_type_folder:
                for status in statuses:
                    status_query = f"'{reg_type_folder['id']}' in parents and name = '{status}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
                    status_results = service.files().list(
                        q=status_query,
                        fields="files(id, name)",
                        supportsAllDrives=True,
                        supportsTeamDrives=True,
                        includeItemsFromAllDrives=True
                    ).execute()
                    existing_statuses = status_results.get('files', [])
                    
                    if not existing_statuses:
                        create_google_drive_folder(service, status, reg_type_folder['id'], shared_drive_id)
        
        return {
            'project_folder': project_folder,
            'campaign_folder': campaign_folder,
            'reg_doc_folder': reg_doc_folder
        }
        
    except Exception as e:
        logger.error(f"Error creating campaign folder structure: {e}")
        return None

def background_create_folders(molecule_code: str, campaign_number: str):
    """Background function to create folder structure"""
    job_key = f"{molecule_code}_{campaign_number}"
    
    logger.info(f"BACKGROUND: Starting folder creation for {job_key}")
    
    try:
        # Update status to running
        job_status[job_key] = {
            "status": "running",
            "message": "Creating folder structure...",
            "started_at": datetime.now().isoformat(),
            "progress": 0
        }
        
        logger.info(f"BACKGROUND: Status updated to running for {job_key}")
        
        # Initialize Google Drive service
        logger.info(f"BACKGROUND: Initializing Google Drive service for {job_key}")
        drive_service = initialize_google_drive_service()
        if not drive_service:
            logger.error(f"BACKGROUND: Failed to initialize Google Drive service for {job_key}")
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to initialize Google Drive service",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        logger.info(f"BACKGROUND: Google Drive service initialized for {job_key}")
        
        # Get shared drive ID
        shared_drive_id = get_shared_drive_id(drive_service)
        
        # Update progress
        job_status[job_key]["progress"] = 10
        job_status[job_key]["message"] = "Checking existing folders..."
        
        # Create folder structure
        result = create_campaign_folder_structure(
            drive_service, 
            campaign_number, 
            molecule_code,
            None,  # parent_folder_id
            shared_drive_id
        )
        
        if result:
            # Store the result
            job_results[job_key] = {
                "project_folder": {
                    "id": result['project_folder']['id'],
                    "name": result['project_folder']['name'],
                    "link": result['project_folder'].get('webViewLink', f"https://drive.google.com/drive/folders/{result['project_folder']['id']}")
                },
                "campaign_folder": {
                    "id": result['campaign_folder']['id'],
                    "name": result['campaign_folder']['name'],
                    "link": result['campaign_folder'].get('webViewLink', f"https://drive.google.com/drive/folders/{result['campaign_folder']['id']}")
                },
                "reg_doc_folder": {
                    "id": result['reg_doc_folder']['id'],
                    "name": result['reg_doc_folder']['name'],
                    "link": result['reg_doc_folder'].get('webViewLink', f"https://drive.google.com/drive/folders/{result['reg_doc_folder']['id']}")
                },
                "molecule_code": molecule_code,
                "campaign_number": campaign_number
            }
            
            # Update status to completed
            job_status[job_key] = {
                "status": "completed",
                "message": "Folder structure created successfully",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat(),
                "progress": 100
            }
            
            logger.info(f"Background job completed for {job_key}")
        else:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to create folder structure",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Background job failed for {job_key}: {e}")
        job_status[job_key] = {
            "status": "failed",
            "message": f"Error: {str(e)}",
            "started_at": job_status[job_key]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

def background_generate_document(molecule_code: str, campaign_number: str, product_code: str, 
                                dosage_form: str, mechanism_of_action: str, drug_class: str, 
                                indication: str, additional_instructions: str, composition_data: list):
    """Background function to generate document"""
    job_key = f"doc_{molecule_code}_{campaign_number}"
    
    logger.info(f"BACKGROUND: Starting document generation for {job_key}")
    
    try:
        # Update status to running
        job_status[job_key] = {
            "status": "running",
            "message": "Initializing document generation...",
            "started_at": datetime.now().isoformat(),
            "progress": 0
        }
        
        logger.info(f"BACKGROUND: Status updated to running for {job_key}")
        
        # Initialize Google Drive service
        logger.info(f"BACKGROUND: Initializing Google Drive service for {job_key}")
        drive_service = initialize_google_drive_service()
        if not drive_service:
            logger.error(f"BACKGROUND: Failed to initialize Google Drive service for {job_key}")
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to initialize Google Drive service",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        logger.info(f"BACKGROUND: Google Drive service initialized for {job_key}")
        
        # Get shared drive ID
        shared_drive_id = get_shared_drive_id(drive_service)
        
        # Update progress
        job_status[job_key]["progress"] = 10
        job_status[job_key]["message"] = "Finding target folder..."
        
        # Find target folder
        target_folder, folder_path = find_target_folder(drive_service, molecule_code, campaign_number)
        
        if not target_folder:
            logger.error(f"BACKGROUND: Target folder not found for {job_key}")
            job_status[job_key] = {
                "status": "failed",
                "message": f"Target folder not found for Molecule {molecule_code} Campaign {campaign_number}",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
        # Update progress
        job_status[job_key]["progress"] = 20
        job_status[job_key]["message"] = "Preparing composition data..."
        
        # Use provided composition data or create sample data
        if composition_data:
            df = pd.DataFrame(composition_data)
        else:
            df = create_sample_pharma_data()
        
        # Create drug info dictionary
        drug_info = {
            'class': drug_class,
            'indication': indication
        }
        
        # Update progress
        job_status[job_key]["progress"] = 30
        job_status[job_key]["message"] = "Generating regulatory text with AI..."
        
        # Generate regulatory text
        logger.info("BACKGROUND: Generating regulatory text with AI...")
        sections = generate_regulatory_text_with_ai(
            product_code, 
            dosage_form, 
            df, 
            mechanism_of_action, 
            drug_info,
            additional_instructions
        )
        
        # Update progress
        job_status[job_key]["progress"] = 60
        job_status[job_key]["message"] = "Generating PDF document..."
        
        # Generate PDF
        logger.info("BACKGROUND: Generating PDF document...")
        pdf_buffer = export_to_pdf_regulatory(
            df, 
            sections, 
            product_code, 
            dosage_form,
            molecule_code,
            campaign_number
        )
        pdf_buffer.seek(0)
        
        # Update progress
        job_status[job_key]["progress"] = 80
        job_status[job_key]["message"] = "Uploading to Google Drive..."
        
        # Upload to Google Drive
        logger.info("BACKGROUND: Uploading PDF to Google Drive...")
        file_name = f"Section_3.2.P.1_{product_code}_Campaign_{campaign_number}.pdf"
        uploaded_file = upload_file_to_google_drive(
            drive_service,
            pdf_buffer.getvalue(),
            file_name,
            "application/pdf",
            target_folder['id'],
            shared_drive_id
        )
        
        if uploaded_file:
            # Store the result
            job_results[job_key] = {
                "file_id": uploaded_file['id'],
                "file_name": uploaded_file['name'],
                "file_link": uploaded_file.get('webViewLink', f"https://drive.google.com/file/d/{uploaded_file['id']}/view"),
                "folder_path": folder_path,
                "folder_link": f"https://drive.google.com/drive/folders/{target_folder['id']}",
                "molecule_code": molecule_code,
                "campaign_number": campaign_number,
                "product_code": product_code,
                "sections": sections,
                "composition_data": df.to_dict('records')
            }
            
            # Update status to completed
            job_status[job_key] = {
                "status": "completed",
                "message": "Document generated and uploaded successfully",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat(),
                "progress": 100
            }
            
            logger.info(f"Background document generation completed for {job_key}")
        else:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to upload document to Google Drive",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Background document generation failed for {job_key}: {e}")
        job_status[job_key] = {
            "status": "failed",
            "message": f"Error: {str(e)}",
            "started_at": job_status[job_key]["started_at"],
            "completed_at": datetime.now().isoformat()
        }

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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    # Check Google Drive availability
    drive_service = initialize_google_drive_service()
    google_drive_status = "available" if drive_service else "unavailable"
    
    # Check Egnyte availability
    egnyte_status = "available" if EGNYTE_AVAILABLE else "unavailable"
    
    return jsonify({
        "status": "healthy",
        "message": "Document Generation API is running",
        "services": {
            "google_drive": google_drive_status,
            "egnyte": egnyte_status
        }
    })

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

@app.route('/generate-folder-structure', methods=['POST'])
def generate_folder_structure():
    """Start background job to generate campaign folder structure"""
    try:
        logger.info("START: generate_folder_structure route")
        
        data = request.get_json()
        
        if not data:
            logger.error("No JSON data provided")
            return jsonify({"error": "No JSON data provided"}), 400
        
        molecule_code = data.get('molecule_code')
        campaign_number = data.get('campaign_number')
        
        if not molecule_code or not campaign_number:
            logger.error("Missing required parameters")
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        logger.info(f"Processing request for molecule: {molecule_code}, campaign: {campaign_number}")
        
        job_key = f"{molecule_code}_{campaign_number}"
        
        # Check if job is already running
        if job_key in job_status and job_status[job_key]["status"] == "running":
            logger.info(f"Job already running for {job_key}")
            return jsonify({
                "status": "already_running",
                "message": "Folder creation job is already running",
                "job_key": job_key
            })
        
        # Check if job is already completed
        if job_key in job_status and job_status[job_key]["status"] == "completed":
            logger.info(f"Job already completed for {job_key}")
            return jsonify({
                "status": "already_completed",
                "message": "Folder structure already exists",
                "job_key": job_key,
                "data": job_results.get(job_key)
            })
        
        logger.info(f"Starting background thread for {job_key}")
        
        # Start background thread
        thread = threading.Thread(
            target=background_create_folders,
            args=(molecule_code, campaign_number),
            daemon=True
        )
        thread.start()
        
        logger.info(f"RETURNING: Background job started for {job_key}")
        
        return jsonify({
            "status": "started",
            "message": "Folder creation job started",
            "job_key": job_key,
            "poll_url": f"/folder-status?molecule_code={molecule_code}&campaign_number={campaign_number}"
        })
        
    except Exception as e:
        logger.error(f"Error in generate_folder_structure: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/deposit-file', methods=['POST'])
def deposit_file():
    """Deposit a file to the specified Google Drive folder"""
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Get form data
        molecule_code = request.form.get('molecule_code')
        campaign_number = request.form.get('campaign_number')
        file_name = request.form.get('file_name', file.filename)
        
        if not molecule_code or not campaign_number:
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        # Initialize Google Drive service
        drive_service = initialize_google_drive_service()
        if not drive_service:
            return jsonify({"error": "Failed to initialize Google Drive service"}), 500
        
        # Get shared drive ID
        shared_drive_id = get_shared_drive_id(drive_service)
        
        # Find target folder
        target_folder, folder_path = find_target_folder(drive_service, molecule_code, campaign_number)
        
        if not target_folder:
            return jsonify({"error": f"Target folder not found for Molecule {molecule_code} Campaign {campaign_number}"}), 404
        
        # Read file data
        file_data = file.read()
        
        # Determine MIME type
        mime_type = file.content_type or 'application/octet-stream'
        
        # Upload file to Google Drive
        uploaded_file = upload_file_to_google_drive(
            drive_service,
            file_data,
            file_name,
            mime_type,
            target_folder['id'],
            shared_drive_id
        )
        
        if uploaded_file:
            return jsonify({
                "status": "success",
                "message": "File uploaded successfully",
                "data": {
                    "file_id": uploaded_file['id'],
                    "file_name": uploaded_file['name'],
                    "file_link": uploaded_file.get('webViewLink', f"https://drive.google.com/file/d/{uploaded_file['id']}/view"),
                    "folder_path": folder_path,
                    "folder_link": f"https://drive.google.com/drive/folders/{target_folder['id']}",
                    "molecule_code": molecule_code,
                    "campaign_number": campaign_number
                }
            })
        else:
            return jsonify({"error": "Failed to upload file"}), 500
            
    except Exception as e:
        logger.error(f"Error in deposit_file: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/deposit-file-with-path', methods=['POST'])
def deposit_file_with_path():
    """Deposit a file to a specific Google Drive folder path"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        file_path = data.get('file_path')
        folder_id = data.get('folder_id')
        file_name = data.get('file_name')
        file_data_base64 = data.get('file_data')
        
        if not file_path or not file_name or not file_data_base64:
            return jsonify({"error": "file_path, file_name, and file_data are required"}), 400
        
        # Decode base64 file data
        try:
            file_data = base64.b64decode(file_data_base64)
        except Exception as e:
            return jsonify({"error": f"Invalid file data encoding: {e}"}), 400
        
        # Initialize Google Drive service
        drive_service = initialize_google_drive_service()
        if not drive_service:
            return jsonify({"error": "Failed to initialize Google Drive service"}), 500
        
        # Get shared drive ID
        shared_drive_id = get_shared_drive_id(drive_service)
        
        # Determine MIME type based on file extension
        mime_type = 'application/octet-stream'
        if file_name.endswith('.pdf'):
            mime_type = 'application/pdf'
        elif file_name.endswith('.docx'):
            mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif file_name.endswith('.xlsx'):
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif file_name.endswith('.jpg') or file_name.endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif file_name.endswith('.png'):
            mime_type = 'image/png'
        
        # Upload file to Google Drive
        uploaded_file = upload_file_to_google_drive(
            drive_service,
            file_data,
            file_name,
            mime_type,
            folder_id,
            shared_drive_id
        )
        
        if uploaded_file:
            return jsonify({
                "status": "success",
                "message": "File uploaded successfully",
                "data": {
                    "file_id": uploaded_file['id'],
                    "file_name": uploaded_file['name'],
                    "file_link": uploaded_file.get('webViewLink', f"https://drive.google.com/file/d/{uploaded_file['id']}/view"),
                    "file_path": file_path,
                    "folder_id": folder_id
                }
            })
        else:
            return jsonify({"error": "Failed to upload file"}), 500
            
    except Exception as e:
        logger.error(f"Error in deposit_file_with_path: {e}")
        return jsonify({"error": str(e)}), 500

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

@app.route('/list-folders', methods=['GET'])
def list_folders():
    """List available folders in Google Drive"""
    try:
        # Initialize Google Drive service
        drive_service = initialize_google_drive_service()
        if not drive_service:
            return jsonify({"error": "Failed to initialize Google Drive service"}), 500
        
        # Get shared drive ID
        shared_drive_id = get_shared_drive_id(drive_service)
        
        # List folders
        query = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(
            q=query, 
            fields="files(id, name, createdTime, webViewLink)",
            supportsAllDrives=True,
            supportsTeamDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        folders = results.get('files', [])
        
        return jsonify({
            "status": "success",
            "data": {
                "folders": folders,
                "shared_drive_id": shared_drive_id
            }
        })
        
    except Exception as e:
        logger.error(f"Error in list_folders: {e}")
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

if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000) 