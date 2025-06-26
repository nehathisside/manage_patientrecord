async function suggestDoctor(symptoms) {
    const res = await fetch('/api/suggest-doctor', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symptoms })
    });
    const data = await res.json();
    const list = document.getElementById('suggestedDoctors');
    list.innerHTML = '';
    data.forEach(doc => {
        const li = document.createElement('li');
        li.textContent = `${doc.name} (${doc.speciality})`;
        list.appendChild(li);
    });
}

function validateForm(formId) {
    const form = document.getElementById(formId);
    let valid = true;
    const fields = form.querySelectorAll('input[required], select[required]');
    fields.forEach(f => {
        if (!f.value.trim()) {
            f.style.borderColor = 'red';
            valid = false;
        } else if (f.type === 'number' && parseFloat(f.value) < 0) {
            f.style.borderColor = 'red';
            valid = false;
            alert('Age cannot be negative!');
        } else {
            f.style.borderColor = '';
        }
    });
    return valid;
}

async function submitForm() {
    if (!validateForm('appointmentForm')) return;

    const age = document.getElementById('age').value;
    if (age < 0 || age > 150) {
        alert('Please enter a valid age between 0 and 150');
        return;
    }
    
    const data = {
        name: document.getElementById('name').value,
        age: document.getElementById('age').value,
        gender: document.getElementById('gender').value,
        disease: document.getElementById('disease').value,
        symptoms: document.getElementById('symptoms').value,
        address: document.getElementById('address').value,
        phone: document.getElementById('phone').value,
        appointment_time: document.getElementById('appointment_time').value
    };

    const res = await fetch('/add_patient', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

    const result = await res.json();
    alert(result.message + "\nSuggested Doctor: " + result.doctor);

    document.getElementById('appointmentForm').reset();

    document.getElementById('suggestedDoctors').innerHTML = '';
}


async function loadPatients() {
    const res = await fetch('/patients');
    const data = await res.json();
    window.patientData = data; // Cache
    populateDoctorFilter(data);
    displayPatients(data);
}

function populateDoctorFilter(data) {
    const doctorSet = new Set(data.map(p => p.doctor));
    const filter = document.getElementById('filterDoctor');
    filter.innerHTML = `<option value="">All Doctors</option>`;
    doctorSet.forEach(doc => {
        const opt = document.createElement('option');
        opt.value = doc;
        opt.textContent = doc;
        filter.appendChild(opt);
    });
}

function displayPatients(data) {
    const tbody = document.getElementById('patientTableBody');
    tbody.innerHTML = '';
    data.forEach(p => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${p.id}</td>
            <td>${p.name}</td>
            <td>${p.phone || '—'}</td>
            <td>${p.doctor}</td>
            <td>
                <select onchange="updateStatus('${p.id}', this.value)">
                    <option ${p.status === 'Pending' ? 'selected' : ''}>Pending</option>
                    <option ${p.status === 'Admitted' ? 'selected' : ''}>Admitted</option>
                    <option ${p.status === 'Discharged' ? 'selected' : ''}>Discharged</option>
                </select>
            </td>
            <td><button onclick="assignBed('${p.id}')">Assign Bed</button></td>
        `;
        tbody.appendChild(row);
    });
}

function filterPatients() {
    const idVal = document.getElementById('searchId').value.toLowerCase();
    const phoneVal = document.getElementById('searchPhone').value.toLowerCase();
    const doctorVal = document.getElementById('filterDoctor').value;
    const statusVal = document.getElementById('filterStatus').value;

    const filtered = window.patientData.filter(p =>
        (!idVal || p.id.toLowerCase().includes(idVal)) &&
        (!phoneVal || (p.phone && p.phone.toLowerCase().includes(phoneVal))) &&
        (!doctorVal || p.doctor === doctorVal) &&
        (!statusVal || p.status === statusVal)
    );
    displayPatients(filtered);
}

async function updateStatus(id, newStatus) {
    const res = await fetch(`/update_status/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus })
    });
    const result = await res.json();
    alert(result.message || result.error);
    loadPatients();
}

async function assignBed(id) {
    const res = await fetch(`/assign_bed/${id}`);
    const result = await res.json();
    alert(result.error || `✅ Bed assigned: ${result.bed_number}`);
    loadPatients();
}

document.addEventListener('DOMContentLoaded', loadPatients);
