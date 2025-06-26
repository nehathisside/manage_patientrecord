from flask import Flask, request, jsonify, render_template
from datetime import datetime
import uuid
from collections import deque, defaultdict
import heapq
import sqlite3

app = Flask(__name__)

DATABASE = 'hospital.db'

def get_db_connection():
    """Create and return a database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row 
    return conn

def init_database():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            disease TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            doctor TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    
    conn.execute('CREATE INDEX IF NOT EXISTS idx_phone ON patients(phone)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_doctor ON patients(doctor)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_status ON patients(status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_appointment_time ON patients(appointment_time)')
    
    conn.commit()
    conn.close()

doctor_specialties = {
    "fever": "Dr. Sharma (General)",
    "cough": "Dr. Mehta (Chest)",
    "injury": "Dr. Verma (Ortho)",
    "diabetes": "Dr. Joshi (Physician)",
    "heart": "Dr. Singh (Cardiologist)",
    "skin": "Dr. Batra (Dermatologist)"
}

def suggest_doctor(symptoms):
    for keyword, doctor in doctor_specialties.items():
        if keyword.lower() in symptoms.lower():
            return doctor
    return "Dr. Ahuja (General Practitioner)"

class Patient:
    def __init__(self, name, age, gender, phone, address, disease, symptoms, appointment_time):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.age = age
        self.gender = gender
        self.phone = phone
        self.address = address
        self.disease = disease
        self.symptoms = symptoms
        self.appointment_time = appointment_time
        self.registered_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.doctor = suggest_doctor(symptoms)
        self.status = "Pending"

    def to_dict(self):
        return self.__dict__

class HospitalManager:
    def __init__(self):
        self.patient_queue = deque()
        self.id_map = {}
        self.phone_map = defaultdict(set) 
        self.doctor_map = defaultdict(set)
        self.status_map = defaultdict(set)
        self.priority_queue = []
        
        init_database()
        
        self._load_from_database()

    def _load_from_database(self):
        """Load existing patients from database into memory structures"""
        conn = get_db_connection()
        try:
            patients = conn.execute('SELECT * FROM patients ORDER BY registered_at').fetchall()
            for row in patients:
                patient = Patient(
                    name=row['name'],
                    age=row['age'],
                    gender=row['gender'],
                    phone=row['phone'],
                    address=row['address'],
                    disease=row['disease'],
                    symptoms=row['symptoms'],
                    appointment_time=row['appointment_time']
                )
                patient.id = row['id']
                patient.registered_at = row['registered_at']
                patient.doctor = row['doctor']
                patient.status = row['status']
                
                self._add_to_memory_structures(patient)
        finally:
            conn.close()

    def _add_to_memory_structures(self, patient):
        """Add patient to original in-memory data structures"""
        self.patient_queue.append(patient)
        self.id_map[patient.id] = patient
        self.phone_map[patient.phone].add(patient.id)
        self.doctor_map[patient.doctor.lower()].add(patient.id)
        self.status_map[patient.status.lower()].add(patient.id)
        
        appt_time = datetime.strptime(patient.appointment_time, "%Y-%m-%dT%H:%M")
        heapq.heappush(self.priority_queue, (appt_time, patient))

    def _save_to_database(self, patient):
        """Save patient to database"""
        conn = get_db_connection()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO patients (id, name, age, gender, phone, address, disease, 
                                               symptoms, appointment_time, registered_at, doctor, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (patient.id, patient.name, patient.age, patient.gender, patient.phone,
                  patient.address, patient.disease, patient.symptoms, patient.appointment_time,
                  patient.registered_at, patient.doctor, patient.status))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _update_database_status(self, pid, new_status):
        """Update patient status in database"""
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                'UPDATE patients SET status = ? WHERE id = ?', 
                (new_status, pid)
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def _delete_from_database(self, pid):
        """Delete patient from database"""
        conn = get_db_connection()
        try:
            cursor = conn.execute('DELETE FROM patients WHERE id = ?', (pid,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return False
        finally:
            conn.close()

    def add_patient(self, name, age, gender, phone, address, disease, symptoms, appointment_time):
        patient = Patient(name, age, gender, phone, address, disease, symptoms, appointment_time)
        
        self._add_to_memory_structures(patient)
        
        self._save_to_database(patient)
        
        return patient

    def get_all_patients(self):
        return [p.to_dict() for p in self.patient_queue]

    def search_by_id(self, pid):
        patient = self.id_map.get(pid)
        return patient.to_dict() if patient else None

    def search_by_phone(self, phone):
        ids = self.phone_map.get(phone, set())
        return [self.id_map[pid].to_dict() for pid in ids]

    def filter_by_doctor(self, doctor):
        ids = self.doctor_map.get(doctor.lower(), set())
        return [self.id_map[pid].to_dict() for pid in ids]

    def filter_by_status(self, status):
        ids = self.status_map.get(status.lower(), set())
        return [self.id_map[pid].to_dict() for pid in ids]

    def get_priority_ordered_patients(self):
        sorted_queue = sorted(self.priority_queue)
        return [p.to_dict() for _, p in sorted_queue]

    def update_patient_status(self, pid, new_status):
        if pid in self.id_map:
            patient = self.id_map[pid]
            old_status = patient.status.lower()
            patient.status = new_status
            self.status_map[old_status].discard(pid)
            self.status_map[new_status.lower()].add(pid)
            
            self._update_database_status(pid, new_status)
            return True
        return False

    def get_all_patients_from_db(self):
        """Get all patients directly from database"""
        conn = get_db_connection()
        try:
            patients = conn.execute('SELECT * FROM patients ORDER BY appointment_time').fetchall()
            return [dict(patient) for patient in patients]
        finally:
            conn.close()

    def search_by_id_in_db(self, pid):
        """Search patient by ID directly in database"""
        conn = get_db_connection()
        try:
            patient = conn.execute('SELECT * FROM patients WHERE id = ?', (pid,)).fetchone()
            return dict(patient) if patient else None
        finally:
            conn.close()

    def delete_patient(self, pid):
        """Delete patient from both memory and database"""
        if pid in self.id_map:
            patient = self.id_map[pid]
            
            self.patient_queue = deque([p for p in self.patient_queue if p.id != pid])
            
            del self.id_map[pid]
            self.phone_map[patient.phone].discard(pid)
            self.doctor_map[patient.doctor.lower()].discard(pid)
            self.status_map[patient.status.lower()].discard(pid)
            
            self.priority_queue = [(time, p) for time, p in self.priority_queue if p.id != pid]
            heapq.heapify(self.priority_queue)
            
            return self._delete_from_database(pid)
        return False

    def get_database_statistics(self):
        """Get statistics directly from database"""
        conn = get_db_connection()
        try:
            stats = {}
            
            total = conn.execute('SELECT COUNT(*) as count FROM patients').fetchone()
            stats['total_patients'] = total['count']
            
            status_counts = conn.execute('''
                SELECT status, COUNT(*) as count 
                FROM patients 
                GROUP BY status
            ''').fetchall()
            stats['by_status'] = {row['status']: row['count'] for row in status_counts}
            
            doctor_counts = conn.execute('''
                SELECT doctor, COUNT(*) as count 
                FROM patients 
                GROUP BY doctor 
                ORDER BY count DESC
            ''').fetchall()
            stats['by_doctor'] = {row['doctor']: row['count'] for row in doctor_counts}
            
            return stats
        finally:
            conn.close()

    def sync_memory_to_database(self):
        """Manually sync all memory data to database (utility function)"""
        for patient in self.patient_queue:
            self._save_to_database(patient)

    def reload_from_database(self):
        """Reload all data from database to memory (utility function)"""
        self.patient_queue.clear()
        self.id_map.clear()
        self.phone_map.clear()
        self.doctor_map.clear()
        self.status_map.clear()
        self.priority_queue.clear()
        
        self._load_from_database()


hospital = HospitalManager()

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/add_patient', methods=['POST'])
def add_patient():
    try:
        data = request.json
        patient = hospital.add_patient(
            name=data["name"],
            age=data["age"],
            gender=data["gender"],
            phone=data["phone"],
            address=data["address"],
            disease=data["disease"],
            symptoms=data["symptoms"],
            appointment_time=data["appointment_time"]
        )
        return jsonify({"message": "✅ Patient added", "id": patient.id, "doctor": patient.doctor})
    except Exception as e:
        return jsonify({"error": f"Failed to add patient: {str(e)}"}), 500

@app.route('/patients')
def patients_page():
    return render_template("patients.html")

@app.route('/api/patients')
def get_patients():
    try:
        return jsonify(hospital.get_all_patients())
    except Exception as e:
        return jsonify({"error": f"Failed to fetch patients: {str(e)}"}), 500

@app.route('/api/patients/db')
def get_patients_from_db():
    """NEW: Get patients directly from database"""
    try:
        return jsonify(hospital.get_all_patients_from_db())
    except Exception as e:
        return jsonify({"error": f"Failed to fetch patients from DB: {str(e)}"}), 500

@app.route('/api/search_by_id/<pid>')
def search_by_id(pid):
    try:
        result = hospital.search_by_id(pid)
        if result:
            return jsonify(result)
        else:
            return jsonify({"error": "Patient not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

@app.route('/api/search_by_id_db/<pid>')
def search_by_id_in_db(pid):
    """NEW: Search directly in database"""
    try:
        result = hospital.search_by_id_in_db(pid)
        if result:
            return jsonify(result)
        else:
            return jsonify({"error": "Patient not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Database search failed: {str(e)}"}), 500

@app.route('/api/search_by_phone/<phone>')
def search_by_phone(phone):
    try:
        # Searches in memory (original behavior)
        return jsonify(hospital.search_by_phone(phone))
    except Exception as e:
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

@app.route('/api/filter_by_doctor/<doctor>')
def filter_by_doctor(doctor):
    try:
        return jsonify(hospital.filter_by_doctor(doctor))
    except Exception as e:
        return jsonify({"error": f"Filter failed: {str(e)}"}), 500

@app.route('/api/filter_by_status/<status>')
def filter_by_status(status):
    try:
        return jsonify(hospital.filter_by_status(status))
    except Exception as e:
        return jsonify({"error": f"Filter failed: {str(e)}"}), 500

@app.route('/api/suggest-doctor', methods=['POST'])
def api_suggest_doctor():
    try:
        data = request.json
        symptoms = data.get("symptoms", "")
        doctor = suggest_doctor(symptoms)
        return jsonify([{"name": doctor, "speciality": symptoms}])
    except Exception as e:
        return jsonify({"error": f"Failed to suggest doctor: {str(e)}"}), 500

@app.route('/api/update_status/<patient_id>', methods=['POST'])
def update_status(patient_id):
    try:
        new_status = request.json.get("status")
        success = hospital.update_patient_status(patient_id, new_status)
        if success:
            return jsonify({"message": "✅ Status updated"})
        return jsonify({"error": "Patient not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to update status: {str(e)}"}), 500

@app.route('/api/delete_patient/<patient_id>', methods=['DELETE'])
def delete_patient(patient_id):
    """NEW: Delete patient from both memory and database"""
    try:
        success = hospital.delete_patient(patient_id)
        if success:
            return jsonify({"message": "✅ Patient deleted"})
        return jsonify({"error": "Patient not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to delete patient: {str(e)}"}), 500

@app.route('/api/statistics')
def get_statistics():
    """NEW: Get statistics from database"""
    try:
        stats = hospital.get_database_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": f"Failed to get statistics: {str(e)}"}), 500

@app.route('/api/sync', methods=['POST'])
def sync_data():
    """NEW: Manually sync memory to database"""
    try:
        hospital.sync_memory_to_database()
        return jsonify({"message": "✅ Data synced to database"})
    except Exception as e:
        return jsonify({"error": f"Failed to sync: {str(e)}"}), 500

@app.route('/api/reload', methods=['POST'])
def reload_data():
    """NEW: Reload data from database to memory"""
    try:
        hospital.reload_from_database()
        return jsonify({"message": "✅ Data reloaded from database"})
    except Exception as e:
        return jsonify({"error": f"Failed to reload: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)