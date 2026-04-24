"""Simple Locust load test for Document Management System"""

from locust import HttpUser, between, task
import json
import time
import uuid
from config import (
    API_HOST, TEST_USER_PREFIX, TEST_PASSWORD, 
    ENDPOINTS
)


class DocumentUser(HttpUser):
    """Simulates a document management system user"""
    
    host = API_HOST
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.access_token = None
        self.created_folder_id = None
        unique_id = str(uuid.uuid4())[:8]
        self.user_email = f"{TEST_USER_PREFIX}_{unique_id}@testone.com"
        self.username = f"user_{unique_id}"
    
    def on_start(self):
        """Called when a simulated user starts - register and login"""
        # Register user
        register_data = {
            "username": self.username,
            "email": self.user_email,
            "password": TEST_PASSWORD
        }
        
        with self.client.post(
            ENDPOINTS["register"], 
            json=register_data,
            catch_response=True
        ) as resp:
            if resp.status_code in [200, 201]:
                resp.success()
            elif resp.status_code == 400:
                # Email already exists - that's fine, user already created
                pass
            else:
                print(f"⚠️  Register failed: {resp.status_code} - {resp.text[:100]}")
                resp.failure(f"Register failed: {resp.status_code}")
                return
        
        # Login
        login_data = {
            "email": self.user_email,
            "password": TEST_PASSWORD
        }
        
        with self.client.post(
            ENDPOINTS["login"],
            json=login_data,
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                try:
                    self.access_token = resp.json().get("access_token")
                    if self.access_token:
                        resp.success()
                    else:
                        print(f"❌ Login response missing access_token: {resp.json()}")
                        resp.failure("No access_token in response")
                        return
                except Exception as e:
                    print(f"❌ Login parse error: {e}")
                    resp.failure(f"Login parse error: {e}")
                    return
            else:
                print(f"❌ Login failed: {resp.status_code} - {resp.text[:150]}")
                resp.failure(f"Login failed: {resp.status_code}")
                return
        
        print(f"✅ User {self.username} started successfully")
    
    def get_auth_header(self):
        """Helper to get authorization header"""
        if not self.access_token:
            raise Exception("❌ No access_token available - login failed?")
        return {"Authorization": f"Bearer {self.access_token}"}
    
    @task(3)
    def list_folders(self):
        """List all folders for current user"""
        try:
            headers = self.get_auth_header()
        except Exception as e:
            print(f"❌ {e}")
            return
        
        with self.client.get(
            ENDPOINTS["list_folders"],
            headers=headers,
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 401:
                print(f"⚠️  401 Unauthorized - token might be invalid")
                resp.failure(f"List folders failed: 401 Unauthorized")
            else:
                resp.failure(f"List folders failed: {resp.status_code}")
    
    @task(2)
    def create_folder(self):
        """Create a new folder"""
        folder_data = {
            "name": f"Folder_{int(time.time() * 1000)}",
            "parent_id": None
        }
        
        with self.client.post(
            ENDPOINTS["create_folder"],
            json=folder_data,
            headers=self.get_auth_header(),
            catch_response=True
        ) as resp:
            if resp.status_code in [200, 201]:
                folder = resp.json()
                self.created_folder_id = folder.get("id")
                resp.success()
            else:
                resp.failure(f"Create folder failed: {resp.status_code}")
    
    @task(2)
    def list_documents(self):
        """List documents"""
        with self.client.get(
            ENDPOINTS["list_documents"],
            headers=self.get_auth_header(),
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"List documents failed: {resp.status_code}")
    
    @task(1)
    def upload_document(self):
        """Upload a document with realistic presigned URL flow"""
        file_content = b"This is test content for load testing - " + str(time.time()).encode()
        
        # Step 1: Request presigned URL from API
        with self.client.post(
            ENDPOINTS["upload"],
            data={"folder_id": str(self.created_folder_id) if self.created_folder_id else ""},
            files={"file": ("test_doc.txt", file_content)},
            headers=self.get_auth_header(),
            catch_response=True
        ) as resp:
            if resp.status_code in [200, 201]:
                try:
                    response_json = resp.json()
                    upload_url = response_json.get("upload_url")
                    document_id = response_json.get("document_id")
                    resp.success()
                except Exception as e:
                    resp.failure(f"Failed to parse response: {str(e)}")
                    return
            else:
                resp.failure(f"Failed to get presigned URL: {resp.status_code}")
                return
        
        # Step 2: Upload file to S3 using presigned URL (realistic - no credentials)
        if upload_url:
            with self.client.put(
                upload_url,
                data=file_content,
                headers={"Content-Type": "application/octet-stream"},
                catch_response=True,
                name="/s3/upload"
            ) as s3_resp:
                if s3_resp.status_code in [200, 201]:
                    s3_resp.success()
                else:
                    s3_resp.failure(f"S3 upload failed: {s3_resp.status_code} - {s3_resp.text[:100]}")
