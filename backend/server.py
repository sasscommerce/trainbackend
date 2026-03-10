from fastapi import FastAPI, APIRouter, HTTPException, Query, Depends, Header
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
from bson import ObjectId
import jwt
import bcrypt
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'trainlytics-super-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# ============== MOTIVATION QUOTES ==============

MOTIVATION_QUOTES = [
    {"quote": "The only bad workout is the one that didn't happen.", "author": "Unknown"},
    {"quote": "Strength does not come from physical capacity. It comes from an indomitable will.", "author": "Mahatma Gandhi"},
    {"quote": "The pain you feel today will be the strength you feel tomorrow.", "author": "Arnold Schwarzenegger"},
    {"quote": "Your body can stand almost anything. It's your mind that you have to convince.", "author": "Unknown"},
    {"quote": "Success is usually the culmination of controlling failure.", "author": "Sylvester Stallone"},
    {"quote": "The clock is ticking. Are you becoming the person you want to be?", "author": "Greg Plitt"},
    {"quote": "Don't limit your challenges. Challenge your limits.", "author": "Unknown"},
    {"quote": "The only way to define your limits is by going beyond them.", "author": "Arthur C. Clarke"},
    {"quote": "Wake up with determination. Go to bed with satisfaction.", "author": "Unknown"},
    {"quote": "The difference between try and triumph is a little umph.", "author": "Marvin Phillips"},
    {"quote": "Push yourself because no one else is going to do it for you.", "author": "Unknown"},
    {"quote": "Great things never come from comfort zones.", "author": "Unknown"},
    {"quote": "The harder you work, the luckier you get.", "author": "Gary Player"},
    {"quote": "Fitness is not about being better than someone else. It's about being better than you used to be.", "author": "Khloe Kardashian"},
    {"quote": "The body achieves what the mind believes.", "author": "Napoleon Hill"},
    {"quote": "Sore today, strong tomorrow.", "author": "Unknown"},
    {"quote": "Your health is an investment, not an expense.", "author": "Unknown"},
    {"quote": "Motivation is what gets you started. Habit is what keeps you going.", "author": "Jim Ryun"},
    {"quote": "The only person you are destined to become is the person you decide to be.", "author": "Ralph Waldo Emerson"},
    {"quote": "Sweat is just fat crying.", "author": "Unknown"},
    {"quote": "If it doesn't challenge you, it won't change you.", "author": "Fred DeVito"},
    {"quote": "Train insane or remain the same.", "author": "Unknown"},
    {"quote": "The pain of discipline is nothing like the pain of disappointment.", "author": "Justin Langer"},
    {"quote": "Don't stop when you're tired. Stop when you're done.", "author": "Unknown"},
    {"quote": "Champions are made when no one is watching.", "author": "Unknown"},
]

# ============== AUTH MODELS ==============

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    age: Optional[int] = None
    weight: Optional[float] = None  # in kg
    height: Optional[float] = None  # in cm
    fitness_goals: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    fitness_goals: Optional[str] = None
    created_at: datetime

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    fitness_goals: Optional[str] = None

class WeightEntry(BaseModel):
    weight: float
    date: Optional[datetime] = None
    notes: Optional[str] = None

class WeightHistoryItem(BaseModel):
    id: str
    weight: float
    date: datetime
    notes: Optional[str] = None

class HeartRateZones(BaseModel):
    max_heart_rate: int
    zone1_recovery: dict  # 50-60% - Recovery
    zone2_fat_burn: dict  # 60-70% - Fat Burn
    zone3_aerobic: dict   # 70-80% - Aerobic
    zone4_anaerobic: dict # 80-90% - Anaerobic
    zone5_max: dict       # 90-100% - Maximum

class StrengthProgression(BaseModel):
    exercise_name: str
    current_max: float
    previous_max: float
    improvement: float
    improvement_percent: float
    total_volume_trend: str  # "increasing", "decreasing", "stable"
    last_workout_date: Optional[datetime] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile

# ============== COMPOUND LIFTS ==============

COMPOUND_LIFTS = [
    "BB Back Squat", "Squat", "Back Squat", "Front Squat", "BB Front Squat",
    "Deadlift", "Conventional Deadlift", "Romanian Deadlift", "Sumo Deadlift", "Snatch Grip RDL",
    "Bench Press", "Dumbbell Bench Press", "Incline Bench Press", "Lying Bench Press", "Bench/Floor Press",
    "Overhead Press", "Shoulder Press", "Military Press", "BB Medball Press",
    "Bent Over Row", "Barbell Row", "Bent Over Row (Barbell)", "Pendlay Row",
    "Pull-ups", "Chin-ups", "Weighted Pull-ups"
]

def is_compound_lift(exercise_name: str) -> bool:
    """Check if an exercise is a compound lift"""
    exercise_lower = exercise_name.lower()
    for lift in COMPOUND_LIFTS:
        if lift.lower() in exercise_lower or exercise_lower in lift.lower():
            return True
    # Check for common patterns
    if any(pattern in exercise_lower for pattern in ['squat', 'deadlift', 'bench', 'press', 'row', 'pull-up', 'chin-up']):
        return True
    return False

def get_lift_category(exercise_name: str) -> str:
    """Categorize a compound lift"""
    exercise_lower = exercise_name.lower()
    if 'squat' in exercise_lower:
        return 'Squat'
    elif 'deadlift' in exercise_lower or 'rdl' in exercise_lower:
        return 'Deadlift'
    elif 'bench' in exercise_lower or 'chest press' in exercise_lower:
        return 'Bench Press'
    elif 'press' in exercise_lower or 'shoulder' in exercise_lower:
        return 'Overhead Press'
    elif 'row' in exercise_lower:
        return 'Row'
    elif 'pull' in exercise_lower or 'chin' in exercise_lower:
        return 'Pull-up'
    return 'Other'

# ============== MODELS ==============

class ExerciseSet(BaseModel):
    set_number: int
    reps: int
    weight: float
    rpe: Optional[int] = None  # Rate of Perceived Exertion 1-10
    rest_time: Optional[int] = None  # in seconds

class WorkoutExercise(BaseModel):
    exercise_id: Optional[str] = None
    exercise_name: str
    body_part: str
    workout_type: str  # strength, cardio, mobility, sports, custom
    sets: List[ExerciseSet]
    duration: Optional[int] = None  # in minutes for cardio
    notes: Optional[str] = None
    total_volume: Optional[float] = None  # auto-calculated
    estimated_1rm: Optional[float] = None  # auto-calculated

class WorkoutCreate(BaseModel):
    date: Optional[datetime] = None
    workout_type: str  # strength, cardio, mobility, sports, custom
    exercises: List[WorkoutExercise]
    duration: Optional[int] = None  # total workout duration in minutes
    notes: Optional[str] = None  # injury, fatigue, mood

class Workout(BaseModel):
    id: str
    user_id: Optional[str] = None
    date: datetime
    workout_type: str
    exercises: List[WorkoutExercise]
    duration: Optional[int] = None
    notes: Optional[str] = None
    total_volume: float = 0
    created_at: datetime

