from flask import Flask, request, jsonify
import requests
import json
import threading
import time
from datetime import datetime
from credentials import DOMAIN, CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, ROOT_FOLDER

app = Flask(__name__)

# In-memory storage for job results
job_results = {}
job_status = {}

def get_egnyte_token():
    """Get Egnyte access token"""
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
        print(f"Error getting token: {e}")
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
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error creating folder: {e}")
        return None

def get_egnyte_folder_details(access_token, folder_id):
    """Get folder details"""
    url = f"https://{DOMAIN}/pubapi/v1/fs/ids/folder/{folder_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting folder details: {e}")
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
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error listing folder contents: {e}")
        return None

def background_create_egnyte_folders(molecule_code: str, campaign_number: str):
    """Background function to create Egnyte folder structure"""
    job_key = f"egnyte_{molecule_code}_{campaign_number}"
    
    print(f"BACKGROUND: Starting Egnyte folder creation for {job_key}")
    
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
        
        # Create project folder
        project_folder_name = f"Project; Molecule {molecule_code}"
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
        job_status[job_key]["message"] = "Creating subfolders..."
        
        # Create Pre and Post folders
        pre_folder = create_egnyte_folder(access_token, campaign_folder_id, "Pre")
        post_folder = create_egnyte_folder(access_token, campaign_folder_id, "Post")
        
        # Create department folders under Pre and Post
        departments = ["mfg", "Anal", "Stability", "CTM"]
        statuses = ["Draft", "Review", "Approved"]
        
        for phase_folder_id in [pre_folder.get('folder_id') if pre_folder else None, 
                               post_folder.get('folder_id') if post_folder else None]:
            if phase_folder_id:
                for dept in departments:
                    dept_folder = create_egnyte_folder(access_token, phase_folder_id, dept)
                    if dept_folder:
                        dept_folder_id = dept_folder.get('folder_id')
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
        
        print(f"Background Egnyte job completed for {job_key}")
        
    except Exception as e:
        print(f"Background Egnyte job failed for {job_key}: {e}")
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
        "message": "Egnyte API is running"
    })

@app.route('/egnyte-generate-folder-structure', methods=['POST'])
def egnyte_generate_folder_structure():
    """Start background job to generate Egnyte folder structure"""
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
    app.run(debug=True, host='0.0.0.0', port=5001) 