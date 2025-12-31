import os
import pickle
from typing import Optional, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

class DriveUploader:
    def __init__(self, credentials_path: str = 'credentials.json'):
        """
        Initialize the Google Drive uploader.
        
        Args:
            credentials_path: Path to the OAuth credentials JSON file
        """
        self.credentials_path = credentials_path
        self.service = None
        self.folder_cache: Dict[str, str] = {}  # Cache folder IDs
        
    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API using OAuth 2.0.
        Returns True if successful, False otherwise.
        """
        creds = None
        token_path = 'token.pickle'
        
        # Check if we have saved credentials
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If credentials are invalid or don't exist, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    print(f"ERROR: Credentials file not found at {self.credentials_path}")
                    print("Please download OAuth credentials from Google Cloud Console")
                    print("and save as 'credentials.json' in the project root.")
                    return False
                
                print("Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        try:
            self.service = build('drive', 'v3', credentials=creds)
            print("✓ Successfully authenticated with Google Drive")
            return True
        except Exception as e:
            print(f"Failed to build Drive service: {e}")
            return False
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Create a folder in Google Drive.
        
        Args:
            folder_name: Name of the folder to create
            parent_id: ID of parent folder (None for root)
            
        Returns:
            Folder ID if successful, None otherwise
        """
        if not self.service:
            print("Not authenticated. Call authenticate() first.")
            return None
        
        # Check cache first
        cache_key = f"{parent_id or 'root'}:{folder_name}"
        if cache_key in self.folder_cache:
            return self.folder_cache[cache_key]
        
        try:
            # Check if folder already exists
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            if items:
                folder_id = items[0]['id']
                print(f"  Folder '{folder_name}' already exists (ID: {folder_id})")
                self.folder_cache[cache_key] = folder_id
                return folder_id
            
            # Create new folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            print(f"  Created folder '{folder_name}' (ID: {folder_id})")
            self.folder_cache[cache_key] = folder_id
            return folder_id
            
        except HttpError as error:
            print(f"Error creating folder: {error}")
            return None
    
    def upload_file(self, file_path: str, folder_id: Optional[str] = None, 
                   custom_name: Optional[str] = None) -> Optional[str]:
        """
        Upload a file to Google Drive.
        
        Args:
            file_path: Local path to the file
            folder_id: ID of the destination folder (None for root)
            custom_name: Custom name for the file (uses original name if None)
            
        Returns:
            File ID if successful, None otherwise
        """
        if not self.service:
            print("Not authenticated. Call authenticate() first.")
            return None
        
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None
        
        try:
            file_name = custom_name or os.path.basename(file_path)
            
            file_metadata = {'name': file_name}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaFileUpload(file_path, resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            web_link = file.get('webViewLink')
            print(f"  ✓ Uploaded '{file_name}' (ID: {file_id})")
            print(f"    Link: {web_link}")
            return file_id
            
        except HttpError as error:
            print(f"Error uploading file: {error}")
            return None
    
    def create_company_structure(self, company_name: str, year: int, period: str) -> Optional[str]:
        """
        Create the folder structure: Company / Year / Period
        
        Args:
            company_name: Name of the company
            year: Year (e.g., 2024)
            period: Period (e.g., 'Q1', 'Annual')
            
        Returns:
            ID of the period folder if successful, None otherwise
        """
        # Create company folder
        company_folder_id = self.create_folder(company_name)
        if not company_folder_id:
            return None
        
        # Create year folder
        year_folder_id = self.create_folder(str(year), company_folder_id)
        if not year_folder_id:
            return None
        
        # Create period folder
        period_folder_id = self.create_folder(period, year_folder_id)
        return period_folder_id