class ExerciseTemplate(BaseModel):
    id: str
    name: str
    body_part: str
    muscle_group: str
    workout_type: str
    is_custom: bool = False

class ExerciseTemplateCreate(BaseModel):
    name: str
    body_part: str
    muscle_group: str
    workout_type: str
    is_custom: bool = True

class PersonalRecord(BaseModel):
    id: str
    exercise_name: str
    record_type: str  # heaviest_lift, most_reps, highest_volume, longest_session
    value: float
    workout_id: str
    achieved_at: datetime

class DashboardStats(BaseModel):
    total_workouts_this_month: int
    total_volume_this_month: float
    avg_intensity: float
    total_time_spent: int  # in minutes
    current_streak: int
    longest_streak: int
    workouts_this_week: int

# ============== AUTH HELPERS ==============

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_jwt_token(user_id: str, email: str) -> str:
    """Create a JWT token for authentication"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Get current user from JWT token - returns None if not authenticated"""
    if not authorization:
        return None
    
    try:
        # Handle "Bearer token" format
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({'id': payload['user_id']})
        return user
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

async def require_auth(authorization: Optional[str] = Header(None)) -> dict:
    """Require authentication - raises exception if not authenticated"""
    user = await get_current_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

# ============== HELPER FUNCTIONS ==============

def calculate_1rm(weight: float, reps: int) -> float:
    """Brzycki formula for estimated 1RM"""
    if reps == 1:
        return weight
    return weight * (36 / (37 - reps))

def calculate_volume(sets: List[ExerciseSet]) -> float:
    """Calculate total volume (weight * reps * sets)"""
    total = 0
    for s in sets:
        total += s.weight * s.reps
    return total

async def update_personal_records(workout: dict, user_id: Optional[str] = None):
    """Check and update personal records after a workout"""
    records_to_check = []
    
    for exercise in workout.get('exercises', []):
        exercise_name = exercise.get('exercise_name', '')
        total_volume = exercise.get('total_volume', 0)
        
        # Find heaviest lift
        max_weight = 0
        max_reps = 0
        for s in exercise.get('sets', []):
            if s.get('weight', 0) > max_weight:
                max_weight = s.get('weight', 0)
            if s.get('reps', 0) > max_reps:
                max_reps = s.get('reps', 0)
        
        records_to_check.extend([
            {'exercise_name': exercise_name, 'record_type': 'heaviest_lift', 'value': max_weight},
            {'exercise_name': exercise_name, 'record_type': 'most_reps', 'value': max_reps},
            {'exercise_name': exercise_name, 'record_type': 'highest_volume', 'value': total_volume},
        ])
    
    for record in records_to_check:
        if record['value'] <= 0:
            continue
        
        query = {
            'exercise_name': record['exercise_name'],
            'record_type': record['record_type']
        }
        if user_id:
            query['user_id'] = user_id
            
        existing = await db.personal_records.find_one(query)
        
        if not existing or record['value'] > existing.get('value', 0):
            update_data = {
                'id': str(uuid.uuid4()),
                'exercise_name': record['exercise_name'],
                'record_type': record['record_type'],
                'value': record['value'],
                'workout_id': str(workout.get('_id', '')),
                'achieved_at': workout.get('date', datetime.utcnow())
            }
            if user_id:
                update_data['user_id'] = user_id
                
            await db.personal_records.update_one(
                query,
                {'$set': update_data},
                upsert=True
            )

async def calculate_streak(user_id: Optional[str] = None) -> tuple:
    """Calculate current and longest workout streak"""
    query = {}
    if user_id:
        query['user_id'] = user_id
        
    workouts = await db.workouts.find(query).sort('date', -1).to_list(1000)
    
    if not workouts:
        return 0, 0
    
    # Get unique workout dates
    workout_dates = set()
    for w in workouts:
        date = w.get('date')
        if date:
            workout_dates.add(date.date())
    
    sorted_dates = sorted(workout_dates, reverse=True)
    
    if not sorted_dates:
        return 0, 0
    
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    # Current streak
    current_streak = 0
    if sorted_dates[0] == today or sorted_dates[0] == yesterday:
        current_streak = 1
        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] == sorted_dates[i-1] - timedelta(days=1):
                current_streak += 1
            else:
                break
    
    # Longest streak
    longest_streak = 1
    current_count = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i-1] - timedelta(days=1):
            current_count += 1
            longest_streak = max(longest_streak, current_count)
        else:
            current_count = 1
    
    return current_streak, longest_streak

# ============== DEFAULT EXERCISES ==============

