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

def load_openai_api_key():
    """Load OpenAI API key from environment variable"""
    return os.getenv('OPENAI_API_KEY')

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
    
    try:
        # Update status to running
        job_status[job_key] = {
            "status": "running",
            "message": "Creating folder structure...",
            "started_at": datetime.now().isoformat(),
            "progress": 0
        }
        
        # Initialize Google Drive service
        drive_service = initialize_google_drive_service()
        if not drive_service:
            job_status[job_key] = {
                "status": "failed",
                "message": "Failed to initialize Google Drive service",
                "started_at": job_status[job_key]["started_at"],
                "completed_at": datetime.now().isoformat()
            }
            return
        
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "Document Generation API is running"
    })

@app.route('/generate-folder-structure', methods=['POST'])
def generate_folder_structure():
    """Start background job to generate campaign folder structure"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        molecule_code = data.get('molecule_code')
        campaign_number = data.get('campaign_number')
        
        if not molecule_code or not campaign_number:
            return jsonify({"error": "molecule_code and campaign_number are required"}), 400
        
        job_key = f"{molecule_code}_{campaign_number}"
        
        # Check if job is already running
        if job_key in job_status and job_status[job_key]["status"] == "running":
            return jsonify({
                "status": "already_running",
                "message": "Folder creation job is already running",
                "job_key": job_key
            })
        
        # Check if job is already completed
        if job_key in job_status and job_status[job_key]["status"] == "completed":
            return jsonify({
                "status": "already_completed",
                "message": "Folder structure already exists",
                "job_key": job_key,
                "data": job_results.get(job_key)
            })
        
        # Start background thread
        thread = threading.Thread(
            target=background_create_folders,
            args=(molecule_code, campaign_number),
            daemon=True
        )
        thread.start()
        
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

if __name__ == '__main__':
    # For local development
    app.run(debug=True, host='0.0.0.0', port=5000) 