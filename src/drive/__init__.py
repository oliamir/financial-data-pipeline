"""Google Drive uploader for company artifacts.

Uploads financial reports, memos, and Excel models to Google Drive
with folder organization per company.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict

from ..models.company import Company
from ..storage.paths import CompanyPaths
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DriveUploader:
    """Uploads company artifacts to Google Drive."""

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        root_folder_id: Optional[str] = None,
    ):
        self.credentials_path = credentials_path or os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        self.root_folder_id = root_folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        self._service = None

    @property
    def service(self):
        """Lazy-initialize Google Drive API service."""
        if self._service is None:
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                creds = self._load_credentials()
                self._service = build("drive", "v3", credentials=creds)
            except ImportError:
                raise RuntimeError("google-api-python-client not installed")
        return self._service

    def _load_credentials(self):
        """Load OAuth2 credentials from file or token."""
        from google.oauth2.credentials import Credentials

        if self.credentials_path and os.path.exists(self.credentials_path):
            return Credentials.from_authorized_user_file(self.credentials_path)
        raise RuntimeError("No valid credentials found for Google Drive")

    def upload_company_artifacts(
        self,
        company: Company,
        upload_reports: bool = True,
        upload_memo: bool = True,
        upload_model: bool = True,
    ) -> Dict[str, str]:
        """Upload all artifacts for a company.

        Args:
            company: Company to upload for.
            upload_reports: Upload PDF reports.
            upload_memo: Upload investment memo.
            upload_model: Upload Excel model.

        Returns:
            Dict mapping local path to Drive file ID.
        """
        paths = CompanyPaths(company.slug)
        results = {}

        # Ensure company folder exists in Drive
        folder_id = self._get_or_create_folder(company.slug, self.root_folder_id)

        if upload_reports and paths.reports_dir.exists():
            report_folder_id = self._get_or_create_folder("reports", folder_id)
            for pdf_file in sorted(paths.reports_dir.glob("*.pdf")):
                drive_id = self._upload_file(str(pdf_file), report_folder_id)
                if drive_id:
                    results[str(pdf_file)] = drive_id

        if upload_memo and paths.memo_md.exists():
            drive_id = self._upload_file(str(paths.memo_md), folder_id)
            if drive_id:
                results[str(paths.memo_md)] = drive_id

        if upload_model and paths.model_xlsx.exists():
            drive_id = self._upload_file(str(paths.model_xlsx), folder_id)
            if drive_id:
                results[str(paths.model_xlsx)] = drive_id

        logger.info(f"Uploaded {len(results)} files for {company.slug}")
        return results

    def _upload_file(self, local_path: str, parent_folder_id: str) -> Optional[str]:
        """Upload a single file to Drive."""
        try:
            from googleapiclient.http import MediaFileUpload

            filename = os.path.basename(local_path)
            mime_type = self._guess_mime_type(local_path)

            # Check if file already exists
            existing = self.service.files().list(
                q=f"name='{filename}' and '{parent_folder_id}' in parents and trashed=false",
                fields="files(id)",
            ).execute().get("files", [])

            media = MediaFileUpload(local_path, mimetype=mime_type)

            if existing:
                # Update existing
                file_id = existing[0]["id"]
                self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                ).execute()
                logger.debug(f"Updated: {filename}")
                return file_id
            else:
                # Create new
                file_metadata = {
                    "name": filename,
                    "parents": [parent_folder_id],
                }
                result = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields="id",
                ).execute()
                logger.debug(f"Uploaded: {filename}")
                return result.get("id")

        except Exception as e:
            logger.error(f"Upload failed for {local_path}: {e}")
            return None

    def _get_or_create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Get or create a folder in Drive."""
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        results = self.service.files().list(q=query, fields="files(id)").execute()
        existing = results.get("files", [])

        if existing:
            return existing[0]["id"]

        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        folder = self.service.files().create(body=metadata, fields="id").execute()
        return folder.get("id")

    def _guess_mime_type(self, path: str) -> str:
        """Guess MIME type from file extension."""
        ext = Path(path).suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".md": "text/markdown",
            ".json": "application/json",
            ".csv": "text/csv",
        }
        return mime_map.get(ext, "application/octet-stream")