DEFAULT_EXERCISES = [
    # Chest
    {"name": "Bench Press", "body_part": "Chest", "muscle_group": "Pectoralis Major", "workout_type": "strength"},
    {"name": "Incline Bench Press", "body_part": "Chest", "muscle_group": "Upper Chest", "workout_type": "strength"},
    {"name": "Dumbbell Flyes", "body_part": "Chest", "muscle_group": "Pectoralis Major", "workout_type": "strength"},
    {"name": "Push-ups", "body_part": "Chest", "muscle_group": "Pectoralis Major", "workout_type": "strength"},
    {"name": "Cable Crossover", "body_part": "Chest", "muscle_group": "Pectoralis Major", "workout_type": "strength"},
    {"name": "Dumbbell Press", "body_part": "Chest", "muscle_group": "Pectoralis Major", "workout_type": "strength"},
    {"name": "Decline Bench Press", "body_part": "Chest", "muscle_group": "Lower Chest", "workout_type": "strength"},
    
    # Back
    {"name": "Deadlift", "body_part": "Back", "muscle_group": "Erector Spinae", "workout_type": "strength"},
    {"name": "Pull-ups", "body_part": "Back", "muscle_group": "Latissimus Dorsi", "workout_type": "strength"},
    {"name": "Barbell Rows", "body_part": "Back", "muscle_group": "Latissimus Dorsi", "workout_type": "strength"},
    {"name": "Lat Pulldown", "body_part": "Back", "muscle_group": "Latissimus Dorsi", "workout_type": "strength"},
    {"name": "Seated Cable Row", "body_part": "Back", "muscle_group": "Rhomboids", "workout_type": "strength"},
    {"name": "T-Bar Row", "body_part": "Back", "muscle_group": "Middle Back", "workout_type": "strength"},
    {"name": "Chin-ups", "body_part": "Back", "muscle_group": "Latissimus Dorsi", "workout_type": "strength"},
    
    # Legs
    {"name": "Squat", "body_part": "Legs", "muscle_group": "Quadriceps", "workout_type": "strength"},
    {"name": "Leg Press", "body_part": "Legs", "muscle_group": "Quadriceps", "workout_type": "strength"},
    {"name": "Lunges", "body_part": "Legs", "muscle_group": "Quadriceps", "workout_type": "strength"},
    {"name": "Leg Curl", "body_part": "Legs", "muscle_group": "Hamstrings", "workout_type": "strength"},
    {"name": "Leg Extension", "body_part": "Legs", "muscle_group": "Quadriceps", "workout_type": "strength"},
    {"name": "Calf Raises", "body_part": "Legs", "muscle_group": "Calves", "workout_type": "strength"},
    {"name": "Romanian Deadlift", "body_part": "Legs", "muscle_group": "Hamstrings", "workout_type": "strength"},
    {"name": "Bulgarian Split Squat", "body_part": "Legs", "muscle_group": "Quadriceps", "workout_type": "strength"},
    {"name": "Hip Thrust", "body_part": "Legs", "muscle_group": "Glutes", "workout_type": "strength"},
    
    # Shoulders
    {"name": "Overhead Press", "body_part": "Shoulders", "muscle_group": "Deltoids", "workout_type": "strength"},
    {"name": "Lateral Raises", "body_part": "Shoulders", "muscle_group": "Lateral Deltoid", "workout_type": "strength"},
    {"name": "Front Raises", "body_part": "Shoulders", "muscle_group": "Anterior Deltoid", "workout_type": "strength"},
    {"name": "Face Pulls", "body_part": "Shoulders", "muscle_group": "Posterior Deltoid", "workout_type": "strength"},
    {"name": "Arnold Press", "body_part": "Shoulders", "muscle_group": "Deltoids", "workout_type": "strength"},
    {"name": "Upright Row", "body_part": "Shoulders", "muscle_group": "Deltoids", "workout_type": "strength"},
    
    # Arms
    {"name": "Bicep Curls", "body_part": "Arms", "muscle_group": "Biceps", "workout_type": "strength"},
    {"name": "Tricep Pushdown", "body_part": "Arms", "muscle_group": "Triceps", "workout_type": "strength"},
    {"name": "Hammer Curls", "body_part": "Arms", "muscle_group": "Biceps", "workout_type": "strength"},
    {"name": "Skull Crushers", "body_part": "Arms", "muscle_group": "Triceps", "workout_type": "strength"},
    {"name": "Preacher Curls", "body_part": "Arms", "muscle_group": "Biceps", "workout_type": "strength"},
    {"name": "Tricep Dips", "body_part": "Arms", "muscle_group": "Triceps", "workout_type": "strength"},
    {"name": "Concentration Curls", "body_part": "Arms", "muscle_group": "Biceps", "workout_type": "strength"},
    
    # Core
    {"name": "Plank", "body_part": "Core", "muscle_group": "Abdominals", "workout_type": "strength"},
    {"name": "Crunches", "body_part": "Core", "muscle_group": "Abdominals", "workout_type": "strength"},
    {"name": "Russian Twists", "body_part": "Core", "muscle_group": "Obliques", "workout_type": "strength"},
    {"name": "Hanging Leg Raises", "body_part": "Core", "muscle_group": "Abdominals", "workout_type": "strength"},
    {"name": "Ab Wheel Rollout", "body_part": "Core", "muscle_group": "Abdominals", "workout_type": "strength"},
    {"name": "Cable Woodchops", "body_part": "Core", "muscle_group": "Obliques", "workout_type": "strength"},
    
    # Cardio
    {"name": "Running", "body_part": "Full Body", "muscle_group": "Cardiovascular", "workout_type": "cardio"},
    {"name": "Cycling", "body_part": "Legs", "muscle_group": "Cardiovascular", "workout_type": "cardio"},
    {"name": "Rowing", "body_part": "Full Body", "muscle_group": "Cardiovascular", "workout_type": "cardio"},
    {"name": "Jump Rope", "body_part": "Full Body", "muscle_group": "Cardiovascular", "workout_type": "cardio"},
    {"name": "Swimming", "body_part": "Full Body", "muscle_group": "Cardiovascular", "workout_type": "cardio"},
    {"name": "Stair Climbing", "body_part": "Legs", "muscle_group": "Cardiovascular", "workout_type": "cardio"},
    {"name": "Elliptical", "body_part": "Full Body", "muscle_group": "Cardiovascular", "workout_type": "cardio"},
    
    # Mobility
    {"name": "Yoga", "body_part": "Full Body", "muscle_group": "Flexibility", "workout_type": "mobility"},
    {"name": "Stretching", "body_part": "Full Body", "muscle_group": "Flexibility", "workout_type": "mobility"},
    {"name": "Foam Rolling", "body_part": "Full Body", "muscle_group": "Recovery", "workout_type": "mobility"},
]

# ============== AUTH ROUTES ==============

