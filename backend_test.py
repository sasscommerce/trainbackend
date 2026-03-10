#!/usr/bin/env python3
"""
Trainlytics Backend API Testing
Tests new backend endpoints for fitness tracking app
"""

import requests
import json
import uuid
from datetime import datetime, timedelta
import time

# Configuration
BASE_URL = "https://trainlytics-preview.preview.emergentagent.com/api"
TEST_EMAIL = f"testuser_{uuid.uuid4().hex[:8]}@test.com"
TEST_PASSWORD = "testpass123"
TEST_NAME = "Test User"
TEST_AGE = 30
TEST_WEIGHT = 75.0

class TrainlyticsTestRunner:
    def __init__(self):
        self.base_url = BASE_URL
        self.access_token = None
        self.user_id = None
        self.test_results = []
        
    def log_test(self, test_name, success, details):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}: {details}")
        
    def make_request(self, method, endpoint, data=None, auth_required=True, files=None):
        """Make HTTP request with optional authentication"""
        url = f"{self.base_url}{endpoint}"
        headers = {"Content-Type": "application/json"}
        
        if auth_required and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            if files:
                # For file uploads, don't set Content-Type header
                headers.pop("Content-Type", None)
                response = requests.request(method, url, headers=headers, files=files)
            else:
                response = requests.request(method, url, headers=headers, json=data)
            return response
        except Exception as e:
            print(f"Request error to {url}: {e}")
            return None

    def test_user_registration(self):
        """Test user registration with age and weight fields"""
        print("\n=== Testing User Registration ===")
        
        registration_data = {
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": TEST_NAME,
            "age": TEST_AGE,
            "weight": TEST_WEIGHT
        }
        
        response = self.make_request("POST", "/auth/register", registration_data, auth_required=False)
        
        if response and response.status_code == 200:
            data = response.json()
            if "access_token" in data and "user" in data:
                self.access_token = data["access_token"]
                self.user_id = data["user"]["id"]
                user = data["user"]
                
                # Verify user data includes age and weight
                if user.get("age") == TEST_AGE and user.get("weight") == TEST_WEIGHT:
                    self.log_test("User Registration", True, f"User registered with age {user['age']} and weight {user['weight']}kg")
                else:
                    self.log_test("User Registration", False, f"Age/weight mismatch: got age={user.get('age')}, weight={user.get('weight')}")
            else:
                self.log_test("User Registration", False, "Missing access_token or user in response")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("User Registration", False, f"Registration failed: {error_msg}")

    def test_strength_progression_empty(self):
        """Test strength progression endpoint with no workout data"""
        print("\n=== Testing Strength Progression API (Empty) ===")
        
        response = self.make_request("GET", "/strength-progression?days=90", auth_required=False)
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                self.log_test("Strength Progression (Empty)", True, f"Returns empty list: {len(data)} items")
            else:
                self.log_test("Strength Progression (Empty)", False, f"Expected list, got {type(data)}")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Strength Progression (Empty)", False, f"API failed: {error_msg}")

    def test_heart_rate_zones(self):
        """Test heart rate zones calculation for age 30"""
        print("\n=== Testing Heart Rate Zones API ===")
        
        response = self.make_request("GET", "/heart-rate-zones")
        
        if response and response.status_code == 200:
            data = response.json()
            expected_max_hr = 220 - TEST_AGE  # 190 for age 30
            
            if data.get("max_heart_rate") == expected_max_hr:
                # Check zones
                zones = ["zone1_recovery", "zone2_fat_burn", "zone3_aerobic", "zone4_anaerobic", "zone5_max"]
                all_zones_valid = True
                zone_details = []
                
                for zone in zones:
                    if zone in data:
                        zone_data = data[zone]
                        zone_details.append(f"{zone_data['name']}: {zone_data['min']}-{zone_data['max']} bpm")
                    else:
                        all_zones_valid = False
                
                if all_zones_valid:
                    self.log_test("Heart Rate Zones", True, f"Max HR: {expected_max_hr}, Zones: {', '.join(zone_details)}")
                else:
                    self.log_test("Heart Rate Zones", False, "Missing zone data")
            else:
                self.log_test("Heart Rate Zones", False, f"Expected max HR {expected_max_hr}, got {data.get('max_heart_rate')}")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Heart Rate Zones", False, f"API failed: {error_msg}")

    def test_weight_history_crud(self):
        """Test weight history CRUD operations"""
        print("\n=== Testing Weight History API ===")
        
        # 1. Add weight entry
        weight_data = {
            "weight": 76.5,
            "notes": "Morning weigh-in"
        }
        
        response = self.make_request("POST", "/weight-history", weight_data)
        entry_id = None
        
        if response and response.status_code == 200:
            data = response.json()
            entry_id = data.get("id")
            if entry_id and data.get("weight") == 76.5:
                self.log_test("Weight History - Add Entry", True, f"Added entry with ID {entry_id}")
            else:
                self.log_test("Weight History - Add Entry", False, "Invalid response data")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Weight History - Add Entry", False, f"Failed to add: {error_msg}")
            return
        
        # 2. Get weight history
        response = self.make_request("GET", "/weight-history?days=90")
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                found_entry = any(entry.get("id") == entry_id for entry in data)
                if found_entry:
                    self.log_test("Weight History - Get History", True, f"Retrieved {len(data)} entries, found our entry")
                else:
                    self.log_test("Weight History - Get History", False, "Entry not found in history")
            else:
                self.log_test("Weight History - Get History", False, f"Expected list with data, got {type(data)} with {len(data) if isinstance(data, list) else 0} items")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Weight History - Get History", False, f"Failed to get: {error_msg}")
        
        # 3. Delete weight entry
        if entry_id:
            response = self.make_request("DELETE", f"/weight-history/{entry_id}")
            
            if response and response.status_code == 200:
                self.log_test("Weight History - Delete Entry", True, "Entry deleted successfully")
                
                # Verify deletion
                response = self.make_request("GET", "/weight-history?days=90")
                if response and response.status_code == 200:
                    data = response.json()
                    found_entry = any(entry.get("id") == entry_id for entry in data)
                    if not found_entry:
                        self.log_test("Weight History - Verify Deletion", True, "Entry successfully removed from history")
                    else:
                        self.log_test("Weight History - Verify Deletion", False, "Entry still present after deletion")
            else:
                error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
                self.log_test("Weight History - Delete Entry", False, f"Failed to delete: {error_msg}")

    def test_personalized_motivation_without_auth(self):
        """Test personalized motivation without authentication"""
        print("\n=== Testing Personalized Motivation API (No Auth) ===")
        
        response = self.make_request("GET", "/motivation/personalized", auth_required=False)
        
        if response and response.status_code == 200:
            data = response.json()
            if "quote" in data and "personalized_messages" in data:
                quote = data["quote"]
                messages = data["personalized_messages"]
                
                # Should have generic message for non-authenticated users
                if isinstance(messages, list) and len(messages) > 0:
                    self.log_test("Personalized Motivation (No Auth)", True, f"Quote: '{quote.get('quote', 'N/A')}', Messages: {len(messages)}")
                else:
                    self.log_test("Personalized Motivation (No Auth)", False, "Missing or empty personalized messages")
            else:
                self.log_test("Personalized Motivation (No Auth)", False, "Missing quote or personalized_messages in response")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Personalized Motivation (No Auth)", False, f"API failed: {error_msg}")

    def test_personalized_motivation_with_auth(self):
        """Test personalized motivation with authentication"""
        print("\n=== Testing Personalized Motivation API (With Auth) ===")
        
        response = self.make_request("GET", "/motivation/personalized")
        
        if response and response.status_code == 200:
            data = response.json()
            if "quote" in data and "personalized_messages" in data:
                quote = data["quote"]
                messages = data["personalized_messages"]
                
                if isinstance(messages, list):
                    self.log_test("Personalized Motivation (With Auth)", True, f"Quote: '{quote.get('quote', 'N/A')}', Messages: {len(messages)} items - {messages}")
                else:
                    self.log_test("Personalized Motivation (With Auth)", False, f"Messages should be list, got {type(messages)}")
            else:
                self.log_test("Personalized Motivation (With Auth)", False, "Missing quote or personalized_messages in response")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Personalized Motivation (With Auth)", False, f"API failed: {error_msg}")

    def test_csv_import_enhanced(self):
        """Test CSV import with DD-MMM-YY date format and kg weights"""
        print("\n=== Testing Enhanced CSV Import API ===")
        
        # Test CSV content with DD-MMM-YY format as specified
        csv_content = """Date,Workout,Weight,Reps,Sets
06-Jan-25,Bench Press,100 kg,10,3
07-Jan-25,Squat,120 kg,8,4
08-Jan-25,Deadlift,140 kg,5,3"""
        
        # Send CSV data as JSON
        csv_data = {
            "csv_data": csv_content
        }
        
        response = self.make_request("POST", "/import/csv", csv_data, auth_required=True)
        
        if response and response.status_code == 200:
            data = response.json()
            if data.get("success"):
                workouts_created = data.get("workouts_created", 0)
                exercises_imported = data.get("exercises_imported", 0)
                errors = data.get("errors", [])
                
                if workouts_created > 0 and exercises_imported > 0:
                    self.log_test("Enhanced CSV Import", True, f"Created {workouts_created} workouts, imported {exercises_imported} exercises")
                else:
                    self.log_test("Enhanced CSV Import", False, f"No workouts/exercises imported. Errors: {errors}")
            else:
                errors = data.get("errors", [])
                self.log_test("Enhanced CSV Import", False, f"Import failed with errors: {errors}")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Enhanced CSV Import", False, f"API failed: {error_msg}")

    def test_strength_progression_with_data(self):
        """Test strength progression after importing workout data"""
        print("\n=== Testing Strength Progression API (With Data) ===")
        
        response = self.make_request("GET", "/strength-progression?days=90")
        
        if response and response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                if len(data) > 0:
                    # Check structure of first progression item
                    item = data[0]
                    required_fields = ['exercise_name', 'current_max', 'previous_max', 'improvement', 'improvement_percent', 'total_volume_trend']
                    
                    if all(field in item for field in required_fields):
                        progression_summary = []
                        for prog in data:
                            progression_summary.append(f"{prog['exercise_name']}: {prog['current_max']}kg ({prog['improvement_percent']:+.1f}%)")
                        
                        self.log_test("Strength Progression (With Data)", True, f"Found {len(data)} progressions: {', '.join(progression_summary)}")
                    else:
                        missing = [f for f in required_fields if f not in item]
                        self.log_test("Strength Progression (With Data)", False, f"Missing fields: {missing}")
                else:
                    self.log_test("Strength Progression (With Data)", True, "No compound lifts found in imported data (expected for this test data)")
            else:
                self.log_test("Strength Progression (With Data)", False, f"Expected list, got {type(data)}")
        else:
            error_msg = response.json().get("detail", "Unknown error") if response else "Request failed"
            self.log_test("Strength Progression (With Data)", False, f"API failed: {error_msg}")

    def run_all_tests(self):
        """Run all test cases in sequence"""
        print(f"Starting Trainlytics Backend API Tests")
        print(f"Base URL: {self.base_url}")
        print(f"Test User: {TEST_EMAIL}")
        
        try:
            # Test sequence as specified in requirements
            self.test_user_registration()
            
            if not self.access_token:
                print("\n❌ CRITICAL: Cannot continue without authentication token")
                return
            
            self.test_strength_progression_empty()
            self.test_heart_rate_zones() 
            self.test_weight_history_crud()
            self.test_personalized_motivation_without_auth()
            self.test_personalized_motivation_with_auth()
            self.test_csv_import_enhanced()
            self.test_strength_progression_with_data()
            
        except Exception as e:
            print(f"\n❌ CRITICAL ERROR during testing: {e}")
            self.log_test("Test Execution", False, f"Critical error: {e}")
        
        # Summary
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        passed_tests = [t for t in self.test_results if t["success"]]
        failed_tests = [t for t in self.test_results if not t["success"]]
        
        print(f"✅ PASSED: {len(passed_tests)}")
        print(f"❌ FAILED: {len(failed_tests)}")
        print(f"📊 SUCCESS RATE: {len(passed_tests)}/{len(self.test_results)} ({len(passed_tests)/len(self.test_results)*100:.1f}%)")
        
        if failed_tests:
            print(f"\n❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
        
        return len(passed_tests), len(failed_tests)

if __name__ == "__main__":
    runner = TrainlyticsTestRunner()
    passed, failed = runner.run_all_tests()