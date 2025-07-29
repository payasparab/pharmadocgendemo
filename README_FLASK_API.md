# Document Generation Flask API

This Flask API provides endpoints for generating Google Drive folder structures and depositing files, designed for integration with Retool applications.

## Setup

1. Install dependencies:
```bash
pip install -r requirements_flask.txt
```

2. Set up environment variables for Google Drive API:
```bash
export GOOGLE_DRIVE_TYPE="service_account"
export GOOGLE_DRIVE_PROJECT_ID="your-project-id"
export GOOGLE_DRIVE_PRIVATE_KEY_ID="your-private-key-id"
export GOOGLE_DRIVE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
export GOOGLE_DRIVE_CLIENT_EMAIL="your-service-account@project.iam.gserviceaccount.com"
export GOOGLE_DRIVE_CLIENT_ID="your-client-id"
export GOOGLE_DRIVE_AUTH_URI="https://accounts.google.com/o/oauth2/auth"
export GOOGLE_DRIVE_TOKEN_URI="https://oauth2.googleapis.com/token"
export GOOGLE_DRIVE_AUTH_PROVIDER_X509_CERT_URL="https://www.googleapis.com/oauth2/v1/certs"
export GOOGLE_DRIVE_CLIENT_X509_CERT_URL="https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40project.iam.gserviceaccount.com"
```

3. Set up OpenAI API key (optional, for document generation):
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

4. Run the API:
```bash
python flask_api.py
```

## API Endpoints

### 1. Health Check
- **GET** `/health`
- Returns API status

### 2. Generate Folder Structure
- **POST** `/generate-folder-structure`
- Creates campaign folder structure in Google Drive

**Request Body:**
```json
{
  "molecule_code": "THPG001",
  "campaign_number": "3"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Campaign folder structure created successfully",
  "data": {
    "project_folder": {
      "id": "folder_id",
      "name": "Project; Molecule THPG001",
      "link": "https://drive.google.com/drive/folders/folder_id"
    },
    "campaign_folder": {
      "id": "campaign_id",
      "name": "Project THPG001 (Campaign #3)",
      "link": "https://drive.google.com/drive/folders/campaign_id"
    },
    "reg_doc_folder": {
      "id": "reg_doc_id",
      "name": "Draft AI Reg Document",
      "link": "https://drive.google.com/drive/folders/reg_doc_id"
    },
    "molecule_code": "THPG001",
    "campaign_number": "3"
  }
}
```

### 3. Deposit File
- **POST** `/deposit-file`
- Uploads a file to the target folder for a specific molecule and campaign

**Form Data:**
- `file`: The file to upload
- `molecule_code`: Molecule code (e.g., "THPG001")
- `campaign_number`: Campaign number (e.g., "3")
- `file_name`: Optional custom file name

**Response:**
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "data": {
    "file_id": "file_id",
    "file_name": "document.pdf",
    "file_link": "https://drive.google.com/file/d/file_id/view",
    "folder_path": "Project; Molecule THPG001 → Draft AI Reg Document → IND → Draft",
    "folder_link": "https://drive.google.com/drive/folders/folder_id",
    "molecule_code": "THPG001",
    "campaign_number": "3"
  }
}
```

### 4. Deposit File with Path
- **POST** `/deposit-file-with-path`
- Uploads a file to a specific folder using folder ID and base64 encoded file data

**Request Body:**
```json
{
  "file_path": "/path/to/file",
  "folder_id": "google_drive_folder_id",
  "file_name": "document.pdf",
  "file_data": "base64_encoded_file_content"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "File uploaded successfully",
  "data": {
    "file_id": "file_id",
    "file_name": "document.pdf",
    "file_link": "https://drive.google.com/file/d/file_id/view",
    "file_path": "/path/to/file",
    "folder_id": "google_drive_folder_id"
  }
}
```

### 5. List Folders
- **GET** `/list-folders`
- Lists all folders in Google Drive

**Response:**
```json
{
  "status": "success",
  "data": {
    "folders": [
      {
        "id": "folder_id",
        "name": "Folder Name",
        "createdTime": "2023-01-01T00:00:00.000Z",
        "webViewLink": "https://drive.google.com/drive/folders/folder_id"
      }
    ],
    "shared_drive_id": "shared_drive_id"
  }
}
```

## Retool Integration

### Example Retool Query for Generate Folder Structure:
```javascript
// POST request to /generate-folder-structure
{
  "molecule_code": moleculeCodeInput.value,
  "campaign_number": campaignNumberInput.value
}
```

### Example Retool Query for Deposit File:
```javascript
// POST request to /deposit-file
// Use Form Data with:
// - file: fileUpload.value
// - molecule_code: moleculeCodeInput.value
// - campaign_number: campaignNumberInput.value
// - file_name: fileNameInput.value
```

### Example Retool Query for Deposit File with Path:
```javascript
// POST request to /deposit-file-with-path
{
  "file_path": filePathInput.value,
  "folder_id": folderIdInput.value,
  "file_name": fileNameInput.value,
  "file_data": btoa(fileUpload.value) // Base64 encode file
}
```

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `400`: Bad Request (missing required fields)
- `404`: Not Found (folder not found)
- `500`: Internal Server Error

Error responses include a descriptive message:
```json
{
  "error": "Description of the error"
}
```

## Folder Structure Created

The API creates the following folder structure:
```
Project; Molecule {molecule_code}/
├── Project {molecule_code} (Campaign #{campaign_number})/
│   ├── Pre/
│   │   ├── mfg/
│   │   │   ├── Draft/
│   │   │   ├── Review/
│   │   │   └── Approved/
│   │   ├── Anal/
│   │   ├── Stability/
│   │   └── CTM/
│   └── Post/
│       ├── mfg/
│       ├── Anal/
│       ├── Stability/
│       └── CTM/
└── Draft AI Reg Document/
    ├── IND/
    │   ├── Draft/
    │   ├── Review/
    │   └── Approved/
    ├── IMPD/
    └── Canada/
``` 