@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    # Check if email already exists
    existing = await db.users.find_one({'email': user_data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_dict = {
        'id': str(uuid.uuid4()),
        'email': user_data.email,
        'password_hash': hash_password(user_data.password),
        'name': user_data.name,
        'age': user_data.age,
        'weight': user_data.weight,
        'height': user_data.height,
        'fitness_goals': user_data.fitness_goals,
        'created_at': datetime.utcnow()
    }
    
    await db.users.insert_one(user_dict)
    
    # If weight provided, add initial weight entry
    if user_data.weight:
        weight_entry = {
            'id': str(uuid.uuid4()),
            'user_id': user_dict['id'],
            'weight': user_data.weight,
            'date': datetime.utcnow(),
            'notes': 'Initial weight'
        }
        await db.weight_history.insert_one(weight_entry)
    
    # Generate token
    token = create_jwt_token(user_dict['id'], user_dict['email'])
    
    return TokenResponse(
        access_token=token,
        user=UserProfile(
            id=user_dict['id'],
            email=user_dict['email'],
            name=user_dict['name'],
            age=user_dict['age'],
            weight=user_dict['weight'],
            height=user_dict['height'],
            fitness_goals=user_dict['fitness_goals'],
            created_at=user_dict['created_at']
        )
    )

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with email and password"""
    user = await db.users.find_one({'email': credentials.email})
    
    if not user or not verify_password(credentials.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate token
    token = create_jwt_token(user['id'], user['email'])
    
    return TokenResponse(
        access_token=token,
        user=UserProfile(
            id=user['id'],
            email=user['email'],
            name=user['name'],
            age=user.get('age'),
            weight=user.get('weight'),
            height=user.get('height'),
            fitness_goals=user.get('fitness_goals'),
            created_at=user['created_at']
        )
    )

@api_router.get("/auth/me", response_model=UserProfile)
async def get_me(user: dict = Depends(require_auth)):
    """Get current user profile"""
    return UserProfile(
        id=user['id'],
        email=user['email'],
        name=user['name'],
        age=user.get('age'),
        weight=user.get('weight'),
        height=user.get('height'),
        fitness_goals=user.get('fitness_goals'),
        created_at=user['created_at']
    )

@api_router.put("/auth/profile", response_model=UserProfile)
async def update_profile(profile_data: UserProfileUpdate, user: dict = Depends(require_auth)):
    """Update user profile"""
    update_dict = {}
    if profile_data.name is not None:
        update_dict['name'] = profile_data.name
    if profile_data.age is not None:
        update_dict['age'] = profile_data.age
    if profile_data.weight is not None:
        update_dict['weight'] = profile_data.weight
        # Also add to weight history
        weight_entry = {
            'id': str(uuid.uuid4()),
            'user_id': user['id'],
            'weight': profile_data.weight,
            'date': datetime.utcnow(),
            'notes': None
        }
        await db.weight_history.insert_one(weight_entry)
    if profile_data.height is not None:
        update_dict['height'] = profile_data.height
    if profile_data.fitness_goals is not None:
        update_dict['fitness_goals'] = profile_data.fitness_goals
    
    if update_dict:
        await db.users.update_one({'id': user['id']}, {'$set': update_dict})
    
    updated_user = await db.users.find_one({'id': user['id']})
    
    return UserProfile(
        id=updated_user['id'],
        email=updated_user['email'],
        name=updated_user['name'],
        age=updated_user.get('age'),
        weight=updated_user.get('weight'),
        height=updated_user.get('height'),
        fitness_goals=updated_user.get('fitness_goals'),
        created_at=updated_user['created_at']
    )

# ============== WEIGHT HISTORY ROUTES ==============

@api_router.post("/weight-history", response_model=WeightHistoryItem)
async def add_weight_entry(entry: WeightEntry, user: dict = Depends(require_auth)):
    """Add a new weight entry to history"""
    weight_entry = {
        'id': str(uuid.uuid4()),
        'user_id': user['id'],
        'weight': entry.weight,
        'date': entry.date or datetime.utcnow(),
        'notes': entry.notes
    }
    await db.weight_history.insert_one(weight_entry)
    
    # Update user's current weight
    await db.users.update_one({'id': user['id']}, {'$set': {'weight': entry.weight}})
    
    return WeightHistoryItem(**weight_entry)

@api_router.get("/weight-history", response_model=List[WeightHistoryItem])
async def get_weight_history(
    days: int = Query(default=90, le=365),
    user: dict = Depends(require_auth)
):
    """Get weight history for the user"""
    start_date = datetime.utcnow() - timedelta(days=days)
    entries = await db.weight_history.find({
        'user_id': user['id'],
        'date': {'$gte': start_date}
    }).sort('date', 1).to_list(1000)
    
    return [WeightHistoryItem(**e) for e in entries]

@api_router.delete("/weight-history/{entry_id}")
async def delete_weight_entry(entry_id: str, user: dict = Depends(require_auth)):
    """Delete a weight entry"""
    result = await db.weight_history.delete_one({'id': entry_id, 'user_id': user['id']})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Weight entry not found")
    return {"message": "Weight entry deleted"}

# ============== HEART RATE ZONES ==============

@api_router.get("/heart-rate-zones", response_model=HeartRateZones)
async def get_heart_rate_zones(user: dict = Depends(require_auth)):
    """Calculate heart rate zones based on user's age"""
    age = user.get('age')
    if not age:
        raise HTTPException(status_code=400, detail="Age not set in profile. Please update your profile with your age.")
    
    # Calculate max heart rate using the standard formula
    max_hr = 220 - age
    
    return HeartRateZones(
        max_heart_rate=max_hr,
        zone1_recovery={
            "name": "Recovery",
            "min": int(max_hr * 0.50),
            "max": int(max_hr * 0.60),
            "description": "Very light activity, warm-up/cool-down"
        },
        zone2_fat_burn={
            "name": "Fat Burn",
            "min": int(max_hr * 0.60),
            "max": int(max_hr * 0.70),
            "description": "Light activity, improves basic endurance"
        },
        zone3_aerobic={
            "name": "Aerobic",
            "min": int(max_hr * 0.70),
            "max": int(max_hr * 0.80),
            "description": "Moderate activity, improves cardiovascular fitness"
        },
        zone4_anaerobic={
            "name": "Anaerobic",
            "min": int(max_hr * 0.80),
            "max": int(max_hr * 0.90),
            "description": "Hard activity, increases performance capacity"
        },
        zone5_max={
            "name": "Maximum",
            "min": int(max_hr * 0.90),
            "max": max_hr,
            "description": "Maximum effort, develops speed and power"
        }
    )

# ============== STRENGTH PROGRESSION ==============

@api_router.get("/strength-progression", response_model=List[StrengthProgression])
async def get_strength_progression(
    days: int = Query(default=90, le=365),
    user: Optional[dict] = Depends(get_current_user)
):
    """Get strength progression for compound lifts"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    mid_date = now - timedelta(days=days//2)
    
    query = {'date': {'$gte': start_date}}
    if user:
        query['user_id'] = user['id']
    
    workouts = await db.workouts.find(query).sort('date', 1).to_list(1000)
    
    # Track max weight for each compound lift category
    lift_data = {}  # category -> {current_max, previous_max, volumes, last_date}
    
    for workout in workouts:
        workout_date = workout.get('date')
        is_recent = workout_date >= mid_date if workout_date else False
        
        for exercise in workout.get('exercises', []):
            exercise_name = exercise.get('exercise_name', '')
            
            if not is_compound_lift(exercise_name):
                continue
            
            category = get_lift_category(exercise_name)
            if category == 'Other':
                continue
            
            if category not in lift_data:
                lift_data[category] = {
                    'current_max': 0,
                    'previous_max': 0,
                    'recent_volumes': [],
                    'older_volumes': [],
                    'last_date': None,
                    'exercise_name': exercise_name
                }
            
            # Find max weight in this exercise
            max_weight = 0
            total_volume = 0
            for s in exercise.get('sets', []):
                weight = s.get('weight', 0)
                reps = s.get('reps', 0)
                if weight > max_weight:
                    max_weight = weight
                total_volume += weight * reps
            
            if is_recent:
                if max_weight > lift_data[category]['current_max']:
                    lift_data[category]['current_max'] = max_weight
                    lift_data[category]['exercise_name'] = exercise_name
                lift_data[category]['recent_volumes'].append(total_volume)
                lift_data[category]['last_date'] = workout_date
            else:
                if max_weight > lift_data[category]['previous_max']:
                    lift_data[category]['previous_max'] = max_weight
                lift_data[category]['older_volumes'].append(total_volume)
    
    # Build progression list
    progressions = []
    for category, data in lift_data.items():
        current = data['current_max']
        previous = data['previous_max']
        
        # If no previous data, use current as baseline
        if previous == 0:
            previous = current
        
        improvement = current - previous
        improvement_percent = (improvement / previous * 100) if previous > 0 else 0
        
        # Determine volume trend
        recent_avg = sum(data['recent_volumes']) / len(data['recent_volumes']) if data['recent_volumes'] else 0
        older_avg = sum(data['older_volumes']) / len(data['older_volumes']) if data['older_volumes'] else recent_avg
        
        if recent_avg > older_avg * 1.05:
            trend = "increasing"
        elif recent_avg < older_avg * 0.95:
            trend = "decreasing"
        else:
            trend = "stable"
        
        progressions.append(StrengthProgression(
            exercise_name=category,
            current_max=current,
            previous_max=previous,
            improvement=improvement,
            improvement_percent=round(improvement_percent, 1),
            total_volume_trend=trend,
            last_workout_date=data['last_date']
        ))
    
    # Sort by improvement percentage descending
    progressions.sort(key=lambda x: x.improvement_percent, reverse=True)
    
    return progressions

# ============== PERSONALIZED MOTIVATION ==============

@api_router.get("/motivation/personalized")
async def get_personalized_motivation(user: Optional[dict] = Depends(get_current_user)):
    """Get personalized motivation based on user's progress"""
    messages = []
    
    # Get a random quote
    quote = random.choice(MOTIVATION_QUOTES)
    
    if not user:
        return {
            "quote": quote,
            "personalized_messages": ["Log in to see personalized insights!"]
        }
    
    # Get user's recent stats
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (start_of_month - timedelta(days=1)).replace(day=1)
    
    # This month's workouts
    this_month = await db.workouts.find({
        'user_id': user['id'],
        'date': {'$gte': start_of_month}
    }).to_list(1000)
    
    # Last month's workouts
    last_month = await db.workouts.find({
        'user_id': user['id'],
        'date': {'$gte': last_month_start, '$lt': start_of_month}
    }).to_list(1000)
    
    this_month_count = len(this_month)
    last_month_count = len(last_month)
    
    this_month_volume = sum(w.get('total_volume', 0) for w in this_month)
    last_month_volume = sum(w.get('total_volume', 0) for w in last_month)
    
    # Generate personalized messages
    if this_month_count > last_month_count:
        messages.append(f"You've done {this_month_count} workouts this month - that's {this_month_count - last_month_count} more than last month!")
    elif this_month_count > 0:
        messages.append(f"You've completed {this_month_count} workout{'s' if this_month_count > 1 else ''} this month. Keep it up!")
    
    if this_month_volume > last_month_volume and last_month_volume > 0:
        increase_pct = ((this_month_volume - last_month_volume) / last_month_volume) * 100
        messages.append(f"Your training volume is up {increase_pct:.0f}% compared to last month!")
    
    # Check for PRs
    recent_prs = await db.personal_records.find({
        'user_id': user['id'],
        'achieved_at': {'$gte': now - timedelta(days=7)}
    }).to_list(100)
    
    if recent_prs:
        pr_exercises = [pr['exercise_name'] for pr in recent_prs[:3]]
        messages.append(f"You hit new PRs in {', '.join(pr_exercises)} this week!")
    
    # Check streak
    current_streak, longest_streak = await calculate_streak(user['id'])
    if current_streak >= 3:
        messages.append(f"You're on a {current_streak}-day streak! Don't break the chain!")
    
    # Get strength progression
    progressions = await get_strength_progression(days=30, user=user)
    improving_lifts = [p for p in progressions if p.improvement > 0]
    if improving_lifts:
        best = improving_lifts[0]
        messages.append(f"Your {best.exercise_name} has improved by {best.improvement}kg (+{best.improvement_percent}%)!")
    
    # Default message if no personalized ones
    if not messages:
        messages.append("Every workout counts. Let's make today great!")
    
    return {
        "quote": quote,
        "personalized_messages": messages
    }

# ============== MOTIVATION ROUTES ==============

@api_router.get("/motivation/quote")
async def get_motivation_quote():
    """Get a random motivation quote"""
    quote = random.choice(MOTIVATION_QUOTES)
    return quote

@api_router.get("/motivation/quotes")
async def get_all_quotes():
    """Get all motivation quotes"""
    return MOTIVATION_QUOTES

# ============== ROUTES ==============

@api_router.get("/")
async def root():
    return {"message": "Trainlytics API - Your Fitness Analytics Platform"}

# ---- Exercise Templates ----

@api_router.get("/exercises", response_model=List[ExerciseTemplate])
async def get_exercises(
    body_part: Optional[str] = None, 
    workout_type: Optional[str] = None,
    search: Optional[str] = None
):
    """Get all exercise templates with optional filters and search"""
    # First, ensure default exercises exist
    count = await db.exercises.count_documents({})
    if count == 0:
        for ex in DEFAULT_EXERCISES:
            ex['id'] = str(uuid.uuid4())
            ex['is_custom'] = False
            await db.exercises.insert_one(ex)
    
    query = {}
    if body_part:
        query['body_part'] = body_part
    if workout_type:
        query['workout_type'] = workout_type
    if search:
        # Case-insensitive search on name
        query['name'] = {'$regex': search, '$options': 'i'}
    
    exercises = await db.exercises.find(query).to_list(1000)
    return [ExerciseTemplate(**{**ex, 'id': ex.get('id', str(ex.get('_id', '')))}) for ex in exercises]

@api_router.post("/exercises", response_model=ExerciseTemplate)
async def create_exercise(exercise: ExerciseTemplateCreate):
    """Create a custom exercise"""
    exercise_dict = exercise.model_dump()
    exercise_dict['id'] = str(uuid.uuid4())
    exercise_dict['is_custom'] = True
    await db.exercises.insert_one(exercise_dict)
    return ExerciseTemplate(**exercise_dict)

@api_router.get("/body-parts")
async def get_body_parts():
    """Get all unique body parts"""
    body_parts = await db.exercises.distinct('body_part')
    if not body_parts:
        body_parts = list(set([ex['body_part'] for ex in DEFAULT_EXERCISES]))
    return body_parts

# ---- Workouts ----

@api_router.post("/workouts", response_model=Workout)
async def create_workout(workout: WorkoutCreate, user: Optional[dict] = Depends(get_current_user)):
    """Create a new workout with auto-calculations"""
    workout_dict = workout.model_dump()
    workout_dict['id'] = str(uuid.uuid4())
    workout_dict['date'] = workout.date or datetime.utcnow()
    workout_dict['created_at'] = datetime.utcnow()
    
    # Associate with user if authenticated
    if user:
        workout_dict['user_id'] = user['id']
    
    # Calculate metrics for each exercise
    total_volume = 0
    for exercise in workout_dict['exercises']:
        exercise_volume = calculate_volume([ExerciseSet(**s) for s in exercise['sets']])
        exercise['total_volume'] = exercise_volume
        total_volume += exercise_volume
        
        # Calculate estimated 1RM for strength exercises
        if exercise['workout_type'] == 'strength' and exercise['sets']:
            best_set = max(exercise['sets'], key=lambda s: s.get('weight', 0) * s.get('reps', 0))
            if best_set.get('weight') and best_set.get('reps'):
                exercise['estimated_1rm'] = round(calculate_1rm(best_set['weight'], best_set['reps']), 1)
    
    workout_dict['total_volume'] = total_volume
    
    await db.workouts.insert_one(workout_dict)
    
    # Update personal records
    await update_personal_records(workout_dict, user['id'] if user else None)
    
    return Workout(**workout_dict)

@api_router.get("/workouts", response_model=List[Workout])
async def get_workouts(
    limit: int = Query(default=50, le=1000),
    skip: int = 0,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    user: Optional[dict] = Depends(get_current_user)
):
    """Get workouts with optional date filtering"""
    query = {}
    if user:
        query['user_id'] = user['id']
    if start_date:
        query['date'] = {'$gte': start_date}
    if end_date:
        if 'date' in query:
            query['date']['$lte'] = end_date
        else:
            query['date'] = {'$lte': end_date}
    
    workouts = await db.workouts.find(query).sort('date', -1).skip(skip).limit(limit).to_list(limit)
    return [Workout(**{**w, 'id': w.get('id', str(w.get('_id', '')))}) for w in workouts]

@api_router.get("/workouts/{workout_id}", response_model=Workout)
async def get_workout(workout_id: str):
    """Get a specific workout by ID"""
    workout = await db.workouts.find_one({'id': workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return Workout(**{**workout, 'id': workout.get('id', str(workout.get('_id', '')))})

@api_router.delete("/workouts/{workout_id}")
async def delete_workout(workout_id: str, user: Optional[dict] = Depends(get_current_user)):
    """Delete a workout"""
    query = {'id': workout_id}
    if user:
        query['user_id'] = user['id']
    result = await db.workouts.delete_one(query)
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"message": "Workout deleted successfully"}

@api_router.get("/workouts/recent/exercises")
async def get_recent_exercises(user: Optional[dict] = Depends(get_current_user)):
    """Get recently used exercises for quick-add"""
    query = {}
    if user:
        query['user_id'] = user['id']
    workouts = await db.workouts.find(query).sort('date', -1).limit(10).to_list(10)
    exercises = []
    seen = set()
    
    for workout in workouts:
        for ex in workout.get('exercises', []):
            key = ex.get('exercise_name', '')
            if key and key not in seen:
                seen.add(key)
                exercises.append({
                    'exercise_name': ex.get('exercise_name'),
                    'body_part': ex.get('body_part'),
                    'workout_type': ex.get('workout_type'),
                    'last_sets': ex.get('sets', [])
                })
    
    return exercises[:10]

@api_router.get("/workouts/last/repeat")
async def get_last_workout_to_repeat(user: Optional[dict] = Depends(get_current_user)):
    """Get the last workout to repeat"""
    query = {}
    if user:
        query['user_id'] = user['id']
    workout = await db.workouts.find_one(query, sort=[('date', -1)])
    if not workout:
        return None
    return Workout(**{**workout, 'id': workout.get('id', str(workout.get('_id', '')))})

# ---- Dashboard & Analytics ----

@api_router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(user: Optional[dict] = Depends(get_current_user)):
    """Get dashboard statistics"""
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    query = {'date': {'$gte': start_of_month}}
    if user:
        query['user_id'] = user['id']
    
    # Workouts this month
    month_workouts = await db.workouts.find(query).to_list(1000)
    total_workouts_this_month = len(month_workouts)
    
    # Workouts this week
    week_workouts = [w for w in month_workouts if w.get('date', now) >= start_of_week]
    workouts_this_week = len(week_workouts)
    
    # Total volume this month
    total_volume = sum(w.get('total_volume', 0) for w in month_workouts)
    
    # Average intensity (RPE)
    all_rpe = []
    total_duration = 0
    for w in month_workouts:
        total_duration += w.get('duration', 0) or 0
        for ex in w.get('exercises', []):
            for s in ex.get('sets', []):
                if s.get('rpe'):
                    all_rpe.append(s.get('rpe'))
    
    avg_intensity = sum(all_rpe) / len(all_rpe) if all_rpe else 0
    
    # Streaks
    current_streak, longest_streak = await calculate_streak(user['id'] if user else None)
    
    return DashboardStats(
        total_workouts_this_month=total_workouts_this_month,
        total_volume_this_month=round(total_volume, 1),
        avg_intensity=round(avg_intensity, 1),
        total_time_spent=total_duration,
        current_streak=current_streak,
        longest_streak=longest_streak,
        workouts_this_week=workouts_this_week
    )

@api_router.get("/dashboard/weekly-consistency")
async def get_weekly_consistency(user: Optional[dict] = Depends(get_current_user)):
    """Get workout counts for each day of the current week"""
    now = datetime.utcnow()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    data = []
    
    for i, day in enumerate(days):
        day_start = start_of_week + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        query = {'date': {'$gte': day_start, '$lt': day_end}}
        if user:
            query['user_id'] = user['id']
        
        count = await db.workouts.count_documents(query)
        
        data.append({
            'day': day,
            'count': count,
            'is_today': day_start.date() == now.date()
        })
    
    return data

@api_router.get("/dashboard/volume-trend")
async def get_volume_trend(days: int = 30, user: Optional[dict] = Depends(get_current_user)):
    """Get volume trend over time"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    query = {'date': {'$gte': start_date}}
    if user:
        query['user_id'] = user['id']
    
    workouts = await db.workouts.find(query).sort('date', 1).to_list(1000)
    
    # Group by date
    daily_volume = {}
    for w in workouts:
        date_str = w.get('date').strftime('%Y-%m-%d') if w.get('date') else ''
        if date_str:
            daily_volume[date_str] = daily_volume.get(date_str, 0) + w.get('total_volume', 0)
    
    result = []
    for i in range(days):
        date = start_date + timedelta(days=i)
        date_str = date.strftime('%Y-%m-%d')
        result.append({
            'date': date_str,
            'label': date.strftime('%b %d'),
            'volume': round(daily_volume.get(date_str, 0), 1)
        })
    
    return result

@api_router.get("/dashboard/body-part-distribution")
async def get_body_part_distribution(days: int = 30, user: Optional[dict] = Depends(get_current_user)):
    """Get workout distribution by body part"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    query = {'date': {'$gte': start_date}}
    if user:
        query['user_id'] = user['id']
    
    workouts = await db.workouts.find(query).to_list(1000)
    
    distribution = {}
    for w in workouts:
        for ex in w.get('exercises', []):
            body_part = ex.get('body_part', 'Other')
            distribution[body_part] = distribution.get(body_part, 0) + 1
    
    # Convert to list format for pie chart
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
    result = []
    for i, (body_part, count) in enumerate(distribution.items()):
        result.append({
            'label': body_part,
            'value': count,
            'color': colors[i % len(colors)]
        })
    
    return result

# ---- Personal Records ----

@api_router.get("/personal-records", response_model=List[PersonalRecord])
async def get_personal_records(exercise_name: Optional[str] = None, user: Optional[dict] = Depends(get_current_user)):
    """Get personal records"""
    query = {}
    if exercise_name:
        query['exercise_name'] = exercise_name
    if user:
        query['user_id'] = user['id']
    
    records = await db.personal_records.find(query).to_list(1000)
    return [PersonalRecord(**{**r, 'id': r.get('id', str(r.get('_id', '')))}) for r in records]

# ---- Progress Tracking ----

@api_router.get("/progress/exercise/{exercise_name}")
async def get_exercise_progress(
    exercise_name: str,
    days: int = Query(default=90, le=365),
    user: Optional[dict] = Depends(get_current_user)
):
    """Get progress data for a specific exercise"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    query = {'date': {'$gte': start_date}}
    if user:
        query['user_id'] = user['id']
    
    workouts = await db.workouts.find(query).sort('date', 1).to_list(1000)
    
    progress_data = []
    for w in workouts:
        for ex in w.get('exercises', []):
            if ex.get('exercise_name') == exercise_name:
                max_weight = max([s.get('weight', 0) for s in ex.get('sets', [])], default=0)
                progress_data.append({
                    'date': w.get('date').strftime('%Y-%m-%d'),
                    'label': w.get('date').strftime('%b %d'),
                    'max_weight': max_weight,
                    'estimated_1rm': ex.get('estimated_1rm', 0),
                    'total_volume': ex.get('total_volume', 0)
                })
    
    return progress_data

@api_router.get("/progress/summary")
async def get_progress_summary(days: int = 30, user: Optional[dict] = Depends(get_current_user)):
    """Get overall progress summary"""
    now = datetime.utcnow()
    current_start = now - timedelta(days=days)
    previous_start = current_start - timedelta(days=days)
    
    query_current = {'date': {'$gte': current_start}}
    query_previous = {'date': {'$gte': previous_start, '$lt': current_start}}
    
    if user:
        query_current['user_id'] = user['id']
        query_previous['user_id'] = user['id']
    
    current_workouts = await db.workouts.find(query_current).to_list(1000)
    previous_workouts = await db.workouts.find(query_previous).to_list(1000)
    
    current_volume = sum(w.get('total_volume', 0) for w in current_workouts)
    previous_volume = sum(w.get('total_volume', 0) for w in previous_workouts)
    
    volume_change = ((current_volume - previous_volume) / previous_volume * 100) if previous_volume > 0 else 0
    
    return {
        'current_period': {
            'workouts': len(current_workouts),
            'total_volume': round(current_volume, 1),
            'avg_volume_per_workout': round(current_volume / len(current_workouts), 1) if current_workouts else 0
        },
        'previous_period': {
            'workouts': len(previous_workouts),
            'total_volume': round(previous_volume, 1),
            'avg_volume_per_workout': round(previous_volume / len(previous_workouts), 1) if previous_workouts else 0
        },
        'volume_change_percent': round(volume_change, 1)
    }

# ---- Export Data ----

@api_router.get("/export/csv")
async def export_csv(days: int = 30, user: Optional[dict] = Depends(get_current_user)):
    """Export workout data as CSV format"""
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)
    
    query = {'date': {'$gte': start_date}}
    if user:
        query['user_id'] = user['id']
    
    workouts = await db.workouts.find(query).sort('date', 1).to_list(1000)
    
    csv_data = "Date,Workout Type,Exercise,Body Part,Sets,Total Volume,Duration,Notes\n"
    
    for w in workouts:
        date = w.get('date').strftime('%Y-%m-%d') if w.get('date') else ''
        workout_type = w.get('workout_type', '')
        duration = w.get('duration', '')
        workout_notes = w.get('notes', '').replace(',', ';') if w.get('notes') else ''
        
        for ex in w.get('exercises', []):
            exercise_name = ex.get('exercise_name', '').replace(',', ';')
            body_part = ex.get('body_part', '')
            sets_count = len(ex.get('sets', []))
            total_volume = ex.get('total_volume', 0)
            
            csv_data += f"{date},{workout_type},{exercise_name},{body_part},{sets_count},{total_volume},{duration},{workout_notes}\n"
    
    return {"csv_data": csv_data, "filename": f"trainlytics_export_{now.strftime('%Y%m%d')}.csv"}

# ---- Import Data ----

class CSVImportRequest(BaseModel):
    csv_data: str

class ImportResult(BaseModel):
    success: bool
    workouts_created: int
    workouts_merged: int
    exercises_imported: int
    errors: List[str]

@api_router.post("/import/csv", response_model=ImportResult)
async def import_csv(request: CSVImportRequest, user: Optional[dict] = Depends(get_current_user)):
    """Import workout data from CSV format. Supports multiple formats and auto-detects date format."""
    import csv
    from io import StringIO
    import re
    
    def parse_date(date_str: str) -> Optional[datetime]:
        """Parse date from multiple formats"""
        date_str = date_str.strip()
        
        # Try ISO format first: YYYY-MM-DD
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            pass
        
        # Try DD-MMM-YY format: 06-Jan-25
        try:
            return datetime.strptime(date_str, '%d-%b-%y')
        except ValueError:
            pass
        
        # Try DD-MMM-YYYY format: 06-Jan-2025
        try:
            return datetime.strptime(date_str, '%d-%b-%Y')
        except ValueError:
            pass
        
        # Try MM/DD/YYYY format
        try:
            return datetime.strptime(date_str, '%m/%d/%Y')
        except ValueError:
            pass
        
        # Try DD/MM/YYYY format
        try:
            return datetime.strptime(date_str, '%d/%m/%Y')
        except ValueError:
            pass
        
        return None
    
    def parse_weight(weight_str: str) -> float:
        """Parse weight from string, handling 'kg' suffix"""
        if not weight_str:
            return 0
        # Remove 'kg' suffix and any whitespace
        weight_str = re.sub(r'\s*kg\s*', '', weight_str, flags=re.IGNORECASE).strip()
        try:
            return float(weight_str)
        except ValueError:
            return 0
    
    def detect_format(headers: List[str]) -> str:
        """Detect CSV format based on headers"""
        headers_lower = [h.lower().strip() for h in headers]
        
        # Format 1: User's format - Date, Workout, Weight, Reps, Sets
        if 'workout' in headers_lower and 'weight' in headers_lower and 'reps' in headers_lower:
            return 'user_format'
        
        # Format 2: Export format - Date, Workout Type, Exercise, Body Part, Sets, Total Volume, Duration, Notes
        if 'exercise' in headers_lower and 'body part' in headers_lower:
            return 'export_format'
        
        return 'unknown'
    
    errors = []
    workouts_by_date = {}
    exercises_imported = 0
    
    try:
        # Read first line to detect format
        lines = request.csv_data.strip().split('\n')
        if not lines:
            return ImportResult(success=False, workouts_created=0, workouts_merged=0, exercises_imported=0, errors=["Empty CSV"])
        
        reader = csv.DictReader(StringIO(request.csv_data))
        headers = reader.fieldnames or []
        csv_format = detect_format(headers)
        
        if csv_format == 'unknown':
            # Try to be flexible - if we have Date column, try to parse
            pass
        
        for row_num, row in enumerate(reader, start=2):
            try:
                if csv_format == 'user_format':
                    # User's format: Date, Workout, Weight, Reps, Sets
                    date_str = row.get('Date', '').strip()
                    exercise_name = row.get('Workout', '').strip()
                    weight = parse_weight(row.get('Weight', '0'))
                    reps = int(row.get('Reps', 1) or 1)
                    sets_count = int(row.get('Sets', 1) or 1)
                    
                    if not date_str or not exercise_name:
                        errors.append(f"Row {row_num}: Missing date or workout name")
                        continue
                    
                    workout_date = parse_date(date_str)
                    if not workout_date:
                        errors.append(f"Row {row_num}: Invalid date format '{date_str}'")
                        continue
                    
                    # Auto-detect body part from exercise name
                    exercise_lower = exercise_name.lower()
                    if any(x in exercise_lower for x in ['squat', 'lunge', 'leg', 'calf', 'hip']):
                        body_part = 'Legs'
                    elif any(x in exercise_lower for x in ['bench', 'chest', 'push-up', 'fly']):
                        body_part = 'Chest'
                    elif any(x in exercise_lower for x in ['row', 'pull', 'lat', 'back', 'deadlift']):
                        body_part = 'Back'
                    elif any(x in exercise_lower for x in ['shoulder', 'press', 'delt', 'lateral']):
                        body_part = 'Shoulders'
                    elif any(x in exercise_lower for x in ['curl', 'tricep', 'bicep', 'arm']):
                        body_part = 'Arms'
                    elif any(x in exercise_lower for x in ['core', 'ab', 'plank', 'crunch']):
                        body_part = 'Core'
                    else:
                        body_part = 'Full Body'
                    
                    workout_type = 'strength'
                    total_volume = weight * reps * sets_count
                    duration = None
                    notes = None
                    
                else:
                    # Export format: Date, Workout Type, Exercise, Body Part, Sets, Total Volume, Duration, Notes
                    date_str = row.get('Date', '').strip()
                    workout_type = row.get('Workout Type', 'strength').strip().lower()
                    exercise_name = row.get('Exercise', '').strip().replace(';', ',')
                    body_part = row.get('Body Part', '').strip()
                    sets_count = int(row.get('Sets', 1) or 1)
                    total_volume = float(row.get('Total Volume', 0) or 0)
                    duration_str = row.get('Duration', '').strip()
                    duration = int(duration_str) if duration_str.isdigit() else None
                    notes = row.get('Notes', '').strip().replace(';', ',')
                    
                    if not date_str or not exercise_name:
                        errors.append(f"Row {row_num}: Missing date or exercise name")
                        continue
                    
                    workout_date = parse_date(date_str)
                    if not workout_date:
                        errors.append(f"Row {row_num}: Invalid date format '{date_str}'")
                        continue
                    
                    # Default values for export format
                    weight = 0
                    reps = 10
                
                # Ensure workout type is valid
                if workout_type not in ['strength', 'cardio', 'mobility', 'sports', 'custom']:
                    workout_type = 'strength'
                
                # Create standardized date string for grouping
                date_key = workout_date.strftime('%Y-%m-%d')
                key = f"{date_key}_{workout_type}"
                
                if key not in workouts_by_date:
                    workouts_by_date[key] = {
                        'date': workout_date,
                        'workout_type': workout_type,
                        'exercises': [],
                        'duration': duration,
                        'notes': notes
                    }
                
                # Calculate weight per rep from total volume and sets if using export format
                if csv_format != 'user_format' and total_volume > 0:
                    reps_per_set = 10
                    weight = total_volume / (sets_count * reps_per_set)
                else:
                    reps_per_set = reps
                    weight = weight
                
                # Create sets
                sets = []
                for i in range(sets_count):
                    sets.append({
                        'set_number': i + 1,
                        'reps': reps_per_set if csv_format == 'user_format' else 10,
                        'weight': round(weight, 1),
                        'rpe': None
                    })
                
                # Check if exercise already exists in this workout (merge)
                existing_exercise = None
                for ex in workouts_by_date[key]['exercises']:
                    if ex['exercise_name'] == exercise_name:
                        existing_exercise = ex
                        break
                
                if existing_exercise:
                    for s in sets:
                        s['set_number'] = len(existing_exercise['sets']) + 1
                        existing_exercise['sets'].append(s)
                    existing_exercise['total_volume'] = existing_exercise.get('total_volume', 0) + total_volume
                else:
                    workouts_by_date[key]['exercises'].append({
                        'exercise_name': exercise_name,
                        'body_part': body_part or 'Other',
                        'workout_type': workout_type,
                        'sets': sets,
                        'total_volume': total_volume,
                        'notes': None
                    })
                
                exercises_imported += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
    
    except Exception as e:
        return ImportResult(
            success=False,
            workouts_created=0,
            workouts_merged=0,
            exercises_imported=0,
            errors=[f"CSV parsing error: {str(e)}"]
        )
    
    # Now save the workouts to database
    workouts_created = 0
    workouts_merged = 0
    
    for key, workout_data in workouts_by_date.items():
        try:
            # Check if workout already exists for this date
            query = {
                'date': {
                    '$gte': workout_data['date'].replace(hour=0, minute=0, second=0),
                    '$lt': workout_data['date'].replace(hour=23, minute=59, second=59)
                },
                'workout_type': workout_data['workout_type']
            }
            if user:
                query['user_id'] = user['id']
            
            existing_workout = await db.workouts.find_one(query)
            
            if existing_workout:
                # Merge exercises into existing workout
                for new_ex in workout_data['exercises']:
                    # Check if exercise already exists
                    found = False
                    for ex in existing_workout.get('exercises', []):
                        if ex.get('exercise_name') == new_ex['exercise_name']:
                            # Merge sets
                            for s in new_ex['sets']:
                                s['set_number'] = len(ex['sets']) + 1
                                ex['sets'].append(s)
                            ex['total_volume'] = ex.get('total_volume', 0) + new_ex.get('total_volume', 0)
                            found = True
                            break
                    
                    if not found:
                        existing_workout['exercises'].append(new_ex)
                
                # Recalculate total volume
                total_volume = sum(ex.get('total_volume', 0) for ex in existing_workout['exercises'])
                
                await db.workouts.update_one(
                    {'_id': existing_workout['_id']},
                    {'$set': {
                        'exercises': existing_workout['exercises'],
                        'total_volume': total_volume
                    }}
                )
                workouts_merged += 1
            else:
                # Create new workout
                workout_dict = {
                    'id': str(uuid.uuid4()),
                    'date': workout_data['date'],
                    'workout_type': workout_data['workout_type'],
                    'exercises': workout_data['exercises'],
                    'duration': workout_data['duration'],
                    'notes': workout_data['notes'],
                    'total_volume': sum(ex.get('total_volume', 0) for ex in workout_data['exercises']),
                    'created_at': datetime.utcnow()
                }
                
                if user:
                    workout_dict['user_id'] = user['id']
                
                await db.workouts.insert_one(workout_dict)
                workouts_created += 1
                
        except Exception as e:
            errors.append(f"Error saving workout for {key}: {str(e)}")
    
    return ImportResult(
        success=len(errors) == 0 or (workouts_created + workouts_merged) > 0,
        workouts_created=workouts_created,
        workouts_merged=workouts_merged,
        exercises_imported=exercises_imported,
        errors=errors[:10]  # Limit errors to first 10
    )

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
