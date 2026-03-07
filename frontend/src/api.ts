/**
 * API Client for Voice AI Agent Backend
 */

const API_BASE = '/api';

// Types
export interface Patient {
  id: string;
  first_name: string;
  last_name: string;
  phone: string;
  email?: string;
  preferred_language: string;
  preferences?: Record<string, unknown>;
  created_at?: string;
}

export interface Doctor {
  id: string;
  first_name: string;
  last_name: string;
  specialization: string;
  department?: string;
  consultation_duration_minutes?: number;
  is_active?: boolean;
  languages?: string[];
}

export interface Appointment {
  id: string;
  patient_id: string;
  doctor_id: string;
  appointment_date: string;
  start_time: string;
  end_time: string;
  status: string;
  reason?: string;
  notes?: string;
  language_used?: string;
  booking_source: string;
  created_at: string;
  // Alias for compatibility
  scheduled_date?: string;
  scheduled_time?: string;
}

export interface Campaign {
  id: string;
  name: string;
  campaign_type: string;
  status: string;
  message_template: Record<string, string>;
  target_criteria?: Record<string, unknown>;
  scheduled_at?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface HealthStatus {
  status: string;
  service?: string;
  checks?: {
    database: boolean;
    redis: boolean;
  };
  components?: {
    database: string;
    redis: string;
  };
}

// API Functions
export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Failed to fetch health status');
  return res.json();
}

export async function getHealthReady(): Promise<{ status: string; checks: { database: boolean; redis: boolean } }> {
  const res = await fetch(`${API_BASE}/health/ready`);
  if (!res.ok) throw new Error('Failed to fetch readiness status');
  return res.json();
}

export async function getPatients(): Promise<Patient[]> {
  const res = await fetch(`${API_BASE}/patients`);
  if (!res.ok) throw new Error('Failed to fetch patients');
  return res.json();
}

export async function createPatient(data: Omit<Patient, 'id' | 'created_at' | 'preferences'>): Promise<Patient> {
  const res = await fetch(`${API_BASE}/patients`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to create patient');
  }
  return res.json();
}

export async function getDoctors(language?: string): Promise<Doctor[]> {
  const url = language ? `${API_BASE}/doctors?language=${language}` : `${API_BASE}/doctors`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch doctors');
  return res.json();
}

export async function getAppointments(patientId?: string): Promise<Appointment[]> {
  const url = patientId 
    ? `${API_BASE}/appointments?patient_id=${patientId}` 
    : `${API_BASE}/appointments`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch appointments');
  const appointments = await res.json();
  // Map backend field names to frontend for compatibility
  return appointments.map((appt: Appointment) => ({
    ...appt,
    scheduled_date: appt.appointment_date,
    scheduled_time: appt.start_time,
  }));
}

export async function createAppointment(data: {
  patient_id: string;
  doctor_id: string;
  scheduled_date: string;
  scheduled_time: string;
  notes?: string;
}): Promise<Appointment> {
  // Map frontend field names to backend
  const payload = {
    patient_id: data.patient_id,
    doctor_id: data.doctor_id,
    appointment_date: data.scheduled_date,
    start_time: data.scheduled_time,
    reason: data.notes,
    language_used: 'en',
  };
  
  const res = await fetch(`${API_BASE}/appointments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to create appointment');
  }
  return res.json();
}

export async function getCampaigns(): Promise<Campaign[]> {
  const res = await fetch(`${API_BASE}/campaigns`);
  if (!res.ok) throw new Error('Failed to fetch campaigns');
  return res.json();
}

export async function createCampaign(data: {
  name: string;
  campaign_type: string;
  message_template: Record<string, string>;
}): Promise<Campaign> {
  const res = await fetch(`${API_BASE}/campaigns`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Failed to create campaign');
  }
  return res.json();
}
